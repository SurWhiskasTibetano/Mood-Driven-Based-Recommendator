# Recomendador Emocional — Nearby + Rutas con Google Maps

Aplicación en Streamlit que, a partir de un texto sobre el estado emocional del usuario, propone tipos de lugares, los normaliza a palabras clave compatibles con Google Maps Nearby, busca sitios cercanos a una dirección manual, permite seleccionar favoritos y genera una ruta en Google Maps (enlace e iframe). Incluye un Modo inteligente que estima el desvío de ruta al añadir cada candidato y lo etiqueta como genial, muy bien, normal, mal o muy mal.

## Probar la aplicacion

https://surwhiskastibetano-mood-driven-based-recommendator-app-ozhylp.streamlit.app/

---

## Índice
- [Características](#características)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Variables de entorno](#variables-de-entorno)
- [Ejecución](#ejecución)
- [Uso](#uso)
- [Arquitectura y ficheros](#arquitectura-y-ficheros)
- [Flujo de trabajo](#flujo-de-trabajo)
- [Detalles técnicos](#detalles-técnicos)
  - [Normalización y taxonomía](#normalización-y-taxonomía)
  - [Búsqueda Nearby y consolidación](#búsqueda-nearby-y-consolidación)
  - [Scoring](#scoring)
  - [Rutas y Modo inteligente](#rutas-y-modo-inteligente)
  - [Cache y cuotas](#cache-y-cuotas)
- [Límites y buenas prácticas](#límites-y-buenas-prácticas)
- [Solución de problemas](#solución-de-problemas)

---

## Características

- Dirección manual (calle y número) con geocodificación directa e inversa.
- Detección de categoría emocional y mensaje empático.
- Sugerencia de tipos de lugares mediante Gemini 1.5 Flash con salida JSON estricta y fallback sin LLM.
- Normalización de términos a palabras clave compatibles con Google Maps Nearby (sinónimos a canónico).
- Búsqueda Places Nearby con deduplicación por `place_id` y agregación de señales (rating, número de reseñas, foto).
- Ranking por calidad y proximidad al centro de búsqueda.
- Vista de resultados con detalles de cada lugar (foto, rating, reseñas, enlace a Google Maps).
- Selección de candidatos y construcción de ruta con Google Maps (enlace e iframe).
- Modo inteligente para estimar y etiquetar el desvío de ruta por candidato.
- Cache selectiva para reducir latencia y consumo de cuota.

---

## Requisitos

- Python 3.10 o superior
- Dependencias:
  - streamlit
  - googlemaps
  - requests
  - python-dotenv
  - pandas
  - numpy

## Instalación:

pip install streamlit googlemaps requests python-dotenv pandas numpy

## Variables de entorno

Crear un archivo .env en la raíz del proyecto con:

GOOGLE_MAPS_API_KEY=tu_clave_de_google_maps
GEMINI_API_KEY=tu_clave_de_gemini_opcional

Notas:

    GOOGLE_MAPS_API_KEY es obligatoria. Si falta, la aplicación se detiene al arrancar.

    GEMINI_API_KEY es opcional. Si no está o la llamada falla, se usa un fallback curado para el mensaje y los tipos de lugar.

## Ejecución

streamlit run app.py

Uso

    Introduce una dirección en la barra lateral y confirma.

    Ajusta el radio, el filtro de abiertos ahora y la puntuación mínima.

    Describe tu estado de ánimo y pulsa “Recomendar lugares”.

    Revisa los términos sugeridos, añade nuevos si lo necesitas y elimina los que no quieras.

    Explora los resultados cercanos, abre los detalles para ver fotos y reseñas, y marca los que te interesen.

    Activa el Modo inteligente para priorizar lugares que encajen mejor en tu ruta.

    Genera el enlace o el iframe de Google Maps con las paradas seleccionadas, con opción de optimizar el orden.

## Arquitectura y ficheros

- Ficheros:
    - app.py            # Interfaz Streamlit y flujo principal
    - brain.py          # Detección emocional, prompt a Gemini y normalización de sugerencias
    - config.py         # Carga .env, cliente Google Maps, constantes de UI y pesos del scoring
    - maps_io.py        # Utilidades de URLs (embed/link) y Place Details/Photo
    - ranking.py        # Geocoding/Reverse, Nearby con paginación, scoring y filtros
    - routing.py        # Cálculo de rutas, optimización de waypoints e inserción de paradas
    - taxonomy.py       # Taxonomía: sinónimos a canónico, listas curadas y heurísticas

## Tabla de responsabilidades por módulo:
Módulo    Responsabilidad
app.py    UI, estado, orquestación del flujo y vistas
brain.py    Categoría emocional, mensaje empático, sugerencias y normalización
config.py    Claves, cliente googlemaps, constantes (LIST_CONTAINER_HEIGHT_PX, pesos)
maps_io.py    Links/iframes de Maps, Place Details, URL de foto
ranking.py    Nearby con paginación, cálculo de distancias y score compuesto
routing.py    Duración de rutas, optimización, cálculo de desvíos y etiquetado
taxonomy.py    Listas canónicas y mapeos de sinónimos a palabras clave Nearby
## Flujo de trabajo

- Dirección manual: geocodifica a (lat, lon) y fija el centro de búsqueda.
- Texto emocional: con GEMINI_API_KEY, brain.gemini_brain solicita un JSON con category, empathy, place_types.
- Normalización: taxonomy._map_term_to_canon mapea los tipos a palabras clave canónicas aptas para Nearby.
- Nearby: ranking.places_nearby_all busca por cada palabra clave, pagina resultados y deduplica por place_id.
- Scoring: ranking.compute_scores calcula distance_m, normaliza rating y reseñas, y combina con proximidad en un score.
- Resultados: tabla con selección, coincidencias, puntuación, distancia, rating, reseñas y popover de detalles.
- Ruta: con seleccionados, routing.optimize_route_order o routing.route_total_seconds y construcción de enlace/iframe.
- Modo inteligente: routing.compute_multi_stop_detours etiqueta cada candidato con su impacto en la ruta.


## Detalles técnicos
### Normalización y taxonomía

- `taxonomy._map_term_to_canon(term, category_hint)` convierte entradas libres a un vocabulario canónico compatible con Nearby mediante:
  - Coincidencias regex de sinónimos.
  - Coincidencia directa con el vocabulario canónico.
  - Heurística que elimina adjetivos comunes y reintenta.
  - Fallback por emoción con `CANON_BY_EMOTION`.


### Recomendación de coherencia

- Asegurar que todos los canónicos usados en sinónimos existan en `CANON_KEYWORDS`.
- Unificar nombres como *minigolf* frente a *mini golf*.
- Si se usa *templo*, incluirlo también en `CANON_KEYWORDS`.


### Búsqueda Nearby y consolidación

#### ranking.places_nearby_all 
Realiza la búsqueda por keyword dentro de un radio y maneja la paginación con next_page_token (incluye la espera mínima requerida por la API).

#### Deduplicación por place_id 

Combinación de señales:

- Rating máximo observado.
- `user_ratings_total` máximo observado.
- `photo_ref` si no existía.
- Conjunto de términos que coincidieron para mostrar “Coincidió con”.

`maps_io.get_place_details` enriquece con foto, reseñas y URL de Google Maps.

### Scoring

Cálculo del score compuesto:

rating_score   = rating / 5
reviews_score  = log1p(nreseñas) / log1p(max_nreseñas_del_conjunto)
proximity_score= 1 - (distance_m / radius_m)  (recortado a [0,1])

score = (W_RATING * rating_score
       + W_REVIEWS * reviews_score
       + W_PROX    * proximity_score) / (W_RATING + W_REVIEWS + W_PROX)

### Valores por defecto

- `W_RATING = 0.5`
- `W_REVIEWS = 0.3`
- `W_PROX = 0.2`


### Rutas y Modo inteligente

- `routing.optimize_route_order`: utiliza Directions con `optimize_waypoints=True` para reordenar paradas y devuelve duración total.
- `routing.route_total_seconds`: suma de `legs[*].duration.value` en segundos.
- `routing.compute_multi_stop_detours`:
  - Calcula la ruta base (origen = dirección actual; destino = último seleccionado; waypoints = resto).
  - Inserta virtualmente cada candidato, evalúa el mejor caso y calcula:  
    `detour_ratio = (mejor_tiempo - tiempo_base) / tiempo_base`.
  - `label_from_ratio` mapea a genial, muy bien, normal, mal o muy mal.
  - Con muchas paradas, limita posiciones de inserción para contener consumo de cuota.


### Cache y cuotas

- Decoradores `@st.cache_data` en:
  - Place Details: TTL 600 s.
  - Nearby: TTL 300 s.
  - Duraciones y optimización: TTL 180 s.
- El Modo inteligente incrementa las llamadas a Directions.  
  Aplicarlo cuando haya al menos un lugar seleccionado y, si el volumen es grande, limitar el etiquetado a los *top N* por score.


## Límites y buenas prácticas

- Waypoints en Directions tienen límites según plan. Ajustar el número de paradas si te acercas al máximo.
- Si `open_now` no devuelve resultados, la app reintenta sin ese filtro automáticamente.
- Radios grandes favorecen la proximidad relativa; si se busca neutralidad entre radios, considerar funciones de decaimiento por distancia absoluta.
- Para direcciones ambiguas, especificar ciudad y país.


## Solución de problemas

- **Falta `GOOGLE_MAPS_API_KEY`**: la app se detiene con un mensaje en `config.py`. Añade la clave al `.env`.
- **Llamadas a Gemini fallan o no hay clave**: se usa el fallback de taxonomía y mensaje empático.
- **Tabla vacía**: añade términos de lugar o amplía el radio de búsqueda.
- **Etiquetas de ruta vacías**: activa el Modo inteligente y asegúrate de tener al menos un lugar seleccionado.
- **Exceso de paradas**: reduce el número de waypoints o desactiva la optimización.
