import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Análisis de Drenaje", page_icon="🧪", layout="wide")
st.title("🧪 Análisis de Drenaje (Lixiviado)")
st.write("Registre y visualice las mediciones de pH y Conductividad Eléctrica (CE) del agua de drenaje.")

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = init_supabase_connection()

# --- ZONA HORARIA DE PERÚ (SOLUCIÓN AL BUG DE LA HORA) ---
# (Aunque aquí usamos la fecha del selector, es buena práctica tenerlo)
try:
    import pytz
    TZ_PERU = pytz.timezone('America/Lima')
except ImportError:
    st.error("Se necesita la librería 'pytz'. Instálala con: pip install pytz")
    TZ_PERU = None

# ======================================================================
# SECCIÓN 1: FORMULARIO DE INGRESO DE DATOS
# ======================================================================
st.header("Formulario de Registro de Drenaje")

with st.form("drenaje_form"):
    
    col1, col2 = st.columns(2)
    
    with col1:
        fecha_medicion = st.date_input("Fecha de Medición", datetime.now(TZ_PERU) if TZ_PERU else datetime.now())
        # Recordatorio: La Hilera 3 ya no se usa
        sector_seleccionado = st.selectbox("Seleccione la Hilera:", 
                                           options=['Hilera 1 (21 Emerald)', 'Hilera 2 (23 Coco y Cascarilla)'])

    with col2:
        ph_drenaje = st.number_input("pH del Drenaje", min_value=0.0, max_value=14.0, value=6.0, step=0.1, format="%.2f")
        ce_drenaje = st.number_input("CE del Drenaje (dS/m)", min_value=0.0, value=1.5, step=0.1, format="%.2f")
    
    observaciones = st.text_area("Observaciones (Ej: Apariencia del agua, olor, etc.)")
    
    submitted = st.form_submit_button("✅ Guardar Medición")
    
    if submitted:
        if not supabase:
            st.error("Error de conexión con la base de datos.")
        else:
            try:
                datos_para_insertar = {
                    "fecha_medicion": fecha_medicion.strftime("%Y-%m-%d"),
                    "sector": sector_seleccionado,
                    "ph_drenaje": ph_drenaje,
                    "ce_drenaje": ce_drenaje,
                    "observaciones": observaciones
                }
                supabase.table('Drenaje_Registros').insert(datos_para_insertar).execute()
                st.success("¡Medición de drenaje guardada exitosamente!")
                st.balloons()
            except Exception as e:
                st.error(f"Error al guardar en Supabase: {e}")

# ======================================================================
# SECCIÓN 2: HISTORIAL Y GRÁFICOS DE TENDENCIAS
# ======================================================================
st.divider()
st.header("Historial y Tendencias del Drenaje")

# --- Cargar datos del historial ---
@st.cache_data(ttl=300) # Cachear por 5 minutos
def cargar_datos_drenaje():
    if not supabase:
        return pd.DataFrame()
    try:
        response = supabase.table('Drenaje_Registros').select("*").order('fecha_medicion', desc=True).limit(100).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['fecha_medicion'] = pd.to_datetime(df['fecha_medicion'])
        return df
    except Exception as e:
        st.error(f"No se pudieron cargar los datos del historial: {e}")
        return pd.DataFrame()

df_drenaje = cargar_datos_drenaje()

if df_drenaje.empty:
    st.info("Aún no hay registros de mediciones de drenaje.")
else:
    st.write("Últimas mediciones registradas:")
    st.dataframe(df_drenaje, use_container_width=True)

    st.subheader("Tendencias de pH y CE en el Drenaje")
    
    gcol1, gcol2 = st.columns(2)
    
    with gcol1:
        fig_ph = px.line(df_drenaje, x='fecha_medicion', y='ph_drenaje', color='sector', 
                         title="Evolución del pH en Drenaje", markers=True)
        st.plotly_chart(fig_ph, use_container_width=True)

    with gcol2:
        fig_ce = px.line(df_drenaje, x='fecha_medicion', y='ce_drenaje', color='sector', 
                         title="Evolución de la CE (Acumulación de Sales)", markers=True)
        st.plotly_chart(fig_ce, use_container_width=True)
