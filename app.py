import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
from core.workflow import UMACADWorkflow

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize the workflow ONCE
print("Initializing AI Workflow...")
try:
    workflow = UMACADWorkflow(config_path='config/config.yaml')
    print("AI Ready!")
except Exception as e:
    print(f"Error initializing workflow: {e}")

# --- GLOBAL STORAGE FOR THE LAST RUN (Simple solution for demos) ---
LAST_RUN_DATA = {}

@app.route('/')
def home():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Handle the generation request"""
    global LAST_RUN_DATA
    data = request.json
    prompt = data.get('prompt')

    if not prompt:
        return jsonify({'success': False, 'error': 'Please describe what you want to build!'})

    try:
        print(f"Received prompt: {prompt}")
       
        # Run the workflow
        results = workflow.run(user_input=prompt, interactive=False)

        if results['success']:
            # 1. SAVE RESULTS TO GLOBAL VAR (So we can archive later)
            LAST_RUN_DATA = results
           
            # 2. GET FILE PATHS
            stl_path = results['exported_files'].get('stl')
            step_path = results['exported_files'].get('step') # Get STEP file too
           
            def get_rel_path(full_path):
                return os.path.relpath(full_path, os.getcwd())

            # 3. PREPARE RESPONSE
            response_data = {
                'success': True,
                'design_title': results['design_brief'].design_title,
                'stl_url': f"/files/{get_rel_path(stl_path)}",
                # Add STEP URL if it exists
                'step_url': f"/files/{get_rel_path(step_path)}" if step_path else None,
                'renders': {
                    view: f"/files/{get_rel_path(path)}"
                    for view, path in results['renders'].items()
                }
            }
            return jsonify(response_data)
        else:
            return jsonify({'success': False, 'error': results.get('message', 'Generation failed')})
        
    except Exception as e:
        print(f"Error during generation: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/feedback', methods=['POST'])
def feedback():
    """Handle Thumbs Up/Down""" 
    global LAST_RUN_DATA
    data = request.json
    action = data.get('action') # 'upvote' or 'downvote'


    if not LAST_RUN_DATA:
        return jsonify({'success': False, 'message': 'No recent design to vote on.'})

    if action == 'upvote':
        try:
            print("👍 User liked the design! Archiving to Memory...")
            # CALL THE ARCHIVE FUNCTION MANUALLY HERE
            workflow.edr.archive_successful_design(
                design_brief=LAST_RUN_DATA['design_brief'],
                construction_plan=LAST_RUN_DATA['construction_plan'],
                final_code=LAST_RUN_DATA['final_code'],
                metadata={'session_id': LAST_RUN_DATA['session_id']}
            )
            return jsonify({'success': True, 'message': 'Design Learned!'})

        except Exception as e:
            print(f"Archiving failed: {e}")
            return jsonify({'success': False, 'message': 'Failed to save to memory.'})

           

    elif action == 'downvote':
        print("👎 User disliked the design. Discarding...")
        # We just don't save it.
        return jsonify({'success': True, 'message': 'Feedback received.'})
    return jsonify({'success': False})



@app.route('/files/<path:filename>')
def serve_files(filename):
    return send_from_directory('.', filename)



if __name__ == '__main__':
    app.run(debug=True, port=5000) 