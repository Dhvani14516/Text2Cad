"""
Test Suite for UMACAD
Basic functionality tests for Data Structures, Planning, and Execution.
"""

import unittest
import sys
from pathlib import Path

# Add project root to path to ensure modules are found
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.design_brief import (
    DesignBrief, 
    GeometricFeature, 
    Dimension, 
    DimensionType, 
    MaterialSpecification
)
from core.task_plan import ConstructionPlan, DesignTask, TaskType
from utils.validation import validate_design_brief


class TestDesignBrief(unittest.TestCase):
    """Test DesignBrief creation and validation"""
    
    def setUp(self):
        """Common setup for design brief tests"""
        self.default_material = MaterialSpecification(
            material_name="PLA", 
            material_type="plastic", 
            finish="none"
        )

    def test_create_design_brief(self):
        """Test creating a basic design brief"""
        brief = DesignBrief(
            brief_id="test_001",
            user_input_text="Test input",
            user_input_image_path=None,
            design_title="Test Design",
            design_description="A test design",
            design_category="test",
            material=self.default_material
        )
        
        self.assertEqual(brief.brief_id, "test_001")
        self.assertEqual(brief.design_title, "Test Design")
    
    def test_design_brief_with_features(self):
        """Test design brief with geometric features"""
        feature = GeometricFeature(
            feature_id="feature_1",
            feature_type="block",
            dimensions=[
                Dimension(
                    name="length", 
                    type=DimensionType.LENGTH, 
                    value=50.0, 
                    unit="mm", 
                    tolerance=0.1, 
                    tolerance_type="symmetric"
                )
            ]
        )
        
        brief = DesignBrief(
            brief_id="test_002",
            user_input_text="Test",
            user_input_image_path=None,
            design_title="Test",
            design_description="Test",
            design_category="test",
            material=self.default_material,
            features=[feature]
        )
        
        self.assertEqual(len(brief.features), 1)
        self.assertEqual(brief.features[0].feature_id, "feature_1")
    
    def test_validate_design_brief(self):
        """Test design brief validation"""
        brief = DesignBrief(
            brief_id="test_003",
            user_input_text="Test",
            user_input_image_path=None,
            design_title="Valid Brief",
            design_description="A valid test brief",
            design_category="test",
            material=self.default_material
        )
        
        validation = validate_design_brief(brief)
        self.assertTrue(validation['valid'])


class TestConstructionPlan(unittest.TestCase):
    """Test ConstructionPlan functionality"""
    
    def test_create_plan(self):
        """Test creating a construction plan"""
        plan = ConstructionPlan(
            plan_id="plan_001",
            design_brief_id="brief_001",
            strategy="Test strategy",
            reasoning="Test reasoning"
        )
        
        self.assertEqual(plan.plan_id, "plan_001")
        self.assertEqual(len(plan.tasks), 0)
    
    def test_add_tasks(self):
        """Test adding tasks to plan"""
        plan = ConstructionPlan(
            plan_id="plan_002",
            design_brief_id="brief_002",
            strategy="Test",
            reasoning="Test"
        )
        
        task = DesignTask(
            task_id="task_1",
            step_number=1,
            task_type=TaskType.CREATE_SOLID,
            description="Create a box"
        )
        
        plan.tasks.append(task)
        self.assertEqual(len(plan.tasks), 1)
    
    def test_get_next_task(self):
        """Test getting next task from plan"""
        plan = ConstructionPlan(
            plan_id="plan_003",
            design_brief_id="brief_003",
            strategy="Test",
            reasoning="Test",
            tasks=[
                DesignTask(
                    task_id="task_1",
                    step_number=1,
                    task_type=TaskType.CREATE_SOLID,
                    description="Task 1"
                ),
                DesignTask(
                    task_id="task_2",
                    step_number=2,
                    task_type=TaskType.ADD_HOLE,
                    description="Task 2"
                )
            ]
        )
        
        next_task = plan.get_next_task()
        
        # --- FIX: Use explicit python check to satisfy Pylance ---
        if next_task is None:
            self.fail("get_next_task() returned None unexpectedly")
        else:
            # Pylance now knows next_task is definitely a DesignTask here
            self.assertEqual(next_task.task_id, "task_1")


class TestCadQueryIntegration(unittest.TestCase):
    """Test CadQuery execution"""
    
    def test_simple_box_code(self):
        """Test executing simple CadQuery code"""
        try:
            from cadquery_integration.executor import CadQueryExecutor
            
            # Using basic config
            executor = CadQueryExecutor({
                'default_units': 'mm',
                'tolerance': 0.01,
                'render_resolution': 512
            })
            
            code = """
import cadquery as cq
result = cq.Workplane("XY").box(10, 10, 10)
"""
            model, error = executor.execute_code(code)
            
            self.assertIsNone(error)
            self.assertIsNotNone(model)
            
        except ImportError:
            self.skipTest("CadQuery not installed")


class TestValidation(unittest.TestCase):
    """Test validation utilities"""
    
    def test_validate_empty_brief(self):
        """Test validation catches empty brief"""
        # Create a brief with empty string fields but valid structure
        brief = DesignBrief(
            brief_id="test",
            user_input_text="",
            user_input_image_path=None,
            design_title="",
            design_description="",
            design_category="test",
            material=MaterialSpecification(material_name="PLA", material_type="plastic", finish="none")
        )
        
        validation = validate_design_brief(brief)
        
        # Expectation: Should fail because title/description/input are empty
        self.assertFalse(validation['valid'])
        self.assertTrue(len(validation['issues']) > 0)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)