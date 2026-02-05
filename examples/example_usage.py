"""
Example: Using UMACAD Programmatically
Demonstrates how to use UMACAD as a library
"""

import sys
import yaml
from core.workflow import UMACADWorkflow
from core.design_brief import DesignBrief, GeometricFeature, Dimension, DimensionType, MaterialSpecification
from cadquery_integration.executor import CadQueryExecutor
from cadquery_integration.exporter import ModelExporter
from utils.vlm_interface import VLMInterface

# Example 1: Simple Workflow
def example_1_simple_workflow():
    """Run the full workflow with a simple text prompt."""
    print("\n" + "="*60)
    print("Example 1: Simple Workflow")
    print("="*60)
    
    workflow = UMACADWorkflow(config_path="config/config.yaml")
    
    results = workflow.run(
        user_input="Create a simple rectangular mounting bracket with two holes",
        interactive=False  # Skip clarification for automation
    )
    
    if results['success']:
        print(f"✓ Success! Design: {results['design_brief'].design_title}")
        print(f"✓ STL file: {results['exported_files'].get('stl')}")
    else:
        print(f"✗ Failed: {results.get('message')}")

# Example 2: Workflow with Image
def example_2_with_image():
    """Run the workflow with an input image (sketch)."""
    print("\n" + "="*60)
    print("Example 2: With Image Input")
    print("="*60)
    
    workflow = UMACADWorkflow()
    
    results = workflow.run(
        user_input="Create this bracket based on the sketch",
        image_path="examples/bracket_sketch.png",
        interactive=True
    )
    
    if results['success']:
        print(f"✓ Design created: {results['design_brief'].design_title}")

# Example 3: Manual Design Brief
def example_3_manual_design_brief():
    """Manually construct a DesignBrief object without AI."""
    print("\n" + "="*60)
    print("Example 3: Manual DesignBrief")
    print("="*60)
    
    brief = DesignBrief(
        brief_id="manual_001",
        user_input_text="L-shaped bracket",
        user_input_image_path=None,
        design_title="L-Shaped Mounting Bracket",
        design_description="An L-shaped bracket for mounting shelves",
        design_category="bracket",
        material=MaterialSpecification(
            material_name="PLA Plastic",
            material_type="polymer",
            finish="smooth"
        ),
        features=[
            GeometricFeature(
                feature_id="short_leg",
                feature_type="rectangular_block",
                dimensions=[
                    Dimension(name="length", type=DimensionType.LENGTH, value=50.0, unit="mm", tolerance=0.1, tolerance_type="symmetric"),
                    Dimension(name="width", type=DimensionType.WIDTH, value=40.0, unit="mm", tolerance=0.1, tolerance_type="symmetric"),
                    Dimension(name="thickness", type=DimensionType.THICKNESS, value=5.0, unit="mm", tolerance=0.05, tolerance_type="symmetric")
                ],
                position={"x": 0, "y": 0, "z": 0}
            ),
            GeometricFeature(
                feature_id="long_leg",
                feature_type="rectangular_block",
                dimensions=[
                    Dimension(name="length", type=DimensionType.LENGTH, value=100.0, unit="mm", tolerance=0.1, tolerance_type="symmetric"),
                    Dimension(name="width", type=DimensionType.WIDTH, value=40.0, unit="mm", tolerance=0.1, tolerance_type="symmetric"),
                    Dimension(name="thickness", type=DimensionType.THICKNESS, value=5.0, unit="mm", tolerance=0.05, tolerance_type="symmetric")
                ],
                position={"x": 0, "y": 0, "z": 5}
            )
        ],
        tags=["bracket", "L-shape", "mounting"],
        confidence_score=1.0
    )
    
    print(f"Created brief: {brief.design_title}")
    print(f"Features: {len(brief.features)}")
    
    brief.to_json_file("outputs/design_briefs/manual_brief.json")
    print("✓ Saved to outputs/design_briefs/manual_brief.json")

# Example 4: Access Individual Agents
def example_4_access_agents():
    """Directly initialize and use agents (Analyst & Manager)."""
    print("\n" + "="*60)
    print("Example 4: Using Individual Agents")
    print("="*60)
    
    from agents.requirements_analyst import RequirementsAnalyst
    from agents.project_manager import ProjectManager
    from repository.evolving_design_repo import EvolvingDesignRepository
    
    # Load config
    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    # Initialize VLM Interface (Required by agents)
    vlm = VLMInterface(config['openrouter_provider'])

    # 1. Requirements Analyst
    ra = RequirementsAnalyst(
        config=config['agents']['requirements_analyst'],
        vlm_interface=vlm
    )
    
    brief = ra.elicit_requirements(
        user_text="Create a simple box with a hole",
        interactive=False
    )
    print(f"✓ Brief created: {brief.design_title}")
    
    # 2. Project Manager
    edr = EvolvingDesignRepository(config['edr'])
    pm = ProjectManager(
        config=config['agents']['project_manager'],
        vlm_interface=vlm,
        edr=edr
    )
    
    plan = pm.create_construction_plan(brief)
    print(f"✓ Plan created with {len(plan.tasks)} tasks")

# Example 5: Custom Export Formats
def example_5_export_formats():
    """Generate a model and export to specific formats."""
    print("\n" + "="*60)
    print("Example 5: Custom Export Formats")
    print("="*60)
    
    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    code = """
import cadquery as cq
result = cq.Workplane("XY").box(50, 50, 10).faces(">Z").hole(10)
"""
    
    executor = CadQueryExecutor(config['cadquery'])
    model, error = executor.execute_code(code)
    
    if model:
        exporter = ModelExporter(config['cadquery'])
        files = exporter.export_model(
            model,
            output_dir="outputs/models/example",
            filename="test_box",
            formats=['stl', 'step', 'dxf']
        )
        
        print("✓ Exported files:")
        for fmt, path in files.items():
            print(f"  {fmt}: {path}")

# Main Entry Point
if __name__ == '__main__':
    examples = {
        '1': example_1_simple_workflow,
        '2': example_2_with_image,
        '3': example_3_manual_design_brief,
        '4': example_4_access_agents,
        '5': example_5_export_formats
    }
    
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num in examples:
            examples[example_num]()
        else:
            print(f"Example {example_num} not found")
    else:
        print("UMACAD Examples")
        print("="*60)
        print("1. Simple workflow with text input")
        print("2. Workflow with image input")
        print("3. Manual DesignBrief creation")
        print("4. Using individual agents")
        print("5. Custom export formats")
        print("\nUsage: python examples/example_usage.py [1-5]")