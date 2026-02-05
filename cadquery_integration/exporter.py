"""
UMACAD - Model Exporter
Exports CadQuery models to various formats (STL, STEP, etc.)
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger
import json

cq = None
try:
    import cadquery as cq
except ImportError:
    logger.warning("CadQuery not installed! Export functionality will be disabled.")


class ModelExporter:
    """
    Exports CadQuery models to standard CAD formats
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.default_formats: List[str] = config.get('export_formats', ['stl', 'step'])
        
        # Verify CadQuery is available at runtime
        if cq is None:
            raise ImportError("CadQuery library is required for ModelExporter but is not installed.")
    
    def export_model(self,
                     model: Any,
                     output_dir: str,
                     filename: str,
                     formats: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Export model to multiple formats
        
        Args:
            model: CadQuery model object
            output_dir: Output directory path
            filename: Base filename (without extension)
            formats: List of formats to export (stl, step, dxf, svg)
            
        Returns:
            Dictionary of format -> filepath
        """
        export_formats: List[str] = formats if formats is not None else self.default_formats
        
        if export_formats is None:
            export_formats = []
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        exported_files = {}
        
        for fmt in export_formats:
            try:
                filepath = self._export_format(model, output_path, filename, fmt)
                if filepath:
                    exported_files[fmt] = filepath
                    logger.info(f"Exported {fmt.upper()}: {filepath}")
            except Exception as e:
                logger.error(f"Failed to export {fmt}: {e}")
        
        return exported_files
    
    def _export_format(self,
                       model: Any,
                       output_path: Path,
                       filename: str,
                       fmt: str) -> Optional[str]:
        """Export to a specific format"""
        
        filepath = output_path / f"{filename}.{fmt.lower()}"
        path_str = str(filepath)
        fmt_lower = fmt.lower()
        
        if fmt_lower == 'stl':
            return self._export_stl(model, path_str)
        elif fmt_lower == 'step':
            return self._export_step(model, path_str)
        elif fmt_lower == 'dxf':
            return self._export_dxf(model, path_str)
        elif fmt_lower == 'svg':
            return self._export_svg(model, path_str)
        else:
            logger.warning(f"Unsupported export format: {fmt}")
            return None
    
    def _export_stl(self, model: Any, filepath: str) -> Optional[str]:
        """Export to STL format"""
        try:
            if cq:
                cq.exporters.export(model, filepath, exportType='STL', tolerance=0.001, angularTolerance=0.1)
                return filepath
        except Exception as e:
            logger.error(f"STL export error: {e}")
        return None
    
    def _export_step(self, model: Any, filepath: str) -> Optional[str]:
        """Export to STEP format"""
        try:
            if cq:
                cq.exporters.export(model, filepath, exportType='STEP')
                return filepath
        except Exception as e:
            logger.error(f"STEP export error: {e}")
        return None
    
    def _export_dxf(self, model: Any, filepath: str) -> Optional[str]:
        """Export to DXF format"""
        try:
            if cq:
                cq.exporters.export(model, filepath, exportType='DXF')
                return filepath
        except Exception as e:
            logger.error(f"DXF export error: {e}")
        return None
    
    def _export_svg(self, model: Any, filepath: str) -> Optional[str]:
        """Export to SVG format"""
        try:
            if cq:
                cq.exporters.export(model, filepath, exportType='SVG')
                return filepath
        except Exception as e:
            logger.error(f"SVG export error: {e}")
        return None
    
    def export_with_metadata(self,
                             model: Any,
                             output_dir: str,
                             filename: str,
                             metadata: Dict[str, Any],
                             formats: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Export model with metadata file
        
        Args:
            model: CadQuery model
            output_dir: Output directory
            filename: Base filename
            metadata: Metadata dictionary to save
            formats: Export formats
            
        Returns:
            Dictionary of exported files
        """
        # Export model files
        exported = self.export_model(model, output_dir, filename, formats)
        
        # Save metadata
        try:
            metadata_path = Path(output_dir) / f"{filename}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            exported['metadata'] = str(metadata_path)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
        
        return exported