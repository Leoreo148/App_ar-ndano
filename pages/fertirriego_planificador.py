import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client
import pytz # Para manejar la zona horaria
import os # Para comprobar si el archivo existe

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
# PASO 1: TAREA DEL DÍA (LEYENDO DEL EXCEL)
# ======================================================================
st.title("💧🧪 Jornada de Fertiriego y Drenaje")
st.write("Flujo completo para registrar la prueba de drenaje, las mediciones y la jornada de riego.")

# --- RUTA SIMPLIFICADA ---
FILE_PATH = "FRUTALES - EXCEL.xlsx"

# --- FUNCIÓN DE CARGA MODIFICADA ---
@st.cache_data(ttl=600) # Cachear por 10 minutos
def load_cronograma(fecha_hoy):
    """
    Lee el cronograma desde el archivo en la raíz.
    Ahora devuelve un (string, pandas.Series) con los datos de la fila.
    """
    sheet_name = "CRONOGRAMA"
    
    try:
        df = pd.read_excel(
            FILE_PATH, 
            sheet_name=sheet_name, 
            header=4  # <-- La corrección clave
        )
        
        df = df.dropna(subset=['FECHA'])
        df['FECHA'] = pd.to_datetime(df['FECHA'])
        
        task_row_df = df[df['FECHA'] == fecha_hoy]
        
        if task_row_df.empty:
            return "No hay tarea de fertilización programada en el Excel para hoy.", None

        # Guardamos la fila entera de datos
        task_row_data = task_row_df.iloc[0]
        tarea_str = "Riego (Sin grupo de fertilizante específico hoy)"

        # Determinar la tarea (usando los mismos índices)
        if pd.notna(task_row_data.iloc[7]): # Columna 'GRUPO 1'
            tarea_str = "Fertilización Grupo 1"
        elif pd.notna(task_row_data.iloc[10]): # Columna 'GRUPO 2'
            tarea_str = "Fertilización Grupo 2"
        elif pd.notna(task_row_data.iloc[14]): # Columna 'GRUPO 3'
            tarea_str = "Fertilización Grupo 3"
        elif pd.notna(task_row_data.iloc[15]): # Columna 'GRUPO 4'
            tarea_str = "Fertilización Grupo 4"
        elif pd.notna(task_row_data.iloc[16]): # Columna 'OBSERVACIÓN'
            if "LAVADO" in str(task_row_data.iloc[16]).upper():
                tarea_str = "Lavado de Sales"
        
        return tarea_str, task_row_data

    except FileNotFoundError:
        st.error(f"Error 'FileNotFoundError': No se encontró el archivo en la ruta: '{FILE_PATH}'.")
        st.info("Asegúrate de que 'FRUTALES - EXCEL.xlsx' esté en la carpeta raíz (junto a Dashboard.py).")
        return "ERROR: Archivo no encontrado", None
    except KeyError as e:
        st.error(f"Error de 'KeyError': No se encontró la columna {e}. Revisa el Excel. ¿La cabecera está en la fila 5?")
        return f"ERROR: Falta la columna {e}", None
    except Exception as e:
        if "No sheet named" in str(e):
             st.error(f"Error: Se encontró el archivo Excel, pero no se encontró la hoja (sheet) llamada '{sheet_name}'.")
        else:
            st.error(f"Error al procesar el cronograma desde Excel: {e}")
        st.info("Asegúrese también de tener 'openpyxl' instalado (en requirements.txt).")
        return "ERROR AL PROCESAR CRONOGRAMA", None

# --- LÓGICA PRINCIPAL ---
if TZ_PERU:
    try:
        fecha_actual_peru = datetime.now(TZ_PERU).date()
        fecha_hoy_pd = pd.to_datetime(fecha_actual_peru)
        # Ahora obtenemos dos valores de la función
        tarea_de_hoy, datos_dosis = load_cronograma(fecha_hoy_pd) 
        st.session_state.tarea_de_hoy = tarea_de_hoy
        st.session_state.datos_dosis = datos_dosis # Guardamos los datos de la fila
    except Exception as e:
        st.error(f"Error obteniendo fecha o cargando cronograma: {e}")
        fecha_actual_peru = datetime.now().date() # Fallback
        st.session_state.tarea_de_hoy = "Error en fecha"
        st.session_state.datos_dosis = None
else:
    st.error("No se pudo definir la zona horaria. La fecha puede ser incorrecta.")
    fecha_actual_peru = datetime.now().date() # Fallback
    st.session_state.tarea_de_hoy = "Indeterminada"
    st.session_state.datos_dosis = None

st.header("Paso 1: Tarea Programada")
st.info(f"Tarea para hoy ({fecha_actual_peru.strftime('%d/%m/%Y')}): **{st.session_state.tarea_de_hoy}**")

# --- NUEVO: Mostrar dosis del día si existen ---
if st.session_state.datos_dosis is not None:
    with st.expander("Ver dosis programada para hoy (según Excel)"):
        datos = st.session_state.datos_dosis
        dosis_info = {
            "Urea (mg/L/día)": datos.iloc[7],
            "Fosfato Monoamónico (mg/L/día)": datos.iloc[8],
            "Sulf. de Potasio (mg/L/día)": datos.iloc[9],
            "Sulf. de Magnesio (mg/L/día)": datos.iloc[10],
            "Sulf. de Cobre (mg/L/día)": datos.iloc[11],
            "Sulf. de Manganeso (mg/L/día)": datos.iloc[12],
            "Sulf. de Zinc (mg/L/día)": datos.iloc[13],
            "Boro (mg/L/día)": datos.iloc[14],
            "Nitrato de Calcio (mg/L/día)": datos.iloc[15],
        }
        # Filtrar solo los que no son NaN (no tienen valor)
        dosis_info_filtrada = {k: v for k, v in dosis_info.items() if pd.notna(v)}
        
        if not dosis_info_filtrada:
            st.write("No hay dosis de fertilizantes específicas listadas para la tarea de hoy.")
        else:
            st.json(dosis_info_filtrada)


# Si la tarea falló, mostramos un error antes del formulario
if "ERROR" in st.session_state.tarea_de_hoy:
     st.error("No se pudo leer el cronograma. Revisa el error de arriba y asegúrate de que 'FRUTALES - EXCEL.xlsx' esté en la raíz.")
else:
    # ======================================================================
    # PASO 2: PRUEBA DE DRENAJE (¡¡FUERA DEL FORMULARIO!!)
    # Esto ahora se actualizará en vivo.
    # ======================================================================
    
    st.header("Paso 2: Prueba de Drenaje (Testigos)")
    st.write("Ingrese los datos PROMEDIO de sus macetas testigo (6 de coco, 3 de cascarilla).")

    col1, col2 = st.columns(2)
    
    with col1:
        # Este widget ahora está FUERA del form, pero su valor se guarda
        # gracias a la 'key'
        sustrato_testigo = st.radio(
            "Sustrato del Testigo:",
            ("Fibra de Coco", "Cascarilla de Arroz"),
            horizontal=True,
            key="sustrato_testigo"
        )
        # Estos inputs ahora se actualizan en vivo
        testigo_vol_aplicado_ml = st.number_input(
            "Volumen Aplicado (mL/maceta)", 
            min_value=0.0, 
            step=50.0, 
            value=1000.0,
            key="testigo_vol_aplicado_ml" # La 'key' es crucial
        )
        testigo_vol_drenado_ml = st.number_input(
            "Volumen Drenado (mL/maceta)", 
            min_value=0.0, 
            step=10.0, 
            value=250.0,
            key="testigo_vol_drenado_ml" # La 'key' es crucial
        )
        meta_drenaje = st.number_input(
            "Meta de Drenaje Objetivo (%)", 
            min_value=0.0, 
            max_value=100.0, 
            value=25.0, 
            step=1.0,
            key="meta_drenaje"
        )

    # --- CÁLCULO EN VIVO ---
    # Como los inputs están fuera del form, estas variables
    # tendrán el valor actualizado en cada re-ejecución (cada cambio)
    if testigo_vol_aplicado_ml > 0:
        testigo_porc_drenaje = (testigo_vol_drenado_ml / testigo_vol_aplicado_ml) * 100
    else:
        testigo_porc_drenaje = 0.0
    
    with col2:
        # Esta métrica ahora se actualizará instantáneamente
        st.metric("Drenaje Alcanzado", f"{testigo_porc_drenaje:.1f}%")
        
        if 'recomendacion_volumen' not in st.session_state:
             st.session_state.recomendacion_volumen = 1000.0

        if testigo_vol_aplicado_ml == 0:
            st.info("Ingrese un volumen aplicado para calcular.")
        # Usamos la meta_drenaje (que también se actualiza en vivo)
        elif abs(testigo_porc_drenaje - meta_drenaje) < 5: 
            st.success(f"✅ DRENAJE ÓPTIMO. El {testigo_porc_drenaje:.1f}% está cerca de la meta ({meta_drenaje}%).")
            st.session_state.recomendacion_volumen = testigo_vol_aplicado_ml
        elif testigo_porc_drenaje < meta_drenaje:
            st.warning(f"⚠️ DRENAJE INSUFICIENTE. El {testigo_porc_drenaje:.1f}% está por debajo de la meta ({meta_drenaje}%).")
            st.session_state.recomendacion_volumen = testigo_vol_aplicado_ml
        else:
            st.warning(f"⚠️ DRENAJE EXCESIVO. El {testigo_porc_drenaje:.1f}% está muy por encima de la meta ({meta_drenaje}%).")
            st.session_state.recomendacion_volumen = testigo_vol_aplicado_ml

    st.divider()

    # ======================================================================
    # PASO 3 y 4: FORMULARIO UNIFICADO DE JORNADA
    # El formulario AHORA EMPIEZA AQUÍ
    # ======================================================================
    with st.form("jornada_form"):
        
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
            st.subheader("Volumen")
            # El volumen sugerido usará el valor más reciente de session_state
            vol_sugerido = (st.session_state.get('recomendacion_volumen', 1000.0) * 44) / 1000 # 44 plantas
            
            general_vol_aplicado_litros = st.number_input(
                "Volumen Total Aplicado (Litros)", 
                min_value=0.0, 
                value=vol_sugerido, 
                step=1.0, 
                format="%.1f",
                key="general_vol_aplicado_litros"
            )
        
        st.divider()
        
        # --- Sección de Dosis ---
        st.subheader("Configuración de Dosis")
        tipo_dosis = st.radio(
            "¿Cómo se está aplicando la dosis de fertilizante?",
            ("Dosis de hoy (1 día)", "Dosis acumulada (ej: 7 días)"),
            horizontal=True,
            key="tipo_dosis"
        )
        dias_aplicados = 1
        if "acumulada" in tipo_dosis:
            dias_aplicados = st.number_input(
                "¿Cuántos días de dosis está aplicando hoy?", 
                min_value=1, max_value=14, value=7, step=1,
                key="dias_aplicados"
            )
        
        st.divider()
        
        st.subheader("Notas Adicionales")
        observaciones = st.text_area(
            "Observaciones y Productos Aplicados:", 
            placeholder=f"Ej: Se aplicó {st.session_state.tarea_de_hoy}. El drenaje de cascarilla fue X. Todo normal.",
            key="observaciones"
        )

        # --- Botón de Envío ---
        submitted = st.form_submit_button("💾 Guardar Jornada Completa")

    # --- Lógica de Guardado ---
    # Esta lógica no cambia, porque ya leía todo de st.session_state
    if submitted:
        if not supabase:
            st.error("Error fatal: No hay conexión con Supabase.")
        # Leemos el valor de session_state (que se actualizó en vivo)
        elif st.session_state.testigo_vol_aplicado_ml <= 0: 
            st.warning("No se puede guardar: El 'Volumen Aplicado (mL/maceta)' debe ser mayor a cero.")
        else:
            try:
                # Recalcular el porcentaje de drenaje final al guardar
                testigo_porc_drenaje_final = (st.session_state.testigo_vol_drenado_ml / st.session_state.testigo_vol_aplicado_ml) * 100
                
                # Leemos los valores finales de los widgets usando sus keys
                datos_para_insertar = {
                    "fecha": fecha_actual_peru.strftime("%Y-%m-%d"),
                    # Estos valores vienen de FUERA del form (Paso 2)
                    "sustrato_testigo": st.session_state.sustrato_testigo,
                    "testigo_vol_aplicado_ml": st.session_state.testigo_vol_aplicado_ml,
                    "testigo_vol_drenado_ml": st.session_state.testigo_vol_drenado_ml,
                    "testigo_porc_drenaje": testigo_porc_drenaje_final,
                    # Estos valores vienen de DENTRO del form (Paso 3 y 4)
                    "tarea_del_dia": st.session_state.tarea_de_hoy,
                    "testigo_ph_drenaje": st.session_state.testigo_ph_drenaje,
                    "testigo_ce_drenaje": st.session_state.testigo_ce_drenaje,
                    "general_vol_aplicado_litros": st.session_state.general_vol_aplicado_litros,
                    "fuente_ph": st.session_state.fuente_ph,
                    "fuente_ce": st.session_state.fuente_ce,
                    "mezcla_ph_final": st.session_state.mezcla_ph_final,
                    "mezcla_ce_final": st.session_state.mezcla_ce_final,
                    "observaciones": st.session_state.observaciones,
                    "tipo_dosis": st.session_state.tipo_dosis,
                    "dias_aplicados": st.session_state.dias_aplicados if "acumulada" in st.session_state.tipo_dosis else 1
                }
                
                supabase.table('Jornada_Riego').insert(datos_para_insertar).execute()
                
                st.success("¡Jornada de riego guardada exitosamente en la tabla 'Jornada_Riego'!")
                st.balloons()

            except Exception as e:
                st.error(f"Error al guardar en Supabase: {e}")
                st.warning("Posible Causa: ¿Agregaste las columnas 'tipo_dosis' (text) y 'dias_aplicados' (int) a la tabla 'Jornada_Riego' en Supabase?")


    # ======================================================================
    # SECCIÓN DE HISTORIAL Y GRÁFICOS
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
                                         title="CE de la Mezcla Final Aplicada", markers=True)
                st.plotly_chart(fig_ce_mezcla, use_container_width=True)