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
        """Guarantees the code ends by assigning a variable to 'result'."""
        if "result =" in code or "result=" in code:
            return code
        
        # Try AST parsing to find the last expression
        try:
            tree = ast.parse(code)
            if tree.body:
                last_node = tree.body[-1]
                # If last line is just an expression (e.g. cq.Workplane...), assign it
                if isinstance(last_node, ast.Expr):
                    lines = code.strip().split('\n')
                    lines[-1] = f"result = {lines[-1]}"
                    return "\n".join(lines)
                # If last line is an assignment to another var, copy it to result
                if isinstance(last_node, ast.Assign):
                    target = last_node.targets[0]
                    if isinstance(target, ast.Name):
                        return code + f"\nresult = {target.id}"
        except Exception:
            lines = code.strip().split('\n')
            if lines and "cq." in lines[-1]:
                 lines[-1] = f"result = {lines[-1]}"
                 return "\n".join(lines)
                 
        return code
        
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
1. **FORMAT:** Start with `import cadquery as cq`. Output ONLY valid Python code.
2. **STATE MANAGEMENT:** If `PREVIOUS CODE` exists, modify `result`. ALWAYS assign final output to `result`.
3. **SELECTORS:** Use `>Z`, `<Z`, `|Z` selectors for fillets/chamfers. 
4. **COORDINATES:** Primitives are `centered=(True,True,True)`. Use symmetric ranges (e.g., `range(-24, 32, 16)`).
5. **UNIONS:** Never overwrite `result` when creating a new part. Create `part = ...` then `result = result.union(part)`.
6. **PATTERNS:** Do NOT use `polarArray` on solids. Use a for-loop with `.rotate()` and `.union()`.
7. **FEATURES:** Apply cuts/holes immediately to the main body. Do not leave floating objects.
8. **ELLIPSOIDS & SCALING:** CadQuery `.scale()` is UNIFORM ONLY. To create an ellipsoid or non-uniform shape, use `ellipse(r1, r2).revolve()`. Do NOT use `sphere().scale(x,y,z)`.
"""

    def _get_debugger_prompt(self) -> str:
        return """You are a Python CadQuery Debugger. Fix the code based on the error.

COMMON FIXES:
1. **'polarArray' errors**: Replace with `for` loop + `.rotate()` + `.union()`.
2. **'No pending wires'**: Add `.close()` before `.extrude()`.
3. **'Workplane object must have... union!'**: Create a temp var for new parts, then union.
4. **'Standard_Failure' (Fillet/Chamfer)**: Reduce radius or remove operation.
5. **'Model has ZERO volume'**: Check extrusion values.
6. **'AttributeError: scale'**: CadQuery `.scale()` only accepts one argument (uniform). Use `.ellipse(r1, r2).revolve()` instead.
"""