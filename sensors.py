"""
Smart Home Sensor & Telemetry Module
Provides simulated real-time data from home IoT sensors and devices.
"""

from typing import Any, Dict

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
    """Retrieves a comprehensive status report from all smart home sensors.
    Includes climate, indoor air quality, safety alarms, security locks, and battery levels.
    """
    return SMART_HOME_SENSORS
