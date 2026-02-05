"""
UMACAD - Requirements Analyst Agent
Phase 1: Transforms vague user input into structured DesignBrief
"""

from typing import Optional, Dict, List, Any
import json
import re
from loguru import logger
from datetime import datetime

from core.design_brief import DesignBrief, GeometricFeature, Dimension, DimensionType
from utils.vlm_interface import VLMInterface 

class RequirementsAnalyst:
    """
    Requirements Analyst (RA) Agent.
    Responsible for understanding the user's intent and converting it into a structured
    data object (DesignBrief) that the rest of the system can understand.
    """
    
    def __init__(self, config: Dict[str, Any], vlm_interface: VLMInterface):
        self.config = config
        self.vlm = vlm_interface
        self.model_name = config.get('model', 'gpt-4o-mini')
        self.max_rounds = config.get('max_clarification_rounds', 5)
        
    def elicit_requirements(self, user_text: str, image_path: Optional[str] = None, interactive: bool = True) -> DesignBrief:
        """
        Main entry point. Analyzes input and builds the brief.
        """
        logger.info(f"Starting requirement elucidation with {self.model_name}...")
        
        # 1. Initial Analysis (Identify what is missing)
        analysis = self._analyze_initial_input(user_text)
        
        # 2. Build DesignBrief (Convert analysis to structured spec)
        design_brief = self._build_design_brief(
            user_text=user_text,
            image_path=image_path,
            analysis=analysis
        )
        
        return design_brief

    # CORE LOGIC
    def _analyze_initial_input(self, user_text: str) -> Dict[str, Any]:
        """
        Step 1: Ask the LLM to critique the input and find holes.
        """
        system_prompt = self._get_analysis_prompt()
        user_prompt = f'User Input: "{user_text}"'

        try:
            response = self.vlm.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, 
                temperature=0.2
            ).choices[0].message.content
            
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {}

    def _build_design_brief(self, user_text: str, image_path: Optional[str], analysis: Dict) -> DesignBrief:
        """
        Step 2: Ask the LLM to generate the final JSON specification.
        """
        system_prompt = self._get_specification_prompt()
        
        user_prompt = f"""Original Request: {user_text}
Analysis Summary: {json.dumps(analysis)}
Generate the full JSON specification now."""

        try:
            response = self.vlm.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            ).choices[0].message.content
            
            structured_spec = self._parse_json_response(response)
            
            # Convert JSON Dict to Pydantic Object
            brief_id = f"brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            return DesignBrief(
                brief_id=brief_id,
                user_input_text=user_text,
                user_input_image_path=image_path,
                design_title=structured_spec.get('title', 'Untitled Design'),
                design_description=structured_spec.get('description', 'No description'),
                design_category=analysis.get('design_type', 'unknown'),
                features=self._extract_features(structured_spec),
                global_dimensions=self._extract_dimensions(structured_spec),
                constraints=structured_spec.get('constraints', []),
                confidence_score=analysis.get('confidence_score', 0.5),
                tags=analysis.get('tags', []),
                # Explicitly passing None for optional fields is safe
                material=None 
            )
        except Exception as e:
            logger.error(f"Brief construction failed: {e}")
            raise

    # HELPERS
    def _parse_json_response(self, response: Optional[str]) -> Dict[str, Any]:
        """Cleans and parses JSON from LLM output. Handles None safely."""
        if not response: 
            return {}
            
        try:
            # Handle Markdown wrapping
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]
            elif '```' in response:
                response = response.split('```')[1].split('```')[0]
            
            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"JSON Parse Error: {e} | Raw: {response[:50]}...")
            return {}

    def _safe_float(self, value: Any, default: float = 10.0) -> float:
        """Safely convert value to float, handling strings with units."""
        if value is None: return default
        try:
            return float(value)
        except:
            try: 
                match = re.search(r"[-+]?\d*\.\d+|\d+", str(value))
                return float(match.group()) if match else default
            except: 
                return default

    def _extract_features(self, spec: Dict[str, Any]) -> List[GeometricFeature]:
        features = []
        for feat_data in spec.get('features', []):
            dims = []
            for d in feat_data.get('dimensions', []):
                dims.append(Dimension(
                    name=d.get('name', 'dim'),
                    type=DimensionType.LENGTH, 
                    value=self._safe_float(d.get('value')),
                    unit=d.get('unit', 'mm'),
                    tolerance=None,
                    tolerance_type=None
                ))
            features.append(GeometricFeature(
                feature_id=feat_data.get('feature_id', 'unknown'),
                feature_type=feat_data.get('feature_type', 'unknown'),
                dimensions=dims,
                position=feat_data.get('position', {'x':0,'y':0,'z':0}),
                relationships={}
            ))
        return features

    def _extract_dimensions(self, spec: Dict[str, Any]) -> List[Dimension]:
        dims = []
        for d in spec.get('global_dimensions', []):
            dims.append(Dimension(
                name=d.get('name', 'dim'),
                type=DimensionType.LENGTH,
                value=self._safe_float(d.get('value')),
                unit=d.get('unit', 'mm'),
                tolerance=None,
                tolerance_type=None
            ))
        return dims

    # PROMPTS
    def _get_analysis_prompt(self) -> str:
        return """You are a Requirements Analyst for a CAD design system.
Your job is to analyze the user's request and identify ALL missing information, ambiguities, and critical parameters needed for 3D modeling.

OUTPUT FORMAT:
Provide your analysis in a perfect JSON format. DO NOT output any text before or after the JSON block.
{
    "summary": "Brief summary",
    "design_type": "Type of object (bracket, housing, etc.)",
    "known_information": ["List of explicitly stated requirements"],
    "ambiguities": ["List of unclear aspects"],
    "missing_critical_info": ["List of critical missing info"],
    "confidence_score": 0.0-1.0,
    "tags": ["relevant", "tags"]
}"""

    def _get_specification_prompt(self) -> str:
        return """You are a CAD specification writer. Create a detailed JSON spec.
CRITICAL RULE: If dimensions are missing, ESTIMATE values between 10mm and 200mm. NEVER exceed 300mm for default values.

OUTPUT SCHEMA:
{
    "title": "Short title",
    "description": "Detailed description",
    "features": [
        {
            "feature_id": "main_shape",
            "feature_type": "cube/cylinder/etc",
            "dimensions": [
                {"name": "length", "value": 50.0, "unit": "mm"}
            ],
            "position": {"x": 0, "y": 0, "z": 0}
        }
    ],
    "global_dimensions": [
        {"name": "total_length", "value": 100.0, "unit": "mm"}
    ]
}"""