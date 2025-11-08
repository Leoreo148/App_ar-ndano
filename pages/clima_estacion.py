import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client
import pytz # Para manejar la zona horaria
import io # Para leer el archivo de texto subido

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Clima", page_icon="🌦️", layout="wide")
st.title("🌦️ Dashboard de la Estación Meteorológica")

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
# PASO 1: SUBIR NUEVOS DATOS
# ======================================================================
st.header("Paso 1: Cargar nuevos datos de la estación")
st.write("Sube el archivo `.txt` descargado de la estación. Los datos se procesarán y guardarán en la base de datos.")

uploaded_file = st.file_uploader(
    "Selecciona el archivo .txt de la estación", 
    type=["txt"],
    help="Sube el archivo de datos (separado por tabulaciones)"
)

# --- Mapa de Columnas ---
# (Nombre en TXT) : (Nombre en Supabase)
COLUMNS_MAP = {
    'Out': 'temperatura_out',
    'Hum': 'humedad_out',
    'Speed': 'velocidad_viento',
    'Dir': 'direccion_viento',
    'Solar Rad.': 'radiacion_solar',
    'UV Index': 'uv_index',
    'Rain Rate': 'lluvia_rate'
}

if uploaded_file is not None:
    if not supabase:
        st.error("No se puede procesar el archivo: Falla en la conexión con Supabase.")
    else:
        try:
            # Leer el archivo de texto subido
            # Usamos io.StringIO para tratar el texto subido como un archivo
            string_data = io.StringIO(uploaded_file.getvalue().decode('utf-8'))
            
            # Leemos con pandas:
            # 1. sep='\t' -> Indicamos que el separador es una tabulación
            # 2. header=1 -> Indicamos que la fila 2 (índice 1) es la cabecera real
            df = pd.read_csv(string_data, sep='\t', header=1)
            
            st.success("Archivo leído. Procesando datos...")

            # --- Limpieza y Transformación ---
            
            # 1. Crear el timestamp
            # Combinamos 'Date' y 'Time'. 
            # ¡¡IMPORTANTE!! Ajusta el formato 'dd/MM/yy' si tu fecha es diferente (ej: 'MM/dd/yy')
            df['timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%y %H:%M')
            
            # 2. Asegurarnos que la zona horaria sea la de Perú (si está disponible)
            if TZ_PERU:
                df['timestamp'] = df['timestamp'].apply(lambda x: x.tz_localize(TZ_PERU))

            # 3. Renombrar las columnas para que coincidan con Supabase
            df_renamed = df.rename(columns=COLUMNS_MAP)
            
            # 4. Seleccionar solo las columnas que necesitamos para Supabase
            columnas_para_subir = ['timestamp'] + list(COLUMNS_MAP.values())
            
            # 5. Filtrar solo las columnas que REALMENTE existen en el dataframe
            columnas_existentes = [col for col in columnas_para_subir if col in df_renamed.columns]
            df_final = df_renamed[columnas_existentes]
            
            # --- CORRECCIÓN AQUÍ ---
            # Convertir los objetos 'Timestamp' de Python a strings en formato ISO
            # antes de enviarlos a Supabase (que espera JSON).
            df_final['timestamp'] = df_final['timestamp'].apply(lambda x: x.isoformat())

            # 6. Convertir a un formato de diccionario para Supabase
            records_to_insert = df_final.to_dict('records')
            
            # 7. Insertar en Supabase
            # 'upsert=True' es vital: Si subes un archivo con datos de un minuto
            # que ya existía, simplemente lo actualizará en lugar de duplicarlo.
            # Esto depende de que 'timestamp' sea la Clave Primaria.
            response = supabase.table('Datos_Estacion_Clima').upsert(records_to_insert, on_conflict='timestamp').execute()
            
            st.success(f"¡Datos guardados! Se procesaron {len(records_to_insert)} registros.")
            st.write(f"Primeros 5 registros subidos:")
            st.dataframe(df_final.head())
            st.balloons()

        except Exception as e:
            st.error(f"Ocurrió un error al procesar el archivo: {e}")
            st.warning("Verifica el formato del archivo. ¿Está separado por tabulaciones? ¿La cabecera está en la fila 2?")
            st.warning("Verifica también que el formato de fecha en el script (línea 102) coincida con tu archivo (ej: 'dd/MM/yy').")


# ======================================================================
# PASO 2: VISUALIZAR DATOS (EL DASHBOARD)
# ======================================================================
st.divider()
st.header("Paso 2: Analizar datos históricos")

@st.cache_data(ttl=300) # Cachear por 5 minutos
def cargar_datos_clima(start_date, end_date):
    """
    Carga datos desde Supabase para el rango de fechas seleccionado.
    """
    if not supabase:
        st.error("No se pueden cargar datos: Falla en la conexión con Supabase.")
        return pd.DataFrame()
    try:
        # Asegurarnos que las fechas tengan zona horaria para la consulta
        if TZ_PERU:
            start_date_tz = TZ_PERU.localize(datetime.combine(start_date, datetime.min.time()))
            end_date_tz = TZ_PERU.localize(datetime.combine(end_date, datetime.max.time()))
        else:
            start_date_tz = datetime.combine(start_date, datetime.min.time())
            end_date_tz = datetime.combine(end_date, datetime.max.time())

        # Consultar a Supabase por el rango de fechas
        response = supabase.table('Datos_Estacion_Clima') \
            .select("*") \
            .gte('timestamp', start_date_tz.isoformat()) \
            .lte('timestamp', end_date_tz.isoformat()) \
            .order('timestamp', desc=False) \
            .execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"No se pudieron cargar los datos del historial: {e}")
        return pd.DataFrame()

# --- Selectores de Fecha ---
st.write("Selecciona el rango de fechas que quieres analizar (ej: esta semana).")
col_f1, col_f2 = st.columns(2)
with col_f1:
    # Fecha de inicio (por defecto, hace 7 días)
    fecha_inicio = st.date_input("Fecha de Inicio", datetime.now() - pd.Timedelta(days=7))
with col_f2:
    # Fecha de fin (por defecto, hoy)
    fecha_fin = st.date_input("Fecha de Fin", datetime.now())

if fecha_inicio > fecha_fin:
    st.error("La fecha de inicio no puede ser posterior a la fecha de fin.")
else:
    # Cargar los datos para el rango seleccionado
    df_clima = cargar_datos_clima(fecha_inicio, fecha_fin)
    
    if df_clima.empty:
        st.info("No se encontraron datos de la estación meteorológica en Supabase para este rango de fechas.")
    else:
        st.success(f"Cargando {len(df_clima)} registros para el análisis.")
        
        # --- Gráficos de Picos (Velocidad de Viento y Humedad) ---
        st.subheader("Picos de Velocidad de Viento y Humedad")
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_viento = px.line(df_clima, x='timestamp', y='velocidad_viento', 
                                 title="Picos de Velocidad de Viento (km/h)",
                                 labels={'timestamp': 'Fecha y Hora', 'velocidad_viento': 'Velocidad (km/h)'})
            fig_viento.update_traces(line_color='#1f77b4')
            st.plotly_chart(fig_viento, use_container_width=True)
            
        with col_g2:
            fig_humedad = px.line(df_clima, x='timestamp', y='humedad_out', 
                                  title="Picos de Humedad (%)",
                                  labels={'timestamp': 'Fecha y Hora', 'humedad_out': 'Humedad (%)'})
            fig_humedad.update_traces(line_color='#2ca02c')
            st.plotly_chart(fig_humedad, use_container_width=True)

        # --- Análisis de Dirección de Viento ---
        st.subheader("Análisis de Viento")
        
        # Calcular la velocidad máxima y la dirección promedio
        max_viento = df_clima['velocidad_viento'].max()
        avg_viento = df_clima['velocidad_viento'].mean()
        
        # Contar las direcciones
        df_dir_viento = df_clima['direccion_viento'].value_counts().reset_index()
        df_dir_viento.columns = ['Dirección', 'Conteo']

        col_m1, col_m2, col_g3 = st.columns([1, 1, 2])
        with col_m1:
            st.metric("Velocidad Máx. de Viento", f"{max_viento:.1f} km/h")
        with col_m2:
            st.metric("Velocidad Prom. de Viento", f"{avg_viento:.1f} km/h")
        with col_g3:
            fig_dir = px.bar(df_dir_viento, x='Dirección', y='Conteo',
                             title="Dirección del Viento Dominante (Conteo)",
                             labels={'Conteo': 'Registros (por minuto)'})
            st.plotly_chart(fig_dir, use_container_width=True)
            
        # --- Otros Gráficos (Temperatura y Radiación) ---
        st.subheader("Temperatura y Radiación Solar")
        col_g4, col_g5 = st.columns(2)
        
        with col_g4:
            fig_temp = px.line(df_clima, x='timestamp', y='temperatura_out', 
                               title="Evolución de Temperatura (°C)",
                               labels={'timestamp': 'Fecha y Hora', 'temperatura_out': 'Temperatura (°C)'})
            fig_temp.update_traces(line_color='#d62728')
            st.plotly_chart(fig_temp, use_container_width=True)

        with col_g5:
            fig_rad = px.line(df_clima, x='timestamp', y='radiacion_solar', 
                              title="Evolución de Radiación Solar (W/m²)",
                              labels={'timestamp': 'Fecha y Hora', 'radiacion_solar': 'Radiación (W/m²)'})
            fig_rad.update_traces(line_color='#ff7f0e')
            st.plotly_chart(fig_rad, use_container_width=True)