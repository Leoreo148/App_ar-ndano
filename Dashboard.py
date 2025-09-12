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
        "Evaluaciones_Fenologicas", "Fitosanidad", "Mosca_Fruta_Monitoreo", "Riego_Registros"
    ]
    dataframes = {}
    try:
        for tabla in tablas:
            # MODIFICADO: Se ordena por 'Fecha_Evaluacion' o la fecha relevante si existe
            # para asegurar que los últimos registros son los más recientes.
            # Supabase podría no permitir ordenar por 'created_at' en todas las tablas si el campo no existe.
            # Se usará 'Fecha' como un campo genérico, ajústalo si es necesario.
            response = supabase.table(tabla).select("*").order('id', desc=True).execute()
            dataframes[tabla] = pd.DataFrame(response.data)
        return dataframes
    except Exception as e:
        # Se devuelve el error de forma segura para depuración
        st.error(f"Fallo al cargar la tabla '{tabla}': {e}")
        # Se retorna un diccionario vacío para esa tabla para no detener la app
        dataframes[tabla] = pd.DataFrame()
        return dataframes

# --- CARGA Y PROCESAMIENTO PRINCIPAL ---
datos = cargar_todos_los_datos()

if "error" in datos:
    st.error(datos["error"])
    st.stop()

# MODIFICADO: Se corrige el nombre de la tabla para que coincida con la carga.
df_fenologia = datos.get("Evaluaciones_Fenologicas", pd.DataFrame())
df_fitosanidad = datos.get("Fitosanidad", pd.DataFrame())
df_mosca = datos.get("Mosca_Fruta_Monitoreo", pd.DataFrame())
df_fertirriego = datos.get("Riego_Registros", pd.DataFrame())

# --- PROCESAMIENTO DE DATOS (Limpieza y conversión de tipos) ---
# Asegurar que las columnas de fecha existan y sean del tipo correcto
def procesar_fechas(df, nombre_col_fecha):
    if not df.empty and nombre_col_fecha in df.columns:
        df[nombre_col_fecha] = pd.to_datetime(df[nombre_col_fecha], errors='coerce')
    return df

# MODIFICADO: Se procesan las fechas para cada dataframe con su respectiva columna
df_fenologia = procesar_fechas(df_fenologia, 'Fecha_Evaluacion')
df_fitosanidad = procesar_fechas(df_fitosanidad, 'Fecha')
df_mosca = procesar_fechas(df_mosca, 'Fecha')
df_fertirriego = procesar_fechas(df_fertirriego, 'Fecha')


# --- KPIs: MÉTRICAS CLAVE DEL CULTIVO ---
st.header("Métricas Clave (Últimos Registros)")

# Se asegura de ordenar por fecha si la columna existe antes de tomar el último registro
if not df_fertirriego.empty and 'Fecha' in df_fertirriego.columns:
    df_fertirriego = df_fertirriego.sort_values('Fecha', ascending=False)
if not df_fenologia.empty and 'Fecha_Evaluacion' in df_fenologia.columns:
    df_fenologia = df_fenologia.sort_values('Fecha_Evaluacion', ascending=False)
if not df_fitosanidad.empty and 'Fecha' in df_fitosanidad.columns:
    df_fitosanidad = df_fitosanidad.sort_values('Fecha', ascending=False)
if not df_mosca.empty and 'Fecha' in df_mosca.columns:
    df_mosca = df_mosca.sort_values('Fecha', ascending=False)
    
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
        # Se usa iloc[0] por si hay varias evaluaciones en la misma última fecha
        ultima_eval_feno_fecha = df_fenologia['Fecha_Evaluacion'].max()
        ultima_eval_feno = df_fenologia[df_fenologia['Fecha_Evaluacion'] == ultima_eval_feno_fecha]
        diametro_promedio = ultima_eval_feno['diametro_tallo_mm'].mean()
    st.metric("🌱 Diámetro Prom. Tallo", f"{diametro_promedio:.2f} mm", help="Promedio del diámetro del tallo en la última evaluación fenológica.")

# KPI 4: Alerta Sanitaria
with kpi_cols[3]:
    plantas_con_sintomas = 0
    if not df_fitosanidad.empty and 'Datos_Enfermedades' in df_fitosanidad.columns:
        # Usamos el primer registro que ya está ordenado por fecha
        ultima_eval_fito = df_fitosanidad.iloc[0]
        if ultima_eval_fito['Datos_Enfermedades']:
            datos_enfermedades = pd.DataFrame(ultima_eval_fito['Datos_Enfermedades'])
            if not datos_enfermedades.empty:
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

# --- NUEVO: ESTRUCTURA DE PESTAÑAS PARA ORGANIZAR EL ANÁLISIS ---
tab1, tab2 = st.tabs(["📊 Análisis Fenológico por Hilera", "📈 Tendencias Generales"])

# --- NUEVO: PESTAÑA 1 - WIDGET DE ANÁLISIS FENOLÓGICO DETALLADO ---
with tab1:
    st.header("Análisis de Variabilidad Fenológica por Hilera")
    
    if df_fenologia.empty:
        st.warning("No hay datos de evaluaciones fenológicas para analizar.")
    else:
        # --- FILTROS INTERACTIVOS ---
        filter_cols = st.columns(3)
        
        with filter_cols[0]:
            # Filtro 1: Seleccionar la Hilera
            hileras_unicas = sorted(df_fenologia['Hilera'].unique())
            hilera_seleccionada = st.selectbox("1. Seleccione la Hilera", hileras_unicas)
        
        # Filtrar el dataframe por la hilera seleccionada para los siguientes filtros
        df_filtrado_hilera = df_fenologia[df_fenologia['Hilera'] == hilera_seleccionada]
        
        with filter_cols[1]:
            # Filtro 2: Seleccionar la Fecha (dependiente de la hilera)
            fechas_disponibles = sorted(df_filtrado_hilera['Fecha_Evaluacion'].dt.date.unique(), reverse=True)
            fecha_seleccionada = st.selectbox("2. Seleccione la Fecha de Evaluación", fechas_disponibles)

        with filter_cols[2]:
            # Filtro 3: Seleccionar la Métrica a visualizar
            # IMPORTANTE: Asegúrate que estos nombres de columna existan en tu tabla 'Evaluaciones_Fenologicas'
            metricas_disponibles = {
                'Altura de Planta (cm)': 'Altura_Planta_cm',
                'Número de Brotes': 'Numero_Brotes',
                'Número de Yemas': 'Numero_Yemas',
                'Diámetro de Tallo (mm)': 'diametro_tallo_mm'
            }
            metrica_display = st.selectbox("3. Seleccione la Métrica a Graficar", options=list(metricas_disponibles.keys()))
            metrica_seleccionada_col = metricas_disponibles[metrica_display]

        st.divider()

        # --- APLICAR FILTROS Y MOSTRAR DATOS ---
        
        # Convertir la fecha seleccionada de nuevo a datetime para filtrar correctamente
        fecha_seleccionada_dt = pd.to_datetime(fecha_seleccionada)
        
        df_final_filtrado = df_filtrado_hilera[df_filtrado_hilera['Fecha_Evaluacion'].dt.date == fecha_seleccionada]
        
        col_tabla, col_grafico = st.columns(2)

        with col_tabla:
            st.subheader(f"Datos Registrados para la Hilera {hilera_seleccionada} el {fecha_seleccionada}")
            # Ordenar por número de planta para que la tabla sea fácil de leer
            df_display = df_final_filtrado.sort_values(by='Numero_Planta').reset_index(drop=True)
            st.dataframe(df_display)

        with col_grafico:
            st.subheader(f"Variabilidad de '{metrica_display}'")

            # Asegurarse de que la columna de la métrica y la planta existan
            if metrica_seleccionada_col in df_final_filtrado.columns and 'Numero_Planta' in df_final_filtrado.columns:
                 # Graficar la variabilidad dentro de la hilera
                fig_variabilidad = px.line(
                    df_final_filtrado.sort_values(by='Numero_Planta'), 
                    x='Numero_Planta', 
                    y=metrica_seleccionada_col,
                    title=f"Tendencia de '{metrica_display}' en la Hilera {hilera_seleccionada}",
                    labels={
                        "Numero_Planta": "Número de Planta en la Hilera",
                        metrica_seleccionada_col: metrica_display
                    },
                    markers=True
                )
                fig_variabilidad.update_layout(xaxis_title="Número de Planta", yaxis_title=metrica_display)
                st.plotly_chart(fig_variabilidad, use_container_width=True)
            else:
                st.error(f"La métrica '{metrica_seleccionada_col}' o 'Numero_Planta' no se encontró en los datos. Revisa los nombres de las columnas.")


# --- MODIFICADO: PESTAÑA 2 - GRÁFICOS DE TENDENCIAS GENERALES ---
with tab2:
    st.header("Análisis de Tendencias Generales del Fundo")
    gcol1, gcol2 = st.columns(2)

    with gcol1:
        st.subheader("📈 Evolución de Calidad del Fertirriego")
        if not df_fertirriego.empty and 'Fecha' in df_fertirriego.columns:
            df_fert_sorted = df_fertirriego.sort_values(by='Fecha')
            fig_fert = px.line(df_fert_sorted, x='Fecha', y=['pH_final', 'CE_final'], title="Tendencia de pH y CE",
                               labels={"value": "Valor Medido", "variable": "Parámetro"}, markers=True)
            st.plotly_chart(fig_fert, use_container_width=True)
        else:
            st.info("No hay suficientes datos de fertirriego para mostrar un gráfico.")

    with gcol2:
        st.subheader("🌱 Evolución del Crecimiento Vegetativo")
        if not df_fenologia.empty and 'Fecha_Evaluacion' in df_fenologia.columns:
            # MODIFICADO: Agrupando por 'Fecha_Evaluacion' y usando las columnas correctas
            df_feno_agg = df_fenologia.groupby(df_fenologia['Fecha_Evaluacion'].dt.date).agg(
                diametro_promedio=('diametro_tallo_mm', 'mean'),
                brotes_promedio=('Numero_Brotes', 'mean') # Asegúrate que 'Numero_Brotes' existe
            ).reset_index().sort_values(by='Fecha_Evaluacion')
            
            fig_feno = px.line(df_feno_agg, x='Fecha_Evaluacion', y=['diametro_promedio', 'brotes_promedio'], title="Crecimiento Promedio de las Plantas",
                               labels={"value": "Valor Promedio", "variable": "Métrica", "Fecha_Evaluacion": "Fecha"}, markers=True)
            st.plotly_chart(fig_feno, use_container_width=True)
        else:
            st.info("No hay suficientes datos de fenología para mostrar un gráfico.")

    st.divider()
    st.subheader("🪰 Capturas de Mosca de la Fruta (Últimos 30 días)")
    if not df_mosca.empty and 'Fecha' in df_mosca.columns:
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
