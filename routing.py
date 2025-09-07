import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime
from config import gmaps

def _latlon_str(latlon):
    return f"{latlon[0]},{latlon[1]}"

@st.cache_data(ttl=180, show_spinner=False)
def route_total_seconds(origin_text: str, waypoints: tuple, dest_latlon: tuple, mode: str):
    try:
        r = gmaps.directions(
            origin_text,
            _latlon_str(dest_latlon),
            mode=mode,
            waypoints=list(waypoints) if waypoints else None,
            optimize_waypoints=False,
            departure_time=datetime.now()
        )
        if not r:
            return None
        secs = sum(leg["duration"]["value"] for leg in r[0]["legs"])
        return float(secs)
    except Exception:
        return None

@st.cache_data(ttl=180, show_spinner=False)
def optimize_route_order(origin_text: str, stops_latlon: list[tuple[float, float]], mode: str):
    if not stops_latlon:
        return [], [], None, None
    if len(stops_latlon) == 1:
        dest = stops_latlon[0]
        secs = route_total_seconds(origin_text, tuple(), dest, mode)
        return [], [], dest, secs

    dest = stops_latlon[-1]
    waypoints = stops_latlon[:-1]
    try:
        r = gmaps.directions(
            origin_text,
            _latlon_str(dest),
            mode=mode,
            waypoints=[_latlon_str(wp) for wp in waypoints],
            optimize_waypoints=True,
            departure_time=datetime.now()
        )
        if not r:
            return list(range(len(waypoints))), waypoints, dest, None
        order = r[0].get("waypoint_order", list(range(len(waypoints))))
        ordered_wp = [waypoints[i] for i in order]
        secs = sum(leg["duration"]["value"] for leg in r[0]["legs"])
        return order, ordered_wp, dest, float(secs)
    except Exception:
        secs = route_total_seconds(origin_text, tuple(_latlon_str(w) for w in waypoints), dest, mode)
        return list(range(len(waypoints))), waypoints, dest, secs

def label_from_ratio(ratio: float | None) -> str:
    if ratio is None or np.isnan(ratio):
        return ""
    if ratio <= 0.10:   return "genial"
    if ratio <= 0.25:   return "muy bien"
    if ratio <= 0.50:   return "normal"
    if ratio <= 1.00:   return "mal"
    return "muy mal"

def compute_multi_stop_detours(origin_text: str, selected_coords: list[tuple[float,float]], candidates_df, mode: str):
    if candidates_df.empty or len(selected_coords) == 0:
        candidates_df["detour_ratio"] = np.nan
        candidates_df["ruta"] = ""
        return candidates_df

    dest = selected_coords[-1]
    base_waypoints = tuple(_latlon_str(p) for p in selected_coords[:-1])
    base_secs = route_total_seconds(origin_text, base_waypoints, dest, mode)
    if not base_secs or base_secs <= 0:
        candidates_df["detour_ratio"] = np.nan
        candidates_df["ruta"] = ""
        return candidates_df

    many_paradas = len(selected_coords) > 6
    max_insert_positions = 1 if many_paradas else (len(selected_coords))

    ratios = []
    for _, row in candidates_df.iterrows():
        lat, lon = row.get("lat"), row.get("lon")
        if pd.isna(lat) or pd.isna(lon):
            ratios.append(np.nan)
            continue
        cand = (float(lat), float(lon))
        best_secs = None

        if max_insert_positions == 1:
            new_wp = list(base_waypoints) + [_latlon_str(cand)]
            secs = route_total_seconds(origin_text, tuple(new_wp), dest, mode)
            best_secs = secs
        else:
            for i in range(max_insert_positions + 1):
                new_wp = list(base_waypoints)
                new_wp.insert(i, _latlon_str(cand))
                secs = route_total_seconds(origin_text, tuple(new_wp), dest, mode)
                if secs:
                    best_secs = secs if (best_secs is None or secs < best_secs) else best_secs

        if best_secs and best_secs > 0:
            ratios.append(max(0.0, (best_secs - base_secs) / base_secs))
        else:
            ratios.append(np.nan)

    candidates_df = candidates_df.copy()
    candidates_df["detour_ratio"] = ratios
    candidates_df["ruta"] = candidates_df["detour_ratio"].apply(label_from_ratio)
    return candidates_df