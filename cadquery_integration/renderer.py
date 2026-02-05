"""
UMACAD - High-Fidelity 3D Renderer
Uses PyVista for photorealistic snapshots
"""

import os
import tempfile
from PIL import Image, ImageDraw
from typing import Any, Dict, Tuple, Optional, cast
from loguru import logger

pv = None
cq = None
HAS_PYVISTA = False

try:
    import pyvista as pv
    import cadquery as cq
    HAS_PYVISTA = True
    if pv:
        pv.OFF_SCREEN = True
except ImportError:
    HAS_PYVISTA = False
    logger.warning("PyVista not found. Install with `pip install pyvista` for 3D renders.")


class ModelRenderer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.resolution = config.get('render_resolution', 1024)
        
    def render_view(self, model: Any, view: str = 'isometric', resolution: Optional[Tuple[int, int]] = None) -> Image.Image:
        """
        Render a high-quality snapshot of the model.
        """
        # Handle default resolution
        if resolution is None:
            res_val = int(self.resolution)
            res_tuple = (res_val, res_val)
        else:
            res_tuple = resolution
            
        # Check explicit dependency flags
        if not HAS_PYVISTA or pv is None or cq is None:
            return self._create_placeholder(view, res_tuple, "PyVista/CQ Missing")

        _pv: Any = pv
        _cq: Any = cq

        tmp_path = None
        try:
            # 1. Create a Temp Path (SAFE FOR WINDOWS)
            with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
                tmp_path = tmp.name
            
            # 2. Convert CadQuery -> STL
            _cq.exporters.export(model, tmp_path, exportType="STL")
            
            # 3. Load into PyVista
            mesh = _pv.read(tmp_path)
            
            if mesh is None:
                raise ValueError("Failed to load mesh from STL")

            # 4. Setup Plotter
            plotter = _pv.Plotter(off_screen=True, window_size=list(res_tuple))
            plotter.set_background('white')
            
            # 5. Add Mesh with PBR
            # Using _pv (Any) allows passing 'mesh' without strict DataObject vs DataSet checks
            plotter.add_mesh(mesh, color='lightblue', pbr=True, metallic=0.1, roughness=0.6)
            
            # 6. Position Camera
            if view == 'top':
                plotter.view_xy()
            elif view == 'front':
                plotter.view_xz() 
            elif view == 'side':
                plotter.view_yz()
            else: # Isometric
                plotter.view_isometric()
                
            # 7. Take Screenshot
            image_array = plotter.screenshot(return_img=True)
            plotter.close()
            
            if image_array is None:
                raise ValueError("PyVista failed to capture screenshot (returned None)")
            
            return Image.fromarray(image_array)

        except Exception as e:
            logger.error(f"Render failed: {e}")
            return self._create_placeholder(view, res_tuple, str(e))
            
        finally:
            # 8. Cleanup Temp File
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file {tmp_path}: {e}")

    def _create_placeholder(self, view: str, resolution: Tuple[int, int], error_msg: str = "") -> Image.Image:
        """Fallback for errors"""
        img = Image.new('RGB', resolution, color='#ffeeee')
        draw = ImageDraw.Draw(img)
        draw.text((10, 50), f"RENDER FAIL: {view}", fill='red')
        draw.text((10, 80), error_msg[:50], fill='red')
        return img