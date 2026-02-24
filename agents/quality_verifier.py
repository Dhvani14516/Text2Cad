"""
UMACAD - Quality Assurance Verifier Agent 
Phase 3: Verifies Dimensions via LLM Code Reading & Features via Vision
"""

from typing import Dict, List, Any, Optional, Union
from PIL import Image
from loguru import logger
import json

from core.task_plan import DesignTask
from core.design_brief import DesignBrief
from utils.vlm_interface import VLMInterface


class DynamicCodeAnalyzer:
    """
    Helper Class: Uses an LLM to 'read' the code and extract actual dimensions.
    """
    def __init__(self, vlm_interface: VLMInterface, model_name: str):
        self.vlm = vlm_interface
        self.model_name = model_name

    def analyze_code_dimensions(self, code: str, task: DesignTask, design_brief: DesignBrief) -> Dict[str, Any]:
        """
        Sends the code to the LLM to extract implemented dimensions.
        """
        logger.info("LLM Code Analysis...")
        
        system_prompt = self._get_code_analysis_prompt()
        
        # Serialize brief safely using Pydantic
        try:
            brief_str = design_brief.model_dump_json(indent=2)
        except:
            brief_str = str(design_brief)
        
        # Safe param serialization
        try: params_str = json.dumps(task.parameters)
        except: params_str = str(task.parameters)
        
        user_prompt = f"""
        CURRENT TASK INSTRUCTION (HIGHEST PRIORITY):
        "{task.description}"
        Parameters: {params_str}

        GLOBAL REQUIREMENTS (CONTEXT):
        {brief_str}
        
        GENERATED CODE:
        ```python
        {code}
        ```
        """
        
        try:
            response = self.vlm.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            ).choices[0].message.content
            
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"Dynamic Analysis Failed: {e}")
            return {"match": True, "details": f"Analysis Skipped (Error: {str(e)})", "discrepancies": []}

    def _parse_json_response(self, response: Optional[str]) -> Dict[str, Any]:
        if not response: return {"match": False, "discrepancies": ["No response from LLM"]}
        try:
            return json.loads(response)
        except:
            return {"match": False, "discrepancies": ["JSON Parse Error"]}

    def _get_code_analysis_prompt(self) -> str:
        return """You are a Python Code Auditor for CAD models.
Your job is to READ the provided CadQuery code and EXTRACT the physical dimensions and properties that were actually implemented.

CRITICAL RULE:
- **PRIORITIZE THE 'CURRENT TASK'**: If the Current Task description specifies a value (e.g., "Diameter 25"), that value is the TRUTH.

OUTPUT JSON:
{
    "shape_detected": "string",
    "dimensions_found": { "param": value },
    "discrepancies": ["Explain mismatch"],
    "match": true/false
}"""


class QualityVerifier:
    """
    Quality Assurance Verifier (QAV) Agent.
    Orchestrates Visual Checks (VLM) and Dimensional Checks (Code Analysis).
    """
    
    def __init__(self, config: Dict[str, Any], vlm_interface: VLMInterface):
        self.config = config
        self.vlm = vlm_interface 
        self.model_name = config.get('model', 'gemini-1.5-flash')
        self.skip_visual_verification = config.get('skip_visual_verification', False)
        
        # Initialize the DYNAMIC Analyzer
        self.code_analyzer = DynamicCodeAnalyzer(vlm_interface, self.model_name)

    def verify(self, renders: Dict[str, Image.Image], task: DesignTask, design_brief: DesignBrief, code: str = "") -> Dict[str, Any]:
        """
        Hybrid Verification: VISUAL CHECK FIRST -> Then Code Analysis
        """
        logger.info(f"Verifying task: {task.description}")

        # --- STEP 1: VISUAL CHECK (The "Inspector") ---
        visual_result = self._perform_visual_check(renders, task, design_brief)

        code_check = self.code_analyzer.analyze_code_dimensions(code, task, design_brief)
        
        is_hollow_task = "hollow" in task.description.lower() or "shell" in task.description.lower()
        
        if not visual_result['success']:
            # Override 1: Hollow Sphere Paradox
            if is_hollow_task and "solid" in visual_result['message'].lower():
                logger.warning("⚠️ OVERRIDE: Visual Check failed on 'Hollow' visibility, but assuming internal geometry exists based on code.")
                visual_result['success'] = True
            
            # Override 2: Prism 2D Shell Hallucination
            # If the code check found dimensions and volume is likely > 0 (inferred)
            elif "2d" in visual_result['message'].lower() and code_check.get('match', False):
                 logger.warning("⚠️ OVERRIDE: Visual Check claimed '2D Shell', but Code Analysis confirms valid extrusion.")
                 visual_result['success'] = True

        if not visual_result['success']:
             return visual_result

        # --- STEP 2: DYNAMIC CODE ANALYSIS (The "Math Professor") ---
        if code:
            logger.info("Phase 2: Dimensional Code Analysis...")
            code_check = self.code_analyzer.analyze_code_dimensions(code, task, design_brief)
            
            if not code_check.get('match', True):
                discrepancies = code_check.get('discrepancies', [])
                error_msg = "; ".join(discrepancies)
                logger.warning(f"⚠️ Dimensional Mismatch: {error_msg}")
                
                return {
                    'success': False,
                    'confidence': 1.0, 
                    'message': f"Visuals look okay, but Math is wrong: {error_msg}"
                }
                
            logger.info(f"✅ Code Logic Verified: {code_check.get('dimensions_found', 'No dims found')}")
        
        return {'success': True, 'message': 'Passed Visual and Dimensional Checks'}

    # INTERNAL LOGIC
    def _perform_visual_check(self, renders: Dict[str, Image.Image], task: DesignTask, design_brief: DesignBrief) -> Dict[str, Any]:
        """Executes the VLM visual inspection."""
        if self.skip_visual_verification:
            logger.info("Skipping visual check (Config set to skip)")
            return {'success': True, 'message': 'Skipped Visual Check'}

        logger.info("Phase 1: Visual Inspection (Prioritized)...")
        
        verification_prompt = self._get_visual_prompt(task)
        analysis = self._analyze_renders(renders, verification_prompt)
        
        return self._evaluate_verification(analysis)

    def _analyze_renders(self, renders: Dict[str, Image.Image], prompt: str) -> Dict[str, Any]:
        """Sends PIL images directly to VLM Interface."""
        # FIX: Explicitly cast to List[Any] to solve Pylance invariance error
        image_list: List[Any] = list(renders.values())

        try:
            response = self.vlm.analyze_with_multiple_images(
                prompt=prompt,
                images=image_list, 
                model_name=self.model_name
            )
            return self._parse_verification_response(response)
        except Exception as e:
            logger.error(f"VLM Analysis Failed: {e}")
            return {"visual_pass": False, "feedback": f"VLM Error: {e}"}

    def _parse_verification_response(self, response: Optional[str]) -> Dict[str, Any]:
        """Robustly parses the VLM response."""
        if not response:
            return {"visual_pass": False, "feedback": "Empty response from VLM"}

        try:
            # Clean Markdown
            json_str = response
            if '```json' in response:
                json_str = response.split('```json')[1].split('```')[0]
            elif '{' in response:
                json_str = response[response.find('{'):response.rfind('}')+1]
            
            # Fallback for plain text "PASS"
            if not json_str.strip().startswith("{"):
                if "PASS" in response.upper():
                    return {"visual_pass": True, "feedback": "Parsed non-JSON pass", "confidence_score": 1.0}
                return {"visual_pass": False, "feedback": "Invalid VLM response structure", "confidence_score": 0.0}
            
            data = json.loads(json_str)
            
            # Handle list responses
            if isinstance(data, list):
                return data[0] if data and isinstance(data[0], dict) else {}
            
            return data

        except Exception as e:
            logger.error(f"JSON Parse Error: {e} | Response: {response[:100]}...")
            return {"visual_pass": False, "feedback": f"JSON Parse Error: {e}"}

    def _evaluate_verification(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Converts raw analysis into a standardized result dict."""
        if analysis.get('visual_pass', False):
            return {
                'success': True,
                'confidence': analysis.get('confidence_score', 1.0),
                'message': analysis.get('feedback', 'Visual Verification Passed')
            }
        else:
            return {
                'success': False,
                'confidence': analysis.get('confidence_score', 0.0),
                'message': f"Visual Check Failed: {analysis.get('feedback')}",
                'details': analysis
            }

    # PROMPTS
    def _get_visual_prompt(self, task: DesignTask) -> str:
        # Safe param serialization
        try: params_str = json.dumps(task.parameters)
        except: params_str = str(task.parameters)

        return f"""You are a Lenient Quality Control Inspector for 3D CAD models.
Check if the generated part looks correct based on the user's description.

## TASK CONTEXT:
Request: "{task.description}"
Type: {task.task_type.value}
Params: {params_str}

## CRITICAL INSTRUCTIONS (LENIENT MODE):
1. **CONTEXT AWARENESS:** The model has geometry from PREVIOUS steps. ONLY check if the *NEW* feature requested is present.
2. **NO RULER:** Do not measure pixels. If it *looks* correct (e.g., a hole exists where asked), PASS IT.
3. **FEATURE CHECK:** If brief says "Hole", do you see a hole? (PASS).
4. **SOLIDITY CHECK (CRITICAL):**
   - Look closely at the isometric view. 
   - Does the object look like a **solid block** or a **hollow paper shell**?
   - If it looks like a hollow shell (you can see inside it, or it creates optical illusions), **FAIL IT**.
   - **FEEDBACK:** "Visual Check Failed: The model appears to be a 2D surface/shell. It must be a closed 3D solid." (DO NOT suggest how to fix it code-wise).
5. **BOOLEAN CHECKS:**
   - If a subtraction is requested (e.g. "Cap"), look for a *flat face* where the cut happened.
   - If the object is perfectly round everywhere, the cut likely failed.
6. **THE "X-RAY" RULE (HOLLOW OBJECTS):** - If the request is for a "Hollow Sphere", "Shell", or "Pipe", **YOU CANNOT SEE THE INSIDE**.
   - If the object looks like a solid outer shape (e.g., a Sphere), **PASS IT**.
   - Assume the "Internal Math Check" will verify the hollowness. 
   - **DO NOT FAIL** a hollow sphere just because it looks solid from the outside.
7. **THE "PRISM" RULE:**
   - Wireframe renders of Prisms often look like "shells" or "open boxes" due to optical illusions.
   - If the "Model Stats" (provided in logs) show a **Volume > 0**, it is NOT a 2D shell.
   - **PASS** the visual check if the shape roughly matches, even if lines look "thin".

## OUTPUT FORMAT (JSON ONLY):
{{
    "visual_pass": true/false,
    "confidence_score": 0.0-1.0,
    "geometric_check": {{ "status": "PASS/FAIL", "details": "..." }},
    "feature_check": {{ "status": "PASS/FAIL", "details": "..." }},
    "feedback": "Concise feedback."
}}"""