import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from PIL import Image
import cv2
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# MongoDB
from pymongo import MongoClient
from urllib.parse import quote_plus
import pytz

# Configuración MongoDB (NUEVAS CREDENCIALES)
timezone = pytz.timezone('America/Bogota')
usuario = quote_plus("lauratkd16")
clave = quote_plus("fKYKOOnlSOmLCr06")
cluster = "cluster0.hxuwi7t.mongodb.net"
base_datos = "sample_mflix"
uri = f"mongodb+srv://{usuario}:{clave}@{cluster}/?retryWrites=true&w=majority&appName=Cluster0&tlsAllowInvalidCertificates=true"

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client[base_datos]
    coleccion_clima = db["registros_clima"]      # Puedes crear esta colección
    coleccion_fauna = db["catalogo_fauna"]       # Puedes crear esta colección
    mongo_status = "✅ Conectado a MongoDB Atlas"
except Exception as e:
    mongo_status = f"❌ Error al conectar con MongoDB: {e}"

print(mongo_status)  # <-- Esto mostrará el estado en la consola

# Configuración de la página
st.set_page_config(
    page_title="Plataforma de Monitoreo Ambiental",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #4CAF50, #2196F3);
    padding: 1rem;
    border-radius: 10px;
    margin-bottom: 2rem;
}
.metric-card {
    background: white;
    padding: 1rem;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin: 0.5rem 0;
}
.upload-section {
    border: 2px dashed #4CAF50;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown('<div class="main-header"><h1 style="color: white; text-align: center;">🌍 Plataforma Integrada de Monitoreo Ambiental</h1></div>', unsafe_allow_html=True)

# Sidebar para navegación
st.sidebar.title("🔧 Panel de Control")
section = st.sidebar.selectbox(
    "Selecciona una sección:",
    ["📊 Dashboard Principal", "📁 Datos CSV/Satélite", "🌐 Datos IoT ThingSpeak", 
     "🚁 Análisis de Imágenes Drone", "🌧️ Registro Manual Clima", "🐦 Registro de Fauna"]
)

# Funciones auxiliares
@st.cache_data
def load_csv_data(file):
    """Cargar y procesar datos CSV"""
    try:
        df = pd.read_csv(file)
        return df
    except Exception as e:
        st.error(f"Error al cargar CSV: {e}")
        return None

def fetch_thingspeak_data(channel_id, field_id, results=60):
    """Obtener datos de ThingSpeak"""
    try:
        url = f"https://api.thingspeak.com/channels/{channel_id}/fields/{field_id}.json?results={results}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            st.warning(f"No se pudieron obtener datos del campo {field_id}")
            return None
    except Exception as e:
        st.error(f"Error al conectar con ThingSpeak: {e}")
        return None

def analyze_vegetation_colors(image):
    """Analizar colores de vegetación en imagen"""
    try:
        img_array = np.array(image)
        
        # Verificar si la imagen tiene 3 canales (RGB)
        if len(img_array.shape) != 3 or img_array.shape[2] != 3:
            st.error("La imagen debe ser RGB")
            return {}
        
        # Convertir a HSV para mejor detección de verdes
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        
        # Rangos para diferentes tipos de vegetación
        ranges = {
            'Vegetación Sana': ([35, 40, 40], [85, 255, 255]),
            'Vegetación Seca': ([15, 30, 30], [35, 255, 200]),
            'Suelo/Tierra': ([8, 50, 20], [25, 255, 200])
        }
        
        results = {}
        total_pixels = img_array.shape[0] * img_array.shape[1]
        
        for name, (lower, upper) in ranges.items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            percentage = (np.sum(mask > 0) / total_pixels) * 100
            results[name] = percentage
        
        return results
    except Exception as e:
        st.error(f"Error en análisis de vegetación: {e}")
        return {}

# Sección Dashboard Principal
if section == "📊 Dashboard Principal":
    st.header("📊 Dashboard de Monitoreo en Tiempo Real")

    # Contar registros en MongoDB
    try:
        total_fauna = coleccion_fauna.count_documents({})
    except Exception:
        total_fauna = 0
    try:
        total_clima = coleccion_clima.count_documents({})
    except Exception:
        total_clima = 0

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Registros de Fauna", f"{total_fauna}")
    with col2:
        st.metric("Registros de Clima", f"{total_clima}")

    st.subheader("🗺️ Ubicaciones de Monitoreo")

    # --- NUEVO: Obtener datos de MongoDB ---
    try:
        # Fauna (verde)
        fauna_data = list(coleccion_fauna.find({}, {"ubicacion": 1, "fecha": 1, "tipo": 1, "especie": 1, "cantidad": 1, "_id": 0}))
        fauna_map = []
        for f in fauna_data:
            # Intentar extraer lat/lon de la ubicación (espera formato "lat,lon" o "lat lon")
            if "ubicacion" in f and ("," in f["ubicacion"] or " " in f["ubicacion"]):
                parts = f["ubicacion"].replace(",", " ").split()
                try:
                    lat, lon = float(parts[0]), float(parts[1])
                    fauna_map.append({
                        "lat": lat,
                        "lon": lon,
                        "popup": f"🟢 Fauna<br>Especie: {f.get('especie','')}<br>Tipo: {f.get('tipo','')}<br>Cantidad: {f.get('cantidad','')}"
                    })
                except Exception:
                    continue

        # Clima (azul)
        clima_data = list(coleccion_clima.find({}, {"ubicacion": 1, "fecha": 1, "lluvia": 1, "temperatura": 1, "_id": 0}))
        clima_map = []
        for c in clima_data:
            if "ubicacion" in c and ("," in c["ubicacion"] or " " in c["ubicacion"]):
                parts = c["ubicacion"].replace(",", " ").split()
                try:
                    lat, lon = float(parts[0]), float(parts[1])
                    clima_map.append({
                        "lat": lat,
                        "lon": lon,
                        "popup": f"🔵 Clima<br>Lluvia: {c.get('lluvia','')}<br>Temp: {c.get('temperatura','')}°C"
                    })
                except Exception:
                    continue

        # Mostrar mapa con folium
        from streamlit_folium import st_folium
        import folium

        m = folium.Map(location=[4.6097, -74.0817], zoom_start=8, tiles="OpenStreetMap")

        # Puntos de fauna (verde)
        for f in fauna_map:
            folium.CircleMarker(
                location=[f["lat"], f["lon"]],
                radius=7,
                color="green",
                fill=True,
                fill_color="green",
                fill_opacity=0.7,
                popup=folium.Popup(f["popup"], max_width=250)
            ).add_to(m)

        # Puntos de clima (azul)
        for c in clima_map:
            folium.CircleMarker(
                location=[c["lat"], c["lon"]],
                radius=7,
                color="blue",
                fill=True,
                fill_color="blue",
                fill_opacity=0.7,
                popup=folium.Popup(c["popup"], max_width=250)
            ).add_to(m)

        # Leyenda personalizada con texto negro
        legend_html = """
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 180px; height: 70px; 
                    background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
                    border-radius: 8px; padding: 10px;">
        <b style="color:black;">Leyenda</b><br>
        <span style="color:green;">●</span> <span style="color:black;">Fauna</span><br>
        <span style="color:blue;">●</span> <span style="color:black;">Clima</span>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        st_folium(m, width=900, height=500)

    except Exception as e:
        st.warning("No se pudieron mostrar los registros en el mapa. Verifica la conexión a MongoDB y el formato de las ubicaciones.")
        st.text(f"Error: {e}")

# Sección Datos CSV/Satélite
elif section == "📁 Datos CSV/Satélite":
    st.header("🌍 Panel Avanzado Google Earth Engine")
    st.info("Selecciona en el mapa el territorio que deseas explorar y el tipo de datos satelitales que quieres visualizar. Luego, accede al panel avanzado de Google Earth Engine para análisis históricos y visualización detallada.")

    # Mapa interactivo con tiles claros y usabilidad mejorada
    try:
        from streamlit_folium import st_folium
        import folium

        default_lat, default_lon = 4.6097, -74.0817
        lat = st.session_state.get('gee_lat', default_lat)
        lon = st.session_state.get('gee_lon', default_lon)

        m = folium.Map(location=[lat, lon], zoom_start=10, tiles="OpenStreetMap")
        folium.Marker([lat, lon], tooltip="Ubicación seleccionada").add_to(m)
        map_data = st_folium(m, width=900, height=500)

        if map_data and map_data.get('last_clicked'):
            lat = map_data['last_clicked']['lat']
            lon = map_data['last_clicked']['lng']
            st.session_state['gee_lat'] = lat
            st.session_state['gee_lon'] = lon

        st.markdown(f"**Ubicación seleccionada:** {lat:.5f}, {lon:.5f}")

    except Exception as e:
        st.warning("No se pudo cargar el mapa interactivo. Instala `streamlit-folium` y `folium` para habilitar esta función.")
        st.text(f"Error: {e}")

    tipo_dato = st.radio(
        "Selecciona el tipo de datos satelitales a explorar:",
        [
            "🌱 Índices Vegetativos (NDVI, VARI, NDWI, EVI)",
            "🌧️ Precipitaciones y Temperatura",
            "☀️ Radiación Solar",
            "🏠 Conteo de Estructuras (Casas/Edificaciones)"
        ]
    )

    if tipo_dato == "🌱 Índices Vegetativos (NDVI, VARI, NDWI, EVI)":
        st.subheader("🌱 Índices Vegetativos (NDVI, VARI, NDWI, EVI)")
        st.markdown("""
        Visualiza el histórico de índices vegetativos como NDVI, VARI, NDWI y EVI para cualquier zona seleccionada en el mapa.
        [🔗 Ver panel de índices vegetativos en Google Earth Engine](https://code.earthengine.google.com/ed96e4d6474264c5aed574d58a1e615d?hideCode=true)
        """)

    elif tipo_dato == "🌧️ Precipitaciones y Temperatura":
        st.subheader("🌧️ Precipitaciones y Temperatura")
        st.markdown("""
        Consulta el histórico de precipitaciones y temperatura superficial para la zona seleccionada.
        [🔗 Ver panel de precipitaciones y temperatura en Google Earth Engine](https://code.earthengine.google.com/42f6864d239da85005c039039a791b3a?hideCode=true)
        """)

    elif tipo_dato == "☀️ Radiación Solar":
        st.subheader("☀️ Radiación Solar")
        st.markdown("""
        Visualiza el histórico de radiación solar para cualquier punto seleccionado en el mapa.
        [🔗 Ver panel de radiación solar en Google Earth Engine](https://code.earthengine.google.com/eee3a83423627bc8ec346d6d6258b992?hideCode=true)
        """)

    elif tipo_dato == "🏠 Conteo de Estructuras (Casas/Edificaciones)":
        st.subheader("🏠 Conteo de Estructuras (Casas/Edificaciones)")
        st.markdown("""
        Estima la cantidad de estructuras (casas, edificaciones) detectadas automáticamente por satélite en la zona seleccionada.
        [🔗 Ver panel de conteo de estructuras en Google Earth Engine](https://code.earthengine.google.com/166b66f395bb18ae8ddd09eb985ddca0?hideCode=true)
        """)

    st.markdown("---")
    st.caption("Para análisis personalizados, puedes modificar los scripts en Google Earth Engine según tus necesidades. Selecciona la zona de interés en el mapa de GEE y copia las coordenadas para usarlas en los scripts.")

# Sección IoT ThingSpeak
elif section == "🌐 Datos IoT ThingSpeak":
    st.header("🌐 Monitoreo IoT en Tiempo Real")
    
    st.info("Canal ThingSpeak ID: 2928250")
    
    # ==============================
    # NUEVO: Permitir agregar más enlaces de monitoreo ThingSpeak
    # ==============================
    st.subheader("➕ Agregar más enlaces de monitoreo ThingSpeak")
    with st.expander("Agregar enlace de ThingSpeak"):
        new_link = st.text_input("Pega aquí el enlace del gráfico de ThingSpeak (ejemplo: https://thingspeak.mathworks.com/channels/XXXXX/charts/1)")
        if 'thingspeak_links' not in st.session_state:
            st.session_state['thingspeak_links'] = [
                "https://thingspeak.mathworks.com/channels/2928250/charts/1",
                "https://thingspeak.mathworks.com/channels/2928250/charts/2",
                "https://thingspeak.mathworks.com/channels/2928250/charts/3",
                "https://thingspeak.mathworks.com/channels/2928250/charts/4"
            ]
        if st.button("Agregar enlace"):
            if new_link and new_link not in st.session_state['thingspeak_links']:
                st.session_state['thingspeak_links'].append(new_link)
                st.success("Enlace agregado correctamente.")
            elif new_link in st.session_state['thingspeak_links']:
                st.warning("Ese enlace ya fue agregado.")
            else:
                st.warning("Por favor ingresa un enlace válido.")

    # ==============================
    # Botón para actualizar datos
    # ==============================
    if st.button("🔄 Actualizar Datos"):
        with st.spinner("Obteniendo datos de ThingSpeak..."):
            # Configuración de campos
            fields = {
                1: "Sensor 1",
                2: "Sensor 2", 
                3: "Sensor 3",
                4: "Sensor 4"
            }
            # Crear gráficos
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=[f"Campo {i}: {name}" for i, name in fields.items()],
                vertical_spacing=0.1
            )
            for i, (field_id, field_name) in enumerate(fields.items()):
                data = fetch_thingspeak_data("2928250", field_id)
                if data and 'feeds' in data:
                    feeds = data['feeds']
                    timestamps = [feed['created_at'] for feed in feeds if feed['created_at']]
                    values = []
                    for feed in feeds:
                        try:
                            val = float(feed[f'field{field_id}']) if feed[f'field{field_id}'] else 0
                            values.append(val)
                        except (ValueError, TypeError):
                            values.append(0)
                    row = (i // 2) + 1
                    col = (i % 2) + 1
                    fig.add_trace(
                        go.Scatter(x=timestamps, y=values, name=field_name, mode='lines+markers'),
                        row=row, col=col
                    )
            fig.update_layout(height=600, title_text="Datos IoT en Tiempo Real")
            st.plotly_chart(fig, use_container_width=True)
    
    # ==============================
    # Mostrar todos los enlaces de gráficos ThingSpeak
    # ==============================
    st.subheader("🔗 Enlaces Directos a Gráficos")
    for i, link in enumerate(st.session_state['thingspeak_links'], 1):
        st.markdown(f"[📊 Ver Gráfico Campo {i}]({link})")

# Sección Análisis de Imágenes Drone
elif section == "🚁 Análisis de Imágenes Drone":
    st.header("🚁 Análisis de Imágenes de Drone")
    
    uploaded_images = st.file_uploader(
        "📸 Sube imágenes de drone (PNG, JPG, JPEG)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    
    if uploaded_images:
        for uploaded_image in uploaded_images:
            st.subheader(f"🖼️ Análisis: {uploaded_image.name}")
            
            try:
                # Cargar y mostrar imagen
                image = Image.open(uploaded_image)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.image(image, caption="Imagen Original", use_column_width=True)
                
                with col2:
                    st.subheader("🎨 Análisis de Colores RGB")
                    
                    # Convertir a array numpy
                    img_array = np.array(image)
                    
                    if len(img_array.shape) == 3 and img_array.shape[2] >= 3:
                        # Análisis RGB promedio
                        avg_colors = {
                            'Rojo': np.mean(img_array[:,:,0]),
                            'Verde': np.mean(img_array[:,:,1]),
                            'Azul': np.mean(img_array[:,:,2])
                        }
                        
                        for color, value in avg_colors.items():
                            st.metric(f"Promedio {color}", f"{value:.1f}")
                    else:
                        st.error("Imagen no válida para análisis RGB")
                
                # Análisis de vegetación
                st.subheader("🌱 Análisis de Vegetación")
                vegetation_analysis = analyze_vegetation_colors(image)
                
                if vegetation_analysis:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        for veg_type, percentage in vegetation_analysis.items():
                            st.metric(veg_type, f"{percentage:.1f}%")
                    
                    with col2:
                        # Gráfico de distribución
                        fig_pie = px.pie(
                            values=list(vegetation_analysis.values()),
                            names=list(vegetation_analysis.keys()),
                            title="Distribución de Cobertura"
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
            
            except Exception as e:
                st.error(f"Error al procesar imagen {uploaded_image.name}: {e}")

# Sección Registro Manual Clima
elif section == "🌧️ Registro Manual Clima":
    st.header("🌧️ Registro Manual de Condiciones Climáticas")
    st.markdown(f"<span style='color:green'>{mongo_status}</span>", unsafe_allow_html=True)

    st.write("Selecciona la ubicación del reporte haciendo clic en el mapa:")

    from streamlit_folium import st_folium
    import folium

    # Mapa para seleccionar ubicación
    default_lat, default_lon = 4.6097, -74.0817
    clima_map = folium.Map(location=[default_lat, default_lon], zoom_start=10, tiles="OpenStreetMap")
    map_data = st_folium(clima_map, width=700, height=400)

    lat, lon = None, None
    if map_data and map_data.get('last_clicked'):
        lat = map_data['last_clicked']['lat']
        lon = map_data['last_clicked']['lng']
        st.success(f"Ubicación seleccionada: {lat:.5f}, {lon:.5f}")

    with st.form("clima_form"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("📅 Fecha", datetime.now())
            hora = st.time_input("🕐 Hora", datetime.now().time())
        with col2:
            esta_lloviendo = st.selectbox("🌧️ ¿Está lloviendo?", ["No", "Llovizna", "Lluvia ligera", "Lluvia fuerte"])
            intensidad = st.slider("Intensidad de lluvia (1-10)", 1, 10, 1)
            temperatura = st.number_input("🌡️ Temperatura (°C)", min_value=-10, max_value=50, value=20)
        observaciones = st.text_area("📝 Observaciones adicionales")
        foto_clima = st.file_uploader("📷 Foto de las condiciones climáticas", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("💾 Guardar Registro")

        if submitted:
            if lat is None or lon is None:
                st.error("Debes seleccionar una ubicación en el mapa.")
            else:
                registro = {
                    'fecha': str(fecha),
                    'hora': str(hora),
                    'ubicacion': f"{lat},{lon}",
                    'lluvia': esta_lloviendo,
                    'intensidad': int(intensidad),
                    'temperatura': float(temperatura),
                    'observaciones': observaciones,
                    'timestamp': datetime.now(timezone).isoformat()
                }
                try:
                    coleccion_clima.insert_one(registro)
                    st.success("✅ Registro guardado exitosamente en la base de datos!")
                except Exception as e:
                    st.error(f"Error al guardar en MongoDB: {e}")

                st.json(registro)
                if foto_clima:
                    st.image(foto_clima, caption="Foto del clima registrada")

# --- Registro de Fauna ---
elif section == "🐦 Registro de Fauna":
    st.header("🐦 Registro de Fauna y Especies")
    st.markdown(f"<span style='color:green'>{mongo_status}</span>", unsafe_allow_html=True)

    st.write("Selecciona la ubicación del avistamiento haciendo clic en el mapa:")

    # IMPORTANTE: importar folium y st_folium aquí
    from streamlit_folium import st_folium
    import folium

    # Definir coordenadas por defecto
    default_lat, default_lon = 4.6097, -74.0817

    # Mapa para seleccionar ubicación
    fauna_map = folium.Map(location=[default_lat, default_lon], zoom_start=10, tiles="OpenStreetMap")
    map_data_fauna = st_folium(fauna_map, width=700, height=400)

    lat_fauna, lon_fauna = None, None
    if map_data_fauna and map_data_fauna.get('last_clicked'):
        lat_fauna = map_data_fauna['last_clicked']['lat']
        lon_fauna = map_data_fauna['last_clicked']['lng']
        st.success(f"Ubicación seleccionada: {lat_fauna:.5f}, {lon_fauna:.5f}")

    with st.form("fauna_form"):
        col1, col2 = st.columns(2)
        with col1:
            fecha_avistamiento = st.date_input("📅 Fecha de Avistamiento", datetime.now())
            hora_avistamiento = st.time_input("🕐 Hora", datetime.now().time())
        with col2:
            tipo_especie = st.selectbox("🔍 Tipo de Especie", 
                ["Ave", "Mamífero", "Reptil", "Anfibio", "Pez", "Insecto", "Otro"])
            nombre_especie = st.text_input("📛 Nombre de la especie (si se conoce)")
            cantidad = st.number_input("🔢 Cantidad observada", min_value=1, value=1)
        comportamiento = st.multiselect("🎭 Comportamiento observado", 
            ["Alimentándose", "Descansando", "Volando", "Nadando", "Nidificando", 
             "En grupo", "Solitario", "Interacción social"])
        descripcion = st.text_area("📝 Descripción detallada")
        fotos_fauna = st.file_uploader("📸 Fotos de la especie", 
                                     type=["png", "jpg", "jpeg"], 
                                     accept_multiple_files=True)
        condiciones_clima = st.text_input("🌤️ Condiciones climáticas durante el avistamiento")
        submitted_fauna = st.form_submit_button("💾 Guardar Avistamiento")

        if submitted_fauna:
            if lat_fauna is None or lon_fauna is None:
                st.error("Debes seleccionar una ubicación en el mapa.")
            else:
                registro_fauna = {
                    'fecha': str(fecha_avistamiento),
                    'hora': str(hora_avistamiento),
                    'ubicacion': f"{lat_fauna},{lon_fauna}",
                    'tipo': tipo_especie,
                    'especie': nombre_especie,
                    'cantidad': int(cantidad),
                    'comportamiento': comportamiento,
                    'descripcion': descripcion,
                    'condiciones': condiciones_clima,
                    'timestamp': datetime.now(timezone).isoformat()
                }
                try:
                    coleccion_fauna.insert_one(registro_fauna)
                    st.success("✅ Avistamiento registrado exitosamente en la base de datos!")
                except Exception as e:
                    st.error(f"Error al guardar en MongoDB: {e}")

                st.json(registro_fauna)
                if fotos_fauna:
                    st.subheader("📸 Fotos Registradas:")
                    cols = st.columns(min(len(fotos_fauna), 3))
                    for i, foto in enumerate(fotos_fauna):
                        with cols[i % 3]:
                            st.image(foto, caption=f"Foto {i+1}")

# Footer
st.markdown("---")
st.markdown("🌍 **Plataforma de Monitoreo Ambiental** - Desarrollado para conservación e investigación")

# Información adicional en sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ Información del Sistema")
st.sidebar.info("""
**Funcionalidades:**
- ✅ Carga de datos CSV/satelitales
- ✅ Integración IoT ThingSpeak
- ✅ Análisis de imágenes drone
- ✅ Registro manual de clima
- ✅ Catálogo de fauna
- ✅ Dashboard en tiempo real
""")

st.sidebar.markdown("---")
st.sidebar.caption("Versión 2.0 - Junio 2025")