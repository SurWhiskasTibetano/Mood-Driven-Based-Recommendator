# pruebas.py — Recomendador Emocional con dirección (calle y número), Nearby y rutas Google Maps
# Modo: SOLO ubicación manual
# Requisitos: streamlit, googlemaps, requests, python-dotenv, pandas, numpy

import numpy as np
import pandas as pd
import streamlit as st

# --------- Config de página (primera llamada a st.*) ---------
st.set_page_config(page_title="Recomendador Emocional", layout="wide")

# ==== imports desde módulos refactorizados ====
from config import (
    gmaps, GEMINI_API_KEY, GOOGLE_MAPS_API_KEY,
    LIST_CONTAINER_HEIGHT_PX, W_RATING, W_REVIEWS, W_PROX
)
from taxonomy import _map_term_to_canon
from brain import (
    detect_mood_category, _fallback_empathy,
    gemini_brain, normalize_to_nearby_keywords, mock_from_mood
)
from maps_io import (
    gm_embed_directions_url, maps_directions_link,
    get_place_details, place_photo_url
)
from ranking import (
    geocode_address, reverse_geocode, compute_scores,
    places_nearby_all, filter_by_rating_df
)
from routing import (
    route_total_seconds, optimize_route_order, compute_multi_stop_detours
)

# =====================================================================
# ======================  ESTADO INICIAL  =============================
# =====================================================================

if "suggested_terms" not in st.session_state:
    st.session_state.suggested_terms = []
if "raw_results_df" not in st.session_state:
    st.session_state.raw_results_df = pd.DataFrame()
if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame()
if "selected_df" not in st.session_state:
    st.session_state.selected_df = pd.DataFrame()
if "center_latlon" not in st.session_state:
    st.session_state.center_latlon = (40.4168, -3.7038)  # Madrid por defecto
if "center_address" not in st.session_state:
    st.session_state.center_address = reverse_geocode(st.session_state.center_latlon)
if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0
if "pending_resort" not in st.session_state:
    st.session_state.pending_resort = False
if "last_search_sig" not in st.session_state:
    st.session_state.last_search_sig = None
if "route_mode" not in st.session_state:
    st.session_state.route_mode = "driving"
if "intelligent_mode" not in st.session_state:
    st.session_state.intelligent_mode = False
if "optimize_waypoints" not in st.session_state:
    st.session_state.optimize_waypoints = True
if "prev_intelligent_mode" not in st.session_state:
    st.session_state.prev_intelligent_mode = st.session_state.intelligent_mode
if "empathy_message" not in st.session_state:
    st.session_state.empathy_message = ""
if "recent_terms" not in st.session_state:
    st.session_state.recent_terms = []  # para evitar repetir siempre lo mismo

# =====================================================================
# ======================  INTERFAZ  ===================================
# =====================================================================

st.title("🧠➡️📍 Recomendador Emocional")

# Sidebar ubicación y filtros (SOLO MANUAL)
st.sidebar.header("📍 Ubicación y filtros")

addr_default = st.session_state.get("center_address", "")
addr_input = st.sidebar.text_input("Dirección (calle y número, o lugar):", value=addr_default)
if st.sidebar.button("📍 Usar esta dirección"):
    try:
        (lat, lon), fmt = geocode_address(addr_input)
        st.session_state.center_latlon = (lat, lon)
        st.session_state.center_address = fmt
        st.sidebar.success(f"Dirección establecida: {fmt}")
    except Exception as e:
        st.sidebar.error(f"No se pudo geocodificar: {e}")

radius = st.sidebar.slider("Radio de búsqueda (m)", min_value=200, max_value=5000, value=1500, step=100)
open_now = st.sidebar.checkbox("Solo abiertos ahora", value=True)
min_rating = st.sidebar.slider("Puntuación mínima", min_value=0.0, max_value=5.0, value=0.0, step=0.1)

st.sidebar.caption(f"Dirección actual: {st.session_state.center_address}")
st.sidebar.map(pd.DataFrame([{"lat": st.session_state.center_latlon[0], "lon": st.session_state.center_latlon[1]}]))

# Paso 1: emociones → lugares
st.subheader("1) Dime cómo te sientes")
mood_text = st.text_area("Tu estado de ánimo:", placeholder="Ej.: Estoy estresado, me vendría bien desconectar...")

def _remove_term(idx: int):
    try:
        del st.session_state.suggested_terms[idx]
        st.rerun()
    except Exception:
        pass

if st.button("🎯 Recomendar lugares"):
    if mood_text.strip():
        try:
            empathy, places_raw, cat = gemini_brain(mood_text, avoid_terms=st.session_state.recent_terms)
            # Normaliza a keywords Nearby
            places = normalize_to_nearby_keywords(places_raw, cat or "neutro", avoid=st.session_state.recent_terms)
            st.session_state.empathy_message = empathy
            st.session_state.suggested_terms = places
            # Actualiza recientes
            st.session_state.recent_terms = list(dict.fromkeys((st.session_state.recent_terms + places)))[-24:]
        except Exception:
            st.session_state.empathy_message = _fallback_empathy(mood_text)
            st.session_state.suggested_terms = mock_from_mood(mood_text, avoid=st.session_state.recent_terms)

# Mostrar mensaje empático si existe
if st.session_state.empathy_message:
    st.info(st.session_state.empathy_message)

# ---- Lista en casillas (grid) de 'Lugares sugeridos' con ✖ y añadir ----
st.subheader("Lugares sugeridos")

def render_term_cards(terms: list[str], cards_per_row: int = 4):
    if not terms:
        st.info("No hay sugerencias aún. Usa «Recomendar lugares» o añade alguna manualmente.")
        return
    st.caption("Pulsa ✖ para quitar un término.")
    row_cols = None
    for i, term in enumerate(list(terms)):
        if i % cards_per_row == 0:
            row_cols = st.columns(cards_per_row, gap="small")
        col = row_cols[i % cards_per_row]
        with col:
            with st.container():
                inner = st.columns([0.8, 0.2])
                with inner[0]:
                    st.markdown(f"**{term}**")
                with inner[1]:
                    st.button("✖", key=f"del_term_{i}", help=f"Descartar «{term}»", on_click=_remove_term, args=(i,))
                st.markdown("<hr style='margin:6px 0; opacity:0.2;'>", unsafe_allow_html=True)

render_term_cards(st.session_state.suggested_terms, cards_per_row=4)

with st.form("add_term_form", clear_on_submit=True):
    new_term = st.text_input("Añadir tipo de lugar (se normaliza para Google Maps)", placeholder="p. ej., mirador, cafetería tranquila, jardín botánico…")
    add_clicked = st.form_submit_button("➕ Añadir")
    if add_clicked:
        nt = (new_term or "").strip()
        if nt:
            # Normaliza manual también a keyword Nearby
            cat_hint = detect_mood_category(mood_text or "")
            canon = _map_term_to_canon(nt, cat_hint)
            if canon not in st.session_state.suggested_terms:
                st.session_state.suggested_terms.append(canon)
                st.success(f"Añadido: {canon}")
                st.rerun()
            else:
                st.warning("Ese término ya está en la lista.")

place_terms = st.session_state.suggested_terms

# =====================================================================
# ======================  BÚSQUEDA NEARBY  ============================
# =====================================================================

def compute_nearby_df(terms: list[str], center_latlon, radius, open_now, language="es") -> pd.DataFrame:
    from maps_io import _maps_link  # import local para construir link
    by_id = {}
    for term in terms:
        results = places_nearby_all(center_latlon, term, radius=radius, open_now=open_now, language=language)
        if not results and open_now:
            results = places_nearby_all(center_latlon, term, radius=radius, open_now=False, language=language)
        for p in results:
            locp = p.get("geometry", {}).get("location", {})
            pid = p.get("place_id")
            if not pid:
                continue
            photos = p.get("photos", []) or []
            photo_ref = photos[0].get("photo_reference") if (photos and isinstance(photos[0], dict)) else None

            if pid in by_id:
                by_id[pid]["_sug_set"].add(term)
                if p.get("rating", 0) and (p.get("rating", 0) > by_id[pid].get("rating", 0)):
                    by_id[pid]["rating"] = p.get("rating")
                if p.get("user_ratings_total", 0) and (p.get("user_ratings_total", 0) > by_id[pid].get("user_ratings_total", 0)):
                    by_id[pid]["user_ratings_total"] = p.get("user_ratings_total")
                if (not by_id[pid].get("photo_ref")) and photo_ref:
                    by_id[pid]["photo_ref"] = photo_ref
                continue

            by_id[pid] = {
                "✅": False,
                "_sug_set": set([term]),
                "sugerencia": term,
                "name": p.get("name"),
                "rating": p.get("rating"),
                "user_ratings_total": p.get("user_ratings_total"),
                "address": p.get("vicinity"),
                "lat": locp.get("lat"),
                "lon": locp.get("lng"),
                "place_id": pid,
                "maps_link": _maps_link(locp.get("lat"), locp.get("lng")),
                "photo_ref": photo_ref,
            }
    rows = []
    for rec in by_id.values():
        rec["sugerencia"] = ", ".join(sorted(rec["_sug_set"]))
        rec.pop("_sug_set", None)
        rows.append(rec)

    df = pd.DataFrame(rows)
    df = compute_scores(df, center_latlon, radius, w_rating=W_RATING, w_reviews=W_REVIEWS, w_prox=W_PROX)
    df = df.sort_values(by=["score"], ascending=[False]).reset_index(drop=True)
    return df

# Firma de búsqueda
search_sig = (tuple(sorted(place_terms)), st.session_state.center_latlon, int(radius), bool(open_now))

if place_terms:
    if st.session_state.last_search_sig != search_sig:
        new_df = compute_nearby_df(place_terms, st.session_state.center_latlon, radius, open_now, language="es")

        if not st.session_state.raw_results_df.empty and "place_id" in st.session_state.raw_results_df.columns:
            prev = st.session_state.raw_results_df[["place_id", "✅"]].drop_duplicates("place_id")
            new_df = new_df.merge(prev, on="place_id", how="left", suffixes=("", "_old"))
            if "✅_old" in new_df.columns:
                new_df.loc[:, "✅"] = new_df["✅"].eq(True) | new_df["✅_old"].eq(True)
                new_df.drop(columns=["✅_old"], inplace=True)

        if "✅" in new_df.columns:
            new_df["✅"] = new_df["✅"].astype(bool)
            sort_cols = ["✅", "score"] if new_df["✅"].any() else ["score"]
            new_df = new_df.sort_values(by=sort_cols, ascending=[False] * len(sort_cols)).reset_index(drop=True)

        st.session_state.raw_results_df = new_df
        st.session_state.last_search_sig = search_sig
        st.session_state.pending_resort = True
else:
    if not st.session_state.raw_results_df.empty:
        st.session_state.raw_results_df = pd.DataFrame()
        st.session_state.results_df = pd.DataFrame()
        st.session_state.selected_df = pd.DataFrame()

# =====================================================================
# ======================  RESULTADOS CERCA  ============================
# =====================================================================

st.subheader("2) 🔎 Resultados cerca")

new_intelligent_mode = st.checkbox(
    "🧠 Modo inteligente (cálculo de desvíos y etiquetas de ruta)",
    value=st.session_state.get("intelligent_mode", False),
    help="Al activarlo, estimamos cómo encaja cada sitio en tu ruta (genial/muy bien/...). Esto puede tardar más y consume cuota de la API."
)
if "prev_intelligent_mode" not in st.session_state:
    st.session_state.prev_intelligent_mode = new_intelligent_mode

if new_intelligent_mode != st.session_state.prev_intelligent_mode:
    st.session_state.intelligent_mode = new_intelligent_mode
    st.session_state.prev_intelligent_mode = new_intelligent_mode
    st.session_state.editor_nonce += 1
    st.session_state.pending_resort = True
    st.rerun()

st.session_state.intelligent_mode = new_intelligent_mode
if st.session_state.intelligent_mode:
    st.caption("Calculamos el impacto en tu ruta para priorizar lugares que te pillen de camino.")

def _sync_results_back_to_raw():
    if "results_df" in st.session_state and isinstance(st.session_state.results_df, pd.DataFrame) and not st.session_state.results_df.empty:
        res = st.session_state.results_df[["place_id", "✅"]].dropna(subset=["place_id"]).drop_duplicates("place_id")
        raw = st.session_state.raw_results_df
        if not raw.empty:
            raw = raw.merge(res, on="place_id", how="left", suffixes=("", "_new"))
            if "✅_new" in raw.columns:
                raw.loc[:, "✅"] = raw["✅_new"].combine_first(raw["✅"]).eq(True)
                raw = raw.drop(columns=["✅_new"])
            st.session_state.raw_results_df = raw

if not st.session_state.raw_results_df.empty:
    base = st.session_state.raw_results_df.copy()
    base = compute_scores(base, st.session_state.center_latlon, radius, w_rating=W_RATING, w_reviews=W_REVIEWS, w_prox=W_PROX)

    # Ruta base para etiquetas, si procede
    selected_coords = []
    if not base.empty and "✅" in base.columns:
        sel_raw = base[base["✅"] == True]  # noqa
        for _, r in sel_raw.iterrows():
            if pd.notna(r.get("lat")) and pd.notna(r.get("lon")):
                selected_coords.append((float(r["lat"]), float(r["lon"])))

    if st.session_state.intelligent_mode and len(selected_coords) >= 1:
        base = compute_multi_stop_detours(
            origin_text=st.session_state.center_address,
            selected_coords=selected_coords,
            candidates_df=base,
            mode=st.session_state.route_mode
        )
        if "ruta" not in base.columns:
            base["ruta"] = ""
        base["ruta"] = base["ruta"].fillna("").astype(str)
    else:
        base["detour_ratio"] = np.nan
        base["ruta"] = ""

    view_df = filter_by_rating_df(base, min_rating=min_rating)
    if "✅" in view_df.columns:
        view_df.loc[:, "✅"] = view_df["✅"].astype(bool)
    sort_cols = ["✅", "score"] if (st.session_state.get("pending_resort", False) or (not view_df.empty and view_df["✅"].any())) else ["score"]
    view_df = view_df.sort_values(by=sort_cols, ascending=[False] * len(sort_cols)).reset_index(drop=True)
    st.session_state.pending_resort = False

    # ---------- Tabla ----------
    def _toggle_check(place_id: str):
        val = st.session_state.get(f"rowcheck_{place_id}", False)
        raw = st.session_state.raw_results_df
        mask = raw["place_id"] == place_id
        if mask.any():
            raw.loc[mask, "✅"] = bool(val)
            st.session_state.raw_results_df = raw
        st.session_state.selected_df = st.session_state.raw_results_df[st.session_state.raw_results_df["✅"] == True].copy()  # noqa

    header_cols = ["✅", "Nombre", "Coincidió con", "Ruta" if st.session_state.intelligent_mode else None,
                   "Score", "Distancia (m)", "Rating", "Reseñas"]
    header_cols = [h for h in header_cols if h is not None]
    col_widths = [0.7, 3.2, 2.8] + ([1.2] if st.session_state.intelligent_mode else []) + [1.0, 1.4, 1.1, 1.2]
    col_widths = col_widths[:len(header_cols)]
    hdr = st.columns(col_widths, gap="small")
    for c, h in zip(hdr, header_cols):
        c.markdown(f"**{h}**")

    with st.container(height=LIST_CONTAINER_HEIGHT_PX, border=True, width="stretch"):
        for _, row in view_df.iterrows():
            place_id = str(row.get("place_id"))
            name = row.get("name") or "Lugar"
            sug = row.get("sugerencia", "")
            ruta_tag = row.get("ruta", "") if st.session_state.intelligent_mode else None
            score = row.get("score")
            distm = row.get("distance_m")
            rating = row.get("rating")
            reviews_n = row.get("user_ratings_total")
            fallback_photo_ref = row.get("photo_ref")
            checked = bool(row.get("✅", False))

            cols = st.columns(col_widths, gap="small")

            with cols[0]:
                st.checkbox(
                    "Seleccionar",
                    label_visibility="collapsed",
                    key=f"rowcheck_{place_id}",
                    value=checked,
                    help="Seleccionar",
                    on_change=_toggle_check,
                    args=(place_id,)
                )

            with cols[1]:
                with st.popover(name, width="stretch"):
                    details = get_place_details(place_id)
                    # Foto
                    photo_shown = False
                    try:
                        photos = details.get("photos", []) or []
                        pref = None
                        if photos and isinstance(photos[0], dict):
                            pref = photos[0].get("photo_reference")
                        if not pref:
                            pref = fallback_photo_ref
                        if pref:
                            st.image(place_photo_url(pref, maxwidth=640), width="stretch")
                            photo_shown = True
                    except Exception:
                        pass
                    if not photo_shown:
                        st.caption("Sin foto principal disponible.")

                    # Cabecera rating / reseñas
                    r = details.get("rating", rating)
                    ur = details.get("user_ratings_total", reviews_n)
                    head_bits = []
                    if r is not None and str(r) != "nan":
                        head_bits.append(f"⭐ {r}")
                    if ur is not None and str(ur) != "nan":
                        head_bits.append(f"· {int(ur)} reseñas")
                    if head_bits:
                        st.markdown("**" + " ".join(head_bits) + "**")

                    # Reseñas destacadas
                    reviews = details.get("reviews") or []
                    parsed = []
                    for rev in reviews[:3]:
                        author = rev.get("author_name") or rev.get("authorAttribution", {}).get("displayName") or "Usuario"
                        rr = rev.get("rating", "")
                        when = rev.get("relative_time_description") or rev.get("publishTime", "")
                        text = rev.get("text", "")
                        if isinstance(text, dict):
                            text = text.get("text", "")
                        text = (text or "").strip()
                        parsed.append((author, rr, when, text))
                    if parsed:
                        st.markdown("---")
                        st.markdown("**Reseñas destacadas:**")
                        for (auth, rr, when, txt) in parsed:
                            st.markdown(f"**{auth}** — ⭐ {rr} · _{when}_  \n{txt if txt else '_(sin texto)_' }")
                    else:
                        st.caption("Sin reseñas públicas.")

                    maps_url = details.get("url") or row.get("maps_link")
                    if maps_url:
                        st.markdown(f"[Ver en Google Maps ↗]({maps_url})")

            with cols[2]:
                st.write(sug if sug else "")

            idx = 3
            if st.session_state.intelligent_mode:
                with cols[idx]:
                    st.write(ruta_tag if ruta_tag else "")
                idx += 1

            with cols[idx]:
                st.write(f"{(score or 0):.3f}")
            idx += 1

            with cols[idx]:
                st.write(f"{(distm or 0):.0f}")
            idx += 1

            with cols[idx]:
                st.write("" if (rating is None or str(rating) == "nan") else f"{float(rating):.1f}")
            idx += 1

            with cols[idx]:
                st.write("" if (reviews_n is None or str(reviews_n) == "nan") else int(reviews_n))

    st.session_state.results_df = view_df.copy()
    _sync_results_back_to_raw()
    st.session_state.selected_df = st.session_state.raw_results_df[st.session_state.raw_results_df["✅"] == True].copy()  # noqa
else:
    st.info("No hay resultados aún. Añade o recomiende términos arriba para empezar.")

# =====================================================================
# ======================  SELECCIONADOS  ===============================
# =====================================================================

st.subheader("3) ✅ Tus seleccionados")

def _on_remove_selected(place_id: str):
    if "raw_results_df" in st.session_state and isinstance(st.session_state.raw_results_df, pd.DataFrame) and not st.session_state.raw_results_df.empty:
        mask_raw = st.session_state.raw_results_df["place_id"] == place_id
        if mask_raw.any():
            st.session_state.raw_results_df.loc[mask_raw, "✅"] = False
    if "raw_results_df" in st.session_state and not st.session_state.raw_results_df.empty:
        st.session_state.selected_df = st.session_state.raw_results_df[st.session_state.raw_results_df["✅"] == True].copy()  # noqa
    else:
        st.session_state.selected_df = pd.DataFrame()
    st.session_state.editor_nonce += 1
    st.rerun()

def render_selected_cards(df: pd.DataFrame, cards_per_row: int = 2):
    if df.empty:
        st.info("Marca algunos lugares en la tabla del paso 2 para verlos aquí.")
        return
    st.caption("Pulsa ✖ para quitar un lugar de tus seleccionados (también se desmarcará en la tabla del paso 2).")
    records = df.to_dict("records")
    for i, row in enumerate(records):
        if i % cards_per_row == 0:
            row_cols = st.columns(cards_per_row, gap="small")
        col = row_cols[i % cards_per_row]
        with col:
            with st.container():
                name = row.get("name", "Lugar")
                addr = row.get("address", "")
                rating = row.get("rating", None)
                score = row.get("score", None)
                distm = row.get("distance_m", None)
                place_id = str(row.get("place_id", f"idx_{i}"))

                header_cols = st.columns([0.8, 0.2], gap="small")
                with header_cols[0]:
                    st.markdown(f"**{name}**")
                    sub = addr
                    if rating is not None and str(rating) != "nan":
                        sub += f" · ⭐ {rating}"
                    if score is not None and str(score) != "nan":
                        sub += f" · Ⓢ {score:.3f}"
                    if distm is not None and str(distm) != "nan":
                        sub += f" · 📏 {distm:.0f} m"
                    st.caption(sub)
                with header_cols[1]:
                    st.button(
                        "✖",
                        key=f"rm_sel_{place_id}",
                        help="Quitar este lugar de tus seleccionados",
                        on_click=_on_remove_selected,
                        args=(place_id,)
                    )
                st.markdown("<hr style='margin:6px 0; opacity:0.2;'>", unsafe_allow_html=True)

render_selected_cards(st.session_state.selected_df, cards_per_row=2)

# =====================================================================
# ======================  RUTA FINAL  =================================
# =====================================================================

if not st.session_state.selected_df.empty:
    st.subheader("4) 🗺️ Ruta")
    st.caption(
        "Muestra la ruta usando Google Maps. Este bloque solo construye el enlace/iframe "
        "y Google se encarga de dibujar el mapa. "
        "Para priorizar lugares que 'pillen de camino' mientras eliges, usa el 🧠 Modo inteligente (arriba)."
    )

    st.session_state.route_mode = st.radio(
        "Modo de ruta:",
        ["driving", "walking", "bicycling", "transit"],
        horizontal=True,
        index=["driving","walking","bicycling","transit"].index(st.session_state.route_mode)
    )

    st.session_state.optimize_waypoints = st.checkbox(
        "Optimizar el orden de paradas para una ruta más corta",
        value=st.session_state.optimize_waypoints,
        help="Usa la API de Directions para encontrar el orden óptimo de las paradas (origen = tu dirección actual; destino = la última selección)."
    )

    selected_rows = st.session_state.selected_df.to_dict("records")
    selected_coords = [(float(r["lat"]), float(r["lon"])) for r in selected_rows if pd.notna(r.get("lat")) and pd.notna(r.get("lon"))]

    ordered_waypoints = []
    dest_latlon = None
    total_secs = None

    if st.session_state.optimize_waypoints:
        order_idx, ordered_waypoints, dest_latlon, total_secs = optimize_route_order(
            origin_text=st.session_state.center_address,
            stops_latlon=selected_coords,
            mode=st.session_state.route_mode
        )
        if dest_latlon is None and selected_coords:
            dest_latlon = selected_coords[-1]
    else:
        if len(selected_coords) >= 1:
            dest_latlon = selected_coords[-1]
            ordered_waypoints = selected_coords[:-1]
            total_secs = route_total_seconds(
                origin_text=st.session_state.center_address,
                waypoints=tuple(f"{w[0]},{w[1]}" for w in ordered_waypoints),
                dest_latlon=dest_latlon,
                mode=st.session_state.route_mode
            )

    if total_secs:
        mins = int(round(total_secs / 60.0))
        st.caption(f"Duración estimada total: ~{mins} min (según Google Directions).")

    dest_row = selected_rows[-1] if selected_rows else None

    if st.button("🗺️ Ver ruta en el mapa (iframe)"):
        url = gm_embed_directions_url(
            origin_text=st.session_state.center_address,
            dest_place_id=dest_row.get("place_id") if dest_row else None,
            dest_text=dest_row.get("address") if dest_row else None,
            mode=st.session_state.route_mode,
            waypoints_latlon=ordered_waypoints if ordered_waypoints else None
        )
        st.components.v1.iframe(url, height=480, scrolling=False)

    maps_url = maps_directions_link(
        origin_text=st.session_state.center_address,
        dest_place_id=dest_row.get("place_id") if dest_row else None,
        dest_text=dest_row.get("address") if dest_row else None,
        mode=st.session_state.route_mode,
        waypoints_latlon=ordered_waypoints if ordered_waypoints else None,
        optimize_waypoints=st.session_state.optimize_waypoints
    )
    st.markdown(f"[Abrir en Google Maps ↗]({maps_url})")
