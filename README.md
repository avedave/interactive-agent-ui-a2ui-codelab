# Build Interactive Agent Interfaces with A2UI, Gemini, and Cloud Run

This repository contains the complete Google Codelab and accompanying runnable source code demonstrating how to build rich, agent-driven user interfaces using **A2UI v0.9.1** (Agent-to-User Interface protocol), the official **`a2ui-agent-sdk`**, **Gemini 3.8 Flash** on **Vertex AI**, and **Google Cloud Run**.

## Repository Structure

```
.
├── main.py               # Complete FastAPI backend (Vertex AI, Tools, A2uiSchemaManager v0.9.1)
├── sensors.py            # Simulated smart home sensors & low-battery telemetry
├── requirements.txt      # google-genai==2.25.0, a2ui-agent-sdk==0.6.0, fastapi==0.141.1, uvicorn==0.54.0
├── Dockerfile            # Container specification for Cloud Run deployment
├── static/
│   ├── index.html        # Clean chat frontend supporting text and <a2ui-surface>
│   ├── a2ui-bridge.js    # Browser ESM bridge integrating official @a2ui/web_core and @a2ui/lit
│   └── styles.css        # Material Google-style layout and A2UI card styles
├── codelab.md            # Complete 7-step Google Codelab (claat compatible)
├── claat-public/         # Self-hosted assets for offline/local Codelab previewing
└── README.md             # Repository documentation
```

---

## Codelab Overview

| Step | Title | Duration | Description |
| :--- | :--- | :--- | :--- |
| **1** | **Introduction** | 5 min | What is A2UI, trust-boundary security, declarative UI vs arbitrary code execution. |
| **2** | **Environment & Vertex AI Setup** | 8 min | Cloud Shell setup, enabling APIs (`run`, `aiplatform`, `cloudbuild`), IAM configuration, starter repo. |
| **3** | **Building the Baseline Text Agent** | 10 min | Initializing `google-genai` on Vertex AI, tool calling with `get_sensor_report`, text limitations. |
| **4** | **Deploying the Baseline to Cloud Run** | 7 min | Early containerized deployment with `gcloud run deploy --source .` to validate cloud runtime & IAM. |
| **5** | **Understanding A2UI v0.9.1 & The Client Renderer** | 8 min | Exploring the v0.9.1 specification (`createSurface`, `updateComponents`), BasicCatalog primitives, and `<a2ui-surface>`. |
| **6** | **Upgrading the Agent with A2UI & A2uiSchemaManager** | 12 min | Using `a2ui-agent-sdk` to generate system prompts programmatically, parsing `<a2ui-json>`, and testing *"What needs my attention?"*. |
| **7** | **Congratulations & Clean Up** | 3 min | Architecture summary, deletion commands (`gcloud run services delete`), and next steps. |

---

## Quickstart: Running Locally

### 1. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
```bash
export GOOGLE_CLOUD_PROJECT="$(gcloud config get-value project)"
export GOOGLE_CLOUD_REGION="us-central1"
```

### 3. Start the Server
```bash
uvicorn main:app --reload --port 8080
```
Open [http://localhost:8080](http://localhost:8080) in your browser.

### 4. Test Example Queries
- **Conversational Text Advice:** *"What is a healthy indoor humidity?"* -> Conversational plain text response.
- **Attention & Alerts:** *"What needs my attention?"* -> Rich A2UI v0.9.1 alert cards highlighting low batteries (Hallway Smoke Alarm at 11%, Nursery Air Monitor at 14%).
- **Dashboard Telemetry:** *"Show all sensor readings"* -> Visual dashboard cards for climate, air quality, safety alarms, and security locks.

---

## Deploying to Google Cloud Run

Deploy directly from source:
```bash
gcloud run deploy smart-home-a2ui \
  --source . \
  --region "${GOOGLE_CLOUD_REGION:-us-central1}" \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}",GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
```

---

## Exporting & Previewing the Codelab

The tutorial is authored in standard Google Codelabs format (`claat`). To compile and preview the tutorial:

```bash
# Export the markdown to Google Codelab HTML
claat export codelab.md

# Preview locally (from repository root)
claat serve
```
Navigate to the provided port (default `http://localhost:9090`) to view the interactive Codelab with the standard Google developer documentation layout and navigation menu.
