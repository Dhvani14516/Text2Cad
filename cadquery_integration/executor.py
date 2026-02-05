"""
UMACAD - CadQuery Executor (Sandboxed)
Executes Python CadQuery code safely and renders models
"""

from typing import Dict, Tuple, Any, List, Optional
from PIL import Image
from loguru import logger
import json

from .sandbox import CadQuerySandbox, ExecutionStatus
from .renderer import ModelRenderer


class CadQueryExecutor:
    """
    Executes Python CadQuery code safely using a sandbox and generates renders.
    Acts as the bridge between the Agents and the Core CadQuery/PyVista logic.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.render_resolution = config.get('render_resolution', 512)
        
        # Initialize the SAFE sandbox
        self.sandbox = CadQuerySandbox(config={
            'timeout': 30,                
            'enable_security': True,      
            'isolated_process': False,    
            'validate_model': True        
        })
        
        # Initialize the Renderer
        self.renderer = ModelRenderer(config)
        
        logger.info("CadQuery Executor (Sandboxed) initialized")
    
    def reset_namespace(self):
        """Reset the persistent namespace for a new workflow run"""
        self.sandbox.reset_namespace()
        logger.debug("Execution namespace reset")
    
    def execute_code(self, code: str, use_persistent_namespace: bool = True) -> Tuple[Any, Optional[str]]:
        """
        Execute CadQuery code safely using the sandbox
        """
        # 1. Run the code safely via Sandbox
        result = self.sandbox.execute_code(code, use_persistent_namespace)
        
        # 2. Handle Failures (Syntax, Runtime, Security)
        if not result.is_success:
            error_msg = f"{result.status.value}: {result.error}"
            if result.stderr:
                error_msg += f"\nDetails: {result.stderr}"
                
            logger.error(f"Execution failed: {error_msg}")
            return None, error_msg

        # 3. Handle Success & Validation
        logger.info(f"Code executed successfully (Time: {result.execution_time:.2f}s)")
        
        if result.validation:
            vol = result.validation.get('volume', 0.0)
            is_valid_geo = result.validation.get('is_valid', False)
            
            logger.info(f"Model Stats - Volume: {vol}, GeoValid: {is_valid_geo}")

            # [CRITICAL CHECK] Ghost Model Detection
            if vol is None or vol < 0.001:
                error_msg = "Model Validation Failed: The resulting model has ZERO volume (Ghost Model). Check your extrude values or cut operations."
                logger.error(error_msg)
                return None, error_msg

            # General Geometric Invalidity
            if not is_valid_geo:
                issues = "; ".join(result.validation.get('issues', []))
                error_msg = f"Model Geometry Invalid: {issues}"
                logger.error(error_msg)
                return None, error_msg
                
        return result.model, None
    
    def render_views(self, 
                    model: Any,
                    views: Optional[List[str]] = None) -> Dict[str, Image.Image]:
        """
        Render multiple views of the model using the ModelRenderer
        """
        if views is None:
            views = ['top', 'front', 'side', 'isometric']
        
        renders = {}
        res = int(self.render_resolution)
        resolution = (res, res)
        
        for view_name in views:
            try:
                # Delegate to Renderer class
                image = self.renderer.render_view(model, view_name, resolution)
                renders[view_name] = image
                logger.info(f"Rendered {view_name} view")
                
            except Exception as e:
                logger.error(f"Failed to render {view_name}: {e}")
                renders[view_name] = Image.new('RGB', resolution, color='#ffeeee')
        
        return renders
    
    def execute_and_render(self,
                           code: str,
                           views: Optional[List[str]] = None,
                           use_persistent_namespace: bool = True) -> Tuple[Any, Dict[str, Image.Image]]:
        """
        Orchestrator method: Execute code -> Check Validity -> Render Views
        """
        # 1. Execute
        model, error = self.execute_code(code, use_persistent_namespace)
        
        if error:
            raise Exception(f"Code execution failed: {error}")
        
        if model is None:
            raise Exception("Code executed but no model was created (result is None)")
        
        # 2. Render
        renders = self.render_views(model, views)
        
        return model, renders