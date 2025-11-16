# server/main.py
import os, io, json, base64
from typing import List, Dict, Any, Optional, Tuple

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import numpy as np
import requests

# ---------- FastAPI ----------
app = FastAPI(title="Resistor Reader – Gemini only (hardened)", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # open during LAN testing
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Color code tables ----------
COLOR_CODE = {
    "black":  {"digit":0, "multiplier":1e0},
    "brown":  {"digit":1, "multiplier":1e1, "tolerance":1.0},
    "red":    {"digit":2, "multiplier":1e2, "tolerance":2.0},
    "orange": {"digit":3, "multiplier":1e3},
    "yellow": {"digit":4, "multiplier":1e4},
    "green":  {"digit":5, "multiplier":1e5, "tolerance":0.5},
    "blue":   {"digit":6, "multiplier":1e6, "tolerance":0.25},
    "violet": {"digit":7, "multiplier":1e7, "tolerance":0.1},
    "grey":   {"digit":8, "multiplier":1e8, "tolerance":0.05},
    "white":  {"digit":9, "multiplier":1e9},
    "gold":   {"multiplier":1e-1, "tolerance":5.0},
    "silver": {"multiplier":1e-2, "tolerance":10.0},
}
TOL_COLORS = {"brown","red","green","blue","violet","grey","gold","silver"}

# Normalize Gemini’s wording
ALIASES = {
    "gray":"grey", "purple":"violet", "golden":"gold", "silver color":"silver",
    "orange-brown":"orange", "reddish":"red", "brownish":"brown",
}
def norm_color(name: str) -> str:
    c = (name or "").strip().lower()
    return ALIASES.get(c, c)

# E24 snapping
E24 = np.array([10,11,12,13,15,16,18,20,22,24,27,30,33,36,39,43,47,51,56,62,68,75,82,91], dtype=float)
def snap_e24(v: Optional[float]) -> Optional[float]:
    if v is None or v <= 0: return v
    decade = 10 ** np.floor(np.log10(v))
    norm = v / decade * 10
    idx = int(np.argmin(np.abs(E24 - norm)))
    return float((E24[idx]/10.0) * decade)

def compute_value_from_colors(colors: List[str]) -> Tuple[Optional[float], Optional[float]]:
    n = len(colors); tol = None; value = None
    if n == 4:
        d1 = COLOR_CODE.get(colors[0],{}).get("digit")
        d2 = COLOR_CODE.get(colors[1],{}).get("digit")
        mult = COLOR_CODE.get(colors[2],{}).get("multiplier")
        tol  = COLOR_CODE.get(colors[3],{}).get("tolerance")
        if None not in (d1,d2) and mult is not None: value = (d1*10 + d2)*mult
    elif n == 5:
        d1 = COLOR_CODE.get(colors[0],{}).get("digit")
        d2 = COLOR_CODE.get(colors[1],{}).get("digit")
        d3 = COLOR_CODE.get(colors[2],{}).get("digit")
        mult = COLOR_CODE.get(colors[3],{}).get("multiplier")
        tol  = COLOR_CODE.get(colors[4],{}).get("tolerance")
        if None not in (d1,d2,d3) and mult is not None: value = (d1*100 + d2*10 + d3)*mult
    elif n == 3:  # salvage
        d1 = COLOR_CODE.get(colors[0],{}).get("digit")
        d2 = COLOR_CODE.get(colors[1],{}).get("digit")
        mult = COLOR_CODE.get(colors[2],{}).get("multiplier")
        if None not in (d1,d2) and mult is not None: value = (d1*10 + d2)*mult
    elif n >= 6: # ignore tempco
        d1 = COLOR_CODE.get(colors[0],{}).get("digit")
        d2 = COLOR_CODE.get(colors[1],{}).get("digit")
        d3 = COLOR_CODE.get(colors[2],{}).get("digit")
        mult = COLOR_CODE.get(colors[3],{}).get("multiplier")
        tol  = COLOR_CODE.get(colors[4],{}).get("tolerance")
        if None not in (d1,d2,d3) and mult is not None: value = (d1*100 + d2*10 + d3)*mult
    return (float(value) if value is not None else None), tol

def human(v: Optional[float]) -> Optional[str]:
    if v is None: return None
    for name, scale in [("GΩ",1e9),("MΩ",1e6),("kΩ",1e3),("Ω",1.0)]:
        if v >= scale: return f"{v/scale:.2f} {name}"
    return f"{v:.2f} Ω"

# ---------- Image helpers ----------
def pil_to_part(img: Image.Image) -> Dict[str, Any]:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return {"mime_type":"image/jpeg","data":buf.read()}

def resize_max(img: Image.Image, max_side=1024) -> Image.Image:
    w,h = img.size; s = max(w,h)
    if s <= max_side: return img
    r = max_side/float(s)
    return img.resize((int(w*r), int(h*r)), Image.Resampling.LANCZOS)

# ---------- Schema for structured JSON ----------
SCHEMA = {
  "type":"object",
  "properties":{
    "bands":{"type":"array","items":{"type":"object","properties":{
        "index":{"type":"integer"},
        "color_name":{"type":"string"},
        "role":{"type":"string","enum":["digit","multiplier","tolerance","tempco"]},
        "confidence":{"type":"number"}
    },"required":["index","color_name","role","confidence"]}},
    "band_scheme":{"type":"string","enum":["3-band","4-band","5-band","6-band"]}
  },
  "required":["bands"]
}

# ---------- Gemini wrappers (SDK + REST fallback) ----------
def _sdk_generate(parts: List[Any]) -> Optional[str]:
    """
    Try multiple model ids via google-generativeai SDK.
    Returns the model's text (string) or None if all fail.
    """
    try:
        import google.generativeai as genai
    except Exception:
        return None

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    # Force REST transport (more reliable across environments)
    try:
        genai.configure(api_key=api_key, transport="rest")
    except Exception:
        genai.configure(api_key=api_key)

    candidates = [
        os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        "models/gemini-2.5-flash",
        "gemini-2.5-pro",
        "models/gemini-2.5-pro",
        "gemini-2.0-flash",
        "models/gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "models/gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "models/gemini-1.5-flash",
        "gemini-1.5-pro",
        "models/gemini-1.5-pro",
        "gemini-1.5-flash-8b",
        "models/gemini-1.5-flash-8b",
        "gemini-1.0-pro-vision",
        "models/gemini-1.0-pro-vision",
    ]


    generation_config = {
        "temperature": 0.2,
        "response_mime_type": "application/json",
        "response_schema": SCHEMA,
    }

    for name in candidates:
        try:
            model = genai.GenerativeModel(name, generation_config=generation_config)
            out = model.generate_content(parts)
            return (out.text or "").strip()
        except Exception:
            continue
    return None

def _rest_generate(parts: List[Any]) -> Optional[str]:
    """
    Raw REST fallback (v1). Returns text or None.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    def to_rest_content(p):
        if isinstance(p, dict) and "mime_type" in p and "data" in p:
            return {"parts":[{"inline_data":{
                "mime_type": p["mime_type"],
                "data": base64.b64encode(p["data"]).decode()
            }}]}
        else:
            return {"parts":[{"text": str(p)}]}

    rest_candidates = [
        os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash-8b",
        "gemini-1.0-pro-vision",
    ]


    payload = {"contents":[to_rest_content(p) for p in parts]}
    for model in rest_candidates:
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
            r = requests.post(url, json=payload, timeout=40)
            if r.status_code != 200:
                continue
            js = r.json()
            txt = js.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return (txt or "").strip()
        except Exception:
            continue
    return None

def gemini_read_bands(img: Image.Image) -> Tuple[Optional[List[str]], Optional[Dict[str,Any]], Optional[str]]:
    """
    Returns (colors, raw_json, used_backend) where used_backend in {"sdk","rest"}.
    colors is a list of normalized color names (lowercase).
    """
    img = resize_max(img, 1024)
    sys = ("You read resistor color bands from images. "
           "Return strict JSON matching the schema. "
           "Use standard color names: black, brown, red, orange, yellow, green, blue, violet, grey, white, gold, silver. "
           "Read bands left-to-right; if a tolerance band exists, it is typically on the right.")
    user = "Identify bands, roles, and confidence. JSON only."

    parts = [sys, user, pil_to_part(img)]

    # 1) SDK path
    txt = _sdk_generate(parts)
    used = None
    if not txt:
        # 2) REST fallback
        txt = _rest_generate(parts)
        used = "rest"
    else:
        used = "sdk"

    if not txt:
        return None, None, None

    # Extract JSON from text
    try:
        start, end = txt.find("{"), txt.rfind("}")
        payload = txt[start:end+1] if (start != -1 and end != -1) else txt
        js = json.loads(payload)
    except Exception:
        return None, None, used

    triples = [b for b in js.get("bands",[]) if b.get("role") in ("digit","multiplier","tolerance")]
    triples.sort(key=lambda b: int(b.get("index",0)))
    colors = [norm_color(b.get("color_name","")) for b in triples]
    return colors, js, used

# ---------- API schema ----------
class AnalyzeResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
    colors: Optional[List[str]] = None
    value_ohms: Optional[float] = None
    value_display: Optional[str] = None
    tolerance_pct: Optional[float] = None
    snapped_ohms: Optional[float] = None
    snapped_display: Optional[str] = None
    used: Optional[str] = None   # "gemini_only/sdk", "gemini_only/rest"
    gemini: Optional[Dict[str,Any]] = None

# ---------- Endpoint ----------
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    data = await file.read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return AnalyzeResponse(ok=False, message="Invalid image")

    colors, raw, used_backend = gemini_read_bands(img)
    if not colors:
        return AnalyzeResponse(ok=False, message="Gemini could not read bands (model/key access issue?)")

    # Put tolerance band to RIGHT if only one end is tolerance
    if colors:
        left_is_tol  = colors[0]  in TOL_COLORS
        right_is_tol = colors[-1] in TOL_COLORS
        if left_is_tol and not right_is_tol:
            colors = list(reversed(colors))

    value, tol = compute_value_from_colors(colors)
    snapped = snap_e24(value) if value is not None else None

    return AnalyzeResponse(
        ok=True,
        colors=colors,
        value_ohms=value,
        value_display=human(value),
        tolerance_pct=tol,
        snapped_ohms=snapped,
        snapped_display=human(snapped),
        used=f"gemini_only/{used_backend or 'unknown'}",
        gemini=raw
    )

@app.get("/")
def root():
    return {"status":"ok","version":app.version}
