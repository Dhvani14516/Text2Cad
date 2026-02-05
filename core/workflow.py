"""
UMACAD - Main Workflow Orchestration
Coordinates the four phases of the design process:
1. Elucidation (Analyst) -> 2. Planning (Manager) -> 3. Generation (Architect) -> 4. Validation (Verifier)
"""

from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import yaml
import time
from datetime import datetime
from loguru import logger

from core.design_brief import DesignBrief
from core.task_plan import ConstructionPlan
from agents.requirements_analyst import RequirementsAnalyst
from agents.project_manager import ProjectManager
from agents.design_architect import DesignArchitect
from agents.quality_verifier import QualityVerifier
from repository.evolving_design_repo import EvolvingDesignRepository
from cadquery_integration.executor import CadQueryExecutor
from cadquery_integration.exporter import ModelExporter
from utils.vlm_interface import VLMInterface


class WorkflowPhase:
    """Enumeration of workflow phases"""
    REQUIREMENT_ELUCIDATION = 1
    STRATEGIC_PLANNING = 2
    GENERATION_VERIFICATION = 3
    USER_VALIDATION = 4


class UMACADWorkflow:
    """
    Main workflow orchestrator for UMACAD system.
    Manages the complete journey from user input to final 3D model.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the workflow with configuration"""
        self.config = self._load_config(config_path)
        self._setup_logging()
        
        # --- 1. Infrastructure Setup ---
        try:
            # We use OpenRouter as the primary VLM interface as per config
            self.vlm_interface = VLMInterface(self.config['openrouter_provider'])
            self.edr = EvolvingDesignRepository(self.config['edr'])
            logger.info("Initialized Infrastructure (VLM & EDR)")
        except Exception as e:
            logger.error(f"Infrastructure Init Failed: {e}")
            raise

        # --- 2. Agent Initialization ---
        # All agents currently share the same VLM interface, but this can be split if needed
        self.requirements_analyst = RequirementsAnalyst(
            config=self.config['agents']['requirements_analyst'],
            vlm_interface=self.vlm_interface 
        )
        
        self.project_manager = ProjectManager(
            config=self.config['agents']['project_manager'],
            vlm_interface=self.vlm_interface,
            edr=self.edr
        )
        
        self.design_architect = DesignArchitect(
            config=self.config['agents']['design_architect'],
            vlm_interface=self.vlm_interface,
            edr=self.edr
        )
        
        self.quality_verifier = QualityVerifier(
            config=self.config['agents']['quality_verifier'],
            vlm_interface=self.vlm_interface
        )
        
        # --- 3. Integration Tools ---
        self.cad_executor = CadQueryExecutor(self.config['cadquery'])
        self.exporter = ModelExporter(self.config['cadquery'])
        
        # --- 4. Session State ---
        self.current_phase = None
        self.design_brief: Optional[DesignBrief] = None
        self.construction_plan: Optional[ConstructionPlan] = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def run(self, user_input: str, image_path: Optional[str] = None, interactive: bool = True) -> Dict[str, Any]:
        """
        Execute the complete UMACAD workflow.
        """
        logger.info(f"Starting UMACAD workflow - Session: {self.session_id}")
        
        start_time_total = time.time()
        
        metrics: Dict[str, Union[int, float]] = {
            'phase_1_time': 0.0, 'phase_1_tokens': 0,
            'phase_2_time': 0.0, 'phase_2_tokens': 0,
            'phase_3_time': 0.0, 'phase_3_tokens': 0,
            'phase_4_time': 0.0,
            'total_time': 0.0, 'total_tokens': 0
        }
        
        try:
            # Phase 1: Requirement Elucidation
            logger.info("=" * 60 + "\nPHASE 1: Requirement Elucidation\n" + "=" * 60)
            p1_start = time.time()
            p1_tokens_start = self.vlm_interface.get_usage_stats()['total_tokens']
            
            self.design_brief = self._phase1_requirement_elucidation(
                user_input, image_path, interactive
            )
            
            metrics['phase_1_time'] = time.time() - p1_start
            metrics['phase_1_tokens'] = self.vlm_interface.get_usage_stats()['total_tokens'] - p1_tokens_start

            # Phase 2: Strategic Planning
            logger.info("=" * 60 + "\nPHASE 2: Strategic Planning\n" + "=" * 60)
            p2_start = time.time()
            p2_tokens_start = self.vlm_interface.get_usage_stats()['total_tokens']
            
            self.construction_plan = self._phase2_strategic_planning(
                self.design_brief
            )
            
            metrics['phase_2_time'] = time.time() - p2_start
            metrics['phase_2_tokens'] = self.vlm_interface.get_usage_stats()['total_tokens'] - p2_tokens_start

            # Phase 3: Generation & Verification
            logger.info("=" * 60 + "\nPHASE 3: Generation & Verification\n" + "=" * 60)
            p3_start = time.time()
            p3_tokens_start = self.vlm_interface.get_usage_stats()['total_tokens']
            
            final_code = self._phase3_generation_verification(
                self.construction_plan
            )
            
            metrics['phase_3_time'] = time.time() - p3_start
            metrics['phase_3_tokens'] = self.vlm_interface.get_usage_stats()['total_tokens'] - p3_tokens_start
            
            # Phase 4: User Validation & Finalization
            logger.info("=" * 60 + "\nPHASE 4: User Validation & Export\n" + "=" * 60)
            p4_start = time.time()
            
            validation_results = self._phase4_user_validation(
                final_code, interactive
            )
            
            metrics['phase_4_time'] = time.time() - p4_start

            # Phase 5: Self-Learning (Archival)
            if validation_results['success'] and self.config['output'].get('archive_successful_runs', True):
                logger.info("=" * 60 + "\nPHASE 5: Self-Learning (EDR Archival)\n" + "=" * 60)
                
                self.edr.archive_successful_design(
                    design_brief=self.design_brief,
                    construction_plan=self.construction_plan,
                    final_code=final_code,
                    metadata={
                        'session_id': self.session_id,
                        'metrics': metrics,
                        'exported_files': validation_results.get('exported_files', {})
                    }
                )

            # Finalize
            total_time = time.time() - start_time_total
            metrics['total_time'] = total_time
            metrics['total_tokens'] = self.vlm_interface.get_usage_stats()['total_tokens']
            
            validation_results['metrics'] = metrics
            logger.info("Workflow completed successfully!")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Workflow CRITICAL FAILURE: {str(e)}")
            # Return partial metrics even on failure
            metrics['total_time'] = time.time() - start_time_total
            return {
                'success': False,
                'message': str(e),
                'session_id': self.session_id,
                'metrics': metrics
            }

    # PHASE IMPLEMENTATIONS
    def _phase1_requirement_elucidation(self, user_input, image_path, interactive) -> DesignBrief:
        self.current_phase = WorkflowPhase.REQUIREMENT_ELUCIDATION
        
        design_brief = self.requirements_analyst.elicit_requirements(
            user_text=user_input,
            image_path=image_path,
            interactive=interactive
        )
        
        # Persist Brief
        output_path = Path(self.config['output']['design_briefs_path']) / f"{self.session_id}_brief.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        design_brief.to_json_file(str(output_path))
        
        logger.info(f"Brief Saved: {output_path}")
        return design_brief

    def _phase2_strategic_planning(self, design_brief) -> ConstructionPlan:
        self.current_phase = WorkflowPhase.STRATEGIC_PLANNING
        
        construction_plan = self.project_manager.create_construction_plan(design_brief)
        
        # Persist Plan
        output_path = Path(self.config['output']['plans_path']) / f"{self.session_id}_plan.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        construction_plan.to_json_file(str(output_path))
        
        logger.info(f"Plan Saved: {output_path} | Steps: {len(construction_plan.tasks)}")
        return construction_plan

    def _phase3_generation_verification(self, plan: ConstructionPlan) -> str:

        if self.design_brief is None:
            raise ValueError("Design Brief is missing. Cannot start Phase 3.")
        
        self.current_phase = WorkflowPhase.GENERATION_VERIFICATION
        
        # Reset execution namespace for a clean run
        self.cad_executor.reset_namespace()
        max_attempts = self.config['agents']['design_architect']['max_code_generation_attempts']
        
        while not plan.is_completed:
            current_task = plan.get_next_task()
            if not current_task: break
            
            logger.info(f"\nExecuting Task {current_task.step_number}: {current_task.description}")
            
            # Context Building
            code_history = plan.get_completed_code()
            task_success = False
            attempts = 0
            last_error = None
            last_code = None
            
            while not task_success and attempts < max_attempts:
                attempts += 1
                
                try:
                    # 1. Generate (or Debug)
                    if attempts > 1 and last_error and last_code:
                        logger.warning(f"  ➜ Debugging Attempt {attempts}...")
                        full_context = f"{code_history}\n{last_code}"
                        code = self.design_architect.debug_execution_error(
                            code=full_context, error=last_error, task=current_task
                        )
                    else:
                        logger.info(f"  ➜ Generation Attempt {attempts}...")
                        code = self.design_architect.generate_code(
                            task=current_task, design_brief=self.design_brief, previous_code=code_history
                        )
                    
                    last_code = code 
                    
                    # 2. Execute & Render
                    # We execute the full history + new code to ensure context validity
                    full_execution_code = f"{code_history}\n{code}" if code_history else code
                    
                    model, renders = self.cad_executor.execute_and_render(
                        code=full_execution_code,
                        views=self.config['agents']['quality_verifier']['render_views']
                    )
                    
                    # 3. Verify
                    verification = self.quality_verifier.verify(
                        renders=renders,
                        task=current_task,
                        design_brief=self.design_brief,
                        code=full_execution_code 
                    )
                    
                    if verification['success']:
                        logger.info("  ✓ Verification PASSED")
                        plan.mark_task_completed(current_task.task_id, code, verification)
                        task_success = True
                    else:
                        logger.warning(f"  ✗ Verification FAILED: {verification['message']}")
                        last_error = verification['message']
                        
                except Exception as e:
                    logger.error(f"  ✗ Execution Error: {e}")
                    last_error = str(e)
            
            if not task_success:
                msg = f"Task {current_task.step_number} failed after {max_attempts} attempts."
                plan.mark_task_failed(current_task.task_id, msg)
                raise Exception(msg)
        
        logger.info("All tasks completed.")
        return plan.get_completed_code()

    def _phase4_user_validation(self, final_code: str, interactive: bool) -> Dict[str, Any]:

        if self.design_brief is None:
            raise ValueError("Design Brief is missing. Cannot start Phase 3.")
        
        self.current_phase = WorkflowPhase.USER_VALIDATION
        
        # 1. Final Render
        logger.info("Generating high-res final renders...")
        final_model, final_renders = self.cad_executor.execute_and_render(
            code=final_code,
            views=self.config['agents']['quality_verifier']['render_views'],
            use_persistent_namespace=False
        )
        
        # 2. Save Renders
        render_dir = Path(self.config['output']['renders_path']) / self.session_id
        render_dir.mkdir(parents=True, exist_ok=True)
        saved_render_paths = {}
        
        for view_name, image in final_renders.items():
            path = render_dir / f"{view_name}.png"
            image.save(str(path))
            saved_render_paths[view_name] = str(path)
            
        # 3. User Approval Interaction
        user_approved = True
        if interactive and self.config['workflow']['enable_user_validation']:
            print(f"\n{'='*60}\nFINAL DESIGN REVIEW\n{'='*60}")
            print(f"Renders saved to: {render_dir}")
            while True:
                response = input("Approve this design? (yes/no): ").lower()
                if response in ['yes', 'y']: break
                if response in ['no', 'n']: 
                    user_approved = False
                    break
        
        # 4. Export (Only if approved)
        exported_files = {}
        if user_approved:
            model_dir = Path(self.config['output']['models_path']) / self.session_id
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Export 3D files (STL, STEP)
            exported_files = self.exporter.export_model(
                model=final_model,
                output_dir=str(model_dir),
                filename=self.design_brief.design_title.replace(' ', '_'),
                formats=self.config['cadquery']['export_formats']
            )
            
            # Export Python Code
            code_path = model_dir / "parametric_model.py"
            with open(code_path, 'w', encoding='utf-8') as f:
                f.write(final_code)
            exported_files['code'] = str(code_path)
            
            return {
                'success': True,
                'session_id': self.session_id,
                'design_brief': self.design_brief,
                'construction_plan': self.construction_plan,
                'final_code': final_code,
                'renders': saved_render_paths,
                'exported_files': exported_files
            }
        
        return {
            'success': False,
            'session_id': self.session_id,
            'message': 'User rejected the design'
        }

    # HELPERS

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _setup_logging(self) -> None:
        log_config = self.config['logging']
        logger.add(
            log_config['log_file'],
            level=log_config['level'],
            rotation="10 MB"
        )