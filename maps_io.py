import streamlit as st
from urllib.parse import quote_plus
from config import gmaps, GOOGLE_MAPS_API_KEY

def _maps_link(lat, lon):
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

def gm_embed_directions_url(
    origin_text: str,
    dest_place_id: str | None = None,
    dest_text: str | None = None,
    mode: str = "driving",
    waypoints_latlon: list[tuple[float, float]] | None = None,
):
    base = "https://www.google.com/maps/embed/v1/directions"
    if not origin_text:
        raise ValueError("origin_text es obligatorio")
    if not (dest_place_id or dest_text):
        raise ValueError("Debes pasar dest_place_id o dest_text")
    params = [
        f"key={GOOGLE_MAPS_API_KEY}",
        f"origin={quote_plus(origin_text)}",
        f"mode={mode}",
    ]
    if dest_place_id:
        params.append(f"destination=place_id:{dest_place_id}")
    else:
        params.append(f"destination={quote_plus(dest_text)}")
    if waypoints_latlon:
        wp_str = "|".join([f"{lat:.6f},{lon:.6f}" for (lat, lon) in waypoints_latlon])
        params.append(f"waypoints={quote_plus(wp_str)}")
    return f"{base}?{'&'.join(params)}"

def maps_directions_link(
    origin_text: str,
    dest_place_id: str | None = None,
    dest_text: str | None = None,
    mode: str = "driving",
    waypoints_latlon: list[tuple[float, float]] | None = None,
    optimize_waypoints: bool = False,
):
    base = "https://www.google.com/maps/dir/?api=1"
    if not origin_text:
        raise ValueError("origin_text es obligatorio")
    if not (dest_place_id or dest_text):
        raise ValueError("Debes pasar dest_place_id o dest_text")
    origin_param = f"origin={quote_plus(origin_text)}"
    dest_param = f"destination=place_id:{dest_place_id}" if dest_place_id else f"destination={quote_plus(dest_text)}"
    params = [origin_param, dest_param, f"travelmode={mode}"]
    if waypoints_latlon:
        wp_prefix = "optimize:true|" if optimize_waypoints else ""
        wp_body = "|".join([f"{lat:.6f},{lon:.6f}" for (lat, lon) in waypoints_latlon])
        params.append(f"waypoints={quote_plus(wp_prefix + wp_body)}")
    return f"{base}&{'&'.join(params)}"

def gm_embed_place_url(place_id=None, latlon=None):
    base = "https://www.google.com/maps/embed/v1/place"
    if place_id:
        return f"{base}?key={GOOGLE_MAPS_API_KEY}&q=place_id:{place_id}"
    if latlon:
        return f"{base}?key={GOOGLE_MAPS_API_KEY}&q={latlon[0]:.6f},{latlon[1]:.6f}"
    raise ValueError("Debes pasar place_id o latlon.")

@st.cache_data(ttl=600, show_spinner=False)
def get_place_details(place_id: str, language: str = "es") -> dict:
    try:
        fields = [
            "name", "rating", "user_ratings_total", "url", "googleMapsUri",
            "reviews", "photos", "editorial_summary"
        ]
        try:
            resp = gmaps.place(
                place_id=place_id,
                fields=fields,
                language=language,
                reviews_sort="newest",
                reviews_no_translations=False
            )
        except TypeError:
            resp = gmaps.place(place_id=place_id, fields=fields, language=language)
        result = resp.get("result", {}) if resp else {}
        if "url" not in result and "googleMapsUri" in result:
            result["url"] = result.get("googleMapsUri")
        return result
    except Exception:
        return {}

def place_photo_url(photo_reference: str, maxwidth: int = 640) -> str:
    base = "https://maps.googleapis.com/maps/api/place/photo"
    return f"{base}?maxwidth={maxwidth}&photoreference={quote_plus(photo_reference)}&key={GOOGLE_MAPS_API_KEY}"