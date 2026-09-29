import httpx

from app.models.weather import WeatherSnapshot

# Go/No-Go thresholds (simple, deterministic, judge-explainable)
WIND_MAX_KPH = 55.0
VIS_MIN_M = 1000.0
TEMP_MIN_C = -45.0
SEVERE_CONDITIONS = {"THUNDERSTORM", "SEVERE", "STORM", "BLIZZARD"}


def wmo_to_condition(code: int) -> str:
    if code == 0:
        return "CLEAR"
    if code in (1, 2, 3):
        return "CLOUDY"
    if code in (45, 48):
        return "FOG"
    if code in (51, 53, 55, 56, 57):
        return "DRIZZLE"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "RAIN"
    if code in (71, 73, 75, 77, 85, 86):
        return "SNOW"
    if code in (95,):
        return "THUNDERSTORM"
    if code in (96, 99):
        return "SEVERE"
    return "UNKNOWN"


def evaluate_weather(snap: WeatherSnapshot) -> tuple[bool, str]:
    """Threshold rules: wind above max, visibility below min, extreme cold, or severe condition = fail."""
    reasons: list[str] = []
    if (snap.wind_kph or 0) > WIND_MAX_KPH:
        reasons.append(f"wind {snap.wind_kph:.0f} kph > {WIND_MAX_KPH:.0f}")
    if snap.visibility_m is not None and snap.visibility_m < VIS_MIN_M:
        reasons.append(f"visibility {snap.visibility_m:.0f} m < {VIS_MIN_M:.0f}")
    if (snap.temp_c or 0) < TEMP_MIN_C:
        reasons.append(f"temp {snap.temp_c:.0f}°C < {TEMP_MIN_C:.0f}")
    if (snap.condition or "").upper() in SEVERE_CONDITIONS:
        reasons.append(f"condition {snap.condition}")
    if reasons:
        return False, "NO-GO: " + "; ".join(reasons)
    return True, f"GO: {snap.condition} {snap.temp_c:.1f}°C wind {snap.wind_kph:.0f} kph"


def fetch_live(latitude: float, longitude: float, timeout_s: float = 15.0) -> dict:
    """Open-Meteo, no API key. Returns temp_c, wind_kph, visibility_m, condition."""
    r = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "hourly": "visibility",
            "timezone": "UTC",
        },
        timeout=timeout_s,
    )
    r.raise_for_status()
    body = r.json()
    current = body.get("current") or {}
    vis_list = (body.get("hourly") or {}).get("visibility") or []
    return {
        "temp_c": float(current.get("temperature_2m", 0.0)),
        "wind_kph": float(current.get("wind_speed_10m", 0.0)),
        "visibility_m": float(vis_list[0]) if vis_list else None,
        "condition": wmo_to_condition(int(current.get("weather_code", -1))),
    }
