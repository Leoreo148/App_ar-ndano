import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client
import pytz # Para manejar la zona horaria
import os # Para la comprobación de archivo
import re # Para limpiar nombres de columnas

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Jornada de Fertiriego", page_icon="💧🧪", layout="wide")


# --- [NUEVO] DICCIONARIO DE RECETAS (mg/L/día) ---
# Basado en los datos del Excel (Sem 44/45)
RECETAS_FIJAS_MG_L_DIA = {
    "Fertilización Grupo 1": {
        "Urea": 36.25922888,
        "Fosfato Monoamónico": 4.918032787,
        "Sulf. de Potasio": 48.07692308
    },
    "Fertilización Grupo 2": {
        "Sulf. de Magnesio": 37.5,
        "Sulf. de Cobre": 0.4,
        "Sulf. de Manganeso": 2.580645161,
        "Sulf. de Zinc": 0.6976744186
    },
    "Fertilización Grupo 3": {
        "Boro": 4.571428571
    },
    "Fertilización Grupo 4": {
        "Nitrato de Calcio": 75.47169811
    },
    # Tareas sin fertilizantes
    "Recuperación / Sin Riego": {},
    "Lavado de Sales": {},
    "Día No Laborable": {},
    "Riego (Sin grupo)": {} # Fallback
}


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

# Inicializar Supabase
supabase = init_supabase_connection()

# Definir Zona Horaria
try:
    TZ_PERU = pytz.timezone('America/Lima')
except ImportError:
    st.error("Se necesita la librería 'pytz'. Instálala con: pip install pytz")
    TZ_PERU = None

# --- RUTA SIMPLIFICADA ---
FILE_PATH = "FRUTALES - EXCEL.xlsx"

# ======================================================================
# --- FUNCIÓN DE CRONOGRAMA (MODIFICADA) ---
# ======================================================================
@st.cache_data(ttl=600) 
def load_cronograma(fecha_hoy):
    """
    1. Determina la TAREA según el día de la semana.
    2. (Opcional) Busca en el Excel la fila de esa FECHA para validar.
    Devuelve (tarea_str, datos_fila_excel)
    """
    
    # --- 1. Determinar Tarea por Día de la Semana ---
    dia_semana = fecha_hoy.weekday() # Lunes=0, Martes=1, ..., Domingo=6
    
    if dia_semana == 0:
        tarea_str = "Fertilización Grupo 1"
    elif dia_semana == 1:
        tarea_str = "Fertilización Grupo 2"
    elif dia_semana == 2:
        tarea_str = "Fertilización Grupo 3"
    elif dia_semana == 3:
        tarea_str = "Fertilización Grupo 4"
    elif dia_semana == 4:
        tarea_str = "Recuperación / Sin Riego"
    elif dia_semana == 5:
        tarea_str = "Lavado de Sales"
    elif dia_semana == 6:
        tarea_str = "Día No Laborable"
    
    # --- 2. Cargar Excel solo para validar si la fecha existe ---
    # Ya no usamos el Excel para las *dosis*, solo para el registro.
    
    sheet_name = "CRONOGRAMA"
    
    try:
        df = pd.read_excel(
            FILE_PATH, 
            sheet_name=sheet_name, 
            header=5
        )
        
        df = df.rename(columns={'Unnamed: 3': 'FECHA'})
        df = df.dropna(subset=['FECHA'])
        df['FECHA'] = pd.to_datetime(df['FECHA']).dt.date
        
        task_row_df = df[df['FECHA'] == fecha_hoy]
        
        if task_row_df.empty:
            # No se encontró la fecha de hoy en el Excel.
            st.warning(f"Se asignó la tarea '{tarea_str}' por ser {fecha_hoy.strftime('%A')}, pero no se encontró la fecha {fecha_hoy} en el Excel. Se usarán las dosis fijas.")
            # Devolvemos 'None' para la fila, pero la tarea sigue
            return tarea_str, None

        task_row_data = task_row_df.iloc[0]
        return tarea_str, task_row_data

    except FileNotFoundError:
        st.error(f"Error 'FileNotFoundError': No se encontró el archivo en la ruta: '{FILE_PATH}'.")
        return "ERROR: Archivo no encontrado", None
    except Exception as e:
        st.error(f"Error al procesar el cronograma desde Excel: {e}")
        return "ERROR AL PROCESAR CRONOGRAMA", None
# --- FIN DE LA FUNCIÓN ---


# --- LÓGICA PRINCIPAL (PASO 1) ---
if TZ_PERU:
    try:
        fecha_actual_peru = datetime.now(TZ_PERU).date()
        
        # Obtenemos la tarea del día y la fila del excel (aunque ya no la usemos para dosis)
        tarea_de_hoy, datos_fila_excel = load_cronograma(fecha_actual_peru) 
        
        st.session_state.tarea_de_hoy = tarea_de_hoy
        st.session_state.datos_fila_excel = datos_fila_excel # Guardamos por si acaso
        
        # --- [NUEVO] ---
        # Guardamos la RECETA FIJA en session_state también
        st.session_state.receta_de_hoy = RECETAS_FIJAS_MG_L_DIA.get(tarea_de_hoy, {})

    except Exception as e:
        st.error(f"Error obteniendo fecha o cargando cronograma: {e}")
        fecha_actual_peru = datetime.now().date() 
        st.session_state.tarea_de_hoy = "Error en fecha"
        st.session_state.receta_de_hoy = {}
else:
    st.error("No se pudo definir la zona horaria. La fecha puede ser incorrecta.")
    fecha_actual_peru = datetime.now().date() 
    st.session_state.tarea_de_hoy = "Indeterminada"
    st.session_state.receta_de_hoy = {}

st.header("Paso 1: Tarea Programada")
st.info(f"Tarea para hoy ({fecha_actual_peru.strftime('%d/%m/%Y')}): **{st.session_state.tarea_de_hoy}**")


# --- [MODIFICADO] Mostrar dosis del día ---
# Ahora usa la receta fija guardada en st.session_state.receta_de_hoy
with st.expander("Ver dosis DIARIA programada (según receta fija, mg/L/día)"):
    
    receta_actual = st.session_state.get('receta_de_hoy', {})
    
    if not receta_actual:
        st.write(f"La tarea de hoy ({st.session_state.tarea_de_hoy}) no tiene fertilizantes programados.")
    else:
        # Formatear para st.json
        dosis_info_formateada = {
            f"{nombre} (mg/L/día)": valor 
            for nombre, valor in receta_actual.items()
        }
        st.json(dosis_info_formateada)


# Si la tarea falló, no mostramos el resto de la app
if "ERROR" in st.session_state.tarea_de_hoy:
     st.error("No se pudo leer el cronograma. Revisa el error de arriba y asegúrate de que 'FRUTALES - EXCEL.xlsx' esté en la raíz.")
     st.stop()
elif st.session_state.tarea_de_hoy in ["Día No Laborable"]:
    st.success(f"¡Hoy es {st.session_state.tarea_de_hoy}! No hay tareas de fertiriego.")
    st.stop()
else:
    # ======================================================================
    # PASO 2: PRUEBA DE DRENAJE (FUERA DEL FORMULARIO)
    # ======================================================================
    
    st.header("Paso 2: Prueba de Drenaje (Testigos)")
    st.write("Ingrese los datos PROMEDIO de sus macetas testigo.")

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

    # --- CÁLCULO EN VIVO ---
    if testigo_vol_aplicado_ml > 0:
        testigo_porc_drenaje = (testigo_vol_drenado_ml / testigo_vol_aplicado_ml) * 100
    else:
        testigo_porc_drenaje = 0.0
    
    with col2:
        st.metric("Drenaje Alcanzado", f"{testigo_porc_drenaje:.1f}%")
        
        if 'recomendacion_volumen' not in st.session_state:
             st.session_state.recomendacion_volumen = 1000.0

        if testigo_vol_aplicado_ml == 0:
            st.info("Ingrese un volumen aplicado para calcular.")
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
    # PASO 3: REGISTRO GENERAL (FUERA DEL FORMULARIO)
    # ======================================================================
    st.header("Paso 3: Registro General de la Jornada")
    
    rcol1, rcol2 = st.columns(2)
    with rcol1:
        st.subheader("Mezcla Final (Bidón)")
        mezcla_ph_final = st.number_input("pH Mezcla Final", min_value=0.0, max_value=14.0, value=5.8, step=0.1, format="%.2f", key="mezcla_ph_final")
        mezcla_ce_final = st.number_input("CE Mezcla Final (dS/m)", min_value=0.0, value=2.0, step=0.1, format="%.2f", key="mezcla_ce_final")
    
    with rcol2:
        st.subheader("Volumen")
        vol_sugerido = (st.session_state.get('recomendacion_volumen', 1000.0) * 44) / 1000 
        
        general_vol_aplicado_litros = st.number_input(
            "Volumen Total Aplicado (Litros)", 
            min_value=0.0, 
            value=vol_sugerido, 
            step=1.0, 
            format="%.1f",
            key="general_vol_aplicado_litros",
            help="Este valor se usará para calcular los gramos de fertilizante."
        )
    
    st.divider()

    # ======================================================================
    # PASO 4: CÁLCULO DE DOSIS (FUERA DEL FORMULARIO)
    # ======================================================================
    st.header("Paso 4: Cálculo de Dosis de Fertilizantes")
    
    dias_aplicados = st.number_input(
        "¿Cuántos días de dosis vas a aplicar hoy?",
        min_value=1, max_value=14, value=1, step=1,
        key="dias_aplicados",
        help="Escribe '1' para la dosis normal del día. Escribe '7' si aplicas la dosis de toda la semana."
    )
    
    # --- CÁLCULO DE DOSIS EN VIVO ---
    
    current_vol_litros = general_vol_aplicado_litros
    current_dias = dias_aplicados
    
    # --- [MODIFICADO] ---
    # Usamos la receta fija de la tarea de hoy
    receta_para_calculo = st.session_state.get('receta_de_hoy', {})

    st.subheader("Dosis Total de Fertilizante a aplicar en Bidón")
    st.write(f"Cálculo para **{current_dias} día(s)** en un volumen total de **{current_vol_litros:.1f} Litros**:")

    if not receta_para_calculo:
        st.info(f"La tarea de hoy ({st.session_state.tarea_de_hoy}) no tiene fertilizantes programados.")
    else:
        # Mapeo de nombres de receta a nombres de columna en Supabase
        # ESTO ES FIJO
        mapeo_nombre_a_columna_db = {
            "Urea": "total_urea_g",
            "Fosfato Monoamónico": "total_fosfato_monoamonico_g",
            "Sulf. de Potasio": "total_sulf_de_potasio_g",
            "Sulf. de Magnesio": "total_sulf_de_magnesio_g",
            "Sulf. de Cobre": "total_sulf_de_cobre_g",
            "Sulf. de Manganeso": "total_sulf_de_manganeso_g",
            "Sulf. de Zinc": "total_sulf_de_zinc_g",
            "Boro": "total_boro_g",
            "Nitrato de Calcio": "total_nitrato_de_calcio_g"
        }
        
        # Diccionario para guardar los totales que irán a Supabase
        # Inicializamos *todas* las columnas en 0.0
        calculos_finales_g = {col: 0.0 for col in mapeo_nombre_a_columna_db.values()}
        
        # Lista para el DataFrame que se mostrará en pantalla
        display_data = []

        # Iteramos sobre la RECETA FIJA
        for nombre_fertilizante, dosis_mg_l_dia in receta_para_calculo.items():
            
            # 1. (mg/L/día) * días = mg/L totales
            dosis_total_mg_l = dosis_mg_l_dia * current_dias
            # 2. (mg/L) * L = mg totales
            total_mg = dosis_total_mg_l * current_vol_litros
            # 3. mg / 1000 = g totales
            total_g = total_mg / 1000.0
            
            # Guardar para Supabase
            nombre_col_db = mapeo_nombre_a_columna_db.get(nombre_fertilizante)
            if nombre_col_db:
                calculos_finales_g[nombre_col_db] = total_g
            
            # Guardar para mostrar
            display_data.append({"Fertilizante": nombre_fertilizante, "Cantidad Total": f"{total_g:.2f} g"})

        # Guardar los cálculos en session_state para el botón de guardar
        st.session_state.calculos_finales_g = calculos_finales_g

        if not display_data:
             st.info(f"La tarea de hoy ({st.session_state.tarea_de_hoy}) no tiene fertilizantes programados.")
        else:
            st.dataframe(pd.DataFrame(display_data), use_container_width=True)

    st.divider()

    # ======================================================================
    # PASO 5: MEDICIONES Y GUARDADO (DENTRO DEL FORMULARIO)
    # ======================================================================
    with st.form("jornada_form"):
        st.header("Paso 5: Mediciones y Notas (Guardar)")
        
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
        st.subheader("Notas Adicionales")
        observaciones = st.text_area(
            "Observaciones:", 
            placeholder=f"Ej: Se aplicó {st.session_state.tarea_de_hoy}. El drenaje de cascarilla fue X. Todo normal.",
            key="observaciones"
        )

        # --- Botón de Envío ---
        submitted = st.form_submit_button("💾 Guardar Jornada Completa")

    # --- LÓGICA DE GUARDADO ---
    if submitted:
        if not supabase:
            st.error("Error fatal: No hay conexión con Supabase.")
        elif st.session_state.testigo_vol_aplicado_ml <= 0: 
            st.warning("No se puede guardar: El 'Volumen Aplicado (mL/maceta)' debe ser mayor a cero.")
        else:
            try:
                # Recalcular el porcentaje de drenaje final al guardar
                testigo_porc_drenaje_final = (st.session_state.testigo_vol_drenado_ml / st.session_state.testigo_vol_aplicado_ml) * 100
                
                # Leemos los valores finales de los widgets usando sus keys
                datos_para_insertar = {
                    "fecha": fecha_actual_peru.strftime("%Y-%m-%d"),
                    
                    # Paso 1 (Excel)
                    "tarea_del_dia": st.session_state.tarea_de_hoy,
                    
                    # Paso 2 (Drenaje)
                    "sustrato_testigo": st.session_state.sustrato_testigo,
                    "testigo_vol_aplicado_ml": st.session_state.testigo_vol_aplicado_ml,
                    "testigo_vol_drenado_ml": st.session_state.testigo_vol_drenado_ml,
                    "testigo_porc_drenaje": testigo_porc_drenaje_final,
                    
                    # Paso 3 (Registro General)
                    "mezcla_ph_final": st.session_state.mezcla_ph_final,
                    "mezcla_ce_final": st.session_state.mezcla_ce_final,
                    "general_vol_aplicado_litros": st.session_state.general_vol_aplicado_litros,

                    # Paso 4 (Dosis)
                    "dias_aplicados": st.session_state.dias_aplicados,
                    
                    # Paso 5 (Formulario)
                    "testigo_ph_drenaje": st.session_state.testigo_ph_drenaje,
                    "testigo_ce_drenaje": st.session_state.testigo_ce_drenaje,
                    "fuente_ph": st.session_state.fuente_ph,
                    "fuente_ce": st.session_state.fuente_ce,
                    "observaciones": st.session_state.observaciones,
                }
                
                # --- AÑADIR LOS GRAMOS CALCULADOS ---
                if 'calculos_finales_g' in st.session_state:
                    datos_para_insertar.update(st.session_state.calculos_finales_g)
                
                supabase.table('Jornada_Riego').insert(datos_para_insertar).execute()
                
                st.success("¡Jornada de riego guardada exitosamente en la tabla 'Jornada_Riego'!")
                st.balloons()

            except Exception as e:
                st.error(f"Error al guardar en Supabase: {e}")
                st.warning("Error GRAVE al guardar. Posible Causa: ¿Todas las columnas de 'total_..._g' existen en la tabla 'Jornada_Riego' en Supabase?")

    # ======================================================================
    # SECCIÓN DE HISTORIAL Y GRÁFICOS
    # ======================================================================
    st.divider()
    st.header("Historial y Tendencias de la Jornada")

    @st.cache_data(ttl=300) 
    def cargar_datos_jornada():
        if not supabase:
            return pd.DataFrame()
        try:
            response = supabase.table('Jornada_Riego').select("*").order('fecha', desc=True).limit(100).execute()
            if response.data:
                df = pd.DataFrame(response.data)
                df['fecha'] = pd.to_datetime(df['fecha'])
                return df
            else:
                return pd.DataFrame() 
        except Exception as e:
            st.error(f"No se pudieron cargar los datos del historial: {e}")
            return pd.DataFrame()

    df_historial = cargar_datos_jornada()

    if df_historial.empty:
        st.info("Aún no hay registros en 'Jornada_Riego'.")
    else:
        st.write("Últimas jornadas registradas:")
        st.dataframe(df_historial.head(), use_container_width=True)

        st.subheader("Gráficos de Tendencias")
        
        sustratos_unicos = ["Todos"] + list(df_historial['sustrato_testigo'].unique())
        sustrato_filtro = st.selectbox("Filtrar gráficos por sustrato:", sustratos_unicos)
        
        df_filtrado = df_historial
        if sustrato_filtro != "Todos":
            df_filtrado = df_historial[df_historial['sustrato_testigo'] == sustrato_filtro]

        if df_filtrado.empty:
            st.warning("No hay datos para el sustrato seleccionado.")
        else:
            gcol1, gcol2 = st.columns(2)
            with gcol1:
                fig_ph_drenaje = px.line(df_filtrado, x='fecha', y='testigo_ph_drenaje', color='sustrato_testigo',
                                         title="Evolución del pH en Drenaje (Testigo)", markers=True)
                # --- [CORRECCIÓN PRINCIPAL] ---
                # Cambiar 'fig_axph_drenaje' por 'fig_ph_drenaje'
                st.plotly_chart(fig_ph_drenaje, use_container_width=True)
            with gcol2:
                fig_ce_drenaje = px.line(df_filtrado, x='fecha', y='testigo_ce_drenaje', color='sustrato_testigo',
                                         title="Evolución de la CE en Drenaje (Testigo)", markers=True)
                st.plotly_chart(fig_ce_drenaje, use_container_width=True)

            gcol3, gcol4 = st.columns(2)
            with gcol3:
                fig_ph_mezcla = px.line(df_filtrado, x='fecha', y='mezcla_ph_final',
                                         title="pH de la Mezcla Final Aplicada", markers=True)
                st.plotly_chart(fig_ph_mezcla, use_container_width=True)
            with gcol4:
                fig_ce_mezcla = px.line(df_filtrado, x='fecha', y='mezcla_ce_final',
                                         title="CE de la Mezcla Final Aplicada", markers=True)
                st.plotly_chart(fig_ce_mezcla, use_container_width=True)