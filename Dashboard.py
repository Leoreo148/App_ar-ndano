import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard General", page_icon="📊", layout="wide")
st.title("📊 Dashboard General del Cultivo de Arándano")
st.write("Visión integral del estado del cultivo, basada en los datos de fenología, sanidad, riego y nutrición.")

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

# --- FUNCIÓN DE CARGA DE DATOS DE TODOS LOS MÓDULOS ---
@st.cache_data(ttl=300) # Cachear los datos por 5 minutos
def cargar_todos_los_datos():
    if not supabase:
        return { "error": "No se pudo conectar a Supabase." }
    
    tablas = [
        "Fenología", "Fitosanidad", "Mosca_Fruta_Monitoreo", "Riego_Registros""
    ]
    dataframes = {}
    try:
        for tabla in tablas:
            response = supabase.table(tabla).select("*").order('created_at', desc=True).execute()
            dataframes[tabla] = pd.DataFrame(response.data)
        return dataframes
    except Exception as e:
        return { "error": f"Fallo al cargar la tabla {tabla}: {e}" }

# --- CARGA Y PROCESAMIENTO PRINCIPAL ---
datos = cargar_todos_los_datos()

if "error" in datos:
    st.error(datos["error"])
    st.stop()

# Asignar DataFrames a variables para claridad
df_fenologia = datos.get("Fenología", pd.DataFrame())
df_fitosanidad = datos.get("Fitosanidad", pd.DataFrame())
df_mosca = datos.get("Mosca_Fruta_Monitoreo", pd.DataFrame())
df_fertirriego = datos.get("Riego_Registros", pd.DataFrame())

# Convertir columnas de fecha para asegurar el tipo correcto
for df in [df_fenologia, df_fitosanidad, df_mosca, df_fertirriego]:
    if not df.empty and 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'])

# --- KPIs: MÉTRICAS CLAVE DEL CULTIVO ---
st.header("Métricas Clave (Últimos Registros)")
kpi_cols = st.columns(5)

# KPI 1: pH del último fertirriego
with kpi_cols[0]:
    ph_ultimo = df_fertirriego['pH_final'].iloc[0] if not df_fertirriego.empty else 0
    st.metric("💧 pH Último Fertirriego", f"{ph_ultimo:.2f}", help="El pH de la solución nutritiva es crítico para la absorción de nutrientes. Rango ideal: 4.5 - 5.5")

# KPI 2: CE del último fertirriego
with kpi_cols[1]:
    ce_ultima = df_fertirriego['CE_final'].iloc[0] if not df_fertirriego.empty else 0
    st.metric("⚡ CE Último Fertirriego", f"{ce_ultima:.2f} dS/m", help="La Conductividad Eléctrica mide la salinidad. Ideal < 1.0 dS/m.")

# KPI 3: Crecimiento Vegetativo (Diámetro del Tallo)
with kpi_cols[2]:
    diametro_promedio = 0
    if not df_fenologia.empty:
        ultima_eval_feno = df_fenologia[df_fenologia['Fecha'] == df_fenologia['Fecha'].max()]
        diametro_promedio = ultima_eval_feno['diametro_tallo_mm'].mean()
    st.metric("🌱 Diámetro Prom. Tallo", f"{diametro_promedio:.2f} mm", help="Promedio del diámetro del tallo en la última evaluación fenológica.")

# KPI 4: Alerta Sanitaria
with kpi_cols[3]:
    plantas_con_sintomas = 0
    if not df_fitosanidad.empty:
        ultima_eval_fito = df_fitosanidad[df_fitosanidad['Fecha'] == df_fitosanidad['Fecha'].max()].iloc[0]
        datos_enfermedades = pd.DataFrame(ultima_eval_fito['Datos_Enfermedades'])
        if not datos_enfermedades.empty:
            # Suma todas las columnas de severidad/incidencia y cuenta cuántas plantas tienen un valor > 0
            cols_sintomas = [col for col in datos_enfermedades.columns if col not in ['Planta']]
            plantas_con_sintomas = datos_enfermedades[cols_sintomas].sum(axis=1).gt(0).sum()
    st.metric("🔬 Plantas con Síntomas", f"{plantas_con_sintomas}", help="Número de plantas con alguna enfermedad registrada en la última evaluación.")

# KPI 5: Alerta Mosca de la Fruta
with kpi_cols[4]:
    mtd_promedio = 0
    if not df_mosca.empty:
        df_mosca_semana = df_mosca[df_mosca['Fecha'] >= (datetime.now() - timedelta(days=7))]
        if not df_mosca_semana.empty:
            total_capturas = df_mosca_semana[['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta']].sum().sum()
            num_trampas = df_mosca_semana['Numero_Trampa'].nunique()
            mtd_promedio = total_capturas / num_trampas / 7 if num_trampas > 0 else 0
    st.metric("🪰 MTD Semanal", f"{mtd_promedio:.2f}", help="Promedio de Moscas por Trampa por Día en la última semana.")

st.divider()

# --- GRÁFICOS Y VISUALIZACIONES ---
st.header("Análisis de Tendencias")
gcol1, gcol2 = st.columns(2)

with gcol1:
    st.subheader("📈 Evolución de Calidad del Fertirriego")
    if not df_fertirriego.empty:
        df_fert_sorted = df_fertirriego.sort_values(by='Fecha')
        fig_fert = px.line(df_fert_sorted, x='Fecha', y=['pH_final', 'CE_final'], title="Tendencia de pH y CE",
                           labels={"value": "Valor Medido", "variable": "Parámetro"}, markers=True)
        st.plotly_chart(fig_fert, use_container_width=True)
    else:
        st.info("No hay suficientes datos de fertirriego para mostrar un gráfico.")

with gcol2:
    st.subheader("🌱 Evolución del Crecimiento Vegetativo")
    if not df_fenologia.empty:
        df_feno_agg = df_fenologia.groupby('Fecha').agg(
            diametro_promedio=('diametro_tallo_mm', 'mean'),
            brotes_promedio=('numero_brotes_nuevos', 'mean')
        ).reset_index().sort_values(by='Fecha')
        
        fig_feno = px.line(df_feno_agg, x='Fecha', y=['diametro_promedio', 'brotes_promedio'], title="Crecimiento Promedio de las Plantas",
                           labels={"value": "Valor Promedio", "variable": "Métrica"}, markers=True)
        st.plotly_chart(fig_feno, use_container_width=True)
    else:
        st.info("No hay suficientes datos de fenología para mostrar un gráfico.")

st.divider()
st.subheader("🪰 Capturas de Mosca de la Fruta (Últimos 30 días)")
if not df_mosca.empty:
    df_mosca_mes = df_mosca[df_mosca['Fecha'] >= (datetime.now() - timedelta(days=30))]
    if not df_mosca_mes.empty:
        df_mosca_agg = df_mosca_mes.groupby(pd.Grouper(key='Fecha', freq='W-MON')).agg({
            'Ceratitis_capitata': 'sum',
            'Anastrepha_fraterculus': 'sum',
            'Anastrepha_distinta': 'sum'
        }).reset_index()
        df_mosca_melt = df_mosca_agg.melt(id_vars='Fecha', var_name='Especie', value_name='Capturas')
        
        fig_mosca = px.bar(df_mosca_melt, x='Fecha', y='Capturas', color='Especie', title="Total de Capturas Semanales por Especie",
                           labels={"Fecha": "Semana de"})
        st.plotly_chart(fig_mosca, use_container_width=True)
    else:
        st.info("No hay capturas de mosca en los últimos 30 días.")
else:
    st.info("Aún no hay registros de monitoreo de mosca.")