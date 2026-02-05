"""
UMACAD - Validation Utilities
Helper functions for validating data structures and parameters
"""

from typing import Any, Dict, List
from core.design_brief import DesignBrief, Dimension
from core.task_plan import ConstructionPlan, DesignTask


def validate_design_brief(brief: DesignBrief) -> Dict[str, Any]:
    """
    Validate DesignBrief for completeness
    
    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []
    
    # Check required fields
    if not brief.design_title:
        issues.append("Missing design title")
    
    if not brief.design_description:
        issues.append("Missing design description")
    
    if not brief.features:
        warnings.append("No features defined")
    
    # Check feature completeness
    for feature in brief.features:
        if not feature.dimensions:
            warnings.append(f"Feature {feature.feature_id} has no dimensions")
    
    # Check confidence
    if brief.confidence_score < 0.8:
        warnings.append(f"Low confidence score: {brief.confidence_score:.2f}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings
    }


def validate_construction_plan(plan: ConstructionPlan) -> Dict[str, Any]:
    """
    Validate ConstructionPlan for correctness
    
    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []
    
    # Check tasks
    if not plan.tasks:
        issues.append("No tasks in plan")
    
    # Check task sequence
    seen_ids = set()
    for task in plan.tasks:
        if task.task_id in seen_ids:
            issues.append(f"Duplicate task ID: {task.task_id}")
        seen_ids.add(task.task_id)
        
        # Check dependencies
        for dep in task.dependencies:
            if dep not in seen_ids:
                issues.append(f"Task {task.task_id} depends on undefined task {dep}")
    
    # Check step numbering
    for i, task in enumerate(plan.tasks, 1):
        if task.step_number != i:
            warnings.append(f"Task step number mismatch: expected {i}, got {task.step_number}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings
    }


def validate_dimensions(dimensions: List[Dimension]) -> Dict[str, Any]:
    """
    Validate dimension specifications
    
    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []
    
    for dim in dimensions:
        # Check for positive values
        if dim.value <= 0:
            warnings.append(f"Non-positive dimension: {dim.name} = {dim.value}")
        
        # Check for reasonable values (in mm)
        if dim.unit == 'mm':
            if dim.value > 500:
                warnings.append(f"Very large dimension: {dim.name} = {dim.value}mm")
            if dim.value < 0.1:
                warnings.append(f"Very small dimension: {dim.name} = {dim.value}mm")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings
    }


def check_cadquery_syntax(code: str) -> Dict[str, Any]:
    """
    Basic CadQuery code syntax checking
    
    Returns:
        Dictionary with check results
    """
    import ast
    
    issues = []
    warnings = []
    
    # Python syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        issues.append(f"Syntax error: {e}")
        return {'valid': False, 'issues': issues, 'warnings': warnings}
    
    # Check for CadQuery imports
    if 'import cadquery' not in code and 'from cadquery' not in code:
        warnings.append("No CadQuery import found")
    
    # Check for result assignment
    if 'result =' not in code:
        warnings.append("No 'result' variable assignment found")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings
    }
