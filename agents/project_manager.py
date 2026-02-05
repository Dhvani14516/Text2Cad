"""
UMACAD - Project Manager Agent 
Phase 2: Strategic Planning with Aggressive Atomic Rules
"""

from typing import Dict, List, Any, Optional
import json
import re 
from datetime import datetime
from loguru import logger

from core.design_brief import DesignBrief
from core.task_plan import ConstructionPlan, DesignTask, TaskType
from repository.evolving_design_repo import EvolvingDesignRepository
from utils.vlm_interface import VLMInterface


class ProjectManager:
    """
    Project Manager (PM) Agent.
    Breaks down high-level design briefs into atomic, sequential construction tasks.
    """
    
    def __init__(self, config: Dict[str, Any], vlm_interface: VLMInterface, edr: EvolvingDesignRepository):
        self.config = config
        self.vlm = vlm_interface
        self.edr = edr
        self.model_name = config.get('model', 'deepseek-chat')
        self.enable_edr = config.get('enable_edr_lookup', False)
        
    def create_construction_plan(self, design_brief: DesignBrief) -> ConstructionPlan:
        """
        Orchestrates the planning process: Reason -> Act (Search) -> Strategy -> Task Generation.
        """
        logger.info(f"Creating construction plan for '{design_brief.design_title}' using {self.model_name}")
        
        # 1. Reason: Analyze Complexity
        reasoning = self._reason_about_design(design_brief)
        
        # 2. Act: Retrieve Patterns 
        pattern_insights = {}
        if self.enable_edr:
            patterns = self._act_query_edr(design_brief)
            pattern_insights = {"summary": f"Found {len(patterns)} related patterns"}
        
        # 3. Strategy: Formulate Approach
        strategy = self._reason_strategy(design_brief, reasoning)
        
        # 4. Generate: Create Atomic Tasks
        tasks = self._generate_task_sequence(design_brief, strategy)
        
        # 5. Finalize Plan Object
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return ConstructionPlan(
            plan_id=plan_id,
            design_brief_id=design_brief.brief_id,
            strategy=strategy.get('approach', 'Standard Construction'),
            reasoning=strategy.get('reasoning', 'Based on geometric analysis'),
            tasks=tasks,
            estimated_complexity=reasoning.get("complexity", "medium"),
            tags=design_brief.tags
        )

    # PLANNING STEPS
    def _reason_about_design(self, design_brief: DesignBrief) -> Dict[str, Any]:
        """Step 1: Analyzes geometric complexity."""
        system_content = self._get_complexity_prompt()
        user_content = f"""Design: {design_brief.design_title}
Desc: {design_brief.design_description}

Output format: {{ "complexity": "...", "core_shape": "...", "challenges": [] }}"""
        
        return self._call_llm_json(system_content, user_content)

    def _act_query_edr(self, design_brief: DesignBrief) -> List[Any]:
        """Step 2: Searches EDR for similar past designs."""
        try:
            category = design_brief.design_category if design_brief.design_category else "general"
            search_terms = design_brief.tags + [category]
            
            return self.edr.search_patterns(search_terms)
        except Exception as e:
            logger.warning(f"EDR Search failed: {e}")
            return []

    def _reason_strategy(self, design_brief: DesignBrief, reasoning: Dict) -> Dict[str, Any]:
        """Step 3: Creates high-level approach."""
        system_content = self._get_strategy_prompt()
        user_content = f"""Design: {design_brief.design_title}
Complexity: {reasoning.get('complexity')}

Output format: {{ "approach": "...", "reasoning": "..." }}"""
        
        return self._call_llm_json(system_content, user_content)

    def _generate_task_sequence(self, design_brief: DesignBrief, strategy: Dict) -> List[DesignTask]:
        """Step 4: Converts strategy into specific API tasks."""
        
        # Serialize dimensions for context
        dimensions_text = json.dumps([d.model_dump() for d in design_brief.global_dimensions], indent=2)
        valid_tasks_str = ", ".join([t.value for t in TaskType])

        system_content = self._get_task_gen_prompt(valid_tasks_str)
        user_content = f"""USER REQUIREMENTS:
Global Dimensions: {dimensions_text}
Desc: {design_brief.design_description}
Strategy: {strategy.get('approach')}

Generate the task list in JSON."""
        
        task_data = self._call_llm_json(system_content, user_content)
        
        tasks = []
        for i, task_dict in enumerate(task_data.get('tasks', [])):
            try:
                # Validate Task Type
                ttype = task_dict.get('task_type', 'create_solid')
                try:
                    task_enum = TaskType(ttype)
                except ValueError:
                    task_enum = TaskType.CREATE_SOLID # Fallback
                
                tasks.append(DesignTask(
                    task_id=f"task_{i+1}",
                    step_number=i+1,
                    task_type=task_enum,
                    description=task_dict.get('description', 'No description'),
                    parameters=task_dict.get('parameters', {}),
                    target_features=task_dict.get('target_features', [])
                ))
            except Exception as e:
                logger.warning(f"Skipping malformed task {i}: {e}")
                continue
        return tasks

    # HELPERS
    def _call_llm_json(self, system_content: str, user_content: str) -> Dict[str, Any]:
        """Helper to call LLM and enforce strict JSON parsing."""
        try:
            response = self.vlm.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"}, 
                temperature=0.5
            ).choices[0].message.content
            
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            return {}

    def _parse_json_response(self, response: Optional[str]) -> Dict[str, Any]:
        """Cleans LLM output (removes <think> tags and markdown). Handles None."""
        if not response: return {}
        
        try:
            # 1. Remove Chain-of-Thought tags (<think>...</think>)
            cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            
            # 2. Extract JSON from Markdown
            if '```json' in cleaned:
                cleaned = cleaned.split('```json')[1].split('```')[0]
            elif '{' in cleaned:
                # Find first { and last }
                cleaned = cleaned[cleaned.find('{'):cleaned.rfind('}')+1]
                
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.error(f"JSON Parse Error: {e} | Raw: {response[:50]}...")
            return {}

    # PROMPTS
    def _get_complexity_prompt(self) -> str:
        return "You are a CAD Expert. Analyze this design request and output valid JSON only."

    def _get_strategy_prompt(self) -> str:
        return "You are a CAD Strategist. Formulate a construction strategy. Output JSON only."

    def _get_task_gen_prompt(self, valid_tasks_str: str) -> str:
        return f"""You are a CAD Project Manager. Convert the strategy into a task list.

CRITICAL RULES FOR TASKS:
1. **ATOMIC SOLIDS ONLY:** Every task MUST generate a 3D SOLID. 
   - FORBIDDEN: "Create Sketch", "Draw Circle", "Define Rectangle". (CadQuery cannot pass 2D sketches between steps).
   - REQUIRED: "Create Cylinder", "Create Box", "Extrude Plate".

2. **MULTI-PART FUSION (NEW RULE):** - If the design has multiple separate parts (like a Snowman with 3 spheres), you MUST combine them.
   - OPTION A: Add a final task with type "boolean_union".
   - OPTION B (Preferred): In the description of Task 2 and 3, say "Create sphere AND UNION it with the previous shape.
   
3. **AGGRESSIVE SIMPLICITY:** - A Cube, Cylinder, Washer, Plate, or simple Bracket MUST be **ONE SINGLE TASK**.
   - Example: "Washer" -> Task 1: "Create cylinder with center hole". (DONE).
   - Do NOT split "Create Cylinder" and "Cut Hole" unless absolutely necessary.

4. **DIMENSION LOYALTY:**
   - Use the EXACT dimensions below. Do not invent numbers.

5. **NO "NICE TO HAVES":** - DO NOT add 'add_fillet' or 'add_chamfer' unless the user SPECIFICALLY asked for "rounded edges" or "chamfered corners".
   - A Cube should be 1 step. Not 4.

VALID TASK TYPES: [{valid_tasks_str}]"""