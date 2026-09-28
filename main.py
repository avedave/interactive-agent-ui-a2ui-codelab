import json
import os
import re
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import types

# A2UI v0.9.1 Schema Manager from the official a2ui-agent-sdk
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from sensors import get_sensor_report

warnings.filterwarnings("ignore", category=DeprecationWarning)

app = FastAPI(title="Smart Home Assistant (A2UI v0.9.1)")

# Configure Vertex AI Gemini Client
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

try:
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )
except Exception as e:
    print(f"Notice: Vertex AI client offline or ADC not found ({e}). Running with smart home fallback surfaces.")
    client = None

# Initialize A2UI v0.9.1 Schema Manager with the official BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.9.1",
    catalogs=[BasicCatalog.get_config("0.9.1")],
)

# Programmatically generate the complete A2UI v0.9.1 system prompt
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
        "'How can I conserve energy with smart thermostats?', 'What does high CO2 mean?'):\n"
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

# Helper functions to build standard A2UI v0.9.1 declarative message envelopes
def build_attention_a2ui_surface(sensor_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Builds A2UI v0.9.1 messages highlighting devices requiring attention."""
    smoke = sensor_data["safety"]["hallway_smoke_detector"]
    nursery = sensor_data["environmental"]["nursery_air_sensor"]

    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["header-row", "smoke-card", "air-card"]
        },
        {
            "id": "header-row",
            "component": "Row",
            "justify": "spaceBetween",
            "children": ["header-title", "header-badge"]
        },
        {
            "id": "header-title",
            "component": "Text",
            "text": "⚠️ Devices Requiring Attention",
            "variant": "h1"
        },
        {
            "id": "header-badge",
            "component": "Text",
            "text": "2 Critical Alerts",
            "variant": "caption"
        },
        # Smoke Alarm Alert Card
        {
            "id": "smoke-card",
            "component": "Card",
            "child": "smoke-col"
        },
        {
            "id": "smoke-col",
            "component": "Column",
            "children": ["smoke-header", "smoke-desc"]
        },
        {
            "id": "smoke-header",
            "component": "Row",
            "justify": "spaceBetween",
            "children": ["smoke-title", "smoke-badge"]
        },
        {
            "id": "smoke-title",
            "component": "Text",
            "text": f"🚨 {smoke['name']}",
            "variant": "h2"
        },
        {
            "id": "smoke-badge",
            "component": "Text",
            "text": f"Battery: {smoke['battery_percent']}% (CRITICAL)",
            "variant": "caption"
        },
        {
            "id": "smoke-desc",
            "component": "Text",
            "text": "Critical battery level. Replace the 9V backup battery immediately to ensure continuous smoke and CO detection.",
            "variant": "body"
        },
        # Nursery Air Monitor Alert Card
        {
            "id": "air-card",
            "component": "Card",
            "child": "air-col"
        },
        {
            "id": "air-col",
            "component": "Column",
            "children": ["air-header", "air-desc"]
        },
        {
            "id": "air-header",
            "component": "Row",
            "justify": "spaceBetween",
            "children": ["air-title", "air-badge"]
        },
        {
            "id": "air-title",
            "component": "Text",
            "text": f"🍃 {nursery['name']}",
            "variant": "h2"
        },
        {
            "id": "air-badge",
            "component": "Text",
            "text": f"Battery: {nursery['battery_percent']}% (LOW)",
            "variant": "caption"
        },
        {
            "id": "air-desc",
            "component": "Text",
            "text": "Low battery warning. Recharge or replace AA batteries soon to maintain nursery air quality tracking.",
            "variant": "body"
        },
    ]

    return [
        {
            "createSurface": {
                "surfaceId": "attention-dashboard",
                "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
            }
        },
        {
            "updateComponents": {
                "surfaceId": "attention-dashboard",
                "components": components
            }
        }
    ]

def build_full_dashboard_a2ui_surface(sensor_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Builds comprehensive A2UI v0.9.1 messages for all sensors."""
    climate = sensor_data["climate"]["thermostat"]
    smoke = sensor_data["safety"]["hallway_smoke_detector"]
    nursery = sensor_data["environmental"]["nursery_air_sensor"]
    lock = sensor_data["security"]["front_door_lock"]

    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["header-row", "climate-card", "safety-card", "security-card"]
        },
        {
            "id": "header-row",
            "component": "Row",
            "justify": "spaceBetween",
            "children": ["header-title", "header-badge"]
        },
        {
            "id": "header-title",
            "component": "Text",
            "text": "🏠 Smart Home Sensor Report",
            "variant": "h1"
        },
        {
            "id": "header-badge",
            "component": "Text",
            "text": "Online Telemetry",
            "variant": "caption"
        },
        # Climate Card
        {
            "id": "climate-card",
            "component": "Card",
            "child": "climate-col"
        },
        {
            "id": "climate-col",
            "component": "Column",
            "children": ["climate-title", "climate-details"]
        },
        {
            "id": "climate-title",
            "component": "Text",
            "text": f"🌡️ {climate['name']}",
            "variant": "h2"
        },
        {
            "id": "climate-details",
            "component": "Text",
            "text": f"Current: {climate['current_temperature']}°F  |  Target: {climate['target_temperature']}°F  |  Humidity: {climate['humidity']}% (Battery: {climate['battery_percent']}%)",
            "variant": "body"
        },
        # Safety & Air Card
        {
            "id": "safety-card",
            "component": "Card",
            "child": "safety-col"
        },
        {
            "id": "safety-col",
            "component": "Column",
            "children": ["safety-title", "smoke-row", "air-row"]
        },
        {
            "id": "safety-title",
            "component": "Text",
            "text": "🛡️ Safety & Air Quality",
            "variant": "h2"
        },
        {
            "id": "smoke-row",
            "component": "Row",
            "justify": "spaceBetween",
            "children": ["smoke-txt", "smoke-b"]
        },
        {
            "id": "smoke-txt",
            "component": "Text",
            "text": f"{smoke['name']}: No Smoke/CO Detected",
            "variant": "body"
        },
        {
            "id": "smoke-b",
            "component": "Text",
            "text": f"Battery: {smoke['battery_percent']}%",
            "variant": "caption"
        },
        {
            "id": "air-row",
            "component": "Row",
            "justify": "spaceBetween",
            "children": ["air-txt", "air-b"]
        },
        {
            "id": "air-txt",
            "component": "Text",
            "text": f"{nursery['name']}: CO2 {nursery['co2_ppm']} ppm ({nursery['voc_index']})",
            "variant": "body"
        },
        {
            "id": "air-b",
            "component": "Text",
            "text": f"Battery: {nursery['battery_percent']}%",
            "variant": "caption"
        },
        # Security Card
        {
            "id": "security-card",
            "component": "Card",
            "child": "sec-col"
        },
        {
            "id": "sec-col",
            "component": "Column",
            "children": ["sec-title", "sec-details"]
        },
        {
            "id": "sec-title",
            "component": "Text",
            "text": "🔒 Security & Access",
            "variant": "h2"
        },
        {
            "id": "sec-details",
            "component": "Text",
            "text": f"{lock['name']}: {lock['state'].upper()} (Battery: {lock['battery_percent']}%)",
            "variant": "body"
        }
    ]

    return [
        {
            "createSurface": {
                "surfaceId": "full-dashboard",
                "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
            }
        },
        {
            "updateComponents": {
                "surfaceId": "full-dashboard",
                "components": components
            }
        }
    ]

def parse_a2ui_response(raw_text: str) -> Tuple[str, Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]]:
    """Extracts conversational text and optional A2UI v0.9.1 payload from model response."""
    # Check for official <a2ui-json> tags
    a2ui_match = re.search(r"<a2ui-json>\s*([\s\S]*?)\s*</a2ui-json>", raw_text)
    if not a2ui_match:
        # Fallback to standard code blocks
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

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None

class ChatResponse(BaseModel):
    text: str
    a2ui: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None

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
            system_instruction=A2UI_SYSTEM_INSTRUCTION,
            temperature=0.3,
            tools=[get_sensor_report],
        )

        if client:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=contents,
                config=config,
            )
            raw_output = response.text or ""
            text_part, a2ui_payload = parse_a2ui_response(raw_output)
        else:
            raw_output = ""
            text_part, a2ui_payload = None, None

        # Fallback helper: Ensure rich A2UI is delivered for key dashboard & attention queries
        low_msg = req.message.lower()
        sensor_data = get_sensor_report()
        if not a2ui_payload:
            if "attention" in low_msg or "battery" in low_msg or "problem" in low_msg:
                a2ui_payload = build_attention_a2ui_surface(sensor_data)
            elif any(k in low_msg for k in ["sensor", "status", "dashboard", "report", "devices"]) and not any(q in low_msg for q in ["what is", "how do", "why"]):
                a2ui_payload = build_full_dashboard_a2ui_surface(sensor_data)

        return ChatResponse(text=text_part or "Sensor analysis complete.", a2ui=a2ui_payload)
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        # When running in environments without ADC credentials, return fallback A2UI surfaces
        low_msg = req.message.lower()
        sensor_data = get_sensor_report()
        if "attention" in low_msg or "battery" in low_msg or "problem" in low_msg:
            return ChatResponse(
                text="I checked your smart home sensors and detected two critical battery warnings.",
                a2ui=build_attention_a2ui_surface(sensor_data)
            )
        elif any(k in low_msg for k in ["sensor", "status", "dashboard", "report", "devices"]):
            return ChatResponse(
                text="Here is your live smart home telemetry report.",
                a2ui=build_full_dashboard_a2ui_surface(sensor_data)
            )
        elif "humidity" in low_msg:
            return ChatResponse(
                text="Healthy indoor humidity is generally recommended to be between 30% and 50%. This prevents mold growth while keeping nasal passages and skin comfortable.",
                a2ui=None
            )
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
