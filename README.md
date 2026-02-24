# UMACAD: Text2Cad Multi-Agent System 

This is an autonomous AI system that converts natural language descriptions into manufacturable 3D CAD models. It utilizes a team of specialized AI agents to analyze requirements, plan construction strategies, and generate parametric Python code using CadQuery.

## Key Features

* **Multi-Agent Architecture:**
* **Analyst:** Clarifies vague user prompts into technical briefs.
* **Manager:** Breaks down the design into a step-by-step construction plan.
* **Architect:** Writes robust CadQuery code to build the model.
* **Verifier:** Visually inspects the output and auto-corrects errors.


* **Self-Learning (EDR):** The system "learns" from successful designs, archiving them into a Vector Database (ChromaDB) to improve future performance.
* **Dual Interfaces:** Command Line Interface (CLI) for batch processing and a Web UI for interactive design.
* **Production Outputs:** Exports to `.STL`, `.STEP`.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Dhvani14516/Text2Cad.git
cd Text2Cad

```

### 2. Set Up Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate

```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

```

### 4. Configure API Keys

Add your openrouter or open ai key in environment

### 5. Setup: Long-Term Memory (Crucial)

Due to GitHub file size limits, the system's "Brain" (Vector Database) is hosted externally.

1. **[Download the (chroma_db.zip)]** : https://drive.google.com/file/d/1dbq7u-Fk2vK_bBuWt72BhCO8zYZlR3xl/view?usp=sharing
2. Extract the zip file.
3. Place the `chroma_db` folder inside `repository/`.
4. Ensure the path looks exactly like this: `Text2Cad/repository/chroma_db/`

---

## How to Run

### Option A: Command Line Interface (CLI)

```bash
# Basic Usage
python main.py "A modular hex-shaped storage container"

# Non-Interactive (Auto-accepts design)
python main.py "Simple 50mm cube" --non-interactive

```

### Option B: Web Interface

Best for visual feedback and easy interaction.

```bash
python app.py

```

* Open your browser to `http://127.0.0.1:5000`
* Type your prompt and click **Generate**.
* View the 3D render, download files, or Upvote/Downvote (to teach the AI).

---

## Project Structure

```text
Text2Cad/
├── agents/                 # AI Agents (Analyst, Manager, Architect, verifier)
├── core/                   # Workflow orchestration logic
├── cadquery_integration/   # Code execution sandbox & rendering
├── repository/             # ChromaDB & Knowledge Base
├── outputs/                # Generated models (STL/STEP) are saved here
├── app.py                  # Flask Web Server
├── main.py                 # CLI Entry Point
└── requirements.txt        # Project dependencies

```
