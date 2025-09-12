import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- Configuración de la Página ---
st.set_page_config(page_title="Fenología del Arándano", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica del Arándano")
st.write("Registre las mediciones de crecimiento y estado para cada planta de la hilera seleccionada.")

# --- Archivo de Configuración (Simulado) ---
# En un proyecto más grande, esto podría estar en un archivo config.py
HILERAS = {
    'Hilera 1 (21 Emerald)': 21,
    'Hilera 2 (23 Biloxi/Emerald)': 23,
    'Hilera 3 (22 Biloxi)': 22
}
ETAPAS_FENOLOGICAS = [
    'Yema Hinchada', 'Punta Verde', 'Salida de Hojas', 
    'Hojas Extendidas', 'Inicio de Floración', 'Plena Flor', 
    'Caída de Pétalos', 'Fruto Verde', 'Pinta', 'Cosecha'
]

# --- Conexión a Supabase ---
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

# --- Funciones de Datos ---
@st.cache_data(ttl=60)
def cargar_fenologia_supabase():
    """Carga el historial de evaluaciones desde la tabla Fenologia_Arandano."""
    if supabase:
        try:
            response = supabase.table('Fenologia_Arandano').select("*").order('Fecha', desc=True).execute()
            df = pd.DataFrame(response.data)
            if not df.empty:
                df['Fecha'] = pd.to_datetime(df['Fecha'])
            return df
        except Exception as e:
            st.error(f"Error al cargar el historial de Supabase: {e}")
    return pd.DataFrame()

# --- Interfaz de Registro ---
with st.expander("➕ Registrar Nueva Evaluación por Planta", expanded=True):
    with st.form("nueva_evaluacion_form"):
        st.subheader("1. Datos Generales de la Jornada")
        col1, col2 = st.columns(2)
        with col1:
            hilera_seleccionada = st.selectbox('Seleccione la Hilera a Evaluar:', options=list(HILERAS.keys()))
        with col2:
            fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())

        num_plantas = HILERAS[hilera_seleccionada]
        st.subheader(f"2. Ingrese los datos para las {num_plantas} plantas de la '{hilera_seleccionada}'")

        # Crear una estructura para guardar los datos de cada planta
        datos_plantas = []
        for i in range(num_plantas):
            st.markdown(f"--- \n **Planta {i+1}**")
            cols_planta = st.columns(5)
            with cols_planta[0]:
                etapa = st.selectbox("Etapa Fenológica", ETAPAS_FENOLOGICAS, key=f"etapa_{i}")
            with cols_planta[1]:
                altura = st.number_input("Altura (cm)", min_value=0.0, format="%.2f", key=f"altura_{i}")
            with cols_planta[2]:
                brotes = st.number_input("N° Brotes", min_value=0, step=1, key=f"brotes_{i}")
            with cols_planta[3]:
                yemas = st.number_input("N° Yemas", min_value=0, step=1, key=f"yemas_{i}")
            with cols_planta[4]:
                productiva = st.checkbox("¿Productiva?", key=f"prod_{i}")
            
            datos_plantas.append({
                'Fecha': fecha_evaluacion.strftime("%Y-%m-%d"),
                'Hilera': hilera_seleccionada,
                'Numero_de_Planta': i + 1,
                'Etapa_Fenologica': etapa,
                'Altura_Planta_cm': altura,
                'Numero_Brotes': brotes,
                'Numero_Yemas': yemas,
                'Es_Productiva': productiva
            })

        submitted = st.form_submit_button("✅ Guardar Evaluación Completa")
        if submitted:
            if supabase:
                try:
                    # Filtrar registros que no fueron llenados (donde todo es cero o por defecto)
                    registros_validos = [
                        reg for reg in datos_plantas 
                        if reg['Altura_Planta_cm'] > 0 or reg['Numero_Brotes'] > 0 or reg['Numero_Yemas'] > 0
                    ]
                    if registros_validos:
                        supabase.table('Fenologia_Arandano').insert(registros_validos).execute()
                        st.toast(f"✅ ¡Evaluación de {len(registros_validos)} plantas guardada exitosamente!", icon="🎉")
                        st.cache_data.clear()
                        # No usamos st.rerun() para que el toast sea visible
                    else:
                        st.warning("No se ingresaron datos en ninguna planta.")
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}")
            else:
                st.error("La conexión con Supabase no está disponible.")

# --- Historial y Análisis ---
st.divider()
st.header("📊 Historial y Análisis Fenológico")
df_historial = cargar_fenologia_supabase()

if df_historial is None or df_historial.empty:
    st.info("Aún no hay datos históricos para mostrar.")
else:
    ultima_fecha_evaluacion = df_historial['Fecha'].max().date()
    st.subheader(f"Análisis de la Última Evaluación ({ultima_fecha_evaluacion.strftime('%d/%m/%Y')})")
    df_ultima_eval = df_historial[df_historial['Fecha'].dt.date == ultima_fecha_evaluacion]

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        # Gráfico de Etapas Fenológicas
        df_etapas = df_ultima_eval['Etapa_Fenologica'].value_counts().reset_index()
        df_etapas.columns = ['Etapa_Fenologica', 'Numero_de_Plantas']
        fig_etapas = px.pie(df_etapas, values='Numero_de_Plantas', names='Etapa_Fenologica', 
                            title='Distribución de Etapas Fenológicas', hole=0.3)
        st.plotly_chart(fig_etapas, use_container_width=True)
    
    with col_g2:
        # Gráfico de Plantas Productivas
        df_productivas = df_ultima_eval['Es_Productiva'].value_counts().reset_index()
        df_productivas.columns = ['Es_Productiva', 'Cantidad']
        df_productivas['Es_Productiva'] = df_productivas['Es_Productiva'].map({True: 'Sí', False: 'No'})
        fig_prod = px.bar(df_productivas, x='Es_Productiva', y='Cantidad', 
                          title='Conteo de Plantas Productivas', text_auto=True,
                          labels={'Es_Productiva': '¿Es Productiva?', 'Cantidad': 'Número de Plantas'})
        st.plotly_chart(fig_prod, use_container_width=True)

    st.divider()
    st.subheader("📈 Análisis de Crecimiento a lo Largo del Tiempo")
    
    # Gráfico Comparativo de Hileras
    df_tendencia_altura = df_historial.groupby(['Fecha', 'Hilera'])['Altura_Planta_cm'].mean().reset_index()
    if not df_tendencia_altura.empty:
        fig_altura = px.line(df_tendencia_altura, x='Fecha', y='Altura_Planta_cm', color='Hilera',
                             title='Evolución de Altura Promedio por Hilera', markers=True,
                             labels={'Fecha': 'Fecha de Medición', 'Altura_Planta_cm': 'Altura Promedio (cm)', 'Hilera': 'Hilera'})
        st.plotly_chart(fig_altura, use_container_width=True)
    
    # Historial Detallado
    with st.expander("Ver historial de datos detallado"):
        st.dataframe(df_historial, use_container_width=True)
