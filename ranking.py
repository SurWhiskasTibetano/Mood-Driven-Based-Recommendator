import math
import time
import numpy as np
import pandas as pd
import streamlit as st
from config import gmaps, W_RATING, W_REVIEWS, W_PROX

def geocode_address(address: str, language: str = "es", region: str = "es"):
    res = gmaps.geocode(address, language=language, region=region)
    if not res:
        raise ValueError("No se pudo geocodificar la dirección.")
    loc = res[0]["geometry"]["location"]
    return (loc["lat"], loc["lng"]), res[0]["formatted_address"]

def reverse_geocode(latlon: tuple[float, float], language: str = "es"):
    try:
        res = gmaps.reverse_geocode(latlon, language=language)
        if res:
            return res[0]["formatted_address"]
    except Exception:
        pass
    return f"{latlon[0]:.6f},{latlon[1]:.6f}"

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def compute_scores(df: pd.DataFrame, center_latlon: tuple[float, float], radius_m: int,
                   w_rating: float = W_RATING, w_reviews: float = W_REVIEWS, w_prox: float = W_PROX) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["rating"] = pd.to_numeric(df.get("rating", np.nan), errors="coerce")
    df["user_ratings_total"] = pd.to_numeric(df.get("user_ratings_total", 0), errors="coerce").fillna(0)

    c_lat, c_lon = center_latlon
    def _dist(row):
        lat, lon = row.get("lat"), row.get("lon")
        if pd.notna(lat) and pd.notna(lon):
            return haversine_m(c_lat, c_lon, float(lat), float(lon))
        return np.nan
    df["distance_m"] = df.apply(_dist, axis=1)

    df["rating_score"] = (df["rating"].fillna(0) / 5.0).clip(0, 1)
    max_reviews = max(1.0, float(df["user_ratings_total"].max()))
    df["reviews_score"] = (np.log1p(df["user_ratings_total"]) / np.log1p(max_reviews)).clip(0, 1)
    prox = 1.0 - (df["distance_m"] / float(radius_m))
    df["proximity_score"] = prox.clip(lower=0, upper=1).fillna(0)
    s = (w_rating * df["rating_score"] + w_reviews * df["reviews_score"] + w_prox * df["proximity_score"])
    denom = max(1e-9, (w_rating + w_reviews + w_prox))
    df["score"] = (s / denom).clip(0, 1)
    return df

@st.cache_data(ttl=300)
def places_nearby_all(location, keyword, radius=1500, open_now=True, language="es"):
    all_results = []
    page = gmaps.places_nearby(
        location=location,
        keyword=keyword,
        radius=radius,
        open_now=open_now,
        language=language
    )
    all_results.extend(page.get("results", []))
    token = page.get("next_page_token")
    while token:
        time.sleep(2)
        page = gmaps.places_nearby(page_token=token, language=language)
        all_results.extend(page.get("results", []))
        token = page.get("next_page_token")
    return all_results

def filter_by_rating_df(df: pd.DataFrame, min_rating=0.0) -> pd.DataFrame:
    if "rating" not in df.columns:
        df["rating"] = None
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    return df[df["rating"] >= float(min_rating)]