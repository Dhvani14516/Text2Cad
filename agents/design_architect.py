"""
UMACAD - Design Architect Agent 
Phase 3: Generates Python CadQuery code with Robust Auto-Correction
"""

from typing import Dict, Any, List, Optional
import json
import ast
import time
import re
from loguru import logger

from core.task_plan import DesignTask
from core.design_brief import DesignBrief
from repository.evolving_design_repo import EvolvingDesignRepository
from utils.vlm_interface import VLMInterface


class DesignArchitect:
    """
    Design Architect (DA) Agent.
    Responsible for converting atomic DesignTasks into executable CadQuery Python code.
    """
    
    def __init__(self, config: Dict[str, Any], vlm_interface: VLMInterface, edr: EvolvingDesignRepository):
        self.config = config
        self.vlm = vlm_interface
        self.edr = edr
        
        self.model_name = config.get('model', 'deepseek-coder')
        self.temperature = 0.0  # Force deterministic code
        self.max_attempts = config.get('max_code_generation_attempts', 3)
        self.enable_syntax_check = True

    def generate_code(self, task: DesignTask, design_brief: DesignBrief, previous_code: str = "") -> str:
        """
        Main entry point to generate code for a specific task.
        """
        logger.info(f"Generating code for Task: {task.description} | Model: {self.model_name}")
        
        # 1. Retrieve RAG Examples
        examples = self._retrieve_rag_context(task)
        
        # 2. Generate Code
        code = self._generate_cadquery_code(task, design_brief, previous_code, examples)
        
        # 3. Post-Processing & Cleanup
        code = self._clean_markdown(code)
        code = self._ensure_result_assignment(code)
        
        return code
    
    def debug_execution_error(self, code: str, error: str, task: DesignTask) -> str:
        """
        Auto-fixer loop that uses the error trace to patch broken code.
        """
        logger.warning(f"Debugging code for: {task.description}")

        system_prompt = self._get_debugger_prompt()
        user_prompt = f"""TASK: {task.description}
BROKEN CODE:
{code}

ERROR TRACE:
{error}

INSTRUCTIONS:
1. Fix the error described in the trace.
2. Ensure `import cadquery as cq` is present.
3. Ensure the final shape is assigned to `result`.
4. Return ONLY the fixed Python code."""

        try:
            response = self.vlm.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0
            ).choices[0].message.content
            
            return self._clean_markdown(response)
        except Exception as e:
            logger.error(f"Debugger Failed: {e}")
            return code

    # INTERNAL LOGIC
    def _retrieve_rag_context(self, task: DesignTask) -> List[str]:
        """Fetches relevant code snippets from the repository."""
        try: 
            raw_examples = self.edr.get_code_examples(task.task_type.value)
            if raw_examples:
                logger.info(f"🔍 RAG: Found {len(raw_examples)} examples for {task.task_type.value}")
                return [ex[:1000] + "...(truncated)" for ex in raw_examples]
        except Exception as e: 
            logger.warning(f"RAG Lookup Failed: {e}")
        return []

    def _generate_cadquery_code(self, task: DesignTask, design_brief: DesignBrief, previous_code: str, examples: List[str]) -> str:
        """Handles the LLM generation loop with retries."""
        system_content = self._get_generator_prompt()
        
        # Safe JSON dump for params
        try:
            params_str = json.dumps(task.parameters)
        except:
            params_str = str(task.parameters)

        user_content = f"""TASK: {task.description}
PARAMS: {params_str}

PREVIOUS CODE:
{previous_code if previous_code else "# No previous code"}

EXAMPLES:
{chr(10).join(examples[:2]) if examples else "# No examples"}"""

        for attempt in range(self.max_attempts):
            try:
                response = self.vlm.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=1024,
                    temperature=self.temperature,
                ).choices[0].message.content
                
                if not response:
                    continue
                
                if "import cadquery" not in response and not previous_code: 
                    response = "import cadquery as cq\n" + response
                    
                return response

            except Exception as e:
                logger.warning(f"Generation attempt {attempt+1} failed: {e}")
                time.sleep(2)
                
        return "result = None # Error: Generation failed after retries"

    def _clean_markdown(self, code: Optional[str]) -> str:
        """Removes <think> tags and Markdown code blocks."""
        if not code: return ""
        
        # Remove reasoning traces
        code = re.sub(r'<think>.*?</think>', '', code, flags=re.DOTALL)
        
        # Extract code from markdown blocks
        match = re.search(r'```python\s*(.*?)\s*```', code, re.DOTALL)
        if match:
            return match.group(1)
            
        match_generic = re.search(r'```\s*(.*?)\s*```', code, re.DOTALL)
        if match_generic:
            return match_generic.group(1)
            
        return code.strip()

    def _ensure_result_assignment(self, code: str) -> str:
        """
        Guarantees the code ends by assigning the final CadQuery model to 'result'.
        Handles:
        - Last expression is a CQ object
        - Last assignment to a temporary variable
        - Multi-line constructions with temporary parts
        """
        if "result =" in code or "result=" in code:
            return code  # Already assigned

        try:
            tree = ast.parse(code)
            last_assignable = None

            for node in reversed(tree.body):
                # If it's an expression returning a CQ object, assign to result
                if isinstance(node, ast.Expr):
                    expr_line = (ast.get_source_segment(code, node) or "").strip()
                    return code + f"\nresult = {expr_line}"
                # If it's an assignment to a variable, track the last one
                if isinstance(node, ast.Assign):
                    target = node.targets[0]
                    if isinstance(target, ast.Name):
                        last_assignable = target.id
                        break

            if last_assignable:
                return code + f"\nresult = {last_assignable}"

        except Exception:
            # Fallback: assign last line if it contains CadQuery calls
            lines = code.strip().split("\n")
            for i in reversed(range(len(lines))):
                if "cq." in lines[i]:
                    lines[i] = f"result = {lines[i]}"
                    return "\n".join(lines)

        # If all else fails, add a placeholder
        return code + "\nresult = None  # WARNING: Could not auto-detect final model"

        
    def _validate_and_fix_syntax(self, code: str) -> str:
        try: 
            ast.parse(code)
            return code
        except: 
            return code

    # PROMPTS
    def _get_generator_prompt(self) -> str:
        return """You are a Python CadQuery Code Generator.

CRITICAL INSTRUCTIONS:
1. **FORMAT & STATE:** Start with `import cadquery as cq`. ALWAYS assign the final 3D solid to the variable `result`. NEVER overwrite `result` directly when adding parts; use `part = ...` then `result = result.union(part)`.
2. **SOLIDS ONLY (.close() MANDATE):** All objects MUST be 3D SOLIDS. 
   - When using `polyline()`, you MUST append `.close()` BEFORE `.extrude()`.
   - BAD (Creates 2D Shell): `polyline(...).extrude(10)`
   - GOOD (Creates Solid): `polyline(...).close().extrude(10)`
   - *Applies heavily to Triangular Prisms and Wedges.*
3. **CYLINDERS:** Use `.cylinder(height, radius)`. NEVER use the `diameter=` keyword (causes crashes). If given diameter, calculate `radius = D / 2`.
4. **CONES & PYRAMIDS:** - **Pyramids:** Use `cq.Workplane("XY").rect(w, l).extrude(h, taper=angle)`. Ensure taper angle doesn't cause self-intersection.
   - **Cones (Robust):** Do NOT use `extrude(taper=...)`. Use `cq.Workplane("XY").cone(bottom_radius, top_radius, height)`. Use a tiny top radius (e.g., 0.1) if 0.0 fails the kernel. 
   - **Custom Lofts:** `cq.Workplane().circle(r1).workplane(offset=h).circle(r2).loft()`.
5. **SPHERES, HEMISPHERES & SHELLS:**
   - **Hemispheres/Caps:** DO NOT use `split()` (fragile). Create a sphere and `intersect()` it with a translated bounding box.
   - **Hollow Shells:** Create `outer`, create `inner`, `cut()` inner from outer, then `union()` back to `result`.
6. **TORUS (DONUT):** Use `cq.Workplane("XZ").moveTo(major_radius, 0).circle(minor_radius).revolve()`. `major` must be > `minor` to avoid self-intersection.
7. **POLYGONS (HEXAGONS):** `.polygon(nSides, diameter)` uses the **circumscribed diameter**. If asked for Side Length (s), calculate `d = 2 * s`.
8. **BOOLEAN SAFETY:** When cutting or intersecting, make the tool (Box/Cylinder) significantly LARGER than the target. Avoid exact edge-to-edge alignment to prevent kernel errors.
9. **ORIENTATION & PLACEMENT:** - Primitives are `centered=(True,True,True)` by default.
   - "Horizontal" = `cq.Workplane("YZ")`, "Vertical" = `cq.Workplane("XY")`.
   - Do NOT rely on `.faces(">Y")` for curved surfaces. Create features at the origin, rotate, and `.translate()` them into place.
10. **REGULAR TETRAHEDRON (Edge Length `a`):** Use method chaining. Math: `h = a * 0.8165`, `r = a * 0.57735`.
11. **PATTERNS & FEATURES:** Do NOT use `polarArray` on solids; use a `for` loop with `.rotate()` and `.union()`. Apply cuts/holes immediately to the main body.
"""

    def _get_debugger_prompt(self) -> str:
        return """You are a Python CadQuery Debugger. Fix the code based on the exact error.

STRATEGIES:
1. **'Visual Check Failed: 2D shell' OR 'No pending wires':** - CAUSE: You extruded an OPEN wire, resulting in a flat surface. 
   - FIX: Add `.close()` to your sketch chain before extruding: `polyline(...).close().extrude(...)`.
2. **'Model has ZERO volume' (Ghost Model):**
   - CAUSE: Boolean operation failed (cut "air"), extrusion length was 0, or geometry self-intersected (e.g., Torus major < minor).
   - FIX: Ensure cutting tools are vastly larger than the target and positioned correctly.
3. **'BRep_API: command not done':**
   - CAUSE: Geometric kernel failure. Common in revolves touching the axis or impossible fillets.
   - FIX: For revolves, offset the profile slightly (e.g., `moveTo(radius + 0.001)`). For ellipsoids, switch to `sphere().each(lambda s: s.transformShape(m))`.
4. **'ValueError: Null TopoDS_Shape' OR 'Hemisphere is full sphere':**
   - CAUSE: `split()` or `cut()` failed because objects didn't intersect.
   - FIX: Ensure cutting tools are large enough. For hemispheres, use `.intersect()` with a box representing the volume you want to KEEP.
5. **'Cannot convert object type Wire to vector' OR 'AttributeError: sweepPath':**
   - CAUSE: Calling `.close()` on a shape that is already invalid, or using non-existent methods.
   - FIX: Ensure `.polyline()` takes a list of tuples. Use `.sweep()` with a valid path wire, or `.revolve()` for rings.
6. **'gp_VectorWithNullMagnitude':**
   - CAUSE: Lofting to a perfect geometric point (radius 0).
   - FIX: Use a tiny radius (e.g., 0.1) for the top of the loft, or use the `cone()` primitive.
7. **'AttributeError: scale' OR 'non-orthogonal GTrsf':**
   - CAUSE: CadQuery `Matrix` and `Workplane` objects don't have a `.scale()` method.
   - FIX: Use `m = Matrix([(x,0,0,0), (0,y,0,0), (0,0,z,0)])` and apply it with `.each(lambda s: s.transformGeometry(m))`.
8. **'Workplane object must have... union!' OR 'Hemisphere is a separate object':**
   - CAUSE: Method chaining broke or a part was orphaned.
   - FIX: Assign the new part to a temp variable, then `result = result.union(temp)`.
9. **'polarArray' errors:** Replace with a standard Python `for` loop, `.rotate()`, and `.union()`.
10. **'AttributeError: sector':** CadQuery lacks `sector`. Revolve a `threePointArc` or cut a sphere in half.
11. **'GeomAPI_ProjectPointOnSurf':** Cannot start a workplane on a curved surface. Start on a standard plane ("XY"), build the part, and `.translate()` it.
12. **'Standard_Failure':** Fillet or chamfer failed. Reduce the radius or verify the selector (e.g., `>Z`) is hitting an actual sharp edge.
13. **'No result variable found':** Ensure the absolute last line is exactly `result = ...`.

GENERAL RULES: Ensure `import cadquery as cq` is present. If an approach fails repeatedly, TRY A DIFFERENT CONSTRUCTION METHOD (e.g., switch from Extrusion to CSG Booleans).
"""