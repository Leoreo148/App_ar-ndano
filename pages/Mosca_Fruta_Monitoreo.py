import streamlit as st
import pandas as pd
from datetime import datetime
import json
from io import BytesIO

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client
from streamlit_local_storage import LocalStorage

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Monitoreo de Mosca", page_icon="🪰", layout="wide")
st.title("🪰 Monitoreo de Mosca de la Fruta")
st.write("Inicie una sesión de monitoreo para un sector y registre las capturas de múltiples trampas.")

# --- INICIALIZACIÓN Y CONEXIONES ---
localS = LocalStorage()
# --- (CAMBIO 1) Clave de almacenamiento local actualizada ---
LOCAL_STORAGE_KEY = 'mosca_fruta_arandano_offline'

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

# --- FUNCIONES ADAPTADAS PARA SUPABASE ---
@st.cache_data(ttl=60)
def cargar_monitoreo_supabase():
    """Carga el historial de monitoreo desde la tabla de Supabase."""
    if supabase:
        try:
            # --- (CAMBIO 2) Nombre de tabla actualizado ---
            response = supabase.table('Mosca_Fruta_Monitoreo').select("*").execute()
            df = pd.DataFrame(response.data)
            return df
        except Exception as e:
            st.error(f"Error al cargar el historial de Supabase: {e}")
    return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Monitoreo_Mosca')
    return output.getvalue()

# --- INICIALIZAR MEMORIA DE SESIÓN ---
if 'sesion_monitoreo' not in st.session_state:
    st.session_state.sesion_monitoreo = []
if 'sector_actual' not in st.session_state:
    st.session_state.sector_actual = ""

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Iniciar y Registrar Sesión de Monitoreo"):
    st.subheader("1. Iniciar Sesión")
    col1, col2 = st.columns(2)
    with col1:
        # --- (CAMBIO 3) Selector de sectores predefinidos en lugar de texto libre ---
        sectores_monitoreo = ['Lindero Paltos', 'Lindero Cítricos', 'Cerco Perimétrico Norte', 'Cerco Perimétrico Sur']
        sector_seleccionado = st.selectbox("Seleccione el Sector a monitorear:", options=sectores_monitoreo, key="sector_input")
    with col2:
        fecha_conteo = st.date_input("Fecha de Conteo", datetime.now())

    if sector_seleccionado:
        st.session_state.sector_actual = sector_seleccionado

    if st.session_state.sector_actual:
        st.subheader(f"2. Registrar Trampas para el Sector: **{st.session_state.sector_actual}**")
        with st.form("nueva_trampa_form", clear_on_submit=True):
            numero_trampa = st.text_input("Número o Código de Trampa", placeholder="Ej: T1, 105")
            tipo_trampa = st.selectbox("Tipo de Trampa", ["Levadura", "Panel", "Conetrap"])
            capturas_capitata = st.number_input("Ceratitis capitata", min_value=0, step=1)
            capturas_fraterculus = st.number_input("Anastrepha fraterculus", min_value=0, step=1)
            capturas_distinta = st.number_input("Anastrepha distinta", min_value=0, step=1)
            
            submitted_trampa = st.form_submit_button("➕ Añadir Trampa a la Sesión")
            if submitted_trampa and numero_trampa:
                st.session_state.sesion_monitoreo.append({
                    "Fecha": fecha_conteo.strftime("%Y-%m-%d"), 
                    "Sector": st.session_state.sector_actual, 
                    "Numero_Trampa": numero_trampa, 
                    "Tipo_Trampa": tipo_trampa,
                    "Ceratitis_capitata": capturas_capitata, 
                    "Anastrepha_fraterculus": capturas_fraterculus, 
                    "Anastrepha_distinta": capturas_distinta
                })
            elif submitted_trampa:
                st.warning("Por favor, ingrese el número de la trampa.")

# --- RESUMEN DE LA SESIÓN Y GUARDADO LOCAL ---
if st.session_state.sesion_monitoreo:
    st.divider()
    st.subheader("Resumen de la Sesión Actual")
    st.dataframe(pd.DataFrame(st.session_state.sesion_monitoreo), use_container_width=True)
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if st.button("💾 Guardar Sesión en Dispositivo (Offline)"):
            registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
            registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
            registros_locales.extend(st.session_state.sesion_monitoreo)
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
            st.success(f"¡Sesión con {len(st.session_state.sesion_monitoreo)} registros guardada en el dispositivo!")
            st.session_state.sesion_monitoreo = []
            st.session_state.sector_actual = ""
            st.rerun()
    with col_g2:
        if st.button("❌ Limpiar Sesión Actual"):
            st.session_state.sesion_monitoreo = []
            st.session_state.sector_actual = ""
            st.rerun()

# --- SECCIÓN DE SINCRONIZACIÓN ---
st.divider()
st.subheader("📡 Sincronización con la Base de Datos")

registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** registros de trampas guardados localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora con Supabase"):
        if supabase:
            with st.spinner("Sincronizando..."):
                try:
                    # --- (CAMBIO 2) Nombre de tabla actualizado ---
                    supabase.table('Mosca_Fruta_Monitoreo').insert(registros_pendientes).execute()
                    localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                    st.success("¡Sincronización completada!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}. Sus datos locales están a salvo.")
        else:
            st.error("No se pudo sincronizar. La conexión con Supabase no está disponible.")
else:
    st.info("✅ Todos los registros de monitoreo están sincronizados.")

# --- HISTORIAL Y DESCARGA ---
st.divider()
st.subheader("📚 Historial de Monitoreo Sincronizado")
df_historial = cargar_monitoreo_supabase()

if df_historial is not None and not df_historial.empty:
    df_historial['Fecha'] = pd.to_datetime(df_historial['Fecha'])
    df_historial_ordenado = df_historial.sort_values(by='Fecha', ascending=False)
    
    st.dataframe(df_historial_ordenado, use_container_width=True)
    
    reporte_excel = to_excel(df_historial_ordenado)
    st.download_button(
        label="📥 Descargar Historial Completo",
        data=reporte_excel,
        file_name=f"Historial_Monitoreo_Mosca_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Aún no se ha sincronizado ninguna sesión de monitoreo.")
