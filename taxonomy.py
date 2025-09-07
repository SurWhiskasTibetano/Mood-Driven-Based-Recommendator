
# --------- Constantes de UI ---------
LIST_CONTAINER_HEIGHT_PX = 720  # altura del contenedor scrollable

# --------- Pesos del score ---------
W_RATING = 0.5
W_REVIEWS = 0.3
W_PROX = 0.2
'''.strip()

files["taxonomy.py"] = r'''
import re
import random
import unicodedata

def _norm(t: str) -> str:
    t = (t or "").lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")

# Curado amplio por emoción (guía + fallback)
CURATED_BY_CATEGORY = {
    "tristeza": [
        "parque luminoso", "jardín botánico", "mirador tranquilo", "paseo junto al agua",
        "cafetería acogedora", "librería", "museo", "centro cultural", "tetería",
        "paseo urbano", "exposición de arte", "cine", "terraza tranquila",
        "paseo fluvial", "sendero fácil", "espacio verde amplio", "museo de historia",
        "museo de arte", "galería", "música suave"
    ],
    "ansiedad/estrés": [
        "parque", "jardín botánico", "spa", "tetería", "yoga", "paseo fluvial", "mirador",
        "cafetería tranquila", "baños árabes", "paseo por la playa", "bosque urbano", "biblioteca",
        "meditación", "camino perimetral", "sendero fácil", "pistas de caminar", "masaje",
        "paseo por el río", "templo", "jardín zen"
    ],
    "ira": [
        "gimnasio", "boxeo", "rocódromo", "piscina", "running", "crossfit",
        "pista de pádel", "circuito de bici", "pista de atletismo",
        "parque de trampolines", "kickboxing", "calistenia", "boulder",
        "sauna tras ejercicio", "baño frío", "spinning", "clase de baile enérgica"
    ],
    "cansancio": [
        "cafetería", "tetería", "librería", "cine", "heladería", "terraza con sombra", "spa",
        "museo pequeño", "paseo corto", "sala de lectura", "galería", "chill-out",
        "parque de barrio", "brunch tranquilo", "mirador con bancos", "sala de té",
        "cafetería con sofás", "biblioteca"
    ],
    "soledad": [
        "cafetería mesas compartidas", "coworking", "taller", "voluntariado", "biblioteca",
        "centro cultural", "clase grupal", "club de lectura", "juegos de mesa", "intercambio de idiomas",
        "bar de vermut tranquilo", "mesas largas", "colectivo creativo", "huerto urbano",
        "mercadillo", "asociación", "meetup", "coro"
    ],
    "aburrimiento": [
        "escape room", "arcade", "bolera", "taller creativo", "museo interactivo", "mercadillo",
        "minigolf", "salón de juegos", "karaoke", "paintball", "laser tag",
        "feria", "parque temático pequeño", "cerámica", "clase de cocina",
        "búsqueda del tesoro", "gincana", "patinaje", "realidad virtual"
    ],
    "felicidad": [
        "discoteca", "bar de cócteles", "karaoke", "rooftop", "conciertos", "tapas",
        "terraza con vistas", "club de comedia", "sala de conciertos", "mercado gastronómico",
        "bar musical", "baile social", "fiesta latina", "festival", "speakeasy",
        "brunch animado", "taberna moderna", "food market"
    ],
    "amor/romance": [
        "mirador", "parque", "terraza romántica", "restaurante íntimo", "paseo atardecer",
        "jardín botánico", "bar de vinos", "bistró", "azotea tranquila", "casco antiguo",
        "paseo fluvial", "velas", "café con encanto", "degustación de vinos",
        "jardines", "museo pequeño", "rincón fotográfico", "patio"
    ],
    "curiosidad": [
        "museo", "galería", "centro cultural", "taller", "librería", "museo de ciencias",
        "exposición temporal", "archivo histórico", "ruta guiada", "museo interactivo", "visita a estudio",
        "itinerario urbano", "centro de innovación", "artesanía", "ruta de murales",
        "visita teatralizada", "planetario", "observatorio", "aula de naturaleza"
    ],
    "calma/paz": [
        "spa", "jardín botánico", "paseo junto al agua", "tetería", "templo",
        "biblioteca", "parque amplio", "baños árabes", "paseo por lago", "sendero fácil",
        "mirador al amanecer", "paseo marítimo", "parque con estanque", "ribera del río",
        "meditación", "yoga suave", "reserva natural", "ermita"
    ],
    "neutro": [
        "parque", "cafetería", "museo", "mirador", "librería", "paseo urbano", "galería",
        "mercadillo", "centro cultural", "paseo junto al agua"
    ],
}

# Palabras clave viables para Google Nearby (canon)
CANON_KEYWORDS = [
    # Naturaleza / paseo
    "parque", "jardín botánico", "mirador", "paseo fluvial", "paseo marítimo", "reserva natural",
    "playa", "sendero", "ribera del río",
    # Cafés y relax
    "cafetería", "tetería", "heladería", "chill-out",
    # Cultura
    "museo", "galería de arte", "centro cultural", "biblioteca", "archivo histórico",
    "museo de ciencias", "planetario", "observatorio",
    # Bienestar
    "spa", "baños árabes", "masaje", "yoga", "meditación", "sauna",
    # Deporte / descarga
    "gimnasio", "boxeo", "rocódromo", "piscina", "pista de pádel", "crossfit",
    "pista de atletismo", "parque de trampolines", "escalada",
    # Ocio
    "escape room", "bolera", "arcade", "karaoke", "minigolf", "laser tag", "paintball", "realidad virtual",
    # Social / comunidad
    "coworking", "club de lectura", "intercambio de idiomas", "asociación",
    # Noche / celebración
    "discoteca", "bar de cócteles", "rooftop", "sala de conciertos", "club de comedia",
    "bar de vinos", "vinoteca", "bistró", "mercado gastronómico",
    # Restauración romántica
    "restaurante romántico", "café con encanto",
]

SYNONYMS_TO_CANON = {
    # Naturaleza / paseo
    r"\bparque luminoso\b": "parque",
    r"\bparque de barrio\b": "parque",
    r"\bpaseo junto al agua\b": "paseo fluvial",
    r"\bpaseo por el río\b": "paseo fluvial",
    r"\bpaseo por la playa\b": "paseo marítimo",
    r"\bribera\b": "ribera del río",
    r"\bsendero fácil\b": "sendero",
    r"\bruta corta\b": "sendero",
    r"\bbosque urbano\b": "parque",
    r"\bespacio verde\b": "parque",
    r"\bmirador tranquilo\b": "mirador",
    r"\bmirador con bancos\b": "mirador",
    # Cafés / relax
    r"\bcafeter[ií]a acogedora\b": "cafetería",
    r"\bcafeter[ií]a tranquila\b": "cafetería",
    r"\bcafeter[ií]a con sof[aá]s\b": "cafetería",
    r"\bsala de t[eé]\b": "tetería",
    r"\bchill[- ]?out\b": "chill-out",
    # Cultura
    r"\bexposici[oó]n de arte\b": "galería de arte",
    r"\bgaler[ií]a\b": "galería de arte",
    r"\bmuseo de arte\b": "museo",
    r"\bmuseo peque[nñ]o\b": "museo",
    r"\bmuseo interactivo\b": "museo",
    r"\bcentro de innovaci[oó]n\b": "centro cultural",
    r"\bruta guiada\b": "centro cultural",
    r"\bitinerario urbano\b": "centro cultural",
    # Bienestar
    r"\bba[nñ]os (arabes|a[rá]bes)\b": "baños árabes",
    r"\btemplo|silencio\b": "templo",
    # Deporte / descarga
    r"\brunning\b": "pista de atletismo",
    r"\bboulder\b": "rocódromo",
    r"\bclase de baile en[ée]rgica\b": "gimnasio",
    r"\bcalistenia\b": "gimnasio",
    # Ocio
    r"\bsal[oó]n de juegos\b": "arcade",
    r"\bparque tem[aá]tico peque[nñ]o\b": "mini golf",
    r"\bgim?c?ana|gincana\b": "escape room",
    r"\bb[uú]squeda del tesoro\b": "escape room",
    r"\bferia\b": "mercado gastronómico",
    r"\bclase de cocina\b": "centro cultural",
    r"\btaller creativo|cer[aá]mica\b": "centro cultural",
    # Social / comunidad
    r"\bmesas compartidas\b": "cafetería",
    r"\bcolectivo creativo\b": "centro cultural",
    r"\bvoluntariado\b": "asociación",
    r"\bmeetup\b": "centro cultural",
    r"\bhuerto urbano\b": "asociación",
    # Noche / romance
    r"\brooftop\b": "rooftop",
    r"\bazotea\b": "rooftop",
    r"\bbar de vermut\b": "bar de cócteles",
    r"\bbar con velas\b": "bar de vinos",
    r"\bdegustaci[oó]n de vinos\b": "vinoteca",
    r"\bcaf[eé] con encanto\b": "café con encanto",
}

# Canon por emoción para completar variedad
CANON_BY_EMOTION = {
    "tristeza": [
        "parque", "jardín botánico", "mirador", "paseo fluvial", "cafetería",
        "librería", "museo", "tetería", "centro cultural", "biblioteca"
    ],
    "ansiedad/estrés": [
        "parque", "jardín botánico", "paseo fluvial", "paseo marítimo", "spa",
        "tetería", "meditación", "yoga", "baños árabes", "biblioteca"
    ],
    "ira": [
        "gimnasio", "boxeo", "rocódromo", "piscina", "pista de pádel",
        "crossfit", "pista de atletismo", "parque de trampolines", "sauna"
    ],
    "cansancio": [
        "cafetería", "tetería", "librería", "cine", "spa", "museo",
        "galería de arte", "parque", "chill-out", "biblioteca"
    ],
    "soledad": [
        "cafetería", "coworking", "club de lectura", "intercambio de idiomas",
        "centro cultural", "biblioteca", "asociación", "cafetería"
    ],
    "aburrimiento": [
        "escape room", "arcade", "bolera", "karaoke", "minigolf",
        "laser tag", "paintball", "realidad virtual"
    ],
    "felicidad": [
        "discoteca", "bar de cócteles", "rooftop", "sala de conciertos",
        "club de comedia", "mercado gastronómico", "bar de vinos"
    ],
    "amor/romance": [
        "mirador", "parque", "bar de vinos", "vinoteca", "bistró",
        "restaurante romántico", "café con encanto", "rooftop", "paseo fluvial"
    ],
    "curiosidad": [
        "museo", "galería de arte", "centro cultural", "museo de ciencias",
        "planetario", "observatorio", "biblioteca"
    ],
    "calma/paz": [
        "spa", "jardín botánico", "paseo fluvial", "paseo marítimo",
        "templo", "meditación", "yoga", "biblioteca", "parque"
    ],
    "neutro": [
        "parque", "cafetería", "museo", "mirador", "galería de arte",
        "centro cultural", "paseo fluvial"
    ],
}

def _map_term_to_canon(term: str, category_hint: str = "neutro") -> str:
    """Mapea un término a una keyword canónica Nearby-friendly."""
    t = _norm(term)
    # 1) Sinónimos por regex
    for pat, canon in SYNONYMS_TO_CANON.items():
        if re.search(pat, t):
            return canon
    # 2) Coincidencia directa con canon
    for canon in CANON_KEYWORDS:
        if _norm(canon) in t or t in _norm(canon):
            return canon
    # 3) Heurística
    t_simple = re.sub(r"\b(tranquil[ao]s?|acogedor[ao]s?|rom[aá]ntic[ao]s?|peque[ñn]o[s]?)\b", "", t).strip()
    for canon in CANON_KEYWORDS:
        if _norm(canon) == t_simple:
            return canon
    # 4) Fallback por emoción
    pool = CANON_BY_EMOTION.get(category_hint, CANON_BY_EMOTION["neutro"])
    return random.choice(pool)