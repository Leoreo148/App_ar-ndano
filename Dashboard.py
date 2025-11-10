import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np # Necesario para el heatmap

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard General", page_icon="📊", layout="wide")
st.title("📊 Dashboard General del Cultivo de Arándano")
st.write("Visión integral del estado del cultivo, basada en los datos de fenología, sanidad y clima.")

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

# --- FUNCIÓN DE CARGA DE DATOS DE TODOS LOS MÓDulos ---
@st.cache_data(ttl=300) # Cachear los datos por 5 minutos
def cargar_todos_los_datos():
    if not supabase:
        return { "error": "No se pudo conectar a Supabase." }
    
    # --- MODIFICADO: Añadida la tabla 'Datos_Estacion_Clima' ---
    tablas = [
        "Fenologia_Arandano", "Fitosanidad", "Mosca_Fruta_Monitoreo", "Datos_Estacion_Clima"
    ]
    dataframes = {}
    try:
        for tabla in tablas:
            response = supabase.table(tabla).select("*").order('id', desc=True).execute()
            dataframes[tabla] = pd.DataFrame(response.data)
        return dataframes
    except Exception as e:
        # Si una tabla falla (ej. Riego_Registros ya no existe), no detenemos todo
        st.warning(f"Fallo al cargar la tabla '{tabla}': {e}")
        dataframes[tabla] = pd.DataFrame()
        return dataframes

# --- CARGA Y PROCESAMIENTO PRINCIPAL ---
datos = cargar_todos_los_datos()

if "error" in datos:
    st.error(datos["error"])
    st.stop()

df_fenologia = datos.get("Fenologia_Arandano", pd.DataFrame())
df_fitosanidad = datos.get("Fitosanidad", pd.DataFrame())
df_mosca = datos.get("Mosca_Fruta_Monitoreo", pd.DataFrame())
# --- NUEVO: Cargar datos de clima ---
df_clima = datos.get("Datos_Estacion_Clima", pd.DataFrame())

# --- PROCESAMIENTO DE DATOS (Limpieza y conversión de tipos) ---
def procesar_fechas(df, nombre_col_fecha):
    if not df.empty and nombre_col_fecha in df.columns:
        df[nombre_col_fecha] = pd.to_datetime(df[nombre_col_fecha], errors='coerce')
    return df

df_fenologia = procesar_fechas(df_fenologia, 'Fecha')
df_fitosanidad = procesar_fechas(df_fitosanidad, 'Fecha')
df_mosca = procesar_fechas(df_mosca, 'Fecha')
# --- NUEVO: Procesar fechas de clima ---
df_clima = procesar_fechas(df_clima, 'timestamp')


# --- CORRECCIÓN DEFINITIVA: Asegurar que el número de planta sea numérico ---
if not df_fenologia.empty and 'Numero_de_Planta' in df_fenologia.columns:
    df_fenologia['Numero_de_Planta'] = pd.to_numeric(df_fenologia['Numero_de_Planta'], errors='coerce')
    df_fenologia.dropna(subset=['Numero_de_Planta'], inplace=True)
    df_fenologia['Numero_de_Planta'] = df_fenologia['Numero_de_Planta'].astype(int)

# --- KPIs: MÉTRICAS CLAVE ELIMINADAS ---
# (Se eliminó toda la sección de st.header("Métricas Clave...") y los kpi_cols)
st.divider()

# --- ESTRUCTURA DE PESTAÑAS SIMPLIFICADA ---
# --- MODIFICADO: Eliminada la Tab 2 de Riego ---
tab1, tab2 = st.tabs(["📊 Análisis Fenológico por Hilera", "📈 Tendencias Generales"])

# --- PESTAÑA 1 - WIDGET DE ANÁLISIS FENOLÓGICO DETALLADO ---
with tab1:
    st.header("Análisis de Variabilidad Fenológica por Hilera")
    
    if df_fenologia.empty:
        st.warning("No hay datos de evaluaciones fenológicas para analizar.")
    else:
        with st.expander("🔍 Verificación de Datos Crudos"):
            st.write("Conteo de plantas únicas registradas por cada evaluación:")
            if 'Numero_de_Planta' in df_fenologia.columns:
                df_conteo = df_fenologia.groupby([df_fenologia['Fecha'].dt.date, 'Hilera'])['Numero_de_Planta'].nunique().reset_index()
                df_conteo = df_conteo.rename(columns={'Fecha': 'Fecha de Evaluación', 'Numero_de_Planta': 'N° de Plantas Registradas'})
                st.dataframe(df_conteo, use_container_width=True)
            else:
                st.warning("No se encontró la columna 'Numero_de_Planta' para generar el resumen.")

        filter_cols = st.columns(3)
        
        with filter_cols[0]:
            hileras_unicas = sorted(df_fenologia['Hilera'].unique())
            hilera_seleccionada = st.selectbox("1. Seleccione la Hilera", hileras_unicas)
        
        df_filtrado_hilera = df_fenologia[df_fenologia['Hilera'] == hilera_seleccionada]
        
        with filter_cols[1]:
            fechas_disponibles = sorted(df_filtrado_hilera['Fecha'].dt.date.unique(), reverse=True)
            if fechas_disponibles:
                fecha_seleccionada = st.selectbox("2. Seleccione la Fecha de Evaluación", fechas_disponibles)
            else:
                st.warning("No hay fechas de evaluación para la hilera seleccionada.")
                fecha_seleccionada = None

        with filter_cols[2]:
            metricas_disponibles = {
                'Altura de Planta (cm)': 'Altura_Planta_cm',
                'Número de Brotes': 'Numero_Brotes',
                'Número de Yemas': 'Numero_Yemas',
                'Diámetro de Tallo (mm)': 'diametro_tallo_mm'
            }
            metrica_display = st.selectbox("3. Seleccione la Métrica a Graficar", options=list(metricas_disponibles.keys()))
            col_metrica = metricas_disponibles[metrica_display]

        st.divider()

        if fecha_seleccionada:
            df_visualizacion = df_filtrado_hilera[df_filtrado_hilera['Fecha'].dt.date == fecha_seleccionada]
            col_planta = 'Numero_de_Planta'

            if not df_visualizacion.empty:
                table_col, chart_col = st.columns([0.4, 0.6])
                
                with table_col:
                    st.write(f"Datos para el {fecha_seleccionada.strftime('%d/%m/%Y')}")
                    st.dataframe(df_visualizacion[[col_planta, col_metrica]].sort_values(by=col_planta), use_container_width=True)
                
                with chart_col:
                    if col_metrica not in df_visualizacion.columns:
                        st.error(f"La métrica '{metrica_display}' no se encuentra en los datos.")
                    else:
                        df_visualizacion_sorted = df_visualizacion.sort_values(by=col_planta)
                        
                        fig = px.line(
                            df_visualizacion_sorted,
                            x=col_planta,
                            y=col_metrica,
                            title=f"Tendencia de '{metrica_display}' en la {hilera_seleccionada}",
                            markers=True,
                            labels={col_planta: "Número de Planta", col_metrica: metrica_display}
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos para la fecha seleccionada.")

# --- PESTAÑA 2 - GRÁFICOS DE TENDENCIAS GENERALES ---
# (Este era tu 'tab3', ahora es 'tab2')
with tab2:
    st.header("Análisis de Tendencias Generales")
    
    st.subheader("🌱 Evolución Fenológica")
    if not df_fenologia.empty:
        # Agregamos todas las métricas que necesitamos calcular
        df_feno_agg = df_fenologia.groupby(df_fenologia['Fecha'].dt.date).agg(
            diametro_promedio=('diametro_tallo_mm', 'mean'),
            altura_promedio=('Altura_Planta_cm', 'mean'),
            brotes_promedio=('Numero_Brotes', 'mean'),
            yemas_promedio=('Numero_Yemas', 'mean')
        ).reset_index().sort_values(by='Fecha')
        
        # Creamos el primer gráfico para Crecimiento (Tallo y Altura)
        fig_crecimiento = px.line(df_feno_agg, x='Fecha', y=['diametro_promedio', 'altura_promedio'], 
                                title="Crecimiento Promedio (Tallo y Altura)",
                                labels={"value": "Valor Promedio", "variable": "Métrica"}, markers=True)
        st.plotly_chart(fig_crecimiento, use_container_width=True)
        
        # Creamos el segundo gráfico para Desarrollo (Brotes y Yemas)
        fig_desarrollo = px.line(df_feno_agg, x='Fecha', y=['brotes_promedio', 'yemas_promedio'], 
                               title="Desarrollo Promedio (Brotes y Yemas)",
                               labels={"value": "Valor Promedio", "variable": "Métrica"}, markers=True)
        st.plotly_chart(fig_desarrollo, use_container_width=True)
    else:
        st.info("No hay datos de fenología para mostrar un gráfico.")

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

    # --- NUEVO GRÁFICO: HEATMAP SEMANAL DE TEMPERATURA ---
    st.divider()
    # --- REEMPLAZADO: Gráfico de Heatmap por Gráfico de Barras Agrupado ---
    st.subheader("📊 Comparativa Semanal de Fenología (Promedios)")
    st.write("Compara el promedio de las métricas fenológicas por hilera, semana a semana.")

    if not df_fenologia.empty and 'Fecha' in df_fenologia.columns:
        # 1. Crear la columna 'Semana'
        # 'isocalendar().week' es la forma correcta de obtener el número de semana
        df_fenologia['Semana'] = 'Semana ' + df_fenologia['Fecha'].dt.isocalendar().week.astype(str)
        
        # 2. Selector para la métrica
        metricas_comparacion = {
            'Altura Promedio (cm)': 'Altura_Planta_cm',
            'N° Brotes Promedio': 'Numero_Brotes',
            'N° Yemas Promedio': 'Numero_Yemas',
            'Diámetro Promedio (mm)': 'diametro_tallo_mm'
        }
        metrica_display_sem = st.selectbox(
            "Seleccione la Métrica a Comparar Semanalmente:", 
            options=list(metricas_comparacion.keys()),
            key="selectbox_metrica_semanal"
        )
        col_metrica_sem = metricas_comparacion[metrica_display_sem]

        # 3. Agrupar los datos por Semana e Hilera, y calcular el promedio de la métrica
        if col_metrica_sem in df_fenologia.columns:
            df_sem_agg = df_fenologia.groupby(
                ['Semana', 'Hilera']
            )[col_metrica_sem].mean().reset_index()
            
            # Ordenar por semana para que el gráfico se vea bien
            df_sem_agg = df_sem_agg.sort_values(by='Semana')

            if not df_sem_agg.empty:
                # 4. Crear el Gráfico de Barras Agrupado
                fig_bar_semanal = px.bar(
                    df_sem_agg,
                    x="Semana",
                    y=col_metrica_sem,
                    color="Hilera",         # Agrupa por hilera
                    barmode="group",        # Modo "agrupado"
                    title=f"Comparativa Semanal de {metrica_display_sem}",
                    labels={
                        col_metrica_sem: metrica_display_sem,
                        "Semana": "Semana de Evaluación"
                    },
                    text_auto=".2f" # Muestra el valor en la barra
                )
                fig_bar_semanal.update_traces(textangle=0, textposition="outside")
                st.plotly_chart(fig_bar_semanal, use_container_width=True)
            else:
                st.info(f"No se encontraron datos para la métrica '{metrica_display_sem}'.")
        else:
            st.warning(f"La métrica '{metrica_display_sem}' no existe en los datos de fenología.")
    else:
        st.info("No se cargaron datos de fenología para el análisis semanal.")