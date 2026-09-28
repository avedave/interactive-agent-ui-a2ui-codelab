id: interactive-agent-ui-a2ui-gemini
summary: Build interactive agent-driven user interfaces using A2UI v0.9.1, Gemini 3.8 Flash on Vertex AI, and Google Cloud Run.
categories: Web, Cloud, AI
environments: Web
status: Published
feedback link: https://github.com/a2ui-project/a2ui/issues
tags: a2ui, gemini, cloudrun, vertexai, python, webcomponents
authors: Google DeepMind

# Build Interactive Agent Interfaces with A2UI, Gemini, and Cloud Run

## Introduction
Duration: 5

### What is A2UI?

When AI agents interact with users today, they are almost universally confined to plain text or Markdown. While Markdown works well for paragraphs and bulleted summaries, it falls short when users need to monitor live telemetry, inspect status indicators, scan dashboards, or review alert cards.

Historically, giving an agent the ability to display a graphical UI required sending executable code (such as raw HTML, JavaScript, or iframe embeds) to the client. However, **executing arbitrary code from an AI model across a trust boundary is a major security vulnerability** (risk of cross-site scripting, arbitrary script execution, and unvetted DOM manipulation).

**A2UI (Agent-to-User Interface)** is an open declarative protocol that solves this problem. Instead of sending executable code, the agent sends **declarative JSON descriptions of UI components**. The client receives this structured data and renders it natively using trusted UI widgets (Web Components, Lit, React, Flutter, or native mobile views).

```
┌─────────────────────────────────┐               ┌──────────────────────────────────┐
│      Gemini 3.8 Flash Agent     │               │        Client Application        │
│  (Cloud Run / Vertex AI Python) │               │   (Browser with Web Components)  │
└────────────────┬────────────────┘               └────────────────▲─────────────────┘
                 │                                                 │
                 │ 1. Declarative A2UI v0.9.1 JSON                 │ 2. Native Render
                 │    <a2ui-json>[ createSurface, ... ]            │    <a2ui-surface>
                 ▼                                                 │
   ┌───────────────────────────────────────────────────────────────┴──────────────────┐
   │                                TRUST BOUNDARY                                    │
   │  No executable JavaScript or arbitrary HTML — only structured, pre-approved data │
   └──────────────────────────────────────────────────────────────────────────────────┘
```

In this hands-on codelab, you will build an intelligent **Smart Home Telemetry Assistant**. You will start with a baseline text-only agent running Gemini on Vertex AI, deploy it early to Google Cloud Run, and then upgrade the backend using **A2UI v0.9.1** and the official **`a2ui-agent-sdk`**. Gemini will dynamically generate rich visual cards for sensor telemetry and device alerts while keeping general advice in plain text.

### What you'll learn

- The core concepts and trust-boundary security of the A2UI declarative protocol.
- How to connect a Python FastAPI backend to **Gemini 3.8 Flash** using the `google-genai` SDK on **Vertex AI**.
- How to equip Gemini with a **Tool** to inspect simulated smart home telemetry.
- How to deploy a containerized application to **Google Cloud Run**.
- How to use the official **`a2ui-agent-sdk`** and `A2uiSchemaManager` to generate standard A2UI v0.9.1 prompts programmatically instead of maintaining custom text blobs.
- How to embed an A2UI client renderer (`&lt;a2ui-surface&gt;`) into a web interface with **zero build steps** using browser ES modules.
- How to test queries like *"What needs my attention?"* to detect low batteries and display visual alert cards.

### Prerequisites

- Basic experience with terminal commands and Python.
- A Google Cloud Project with billing enabled.
- Access to Google Cloud Shell or a local machine with the Google Cloud SDK (`gcloud`) installed.

---

## Environment & Vertex AI Setup
Duration: 8

In this step, you will prepare your Google Cloud environment, enable the necessary Cloud APIs, configure IAM access for Vertex AI, and examine the starter repository.

### Launch Google Cloud Shell

Open the [Google Cloud Console](https://console.cloud.google.com/) in your browser, log in to your Google Cloud account, and click the **Activate Cloud Shell** button in the top right corner.

Cloud Shell provides a pre-configured Linux terminal with `gcloud`, `python3`, and `git` already installed.

### Set your Project ID and Region

In Cloud Shell, set your Google Cloud project and preferred region as shell environment variables:

```bash
# Set your active Google Cloud Project ID
export GOOGLE_CLOUD_PROJECT="$(gcloud config get-value project)"
export GOOGLE_CLOUD_REGION="us-central1"

echo "Project ID: ${GOOGLE_CLOUD_PROJECT}"
echo "Region:     ${GOOGLE_CLOUD_REGION}"
```

### Enable Required Google Cloud APIs

Enable the APIs for Cloud Run, Vertex AI, and Cloud Build:

```bash
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com
```

### Configure IAM Permissions for Vertex AI

When deploying to Google Cloud Run, your container runs by default under the **Compute Engine default service account**. Grant this service account the `roles/aiplatform.user` role so it can authenticate against Vertex AI via Application Default Credentials (ADC):

```bash
# Retrieve project number
PROJECT_NUMBER="$(gcloud projects describe ${GOOGLE_CLOUD_PROJECT} --format='value(projectNumber)')"

# Grant Vertex AI User role to the default service account
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

<aside class="positive">
<b>Tip:</b> Configuring IAM roles early ensures that your Cloud Run deployment can call Gemini on Vertex AI immediately upon deployment without authentication errors.
</aside>

### Clone and Inspect the Starter Repository

To focus directly on backend logic, Gemini prompting, and A2UI rendering, clone the pre-built starter repository which already includes the web frontend boilerplate (`index.html`, `styles.css`, `a2ui-bridge.js`), `Dockerfile`, and `sensors.py`:

```bash
git clone https://github.com/avedave/smart-home-a2ui-starter.git
cd smart-home-a2ui-starter
```

<aside class="negative">
<b>Note:</b> If you are already working directly in the project workspace, simply navigate to the workspace directory: <code>cd ~/projects/a2ui/ag</code>.
</aside>

### Install Dependencies

Set up a virtual environment and install the required dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The `requirements.txt` file includes:
- `fastapi==0.141.1`: Modern, lightweight asynchronous web framework.
- `uvicorn[standard]==0.54.0`: High-performance ASGI web server.
- `google-genai==2.25.0`: Google Gen AI SDK for Python with Vertex AI support.
- `a2ui-agent-sdk==0.6.0`: Official A2UI Python SDK providing `A2uiSchemaManager` and `BasicCatalog`.

### Inspect `sensors.py`

Open and view `sensors.py`. This module provides simulated telemetry from smart home sensors:

```python
SMART_HOME_SENSORS = {
    "climate": {
        "thermostat": {
            "name": "Living Room Thermostat",
            "current_temperature": 71,
            "target_temperature": 72,
            "humidity": 45,
            "mode": "heat",
            "battery_percent": 92,
            "status": "normal",
        },
    },
    "environmental": {
        "nursery_air_sensor": {
            "name": "Nursery Air Quality Monitor",
            "co2_ppm": 540,
            "voc_index": "Good",
            "humidity": 48,
            "battery_percent": 14,  # LOW BATTERY! Needs attention
            "status": "low_battery_warning",
        },
        "basement_water_sensor": {
            "name": "Basement Water Leak Detector",
            "moisture_detected": False,
            "battery_percent": 95,
            "status": "normal",
        },
    },
    "safety": {
        "hallway_smoke_detector": {
            "name": "Hallway Smoke & CO Alarm",
            "smoke_detected": False,
            "co_detected": False,
            "battery_percent": 11,  # CRITICALLY LOW BATTERY! Needs attention
            "status": "critical_battery",
        },
    },
    "security": {
        "front_door_lock": {
            "name": "Front Door Smart Lock",
            "state": "locked",
            "battery_percent": 88,
            "status": "normal",
        },
        "garage_door": {
            "name": "Garage Overhead Door",
            "state": "closed",
            "battery_percent": 90,
            "status": "normal",
        },
    },
    "lighting": {
        "living_room": {"name": "Living Room Ceiling", "state": "on", "brightness": 80},
        "kitchen": {"name": "Kitchen Pendant", "state": "off", "brightness": 0},
        "bedroom": {"name": "Bedroom Lamp", "state": "on", "brightness": 50},
    },
}

def get_sensor_report() -> Dict[str, Any]:
    """Retrieves a comprehensive status report from all smart home sensors."""
    return SMART_HOME_SENSORS
```

<aside class="positive">
<b>Key Scenario:</b> Notice the two battery conditions: the <b>Nursery Air Quality Monitor</b> is down to 14% (warning), and the <b>Hallway Smoke & CO Alarm</b> has dropped to a critical 11%. Later in this codelab, you will ask Gemini: <i>"What needs my attention?"</i> and see how A2UI highlights these urgent warnings.
</aside>

---

## Building the Baseline Text Agent
Duration: 10

Before introducing A2UI, you will create a baseline agent in `main.py` that interacts with Gemini 3.8 Flash on Vertex AI and returns traditional text-only responses.

### Author `main.py`

Create or edit `main.py` in your project root with the following implementation:

```python
import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import types

from sensors import get_sensor_report

app = FastAPI(title="Smart Home Assistant")

# Configure Vertex AI Gemini Client
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

BASELINE_SYSTEM_INSTRUCTION = """You are a helpful Smart Home Voice & Telemetry Assistant.
You monitor IoT home sensors: climate, indoor air quality, smoke detectors, security locks, and battery health.
You have access to the `get_sensor_report` tool to inspect real-time sensor data.
Provide helpful, friendly text answers to user questions."""

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None

class ChatResponse(BaseModel):
    text: str
    a2ui: Optional[Any] = None

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        contents = []
        if req.history:
            for msg in req.history:
                contents.append(types.Content(
                    role=msg.role,
                    parts=[types.Part.from_text(text=msg.content)]
                ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=req.message)]
        ))

        config = types.GenerateContentConfig(
            system_instruction=BASELINE_SYSTEM_INSTRUCTION,
            temperature=0.3,
            tools=[get_sensor_report],
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=contents,
            config=config,
        )

        return ChatResponse(text=response.text or "No response generated.", a2ui=None)
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sensors")
async def sensors_endpoint():
    """Returns raw sensor telemetry."""
    return get_sensor_report()

# Mount static frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Smart Home Telemetry API running."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
```

### Key Architectural Concepts in `main.py`

1. **Vertex AI Initialization:** The `genai.Client(vertexai=True, ...)` initializes the unified `google-genai` SDK using Google Cloud credentials.
2. **Function Calling (Tools):** We pass `tools=[get_sensor_report]` to `types.GenerateContentConfig`. When the user asks about the home, Gemini automatically calls `get_sensor_report()` to fetch the real-time sensor dictionary.
3. **Model Selection:** We use `gemini-3.8-flash`, offering low latency, cost efficiency, and strong reasoning capabilities for function calling.

### Test the Baseline Agent Locally

Start the local server:

```bash
uvicorn main:app --reload --port 8080
```

Click **Web Preview** in the top right of Cloud Shell and select **Preview on port 8080**.

Try two different prompts:

1. **Conversational Question:**
   - Prompt: *"What is a healthy indoor humidity?"*
   - Result: Gemini provides a helpful, friendly paragraph explaining that 30% to 50% relative humidity is ideal. This is a great user experience for text.

2. **Telemetry / Status Check:**
   - Prompt: *"Show all sensor readings"* or *"What is the status of my home?"*
   - Result: Gemini fetches the sensor dictionary and outputs a long list of bullet points or a wall of text.

<aside class="negative">
<b>The Text-Only UX Problem:</b> Notice the contrast. While text works well for explanations, scanning through paragraphs of bullet points to find which battery is dead or which alarm is triggering is slow, error-prone, and cumbersome. Users expect visual dashboards and status badges for IoT devices.
</aside>

Press `Ctrl+C` in your terminal to stop the local test server before proceeding.

---

## Deploying the Baseline to Cloud Run
Duration: 7

Deploying to Google Cloud Run early allows you to verify that containerization, Cloud Build, IAM service account permissions, and Vertex AI connectivity work end-to-end.

### Review the `Dockerfile`

The starter repository contains a production-ready `Dockerfile`:

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Deploy to Cloud Run

Run `gcloud run deploy` to build and deploy your container from source:

```bash
gcloud run deploy smart-home-a2ui \
  --source . \
  --region "${GOOGLE_CLOUD_REGION}" \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}",GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION}"
```

When prompted to confirm the service name or creation, press **Enter**.

Google Cloud Build will package the container, upload it to Artifact Registry, and launch a Cloud Run service.

Once the command completes, you will see a service URL in your terminal:
```
Service [smart-home-a2ui] revision [smart-home-a2ui-00001-xxx] has been deployed and is serving 100 percent of traffic.
Service URL: https://smart-home-a2ui-xxxxxx-uc.a.run.app
```

Open the **Service URL** in your browser. You now have a live, cloud-hosted smart home agent running on Cloud Run!

---

## Understanding A2UI v0.9.1 & The Client Renderer
Duration: 8

Now that the baseline agent is running in the cloud, let's explore how **A2UI v0.9.1** bridges the gap between text chat and rich graphical user interfaces without compromising security.

### Declarative UI vs. Executable Code

Why not have Gemini generate raw HTML or React code?
- **Security Vulnerability:** Models generating raw HTML/JS can introduce Cross-Site Scripting (XSS), script injection, or bypass client-side security policies.
- **Fragile Styling:** Raw HTML code generated by an LLM frequently clashes with the host application's theme, layout, and responsiveness.
- **Lack of Governance:** The client application has no control over what elements the model creates.

**A2UI v0.9.1 solves this with a prompt-first, declarative message protocol.** Instead of arbitrary code, the server streams structured JSON messages:

1. **`createSurface`**: Signals the client to initialize a rendering surface.
2. **`updateComponents`**: Sends a flat array of component definitions (with ID references for parent-child hierarchies).
3. **`updateDataModel`**: Updates or populates dynamic data bindings separately from the UI structure.

Here is an example A2UI v0.9.1 message payload:

```json
[
  {
    "createSurface": {
      "surfaceId": "smoke-alarm-alert",
      "catalogId": "https://a2ui.org/specification/v0_9_1/catalogs/basic/catalog.json"
    }
  },
  {
    "updateComponents": {
      "surfaceId": "smoke-alarm-alert",
      "components": [
        {
          "id": "root",
          "component": "Card",
          "child": "content-col"
        },
        {
          "id": "content-col",
          "component": "Column",
          "children": ["title-text", "status-text"]
        },
        {
          "id": "title-text",
          "component": "Text",
          "text": "Hallway Smoke & CO Alarm",
          "variant": "h2"
        },
        {
          "id": "status-text",
          "component": "Text",
          "text": "Battery: 11% (CRITICAL)",
          "variant": "caption"
        }
      ]
    }
  }
]
```

The client receives this JSON and maps it to pre-vetted, styled components. No code is executed; only pre-approved components from the catalog are rendered!

### The Standard 18 Primitives (`BasicCatalog`)

A2UI v0.9.1 provides 18 standard primitives organized into four categories:

| Category | Primitives |
| :--- | :--- |
| **Layout** | `Card`, `Column`, `Row`, `List`, `Tabs`, `Divider`, `Modal` |
| **Display** | `Text`, `Image`, `Icon`, `Video`, `AudioPlayer` |
| **Input** | `TextField`, `CheckBox`, `ChoicePicker`, `Slider`, `DateTimeInput` |
| **Action** | `Button` |

### The Two-Tier Web Architecture

According to the official [A2UI Client Setup Guide](https://github.com/a2ui-project/a2ui/blob/main/docs/public/guides/client-setup.md), web frontends for A2UI are built on two distinct layers:

```
┌────────────────────────────────────────────────────────┐
│               Agent (Python / Gemini)                 │
│         Emits A2UI v0.9 Protocol Messages              │
└───────────────────────────┬────────────────────────────┘
                            │ (JSON stream)
┌───────────────────────────▼────────────────────────────┐
│         Shared Foundation: @a2ui/web_core              │
│  • MessageProcessor (processes stream & envelopes)     │
│  • SurfaceModel, ComponentModel, DataModel             │
│  • Reactive signals & data path binding ({"path": ..}) │
│  • Action dispatching (userAction envelopes)           │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
┌───────────────▼────────┐      ┌────────▼───────────────┐
│     @a2ui/lit          │      │  @a2ui/react / Angular │
│  • <a2ui-surface>      │      │  • React hooks / ctx   │
│  • basicCatalog (v0.9) │      │  • Angular service     │
└────────────────────────┘      └────────────────────────┘
```

1. **Shared Foundation (`@a2ui/web_core`)**:
   Provides the `MessageProcessor` that parses the stream of protocol messages (`createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`), builds the reactive `SurfaceModel`, and manages decoupled data bindings.
2. **Framework Presentation (`@a2ui/lit`, `@a2ui/react`, `@a2ui/angular`)**:
   Provides pre-styled, accessible UI components. For Web Components, `@a2ui/lit` registers the official `&lt;a2ui-surface&gt;` custom element and provides the standard `basicCatalog` containing all 18 primitives.

### The A2UI Client Bridge (`static/a2ui-bridge.js`)

In `static/a2ui-bridge.js`, we import the official `@a2ui/web_core` and `@a2ui/lit` packages directly in the browser via modern ESM without requiring any Node.js, `npm`, or Vite build step:

```javascript
import { MessageProcessor, injectBasicCatalogStyles } from 'https://esm.sh/@a2ui/web_core@0.11.0/v0_9';
import { basicCatalog } from 'https://esm.sh/@a2ui/lit@0.11.0/v0_9';

// Initialize the official A2UI MessageProcessor with the basic catalog
const processor = new MessageProcessor([basicCatalog]);
injectBasicCatalogStyles(document);

export async function renderA2UIMessages(container, messages) {
  // Feed incoming A2UI envelopes into the MessageProcessor
  processor.processMessages(messages);

  const surface = processor.model.surfacesMap.get('attention-dashboard');
  if (surface) {
    const surfaceEl = document.createElement('a2ui-surface');
    // Bind the reactive SurfaceModel to the official Lit custom element
    surfaceEl.surface = surface;
    container.appendChild(surfaceEl);
    await surfaceEl.updateComplete;
    return surfaceEl;
  }
}
```

The bridge also includes a resilient offline fallback so the application continues to render cleanly even in air-gapped or offline environments.

### Client Chat Integration (`static/index.html`)

When the user submits a message, `static/index.html` calls `/api/chat`. If the response contains an `a2ui` surface payload, it calls `window.renderA2UIMessages` to mount the official `&lt;a2ui-surface&gt;`:

```javascript
if (a2uiSurfaceData) {
  const surfaceContainer = document.createElement('div');
  surfaceContainer.className = 'surface-wrapper';
  bubble.appendChild(surfaceContainer);

  if (typeof window.renderA2UIMessages === 'function') {
    window.renderA2UIMessages(surfaceContainer, a2uiSurfaceData).then(() => {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    });
  }
}
```

Now let's teach Gemini how to generate this A2UI v0.9.1 JSON using `a2ui-agent-sdk`!

---

## Upgrading the Agent with A2UI & A2uiSchemaManager
Duration: 12

Instead of authoring a custom, hand-crafted system prompt ("blob of text"), we will use the official **`a2ui-agent-sdk`** package and its `A2uiSchemaManager`.

### Why use `A2uiSchemaManager`?

1. **Prompt-First Schema Generation:** Automatically generates the complete A2UI v0.9.1 JSON Schema, component catalog definitions, and few-shot examples for Gemini.
2. **Clean Developer API:** You only provide three domain-specific descriptions:
   - `role_description`: Persona and available tools.
   - `workflow_description`: When to respond in plain text vs when to emit A2UI JSON.
   - `ui_description`: Design heuristics (e.g. Cards for alerts, Columns for layout).
3. **Standards Compliant:** Automatically enforces the official `<a2ui-json> ... </a2ui-json>` protocol tags and top-down component ordering.

### Updating `main.py`

Open `main.py` and update it to use `A2uiSchemaManager`:

```python
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import types

# Import official A2UI v0.9.1 tools from a2ui-agent-sdk
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from sensors import get_sensor_report

app = FastAPI(title="Smart Home Assistant (A2UI v0.9.1)")

# Configure Vertex AI Gemini Client
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

# Initialize A2UI v0.9.1 Schema Manager with BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.9.1",
    catalogs=[BasicCatalog.get_config("0.9.1")],
)

# Generate the complete system instruction programmatically
A2UI_SYSTEM_INSTRUCTION = schema_manager.generate_system_prompt(
    role_description=(
        "You are an intelligent Smart Home Voice & Telemetry Assistant. "
        "You monitor IoT home sensors: climate, indoor air quality, smoke detectors, "
        "security locks, and battery health. "
        "You have access to the `get_sensor_report` tool to inspect real-time sensor data."
    ),
    workflow_description=(
        "DECISION RULE FOR OUTPUT FORMAT:\n\n"
        "1. TEXT-ONLY RESPONSE:\n"
        "   When the user asks conversational questions, general knowledge, explanations, "
        "recommendations, or troubleshooting (e.g., 'What humidity is ideal for sleep?', "
        "'How can I conserve energy with smart thermostats?'):\n"
        "   -> Respond ONLY in friendly, clear markdown text. Do NOT emit any <a2ui-json> blocks.\n\n"
        "2. A2UI GENERATIVE UI RESPONSE:\n"
        "   When the user asks to inspect sensors, check device status, review dashboards, "
        "or ask 'What needs my attention?':\n"
        "   -> First provide a short friendly text summary (1-2 sentences). Specifically highlight if any "
        "device has a critically low battery.\n"
        "   -> THEN append an A2UI v0.9.1 JSON payload enclosed strictly in `<a2ui-json> ... </a2ui-json>`.\n"
        "   The JSON must be a list containing a `createSurface` message followed by an `updateComponents` message "
        "defining the visual cards for the devices."
    ),
    ui_description=(
        "Design guidelines for A2UI v0.9.1:\n"
        "- Use `Card` components for each device or alert grouping.\n"
        "- Use `Row` and `Column` components to structure layout.\n"
        "- For `Row`, use camelCase for `justify` (e.g. 'spaceBetween', 'center', 'start', 'end').\n"
        "- Use `Text` with variant ('h1', 'h2', 'body', 'caption') for titles and descriptions.\n"
        "- For devices with low batteries (especially the Hallway Smoke Alarm at 11% and Nursery Monitor at 14%), "
        "generate prominent alert cards."
    ),
    include_schema=True,
    include_examples=True,
)

def parse_a2ui_response(raw_text: str) -> Tuple[str, Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]]:
    """Extracts conversational text and optional A2UI v0.9.1 payload from model response."""
    a2ui_match = re.search(r"<a2ui-json>\s*([\s\S]*?)\s*</a2ui-json>", raw_text)
    if not a2ui_match:
        a2ui_match = re.search(r"```(?:a2ui|json)\s*\n([\s\S]*?)\n```", raw_text)

    if a2ui_match:
        json_content = a2ui_match.group(1).strip()
        text_before = raw_text[:a2ui_match.start()].strip()
        text_after = raw_text[a2ui_match.end():].strip()
        cleaned_text = f"{text_before} {text_after}".strip()

        try:
            surface_data = json.loads(json_content)
            return cleaned_text, surface_data
        except json.JSONDecodeError:
            pass

    return raw_text.strip(), None
```

### Test the Upgraded Agent Locally

Run the application:

```bash
uvicorn main:app --reload --port 8080
```

Open Web Preview on port 8080 and test the following queries:

#### 1. Conversational Question
- Click the chip or type: **"What is a healthy indoor humidity?"**
- **Observation:** Notice that Gemini returns pure conversational text. It does not output any unnecessary UI cards. The interface stays clean and lightweight!

#### 2. Attention & Low Battery Query
- Click the chip or type: **"What needs my attention?"**
- **Observation:** Gemini calls `get_sensor_report()`, analyzes the telemetry, and identifies that:
  - The **Hallway Smoke & CO Alarm** has a critically low battery (11%).
  - The **Nursery Air Quality Monitor** has a low battery warning (14%).
- The assistant emits `<a2ui-json>` with `createSurface` and `updateComponents` defining structured **Alert Cards** featuring prominent critical and warning badges!

#### 3. Full Sensor Dashboard
- Click the chip or type: **"Show all sensor readings"**
- **Observation:** The assistant generates a full multi-device report with categorized cards for Climate, Safety & Air Quality, and Security locks.

### Redeploy the Upgraded Application to Cloud Run

Deploy the updated application to your live Cloud Run service:

```bash
gcloud run deploy smart-home-a2ui \
  --source . \
  --region "${GOOGLE_CLOUD_REGION}" \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}",GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION}"
```

Visit your public Cloud Run URL. Your cloud-deployed agent is now powered by official A2UI v0.9.1!

---

## Congratulations & Clean Up
Duration: 3

### What You Built and Learned

Congratulations! You have successfully built and deployed an interactive, agent-driven smart home telemetry application using **A2UI v0.9.1**, **`a2ui-agent-sdk`**, **Gemini 3.8 Flash** on **Vertex AI**, and **Google Cloud Run**.

Here is a summary of what you accomplished:

1. **A2UI v0.9.1 Specification:** Learned the prompt-first architecture, `createSurface`, `updateComponents`, and standard primitives in `BasicCatalog`.
2. **Schema-Driven System Prompts:** Used `A2uiSchemaManager.generate_system_prompt()` from `a2ui-agent-sdk` to programmatically generate prompts instead of maintaining custom text blobs.
3. **Function Calling with Vertex AI:** Integrated the `google-genai` Python SDK with `gemini-3.8-flash` on Vertex AI to inspect live IoT sensor telemetry.
4. **Attention Detection:** Built an experience where prompts like *"What needs my attention?"* surface actionable warning cards for low-battery devices.
5. **Zero-Build Web Component Rendering:** Embedded `&lt;a2ui-surface&gt;` into the chat client using modern browser ES modules with zero build steps or bundlers.
6. **Serverless Cloud Deployment:** Deployed the solution to Google Cloud Run with IAM service account permissions configured for Vertex AI.

### Clean Up Resources

To avoid incurring ongoing Google Cloud charges for Cloud Run and Artifact Registry container images, delete the deployed service:

```bash
# Delete the Cloud Run service
gcloud run services delete smart-home-a2ui \
  --region "${GOOGLE_CLOUD_REGION}" \
  --quiet
```

### Next Steps & Resources

- Explore the official [A2UI Project Repository](https://github.com/a2ui-project/a2ui) for specifications, Lit/React renderers, and standard component catalogs.
- Read the [A2UI v0.9.1 Specification](https://raw.githubusercontent.com/a2ui-project/a2ui/main/docs/public/specification/v0.9.1-a2ui.md).
- Read the [Gemini on Vertex AI Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/overview) to explore function calling, multimodal inputs, and streaming responses.
- Check out [Google Cloud Run Documentation](https://cloud.google.com/run/docs) for scaling, custom domains, and concurrency optimizations.
