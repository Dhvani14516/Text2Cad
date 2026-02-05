"""
UMACAD - Unified Multi-Agent Collaborative Design
Main Entry Point
"""

import sys
import argparse
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from core.workflow import UMACADWorkflow


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = "DEBUG" if verbose else "INFO"
    
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    logger.add(
        "logs/umacad.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days"
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="UMACAD - Transform ideas into manufacturable 3D CAD models"
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Design description (text)'
    )
    
    parser.add_argument(
        '--image',
        type=str,
        help='Path to sketch or reference image'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Run without user interaction'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Display banner
    print("=" * 70)
    print("  UMACAD - Unified Multi-Agent Collaborative Design")
    print("  From Napkin Sketch to Physical Object")
    print("=" * 70)
    print()
    
    try:
        # Initialize workflow
        logger.info("Initializing UMACAD workflow...")
        workflow = UMACADWorkflow(config_path=args.config)
        
        # Run workflow
        logger.info(f"Processing design request: {args.input}")
        results = workflow.run(
            user_input=args.input,
            image_path=args.image,
            interactive=not args.non_interactive
        )
        
        # Display results
        if results['success']:
            print("\n" + "=" * 70)
            print("  SUCCESS!")
            print("=" * 70)
            print(f"\nSession ID: {results['session_id']}")
            print(f"\nDesign: {results['design_brief'].design_title}")
            print(f"Description: {results['design_brief'].design_description}")
            
            print(f"\nConstruction completed in {len(results['construction_plan'].tasks)} steps")

            # 2. [NEW] TASK STEPS (The "Recipe")
            print("\n" + "-" * 30)
            print("  CONSTRUCTION STEPS")
            print("-" * 30)
            plan = results['construction_plan']
            for task in plan.tasks:
                status_icon = "✓" if task.status == "completed" else "✗"
                # If we saved time in metadata in workflow.py, print it
                time_str = ""
                if hasattr(task, 'metadata') and task.metadata and 'execution_time_sec' in task.metadata:
                    time_str = f"({task.metadata['execution_time_sec']:.1f}s)"
                
                print(f"{status_icon} Step {task.step_number}: {task.description} {time_str}")

            # 3. [NEW] PERFORMANCE METRICS
            m = results['metrics']
            print("\n" + "-" * 30)
            print("  PERFORMANCE METRICS")
            print("-" * 30)
            
            # Use .get() to safely handle missing token counts
            p1_tokens = m.get('phase_1_tokens', 0)
            p2_tokens = m.get('phase_2_tokens', 0)
            p3_tokens = m.get('phase_3_tokens', 0)
            
            print(f"Phase 1 (Analyst):  {m.get('phase_1_time', 0):.1f}s | {p1_tokens} tokens")
            print(f"Phase 2 (Manager):  {m.get('phase_2_time', 0):.1f}s | {p2_tokens} tokens")
            print(f"Phase 3 (Builder):  {m.get('phase_3_time', 0):.1f}s | {p3_tokens} tokens")
            print(f"Phase 4 (Export):   {m.get('phase_4_time', 0):.1f}s")
            print("-" * 30)
            print(f"TOTAL TIME:         {m.get('total_time', 0):.1f}s")
            print(f"TOTAL TOKENS:       {m.get('total_tokens', 0)}")
            print("=" * 70)
            
            print("\nExported Files:")
            for fmt, path in results['exported_files'].items():
                print(f"  {fmt.upper()}: {path}")
            
            print("\nRenderings:")
            for view, path in results['renders'].items():
                print(f"  {view}: {path}")
            
            print("\n✓ Your 3D model is ready for manufacturing!")
            
        else:
            print("\n" + "=" * 70)
            print("  WORKFLOW INCOMPLETE")
            print("=" * 70)
            print(f"\n{results.get('message', 'Unknown error')}")
    
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        sys.exit(1)
    
    except Exception as e:
        logger.exception("Fatal error in workflow")
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
