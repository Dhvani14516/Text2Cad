"""
UMACAD - Safe CadQuery Sandbox
Wraps execution in a controlled environment to catch errors and prevent unsafe operations.
"""

import sys
import io
import traceback
import tempfile
import ast
import subprocess
import json
import base64
import time
import builtins
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class ExecutionStatus(Enum):
    """Execution status codes"""
    SUCCESS = "success"
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    NO_RESULT = "no_result"


@dataclass
class ExecutionResult:
    """Result of code execution"""
    status: ExecutionStatus
    model: Any = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    validation: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'status': self.status.value,
            'error': self.error,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'execution_time': self.execution_time,
            'validation': self.validation,
            'warnings': self.warnings,
            'success': self.is_success
        }


class SecurityValidator:
    """Validates code for security issues before execution"""
    
    FORBIDDEN_IMPORTS = {
        'os', 'subprocess', 'shutil', 'pathlib', 'socket', 'urllib',
        'requests', 'http', 'ftplib', 'telnetlib', 'eval', 'exec',
        '__import__', 'compile', 'open'
    }
    
    FORBIDDEN_FUNCTIONS = {
        'eval', 'exec', 'compile', '__import__', 'open', 'input',
        'file', 'execfile', 'reload'
    }
    
    FORBIDDEN_ATTRIBUTES = {
        '__import__', '__loader__', '__spec__', '__builtins__'
    }
    
    @staticmethod
    def validate_code(code: str) -> Tuple[bool, List[str]]:
        """
        Validate code for security issues
        Returns: (is_safe, list_of_issues)
        """
        issues = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in SecurityValidator.FORBIDDEN_IMPORTS:
                            issues.append(f"Forbidden import: {alias.name}")
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in SecurityValidator.FORBIDDEN_IMPORTS:
                        issues.append(f"Forbidden import from: {node.module}")
                
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in SecurityValidator.FORBIDDEN_FUNCTIONS:
                            issues.append(f"Forbidden function call: {node.func.id}")
                
                elif isinstance(node, ast.Attribute):
                    if node.attr in SecurityValidator.FORBIDDEN_ATTRIBUTES:
                        issues.append(f"Forbidden attribute access: {node.attr}")
        
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
        
        return len(issues) == 0, issues


class SandboxExecutor:
    """
    Executes CadQuery code in a sandboxed environment
    """
    
    def __init__(self, 
                 timeout: int = 30,
                 enable_security_checks: bool = True,
                 isolated_process: bool = False):
        self.timeout = timeout
        self.enable_security_checks = enable_security_checks
        self.isolated_process = isolated_process
        
        self.cq = None
        if not isolated_process:
            try:
                import cadquery as cq
                self.cq = cq
            except ImportError:
                pass
    
    def execute(self, code: str, 
                validate_model: bool = True,
                namespace: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Execute CadQuery code in sandbox"""
        start_time = time.time()
        warnings: List[str] = []
        
        if self.enable_security_checks:
            is_safe, issues = SecurityValidator.validate_code(code)
            if not is_safe:
                return ExecutionResult(
                    status=ExecutionStatus.SECURITY_VIOLATION,
                    error=f"Security validation failed: {', '.join(issues)}",
                    execution_time=time.time() - start_time
                )
        
        if self.isolated_process:
            return self._execute_in_subprocess(code, start_time)
        else:
            return self._execute_in_process(code, validate_model, namespace, start_time, warnings)
    
    def _execute_in_process(self, 
                            code: str,
                            validate_model: bool,
                            namespace: Optional[Dict[str, Any]],
                            start_time: float,
                            warnings: List[str]) -> ExecutionResult:
        """Execute code in the current process"""
        
        if self.cq is None:
             return ExecutionResult(
                status=ExecutionStatus.RUNTIME_ERROR,
                error="CadQuery module not found in current environment.",
                execution_time=time.time() - start_time
            )

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            if namespace is None:
                namespace = {
                    'cq': self.cq,
                    'cadquery': self.cq,
                    '__name__': '__main__',
                    '__builtins__': builtins.__dict__.copy()
                }
            
            try:
                exec(code, namespace)
            except SyntaxError as e:
                return ExecutionResult(
                    status=ExecutionStatus.SYNTAX_ERROR,
                    error=f"Syntax error at line {e.lineno}: {e.msg}",
                    stderr=stderr_capture.getvalue(),
                    execution_time=time.time() - start_time
                )
            except Exception as e:
                return ExecutionResult(
                    status=ExecutionStatus.RUNTIME_ERROR,
                    error=f"{type(e).__name__}: {str(e)}",
                    stderr=traceback.format_exc(),
                    execution_time=time.time() - start_time
                )
            
            result = namespace.get('result')
            if result is None:
                # Heuristic search for Workplane
                for key, value in namespace.items():
                    if hasattr(value, 'val') and hasattr(value, 'toSTEP'): 
                        result = value
                        warnings.append(f"No 'result' variable found, using '{key}' instead")
                        break
            
            if result is None:
                return ExecutionResult(
                    status=ExecutionStatus.NO_RESULT,
                    error="No 'result' variable found. Assign your final model to 'result'.",
                    stdout=stdout_capture.getvalue(),
                    stderr=stderr_capture.getvalue(),
                    warnings=warnings,
                    execution_time=time.time() - start_time
                )
            
            validation = None
            if validate_model:
                validation = self._validate_model(result)
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                model=result,
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                validation=validation,
                warnings=warnings,
                execution_time=time.time() - start_time
            )
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def _execute_in_subprocess(self, code: str, start_time: float) -> ExecutionResult:
        """
        Execute code in isolated subprocess using safe Base64 encoding.
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            temp_file = Path(f.name)
            
            encoded_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')
            
            # Subprocess wrapper without OCP imports
            wrapper_code = f"""
import sys
import json
import traceback
import base64
import cadquery as cq

try:
    user_code = base64.b64decode("{encoded_code}").decode('utf-8')
except Exception as e:
    print(json.dumps({{'status': 'runtime_error', 'error': 'Failed to decode code payload'}}))
    sys.exit(1)

result_data = {{
    'status': 'success',
    'error': None,
    'has_result': False
}}

try:
    namespace = {{'cq': cq, 'cadquery': cq}}
    exec(user_code, namespace)
    
    if 'result' in namespace:
        result_data['has_result'] = True
        result = namespace['result']
        
        # --- VALIDATION (Native CadQuery API) ---
        try:
            # 1. Bounding Box
            bbox = result.val().BoundingBox()
            result_data['bounding_box'] = {{
                'xmin': bbox.xmin, 'xmax': bbox.xmax,
                'ymin': bbox.ymin, 'ymax': bbox.ymax,
                'zmin': bbox.zmin, 'zmax': bbox.zmax
            }}
            
            # 2. Volume (Ghost Detection)
            # Use native .Volume() instead of OCP
            if hasattr(result.val(), 'Volume'):
                result_data['volume'] = result.val().Volume()
            else:
                result_data['volume'] = 0.0
                
        except Exception as e:
            result_data['validation_error'] = str(e)
            
    else:
        result_data['status'] = 'no_result'
        result_data['error'] = 'No result variable found'
        
except SyntaxError as e:
    result_data['status'] = 'syntax_error'
    result_data['error'] = f'Syntax error at line {{e.lineno}}: {{e.msg}}'
except Exception as e:
    result_data['status'] = 'runtime_error'
    result_data['error'] = str(e)
    result_data['traceback'] = traceback.format_exc()

print(json.dumps(result_data))
"""
            f.write(wrapper_code)
        
        try:
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            try:
                output = json.loads(result.stdout)
                status_map = {
                    'success': ExecutionStatus.SUCCESS,
                    'syntax_error': ExecutionStatus.SYNTAX_ERROR,
                    'runtime_error': ExecutionStatus.RUNTIME_ERROR,
                    'no_result': ExecutionStatus.NO_RESULT
                }
                
                validation = None
                if output.get('bounding_box') or output.get('volume'):
                    validation = {
                        'bounding_box': output.get('bounding_box'),
                        'volume': output.get('volume'),
                        'is_valid': True
                    }

                return ExecutionResult(
                    status=status_map.get(output['status'], ExecutionStatus.RUNTIME_ERROR),
                    error=output.get('error'),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    validation=validation,
                    execution_time=time.time() - start_time
                )
            except json.JSONDecodeError:
                return ExecutionResult(
                    status=ExecutionStatus.RUNTIME_ERROR,
                    error="Failed to parse subprocess output",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time=time.time() - start_time
                )
        
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error=f"Execution exceeded timeout of {self.timeout} seconds",
                execution_time=time.time() - start_time
            )
        finally:
            temp_file.unlink(missing_ok=True)
    
    def _validate_model(self, model: Any) -> Dict[str, Any]:
        """
        Validate using high-level CadQuery API (No direct OCP imports)
        """
        validation = {
            'is_valid': False,
            'has_geometry': False,
            'is_solid': False,
            'volume': None,
            'issues': []
        }
        
        try:
            if model is None:
                validation['issues'].append("Model is None")
                return validation
            
            validation['has_geometry'] = True
            
            # --- DEFINE SHAPE HERE ---
            try:
                shape = model.val()
            except Exception as e:
                validation['issues'].append(f"Critical: Could not extract shape: {e}")
                return validation
            # -------------------------

            # 1. Bounding Box
            try:
                bbox = shape.BoundingBox()
                validation['bounding_box'] = {
                    'xmin': round(bbox.xmin, 3), 'xmax': round(bbox.xmax, 3),
                    'ymin': round(bbox.ymin, 3), 'ymax': round(bbox.ymax, 3),
                    'zmin': round(bbox.zmin, 3), 'zmax': round(bbox.zmax, 3)
                }
            except Exception as e:
                validation['issues'].append(f"BoundingBox failed: {e}")

            # 2. Volume & Validity
            try:
                # Use CadQuery's wrapper methods
                if hasattr(shape, 'isValid'):
                    validation['is_solid'] = shape.isValid() 
                
                if validation['is_solid']:
                    if hasattr(shape, 'Volume'):
                        vol = shape.Volume()
                        validation['volume'] = round(vol, 3)
                        validation['is_valid'] = True
                    else:
                        validation['issues'].append("Shape does not have volume")
                else:
                    validation['issues'].append("Geometry is invalid")
            except Exception as e:
                validation['issues'].append(f"Validation failed: {e}")
                if 'bounding_box' in validation:
                    validation['is_valid'] = True

        except Exception as e:
            validation['issues'].append(f"General validation error: {e}")
        
        return validation


class CadQuerySandbox:
    """
    High-level interface for safe CadQuery code execution
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        
        self.executor = SandboxExecutor(
            timeout=config.get('timeout', 30),
            enable_security_checks=config.get('enable_security', True),
            isolated_process=config.get('isolated_process', False)
        )
        
        self.validate_model = config.get('validate_model', True)
        self.persistent_namespace = None
    
    def execute_code(self, 
                     code: str,
                     use_persistent_namespace: bool = False) -> ExecutionResult:
        
        namespace = self.persistent_namespace if use_persistent_namespace else None
        
        result = self.executor.execute(
            code,
            validate_model=self.validate_model,
            namespace=namespace
        )
        
        if use_persistent_namespace and result.is_success:
            if not self.executor.isolated_process:
                self.persistent_namespace = namespace
        
        return result
    
    def reset_namespace(self):
        self.persistent_namespace = None
    
    def validate_syntax(self, code: str) -> Tuple[bool, List[str]]:
        errors = []
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return False, errors