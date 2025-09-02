# streamlit_app.py

import os
import math
import json
import streamlit as st
import pandas as pd
import requests
import googlemaps
import streamlit.components.v1 as components
from dotenv import load_dotenv
from streamlit_geolocation import streamlit_geolocation

# — Carga variables de entorno
load_dotenv()

# — Claves API
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")      or "AIzaSyCiAaIEGY8_XO9zwQKhiZZEmpBVF0yiZb8"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY") or "AIzaSyCA0Y7hhoNifUVEMNhjq8qdaaSGHOeRGWE"

gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

st.set_page_config(page_title="Recomendador Emocional", layout="wide")
st.title("📍 Recomendador Emocional")

st.markdown(
    """
    - Permite compartir tu ubicación para centrar el mapa.
    - Si lo rechazas, puedes introducir tu dirección manualmente.
    - Al pulsar **Recomiéndame un lugar**, verás tu posición (rojo)
      y los lugares sugeridos (azul) en el mapa.
    - Al hacer clic en un lugar, se mostrará la ruta desde tu ubicación.
    """
)

# — Helpers para distancia y rumbo
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # km
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def bearing(lat1, lon1, lat2, lon2):
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    y = math.sin(Δλ) * math.cos(φ2)
    x = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(Δλ)
    θ = (math.degrees(math.atan2(y, x)) + 360) % 360
    return θ

def compass_point(angle):
    dirs = [
        ("Norte",     "↑"),
        ("Noreste",   "↗"),
        ("Este",      "→"),
        ("Sureste",   "↘"),
        ("Sur",       "↓"),
        ("Suroeste",  "↙"),
        ("Oeste",     "←"),
        ("Noroeste",  "↖"),
    ]
    idx = int((angle + 22.5) // 45) % 8
    name, sym = dirs[idx]
    return f"{name} {sym}"

# — Control de recarga para geolocalización
if "geo_rerun" not in st.session_state:
    st.session_state.geo_rerun = False

# — Inicialización por defecto
if "places" not in st.session_state:
    st.session_state.places = pd.DataFrame()
if "tipo" not in st.session_state:
    st.session_state.tipo = ""

# — Intento de geolocalización con Streamlit Geolocation
location = streamlit_geolocation()
if location and location.get("latitude") and location.get("longitude"):
    lat = location["latitude"]
    lng = location["longitude"]
    st.success(f"Ubicación detectada: {lat:.5f}, {lng:.5f}")
else:
    # — Fallback: geolocalización por IP
    try:
        resp = requests.get("http://ip-api.com/json/").json()
        lat = resp.get("lat")
        lng = resp.get("lon")
        if lat and lng:
            st.success(f"Ubicación aproximada por IP: {lat:.5f}, {lng:.5f}")
        else:
            raise ValueError("Sin coordenadas")
    except Exception:
        st.warning("No pudimos determinar tu ubicación (ni por GPS ni por IP).")
        lat = lng = None


st.markdown("---")

# — Estado de ánimo
mood = st.text_area("¿Cómo te sientes hoy?", placeholder="Ej: Estoy estresado, quiero relajarme…")

# — Botón de recomendación
if st.button("🔍 Recomiéndame un lugar"):
    if not mood:
        st.warning("Describe cómo te sientes antes de continuar.")
    elif lat is None or lng is None:
        st.warning("Necesitamos tu ubicación (detectada o manual).")
    else:
        with st.spinner("Consultando Gemini y buscando lugares…"):
            prompt = (
                f'Una persona dice: "{mood}".\n'
                "¿Qué tipo de lugar concreto recomendarías para mejorar su estado?\n"
                "Responde solo con una palabra: parque, cafetería, museo, playa, naturaleza,gimnasio,biblioteca, restaurante,cine,recreativas etc."
            )
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": GEMINI_API_KEY
                },
                json={"contents":[{"parts":[{"text":prompt}]}]}
            )
            r.raise_for_status()
            tipo = r.json()['candidates'][0]['content']['parts'][0]['text'].strip().lower()

            results = gmaps.places_nearby(
                location=(lat, lng),
                keyword=tipo,
                radius=3000,
                open_now=True
            ).get("results", [])[:10]

            # Prepara datos
            places = []
            for p in results:
                plat = p["geometry"]["location"]["lat"]
                plon = p["geometry"]["location"]["lng"]
                dist = haversine(lat, lng, plat, plon)
                ang  = bearing(lat, lng, plat, plon)
                places.append({
                    "name":      p["name"],
                    "dirección": p.get("vicinity", ""),
                    "rating":    p.get("rating", "–"),
                    "dist_km":   f"{dist:.2f}",
                    "rumbo":     compass_point(ang),
                    "lat":       plat,
                    "lon":       plon
                })
            st.session_state.places = pd.DataFrame(places)
            st.session_state.tipo   = tipo

# — Mapa y tabla con ruta
if lat is not None and lng is not None:
    if not st.session_state.places.empty:
        df = st.session_state.places.rename(columns={
            "name":      "Nombre",
            "dirección": "Dirección",
            "rating":    "Valoración",
            "dist_km":   "Distancia (km)",
            "rumbo":     "Rumbo"
        })
        df["Valoración"] = df["Valoración"].astype(str)

        st.subheader(f"✨ Gemini recomienda: {st.session_state.tipo.capitalize()}")
        st.table(df[["Nombre","Dirección","Valoración","Distancia (km)","Rumbo"]])

        # Marcadores: tu ubicación + lugares
        markers = [{"lat": lat, "lng": lng, "title": "Tú", "isUser": True}] + [
            {"lat": row["lat"], "lng": row["lon"], "title": row["name"], "isUser": False}
            for _, row in st.session_state.places.iterrows()
        ]
        markers_json = json.dumps(markers)

        # HTML + JS de Google Maps con DirectionsService
        mapa_html = f"""
        <div id="map" style="width:100%; height:600px; border:1px solid #ddd;"></div>
        <script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}"></script>
        <script>
          let map, directionsService, directionsRenderer;

          function initMap() {{
            const userPos = {{ lat: {lat}, lng: {lng} }};
            map = new google.maps.Map(document.getElementById('map'), {{
              center: userPos,
              zoom: 14
            }});
            directionsService = new google.maps.DirectionsService();
            directionsRenderer = new google.maps.DirectionsRenderer();
            directionsRenderer.setMap(map);

            const markers = {markers_json};
            markers.forEach(m => {{
              const mark = new google.maps.Marker({{
                position: {{ lat: m.lat, lng: m.lng }},
                map: map,
                title: m.title,
                icon: m.isUser
                  ? {{ path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: 'red', fillOpacity: 1, strokeWeight: 0 }}
                  : null
              }});
              if (!m.isUser) {{
                mark.addListener('click', () => {{
                  // trazar ruta desde usuario hasta este marcador
                  directionsService.route({{
                    origin: userPos,
                    destination: {{ lat: m.lat, lng: m.lng }},
                    travelMode: 'DRIVING'
                  }}, (result, status) => {{
                    if (status === 'OK') {{
                      directionsRenderer.setDirections(result);
                    }} else {{
                      alert('No se pudo calcular la ruta: ' + status);
                    }}
                  }});
                }});
              }}
            }});
          }}

          // Inicializa cuando se cargue el script
          window.onload = initMap;
        </script>
        """
        components.html(mapa_html, height=600)
    else:
        st.info("Cuando tengamos tu ubicación, aquí aparecerá el mapa.")
