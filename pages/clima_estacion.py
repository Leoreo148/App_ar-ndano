import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, time # Importar 'time'
from supabase import create_client 
import pytz 
import os 
import re 

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Estación Meteorológica", page_icon="🌦️", layout="wide")

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

# --- ZONA HORARIA DE PERÚ ---
try:
    TZ_PERU = pytz.timezone('America/Lima')
except ImportError:
    st.error("Se necesita la librería 'pytz'. Instálala con: pip install pytz")
    TZ_PERU = None

# ======================================================================
# SECCIÓN DE CARGA DE DATOS
# ======================================================================
st.title("🌦️ Dashboard de Estación Meteorológica")
st.write("Sube el archivo de datos (`.txt` o `.xlsx`) de la estación para ingestar y analizar los datos climáticos.")

# --- UPLOADER DE ARCHIVO ---
uploaded_file = st.file_uploader(
    "Sube tu archivo de datos de la estación (.txt o .xlsx)", 
    type=["txt", "xlsx"],
    help="Sube el archivo .txt (tabulado) o .xlsx. El script se encargará de limpiarlo y subirlo a Supabase."
)

# Mapa de columnas del .txt a la base de datos
COLUMNS_MAP = {
    'Date': 'fecha', # Esta es temporal, se eliminará
    'Time': 'hora',  # Esta es temporal, se eliminará
    'Out Hum': 'humedad_out',
    'Out Temp': 'temperatura_out',
    'Wind Speed': 'velocidad_viento',
    'Wind Dir': 'direccion_viento',
    'Solar Rad.': 'radiacion_solar',
    'UV Index': 'uv_index',
    'Rain Rate': 'lluvia_rate'
}

if uploaded_file is not None:
    try:
        with st.spinner(f"Procesando archivo '{uploaded_file.name}'... Esto puede tardar varios minutos."):
            
            df = None
            is_txt = False
            
            if uploaded_file.name.endswith('.txt'):
                st.info("Detectado archivo .txt. Leyendo con separador de tabulación...")
                df = pd.read_csv(uploaded_file, sep='\t', header=1, dtype=str)
                is_txt = True
            
            elif uploaded_file.name.endswith('.xlsx'):
                st.info("Detectado archivo .xlsx. Leyendo la primera hoja...")
                df = pd.read_excel(uploaded_file, header=1)
                is_txt = False
            
            else:
                st.error("Tipo de archivo no soportado. Por favor sube .txt o .xlsx")
                st.stop()
            
            if df is None or df.empty:
                st.warning("El archivo está vacío o no se pudo leer.")
                st.stop()

            # 2. Renombrar las columnas para que coincidan con el MAPA
            df = df.rename(columns=COLUMNS_MAP)
            
            # --- [CORRECCIÓN CRÍTICA] ---
            # Eliminar las MILES de filas vacías que lee de Excel
            # Esto evita que se suban 10,000 registros 'null' a Supabase
            df = df.dropna(subset=['fecha', 'hora'])
            # --- FIN DE LA CORRECCIÓN ---

            # Si después de limpiar no queda nada, nos detenemos.
            if df.empty:
                st.warning("El archivo se leyó, pero no se encontraron filas con datos de 'Date' y 'Time'.")
                st.stop()

            # 3. Limpiar datos no numéricos ('---' -> NaN)
            numeric_cols = [
                'temperatura_out', 'humedad_out', 'velocidad_viento', 
                'radiacion_solar', 'uv_index', 'lluvia_rate'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 4. Combinar 'fecha' y 'hora' en un 'timestamp'
            if 'fecha' not in df.columns or 'hora' not in df.columns:
                st.error("El archivo no contiene las columnas 'Date' o 'Time' esperadas en la cabecera.")
                st.stop()
            
            if is_txt:
                st.write("Procesando timestamp para formato TXT...")
                fecha_hora_str = df['fecha'] + ' ' + df['hora']
                df['timestamp'] = pd.to_datetime(fecha_hora_str, format='%d/%m/%y %H:%M')
            else:
                st.write("Procesando timestamp para formato XLSX...")
                df['timestamp'] = df.apply(
                    lambda row: datetime.combine(
                        row['fecha'].date(),
                        row['hora']
                    ), 
                    axis=1
                )

            # 5. Seleccionar solo las columnas que necesitamos para Supabase
            columnas_para_subir = ['timestamp'] + [col for col in COLUMNS_MAP.values() if col not in ['fecha', 'hora']]
            columnas_existentes = [col for col in columnas_para_subir if col in df.columns]
            df_final = df[columnas_existentes]
            
            # 6. Convertir Timestamps a string ISO para Supabase (JSON)
            df_final['timestamp'] = df_final['timestamp'].apply(lambda x: x.isoformat())

            # 7. Reemplazar 'NaN' (de Python) con 'None' (de JSON)
            df_final = df_final.astype(object).where(pd.notnull(df_final), None)

            # 8. Convertir a un formato de diccionario para Supabase
            records_to_insert = df_final.to_dict('records')
            
            if not records_to_insert:
                st.warning("El archivo no contenía datos válidos para procesar.")
            else:
                st.write(f"Se procesaron {len(records_to_insert)} registros. Subiendo a Supabase...")
                
                # 9. Subir a Supabase con 'upsert'
                response = supabase.table('Datos_Estacion_Clima').upsert(
                    records_to_insert, 
                    on_conflict='timestamp'
                ).execute()
                
                st.success(f"¡Éxito! Se han subido y/o actualizado {len(records_to_insert)} registros en la base de datos.")
                st.balloons()
                st.cache_data.clear()

    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")
        st.warning("Verifica el formato del archivo. ¿La cabecera está en la fila 2 (header=1)?")
        st.info("Si es un TXT, verifica el formato de fecha (ej: 'dd/%m/%y %H:%M').")

st.divider()

# ======================================================================
# SECCIÓN DE VISUALIZACIÓN DE DATOS
# ======================================================================
st.header("Visualización de Datos Climáticos")

@st.cache_data(ttl=600) # Cachear datos por 10 minutos
def cargar_datos_climaticos(start_date, end_date):
    if not supabase:
        st.error("No hay conexión con Supabase.")
        return pd.DataFrame()
    try:
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()
        
        response = supabase.table('Datos_Estacion_Clima') \
                           .select("*") \
                           .gte('timestamp', start_iso) \
                           .lte('timestamp', end_iso) \
                           .order('timestamp', desc=False) \
                           .execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            cols_to_convert = ['velocidad_viento', 'humedad_out', 'radiacion_solar', 'temperatura_out', 'uv_index', 'lluvia_rate']
            for col in cols_to_convert:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar datos del historial: {e}")
        return pd.DataFrame()

# --- Selectores de Fecha ---
today = datetime.now(TZ_PERU).date()
col_f1, col_f2 = st.columns(2)
with col_f1:
    start_date = st.date_input("Fecha de Inicio", today - pd.Timedelta(days=7), max_value=today)
with col_f2:
    end_date = st.date_input("Fecha de Fin", today, min_value=start_date, max_value=today)

start_datetime = datetime.combine(start_date, datetime.min.time()).astimezone(TZ_PERU)
end_datetime = datetime.combine(end_date, datetime.max.time()).astimezone(TZ_PERU)

df_datos = cargar_datos_climaticos(start_datetime, end_datetime)

if df_datos.empty:
    st.info("No se encontraron datos para el rango de fechas seleccionado. Sube un archivo o ajusta las fechas.")
else:
    st.success(f"Mostrando {len(df_datos)} registros por minuto entre {start_date.strftime('%d/%m')} y {end_date.strftime('%d/%m')}.")
    
    # --- Preparar datos para gráficos ---
    df_plot = df_datos.set_index('timestamp')
    df_hourly = df_plot.resample('H').mean(numeric_only=True).reset_index()
    df_wind_dir = df_plot['direccion_viento'].value_counts().reset_index()
    df_wind_dir.columns = ['direccion', 'conteo']

    # --- Gráficos ---
    st.subheader("Tendencias Climáticas (Promedios por Hora)")
    
    gcol1, gcol2, gcol3 = st.columns(3)
    
    with gcol1:
        fig_temp = px.line(df_hourly, x='timestamp', y='temperatura_out',
                             title='Temperatura Exterior (Promedio por Hora)',
                             labels={'temperatura_out': 'Temp (°C)', 'timestamp': 'Fecha y Hora'})
        fig_temp.update_traces(line=dict(color='red'))
        st.plotly_chart(fig_temp, use_container_width=True)

    with gcol2:
        fig_viento = px.line(df_hourly, x='timestamp', y='velocidad_viento',
                             title='Velocidad del Viento (Promedio por Hora)',
                             labels={'velocidad_viento': 'Velocidad (km/h o m/s)', 'timestamp': 'Fecha y Hora'})
        fig_viento.update_traces(line=dict(color='blue'))
        st.plotly_chart(fig_viento, use_container_width=True)

    with gcol3:
        fig_humedad = px.line(df_hourly, x='timestamp', y='humedad_out',
                               title='Humedad Exterior (Promedio por Hora)',
                               labels={'humedad_out': 'Humedad (%)', 'timestamp': 'Fecha y Hora'})
        fig_humedad.update_traces(line=dict(color='green'))
        st.plotly_chart(fig_humedad, use_container_width=True)

    st.subheader("Otras Métricas")
    gcol4, gcol5 = st.columns(2)

    with gcol4:
        fig_radiacion = px.line(df_hourly, x='timestamp', y='radiacion_solar',
                                 title='Radiación Solar (Promedio por Hora)',
                                 labels={'radiacion_solar': 'Radiación (W/m²)', 'timestamp': 'Fecha y Hora'})
        fig_radiacion.update_traces(line=dict(color='orange'))
        st.plotly_chart(fig_radiacion, use_container_width=True)

    with gcol5:
        fig_dir_viento = px.bar(df_wind_dir, x='direccion', y='conteo',
                                 title='Frecuencia Dirección del Viento',
                                 labels={'conteo': 'Número de Registros', 'direccion': 'Dirección'})
        st.plotly_chart(fig_dir_viento, use_container_width=True)

    st.subheader("Datos Crudos (Tabla)")
    st.dataframe(df_datos, use_container_width=True)