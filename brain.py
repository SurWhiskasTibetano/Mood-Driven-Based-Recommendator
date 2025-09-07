import re
import json
import random
import requests
from config import GEMINI_API_KEY
from taxonomy import (
    CURATED_BY_CATEGORY,
    CANON_BY_EMOTION,
    _map_term_to_canon,
    _norm,
)

def detect_mood_category(mood_text: str) -> str:
    """Heurística robusta (fallback) con regex y límites de palabra."""
    p = _norm(mood_text)
    rules = [
        ("tristeza", [
            r"\bmuy mal\b", r"\bmal\b", r"\bfatal\b", r"\bhorrible\b", r"\bbajon\b", r"\bme siento mal\b",
            r"\bdepre", r"\bdeprim", r"\bmelanc", r"\bdesanim", r"\bllor", r"\bvac[ií]o\b",r"\btriste\b"
        ]),
        ("ansiedad/estrés", [r"\bansied", r"\bnervios\b", r"\bagobio\b", r"\bestres\b", r"\bangust", r"\bpreocup"]),
        ("ira", [r"\bira\b", r"\benfad", r"\brabia\b", r"\bfuria\b", r"\bcabre", r"\benoj"]),
        ("cansancio", [r"\bcansancio\b", r"\bcansad", r"\bagotad", r"\bfatiga\b", r"\bburnout\b", r"\bsin fuerzas\b"]),
        ("soledad", [r"\bsoledad\b", r"\bsolo\b", r"\bsola\b", r"\baislad", r"\baislam"]),
        ("aburrimiento", [r"\baburr", r"\bapat", r"\bsin ganas\b", r"\bapatico\b", r"\bapatica\b"]),
        ("felicidad", [r"\bfeliz\b", r"\bcontent", r"\balegr", r"\beufor", r"\bgenial\b", r"\bde lujo\b"]),
        ("amor/romance", [r"\bamor\b", r"\benamora", r"\bromant", r"\bcariñ", r"\brom[aá]nt"]),
        ("curiosidad", [r"\bcurios", r"\bcreativ", r"\binspir", r"\bexplor", r"\bdescubr"]),
        ("calma/paz", [r"\bcalma\b", r"\bpaz\b", r"\btranquil", r"\bseren", r"\brelajad"]),
    ]
    for category, pats in rules:
        if any(re.search(pat, p) for pat in pats):
            return category
    return "neutro"

TONE_HINTS = {
    "tristeza":        ("cálido y suave",            "😔"),
    "ansiedad/estrés": ("calmante y tranquilizador", "😥"),
    "ira":             ("validante y sereno",         "💢"),
    "cansancio":       ("reconfortante",              "😮‍💨"),
    "soledad":         ("acogedor",                   "🤍"),
    "aburrimiento":    ("ligero y motivador",         "🙂"),
    "felicidad":       ("alegre y entusiasta",        "🎉"),
    "amor/romance":    ("tierno y cómplice",          "💞"),
    "curiosidad":      ("inspirador",                 "🌱"),
    "calma/paz":       ("sereno",                     "🧘"),
    "neutro":          ("cálido y cercano",           "🙂"),
}

def _fallback_empathy(mood_text: str) -> str:
    category = detect_mood_category(mood_text)
    _, emoji = TONE_HINTS.get(category, TONE_HINTS["neutro"])
    templates = {
        "tristeza":        f"Siento mucho que estés pasando por esto {emoji}. Voy a recomendarte algunos lugares suaves para ayudarte un poco.",
        "ansiedad/estrés": f"Suena intenso; vamos a bajar revoluciones {emoji}. Te recomendaré sitios tranquilos para desconectar un poco.",
        "ira":             f"Tiene sentido que te sientas así {emoji}. Te propondré opciones para liberar tensión de forma sana.",
        "cansancio":       f"Se nota el cansancio {emoji}. Te sugeriré lugares para recargar pilas con calma.",
        "soledad":         f"Aquí estoy contigo {emoji}. Te propondré sitios donde puedas sentirte acompañado/a a tu ritmo.",
        "aburrimiento":    f"A veces apetece algo distinto {emoji}. Te recomendaré planes con un poco de chispa.",
        "felicidad":       f"¡Qué alegría leerte! {emoji} Te propondré lugares para celebrarlo a tu manera.",
        "amor/romance":    f"Qué bonito momento {emoji}. Te sugeriré rincones con buena atmósfera para un plan especial.",
        "curiosidad":      f"Esa curiosidad es oro {emoji}. Te propondré lugares que inviten a explorar.",
        "calma/paz":       f"Qué bien sentir esa paz {emoji}. Te sugeriré sitios para seguir cuidando ese bienestar.",
        "neutro":          f"Estoy aquí contigo 🙂. Te recomendaré algunos lugares pensados para ti.",
    }
    return templates.get(category, templates["neutro"])

PROMPT_BRAIN_JSON = """ Eres un asistente en español (España). Analiza el estado del usuario y devuelve SOLO un JSON con esta forma: 
{
  "category": "tristeza|ansiedad/estrés|ira|cansancio|soledad|aburrimiento|felicidad|amor/romance|curiosidad|calma/paz",
  "empathy": "1-2 frases, tono acorde a la emoción, EXACTAMENTE 1 emoji, NO empieces con 'Gracias por compartir'",
  "place_types": ["3 a 6 tipos de lugares en España, minúsculas, 1-3 palabras, sin nombres propios"]
}
Criterios:
- Varía los tipos de lugares; evita repetir siempre los mismos.
- Ajusta interior/exterior y social/individual según la emoción.
- Deben ser lugares factibles para buscar en Google Maps Nearby en España.
- Ejemplos (no los devuelvas tal cual): parque, jardín botánico, mirador, paseo fluvial, cafetería, tetería, heladería, librería,
  museo, galería de arte, centro cultural, biblioteca, spa, baños árabes, masaje, yoga, meditación, gimnasio, boxeo, rocódromo,
  piscina, pista de pádel, crossfit, pista de atletismo, parque de trampolines, escape room, bolera, arcade, karaoke, minigolf,
  laser tag, paintball, realidad virtual, coworking, club de lectura, intercambio de idiomas, discoteca, bar de cócteles,
  rooftop, sala de conciertos, club de comedia, bar de vinos, vinoteca, bistró, mercado gastronómico, restaurante romántico,
  café con encanto, planetario, observatorio, reserva natural, templo.
- Si paso “Evita”, no uses esos tipos ni sinónimos.

Estado del usuario: «{mood}»
Evita (si hay): {avoid}
""".strip()

def gemini_brain(mood_text: str, avoid_terms: list[str] | None = None):
    """Devuelve (empathy_message, place_types, category) usando Gemini (JSON estricto)."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")

    avoid = ", ".join(sorted(set((avoid_terms or [])[:12])))
    prompt = PROMPT_BRAIN_JSON.format(mood=mood_text, avoid=avoid if avoid else "—")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "topP": 0.95,
            "maxOutputTokens": 350,
            "responseMimeType": "application/json"
        }
    }
    params = {"key": GEMINI_API_KEY}
    resp = requests.post(url, headers=headers, params=params, data=json.dumps(payload), timeout=20)
    resp.raise_for_status()
    data = resp.json()

    raw = data["candidates"][0]["content"]["parts"][0]["text"]
    obj = json.loads(raw)

    empathy = str(obj.get("empathy", "")).strip()
    places = [str(x).strip().lower() for x in obj.get("place_types", []) if str(x).strip()]
    category = str(obj.get("category", "")).strip().lower()

    if not empathy or not places:
        raise ValueError("JSON incompleto")

    # Filtra evitados y de-dup
    avoid_set = {a.lower() for a in (avoid_terms or [])}
    places = [p for p in places if p not in avoid_set]
    places = list(dict.fromkeys(places))[:6]
    return empathy, places, category

def normalize_to_nearby_keywords(recommended: list[str], category: str, avoid: list[str]) -> list[str]:
    """Normaliza los tipos devueltos por Gemini a keywords viables para Nearby."""
    avoid_set = {a.lower() for a in avoid}
    out = []
    for t in recommended:
        canon = _map_term_to_canon(t, category_hint=category or "neutro")
        if canon.lower() not in avoid_set and canon not in out:
            out.append(canon)
        if len(out) >= 6:
            break
    if len(out) < 3:
        pool = [x for x in CANON_BY_EMOTION.get(category or "neutro", CANON_BY_EMOTION["neutro"]) if x not in out and x not in avoid_set]
        random.shuffle(pool)
        out.extend(pool[: (6 - len(out))])
    return out

def mock_from_mood(mood_text: str, avoid: list[str] | None = None):
    """Fallback clásico: muestrea del curado y normaliza a keywords Nearby."""
    category = detect_mood_category(mood_text)
    avoid = avoid or []
    candidates = CURATED_BY_CATEGORY.get(category, CURATED_BY_CATEGORY["neutro"])[:]
    random.shuffle(candidates)
    raw = []
    for c in candidates:
        if len(raw) >= 6:
            break
        raw.append(c)
    return normalize_to_nearby_keywords(raw, category, avoid)