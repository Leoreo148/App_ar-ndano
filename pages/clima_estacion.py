import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, time 
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
st.write("Sube el archivo de datos (`.xlsx`) de la estación para ingestar y analizar los datos climáticos.")

# --- UPLOADER DE ARCHIVO ---
uploaded_file = st.file_uploader(
    "Sube tu archivo de datos de la estación (.xlsx)", 
    type=["xlsx"],
    help="Sube el archivo .xlsx. El script se encargará de limpiarlo y subirlo a Supabase."
)

# --- [CAMBIO 1] ---
# Este mapa ya no se usará para renombrar, 
# solo como referencia para las columnas que subiremos.
COLUMNAS_FINALES = [
    'fecha', 'hora', 'humedad_out', 'temperatura_out', 'velocidad_viento', 
    'direccion_viento', 'radiacion_solar', 'uv_index', 'lluvia_rate'
]

if uploaded_file is not None:
    try:
        with st.spinner(f"Procesando archivo '{uploaded_file.name}'... Esto puede tardar varios minutos."):
            
            st.info("Detectado archivo .xlsx. Leyendo la primera hoja...")
            df = pd.read_excel(uploaded_file, header=1)
            
            if df is None or df.empty:
                st.warning("El archivo está vacío o no se pudo leer.")
                st.stop()

            # --- [CAMBIO 2 - CORRECCIÓN CRÍTICA] ---
            # Limpiar primero las filas vacías, usando los nombres de columna originales (por índice)
            # Asumimos que 'Date' es la col 0 y 'Time' es la col 1
            col_fecha_original = df.columns[0]
            col_hora_original = df.columns[1]
            df = df.dropna(subset=[col_fecha_original, col_hora_original])

            if df.empty:
                st.warning("El archivo se leyó, pero no se encontraron filas con datos de 'Date' y 'Time'.")
                st.stop()
                
            st.write(f"Encontrados {len(df)} registros con datos. Procesando...")

            # --- [CAMBIO 3 - RENOMBRADO POR POSICIÓN] ---
            # Tomar los nombres de columna actuales
            current_cols = df.columns.tolist()
            
            # Verificar que tengamos suficientes columnas
            if len(current_cols) < 9:
                st.error(f"Error: El archivo solo tiene {len(current_cols)} columnas, se esperaban al menos 9 (Date, Time, Temp, Hum, etc.).")
                st.stop()

            # Crear el mapa de renombrado dinámicamente
            # Asumimos que el orden NUNCA cambia:
            rename_map = {
                current_cols[0]: 'fecha',           # 'Date'
                current_cols[1]: 'hora',            # 'Time'
                current_cols[2]: 'temperatura_out', # 'Out Temp'
                current_cols[3]: 'humedad_out',     # 'Out Hum'
                current_cols[4]: 'velocidad_viento',# 'Wind Speed'
                current_cols[5]: 'direccion_viento',# 'Wind Dir'
                current_cols[6]: 'radiacion_solar', # 'Solar Rad.'
                current_cols[7]: 'uv_index',        # 'UV Index'
                current_cols[8]: 'lluvia_rate'      # 'Rain Rate'
            }

            # 2. Renombrar las columnas
            df = df.rename(columns=rename_map)
            # --- FIN DEL CAMBIO 3 ---


            # 3. Limpiar datos no numéricos ('---' -> NaN)
            numeric_cols = [
                'temperatura_out', 'humedad_out', 'velocidad_viento', 
                'radiacion_solar', 'uv_index', 'lluvia_rate'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    # 'coerce' convierte '---' y otros errores a NaN (Nulo Numérico)
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 4. Combinar 'fecha' y 'hora' en un 'timestamp'
            st.write("Procesando timestamp para formato XLSX...")
            
            df['timestamp_naive'] = df.apply(
                lambda row: datetime.combine(
                    row['fecha'].date(),
                    row['hora']
                ), 
                axis=1
            )
            
            # Localizar ese timestamp a la zona horaria de Perú
            df['timestamp'] = df['timestamp_naive'].apply(
                lambda ts_naive: TZ_PERU.localize(ts_naive)
            )

            # 5. Seleccionar solo las columnas que necesitamos para Supabase
            columnas_para_subir = ['timestamp'] + [col for col in COLUMNAS_FINALES if col not in ['fecha', 'hora']]
            
            # Chequeo final
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
        st.info("Asegúrate que el orden de las columnas sea Date, Time, Out Temp, Out Hum, Wind Speed, etc.")

st.divider()

# ======================================================================
# SECCIÓN DE VISUALIZACIÓN DE DATOS
# ======================================================================
st.header("Visualización de Datos Climáticos")

@st.cache_data(ttl=600) 
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
    # --- [CORRECCIÓN] Poner un rango de fechas por defecto que SÍ tenga datos
    start_date = st.date_input("Fecha de Inicio", datetime(2025, 11, 4), max_value=today)
with col_f2:
    end_date = st.date_input("Fecha de Fin", datetime(2025, 11, 5), min_value=start_date, max_value=today)

# Localizamos las fechas de inicio y fin para que coincidan con los datos de Supabase
start_datetime = TZ_PERU.localize(datetime.combine(start_date, datetime.min.time()))
end_datetime = TZ_PERU.localize(datetime.combine(end_date, datetime.max.time()))

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