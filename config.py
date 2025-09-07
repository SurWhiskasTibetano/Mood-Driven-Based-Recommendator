import os
import googlemaps
import streamlit as st
from dotenv import load_dotenv

# --------- Claves desde .env ---------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    st.error("Falta GOOGLE_MAPS_API_KEY en .env")
    st.stop()

# Cliente Google Maps
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# --------- Constantes de UI ---------
LIST_CONTAINER_HEIGHT_PX = 720  # altura del contenedor scrollable

# --------- Pesos del score ---------
W_RATING = 0.5
W_REVIEWS = 0.3
W_PROX = 0.2