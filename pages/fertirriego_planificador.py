import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client
import pytz # Para manejar la zona horaria

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Jornada de Fertiriego", page_icon="💧🧪", layout="wide")

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
# PASO 1: CARGAR CRONOGRAMA Y TAREA DEL DÍA
# ======================================================================
st.title("💧🧪 Jornada de Fertiriego y Drenaje")
st.write("Flujo completo para registrar la prueba de drenaje, las mediciones y la jornada de riego.")

st.header("Paso 1: Cargar Cronograma")

# --- NUEVO: UPLOADER DE ARCHIVO ---
# En lugar de buscar el archivo, pedimos que se suba.
uploaded_file = st.file_uploader(
    "Sube tu archivo de cronograma (FRUTALES - EXCEL.xlsx)", 
    type=["xlsx"],
    help="Sube el archivo Excel que contiene la pestaña 'CRONOGRAMA'"
)

# El cache ahora depende del archivo subido.
# La función ahora recibe el archivo (file_data) en lugar de un path
@st.cache_data(ttl=600)
def load_cronograma_from_file(file_data, fecha_hoy):
    """
    Lee el cronograma desde el objeto de archivo subido.
    """
    # El nombre de la hoja (Sheet) que quieres leer.
    sheet_name = "CRONOGRAMA"
    
    try:
        # --- CORRECCIÓN ---
        # Pandas puede leer el objeto de archivo subido directamente
        df = pd.read_excel(
            file_data, # Usamos el archivo subido
            sheet_name=sheet_name, 
            header=5 # Fila 6 es la cabecera
        )
        
        # Limpieza básica
        df = df.dropna(subset=['FECHA'])
        df['FECHA'] = pd.to_datetime(df['FECHA'])
        
        # Buscar la fila de hoy
        task_row = df[df['FECHA'] == fecha_hoy]
        
        if task_row.empty:
            return "No hay tarea de fertilización programada en el Excel para hoy."

        # Determinar la tarea
        # Confirma que estos índices de columna (7, 10, 14...) son correctos
        if pd.notna(task_row.iloc[0, 7]): # Columna 'GRUPO 1' (Urea)
            return "Fertilización Grupo 1"
        elif pd.notna(task_row.iloc[0, 10]): # Columna 'GRUPO 2' (Sulf. Magnesio)
            return "Fertilización Grupo 2"
        elif pd.notna(task_row.iloc[0, 14]): # Columna 'GRUPO 3' (Boro)
            return "Fertilización Grupo 3"
        elif pd.notna(task_row.iloc[0, 15]): # Columna 'GRUPO 4' (Nitrato Calcio)
            return "Fertilización Grupo 4"
        elif pd.notna(task_row.iloc[0, 16]): # Columna 'OBSERVACIÓN'
            if "LAVADO" in str(task_row.iloc[0, 16]).upper():
                return "Lavado de Sales"
        
        return "Riego (Sin grupo de fertilizante específico hoy)"

    except Exception as e:
        # Esto podría atrapar un error si la hoja 'CRONOGRAMA' no existe
        if "No sheet named" in str(e):
             st.error(f"Error: Se encontró el archivo Excel, pero no se encontró la hoja (sheet) llamada '{sheet_name}'.")
        else:
            st.error(f"Error al procesar el cronograma desde Excel: {e}")
        st.info("Asegúrese también de tener 'openpyxl' instalado (en requirements.txt).")
        return "ERROR AL PROCESAR CRONOGRAMA"

# --- LÓGICA PRINCIPAL ---
# Solo si el archivo fue subido, procesamos todo lo demás.
if uploaded_file is not None:
    
    # Obtener fecha de hoy y tarea
    if TZ_PERU:
        try:
            fecha_actual_peru = datetime.now(TZ_PERU).date()
            fecha_hoy_pd = pd.to_datetime(fecha_actual_peru)
            # Pasamos el uploaded_file Y la fecha a la función
            tarea_de_hoy = load_cronograma_from_file(uploaded_file, fecha_hoy_pd) 
            st.session_state.tarea_de_hoy = tarea_de_hoy
        except Exception as e:
            st.error(f"Error obteniendo fecha o cargando cronograma: {e}")
            fecha_actual_peru = datetime.now().date() # Fallback
            st.session_state.tarea_de_hoy = "Error en fecha"
    else:
        st.error("No se pudo definir la zona horaria. La fecha puede ser incorrecta.")
        fecha_actual_peru = datetime.now().date() # Fallback
        st.session_state.tarea_de_hoy = "Indeterminada"

    st.info(f"Tarea para hoy ({fecha_actual_peru.strftime('%d/%m/%Y')}): **{st.session_state.tarea_de_hoy}**")
    
    # Si la tarea falló, mostramos un error antes del formulario
    if "ERROR" in st.session_state.tarea_de_hoy:
         st.error("El archivo se subió, pero no se pudo leer el cronograma. Revisa el error de arriba y la pestaña 'CRONOGRAMA' en tu Excel.")
    else:
        # ======================================================================
        # PASO 2, 3 y 4: FORMULARIO UNIFICADO DE JORNADA
        # (Todo esto ahora está dentro de 'if uploaded_file is not None:')
        # ======================================================================
        with st.form("jornada_form"):
            
            st.header("Paso 2: Prueba de Drenaje (Testigos)")
            st.write("Ingrese los datos PROMEDIO de sus macetas testigo (6 de coco, 3 de cascarilla).")

            col1, col2 = st.columns(2)
            
            with col1:
                sustrato_testigo = st.radio(
                    "Sustrato del Testigo:",
                    ("Fibra de Coco", "Cascarilla de Arroz"),
                    horizontal=True,
                    key="sustrato_testigo"
                )
                testigo_vol_aplicado_ml = st.number_input(
                    "Volumen Aplicado (mL/maceta)", 
                    min_value=0.0, 
                    step=50.0, 
                    value=1000.0,
                    key="testigo_vol_aplicado_ml"
                )
                testigo_vol_drenado_ml = st.number_input(
                    "Volumen Drenado (mL/maceta)", 
                    min_value=0.0, 
                    step=10.0, 
                    value=250.0,
                    key="testigo_vol_drenado_ml"
                )
                meta_drenaje = st.number_input(
                    "Meta de Drenaje Objetivo (%)", 
                    min_value=0.0, 
                    max_value=100.0, 
                    value=25.0, 
                    step=1.0,
                    key="meta_drenaje"
                )

            # --- Cálculo y Recomendación Dinámica ---
            if testigo_vol_aplicado_ml > 0:
                testigo_porc_drenaje = (testigo_vol_drenado_ml / testigo_vol_aplicado_ml) * 100
            else:
                testigo_porc_drenaje = 0.0
            
            with col2:
                st.metric("Drenaje Alcanzado", f"{testigo_porc_drenaje:.1f}%")
                
                if 'recomendacion_volumen' not in st.session_state:
                     st.session_state.recomendacion_volumen = 1000.0 # Valor inicial

                if testigo_vol_aplicado_ml == 0:
                    st.info("Ingrese un volumen aplicado para calcular.")
                elif abs(testigo_porc_drenaje - meta_drenaje) < 5: # Rango de +/- 5%
                    st.success(f"✅ DRENAJE ÓPTIMO. El {testigo_porc_drenaje:.1f}% está cerca de la meta ({meta_drenaje}%).")
                    st.session_state.recomendacion_volumen = testigo_vol_aplicado_ml
                elif testigo_porc_drenaje < meta_drenaje:
                    st.warning(f"⚠️ DRENAJE INSUFICIENTE. El {testigo_porc_drenaje:.1f}% está por debajo de la meta ({meta_drenaje}%). Considere aumentar el volumen para lavar sales.")
                    st.session_state.recomendacion_volumen = testigo_vol_aplicado_ml
                else:
                    st.warning(f"⚠️ DRENAJE EXCESIVO. El {testigo_porc_drenaje:.1f}% está muy por encima de la meta ({meta_drenaje}%). Considere reducir el volumen.")
                    st.session_state.recomendacion_volumen = testigo_vol_aplicado_ml

            st.divider()

            # --- Paso 3: Mediciones ---
            st.header("Paso 3: Mediciones (Drenaje y Riego)")
            mcol1, mcol2 = st.columns(2)

            with mcol1:
                st.subheader("Medición del Drenaje (Lixiviado)")
                testigo_ph_drenaje = st.number_input("pH del Drenaje", min_value=0.0, max_value=14.0, value=6.0, step=0.1, format="%.2f", key="testigo_ph_drenaje")
                testigo_ce_drenaje = st.number_input("CE del Drenaje (dS/m)", min_value=0.0, value=1.8, step=0.1, format="%.2f", key="testigo_ce_drenaje")

            with mcol2:
                st.subheader("Agua de Origen (Pozo/Canal)")
                fuente_ph = st.number_input("pH Agua Origen", min_value=0.0, max_value=14.0, value=7.5, step=0.1, format="%.2f", key="fuente_ph")
                fuente_ce = st.number_input("CE Agua Origen (dS/m)", min_value=0.0, value=0.8, step=0.1, format="%.2f", key="fuente_ce")

            st.divider()
            
            # --- Paso 4: Registro General ---
            st.header("Paso 4: Registro General de la Jornada")
            
            rcol1, rcol2 = st.columns(2)
            with rcol1:
                st.subheader("Mezcla Final (Bidón)")
                mezcla_ph_final = st.number_input("pH Mezcla Final", min_value=0.0, max_value=14.0, value=5.8, step=0.1, format="%.2f", key="mezcla_ph_final")
                mezcla_ce_final = st.number_input("CE Mezcla Final (dS/m)", min_value=0.0, value=2.0, step=0.1, format="%.2f", key="mezcla_ce_final")
            
            with rcol2:
                st.subheader("Volumen y Notas")
                # Sugerir volumen total (44 plantas * volumen recomendado)
                vol_sugerido = (st.session_state.get('recomendacion_volumen', 1000.0) * 44) / 1000 # 44 plantas
                
                general_vol_aplicado_litros = st.number_input(
                    "Volumen Total Aplicado (Litros)", 
                    min_value=0.0, 
                    value=vol_sugerido, 
                    step=1.0, 
                    format="%.1f",
                    key="general_vol_aplicado_litros"
                )
            
            observaciones = st.text_area(
                "Observaciones y Productos Aplicados:", 
                placeholder=f"Ej: Se aplicó {st.session_state.tarea_de_hoy}. El drenaje de cascarilla fue X. Todo normal.",
                key="observaciones"
            )

            # --- Botón de Envío ---
            submitted = st.form_submit_button("💾 Guardar Jornada Completa")

        # --- Lógica de Guardado ---
        if submitted:
            if not supabase:
                st.error("Error fatal: No hay conexión con Supabase.")
            elif testigo_vol_aplicado_ml <= 0: # Cambiado a <= 0
                st.warning("No se puede guardar: El 'Volumen Aplicado (mL/maceta)' debe ser mayor a cero.")
            else:
                try:
                    # Recalcular el porcentaje de drenaje para asegurar
                    testigo_porc_drenaje_final = (testigo_vol_drenado_ml / testigo_vol_aplicado_ml) * 100
                    
                    datos_para_insertar = {
                        "fecha": fecha_actual_peru.strftime("%Y-%m-%d"),
                        "sustrato_testigo": sustrato_testigo,
                        "tarea_del_dia": st.session_state.tarea_de_hoy,
                        "testigo_vol_aplicado_ml": testigo_vol_aplicado_ml,
                        "testigo_vol_drenado_ml": testigo_vol_drenado_ml,
                        "testigo_porc_drenaje": testigo_porc_drenaje_final,
                        "testigo_ph_drenaje": testigo_ph_drenaje,
                        "testigo_ce_drenaje": testigo_ce_drenaje,
                        "general_vol_aplicado_litros": general_vol_aplicado_litros,
                        "fuente_ph": fuente_ph,
                        "fuente_ce": fuente_ce,
                        "mezcla_ph_final": mezcla_ph_final,
                        "mezcla_ce_final": mezcla_ce_final,
                        "observaciones": observaciones
                    }
                    
                    # Insertar en la NUEVA tabla 'Jornada_Riego'
                    supabase.table('Jornada_Riego').insert(datos_para_insertar).execute()
                    
                    st.success("¡Jornada de riego guardada exitosamente en la tabla 'Jornada_Riego'!")
                    st.balloons()

                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}")


        # ======================================================================
        # SECCIÓN DE HISTORIAL Y GRÁFICOS (Adaptado de drenaje.py)
        # ======================================================================
        st.divider()
        st.header("Historial y Tendencias de la Jornada")

        @st.cache_data(ttl=300) # Cachear por 5 minutos
        def cargar_datos_jornada():
            if not supabase:
                return pd.DataFrame()
            try:
                # Leer de la NUEVA tabla 'Jornada_Riego'
                response = supabase.table('Jornada_Riego').select("*").order('fecha', desc=True).limit(100).execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    df['fecha'] = pd.to_datetime(df['fecha'])
                    return df
                else:
                    return pd.DataFrame() # Retorna DF vacío si no hay datos
            except Exception as e:
                st.error(f"No se pudieron cargar los datos del historial: {e}")
                return pd.DataFrame()

        df_historial = cargar_datos_jornada()

        if df_historial.empty:
            st.info("Aún no hay registros en 'Jornada_Riego'.")
        else:
            st.write("Últimas jornadas registradas:")
            st.dataframe(df_historial.head(), use_container_width=True) # Mostrar solo las primeras 5

            st.subheader("Gráficos de Tendencias")
            
            # Filtrar por sustrato para que los gráficos no se saturen
            sustratos_unicos = ["Todos"] + list(df_historial['sustrato_testigo'].unique())
            sustrato_filtro = st.selectbox("Filtrar gráficos por sustrato:", sustratos_unicos)
            
            df_filtrado = df_historial
            if sustrato_filtro != "Todos":
                df_filtrado = df_historial[df_historial['sustrato_testigo'] == sustrato_filtro]

            if df_filtrado.empty:
                st.warning("No hay datos para el sustrato seleccionado.")
            else:
                # Gráficos de Drenaje (Testigos)
                gcol1, gcol2 = st.columns(2)
                with gcol1:
                    fig_ph_drenaje = px.line(df_filtrado, x='fecha', y='testigo_ph_drenaje', color='sustrato_testigo',
                                             title="Evolución del pH en Drenaje (Testigo)", markers=True)
                    st.plotly_chart(fig_ph_drenaje, use_container_width=True)
                with gcol2:
                    fig_ce_drenaje = px.line(df_filtrado, x='fecha', y='testigo_ce_drenaje', color='sustrato_testigo',
                                             title="Evolución de la CE en Drenaje (Testigo)", markers=True)
                    st.plotly_chart(fig_ce_drenaje, use_container_width=True)

                # Gráficos de Mezcla Final (Bidón)
                gcol3, gcol4 = st.columns(2)
                with gcol3:
                    fig_ph_mezcla = px.line(df_filtrado, x='fecha', y='mezcla_ph_final',
                                             title="pH de la Mezcla Final Aplicada", markers=True)
                    st.plotly_chart(fig_ph_mezcla, use_container_width=True)
                with gcol4:
                    fig_ce_mezcla = px.line(df_filtrado, x='fecha', y='mezcla_ce_final',
                                             title="CE de la MezMcla Final Aplicada", markers=True)
                    st.plotly_chart(fig_ce_mezcla, use_container_width=True)

else:
    # Si no hay archivo subido, mostrar este mensaje
    st.info("Por favor, sube tu archivo Excel 'FRUTALES - EXCEL.xlsx' para comenzar la jornada.")
    st.image("https://placehold.co/600x200/e8f0ff/4a4a4a?text=Esperando+Archivo...&font=roboto")