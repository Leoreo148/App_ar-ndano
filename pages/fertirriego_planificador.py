import streamlit as st
from datetime import datetime
import numpy as np

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Riego Inteligente", page_icon="🧠💧", layout="wide")
st.title("🧠💧 Riego Inteligente Basado en Humedad")
st.write("Mida la humedad del sustrato para obtener una recomendación y luego registre la acción de riego.")

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

# --- DEFINICIÓN DE UMBRALES Y RECOMENDACIONES POR SUSTRATO ---
SUSTRATO_CONFIG = {
    "Fibra de Coco": {
        "umbral_humedad": 35.0, # % por debajo del cual se recomienda regar
        "volumen_recomendado_ml": 500
    },
    "Cascarilla de Arroz": {
        "umbral_humedad": 45.0, # Se seca más rápido, necesita riego antes
        "volumen_recomendado_ml": 750
    }
}

# --- Inicializar Session State ---
if 'recommendation_generated' not in st.session_state:
    st.session_state.recommendation_generated = False
    st.session_state.humedad_promedio = 0.0
    st.session_state.sector_evaluado = ""
    st.session_state.sustrato_evaluado = ""
    st.session_state.recomendacion_texto = ""
    st.session_state.volumen_sugerido = 0

# ======================================================================================
# PASO 1: FORMULARIO DE EVALUACIÓN DE HUMEDAD
# ======================================================================================
st.header("Paso 1: Medir Humedad del Sustrato")

with st.form("evaluacion_humedad_form"):
    eval_col1, eval_col2 = st.columns(2)
    with eval_col1:
        sectores_del_fundo = [
            'Hilera 1 (Fibra de Coco)',
            'Hilera 2 (Coco y Cascarilla)',
            'Hilera 3 (Fibra de Coco)'
        ]
        sector_seleccionado = st.selectbox("Seleccione la Hilera a Evaluar:", options=sectores_del_fundo, key="sector")
    
    with eval_col2:
        # Lógica para la Hilera 2
        if "Hilera 2" in sector_seleccionado:
            sustrato_seleccionado = st.radio(
                "En la Hilera 2, ¿qué sustrato está midiendo?",
                ("Fibra de Coco", "Cascarilla de Arroz"),
                horizontal=True,
                key="sustrato"
            )
        else:
            sustrato_seleccionado = "Fibra de Coco"
    
    st.write("Ingrese 6 lecturas de humedad (%) de 6 plantas al azar:")
    
    lecturas_cols = st.columns(6)
    lecturas = []
    for i in range(6):
        with lecturas_cols[i]:
            lectura = st.number_input(f"Lectura {i+1}", min_value=0.0, max_value=100.0, step=1.0, key=f"lec_{i}")
            lecturas.append(lectura)
            
    submitted_eval = st.form_submit_button("✅ Calcular y Obtener Recomendación")

    if submitted_eval:
        if any(l == 0.0 for l in lecturas):
            st.warning("Por favor, ingrese las 6 lecturas de humedad.")
        else:
            # Guardar estado y generar recomendación
            st.session_state.humedad_promedio = np.mean(lecturas)
            st.session_state.sector_evaluado = sector_seleccionado
            st.session_state.sustrato_evaluado = sustrato_seleccionado
            
            config = SUSTRATO_CONFIG[sustrato_seleccionado]
            umbral = config["umbral_humedad"]
            volumen = config["volumen_recomendado_ml"]

            if st.session_state.humedad_promedio < umbral:
                st.session_state.recomendacion_texto = f"💧 **RECOMENDACIÓN: PROCEDER CON RIEGO.** El sustrato ({st.session_state.humedad_promedio:.1f}%) está por debajo del umbral de {umbral}%."
                st.session_state.volumen_sugerido = volumen * int(sector_seleccionado.split('(')[1].split(' ')[0]) / 1000 # Convertir a Litros totales
            else:
                st.session_state.recomendacion_texto = f"✅ **RECOMENDACIÓN: NO REGAR.** El sustrato ({st.session_state.humedad_promedio:.1f}%) tiene suficiente humedad (Umbral: {umbral}%)."
                st.session_state.volumen_sugerido = 0
            
            st.session_state.recommendation_generated = True

# ======================================================================================
# PASO 2: MOSTRAR RECOMENDACIÓN
# ======================================================================================
if st.session_state.recommendation_generated:
    st.divider()
    st.header("Paso 2: Recomendación")
    if "NO REGAR" in st.session_state.recomendacion_texto:
        st.success(st.session_state.recomendacion_texto)
    else:
        st.info(st.session_state.recomendacion_texto)
    
    st.divider()
    # ======================================================================================
    # PASO 3: FORMULARIO DE REGISTRO DE ACCIÓN
    # ======================================================================================
    st.header("Paso 3: Registrar Acción Realizada")
    st.write(f"Registro para: **{st.session_state.sector_evaluado} ({st.session_state.sustrato_evaluado})**")

    with st.form("registro_accion_form"):
        # Lógica del cronograma
        CRONOGRAMA = {0: "Riego Acidificado", 1: "Riego con Fertilizante", 2: "Riego Acidificado", 3: "Riego con Fertilizante", 4: "Riego Acidificado", 5: "Lavado de Sales", 6: "Descanso"}
        dia_actual_idx = datetime.now().weekday()
        tarea_de_hoy = CRONOGRAMA.get(dia_actual_idx, "N/A")
        st.info(f"Tarea programada para hoy según cronograma: **{tarea_de_hoy}**")

        # Formulario de registro
        volumen_aplicado = st.number_input("Volumen Total Realmente Aplicado (Litros)", min_value=0.0, value=st.session_state.volumen_sugerido, step=0.5, format="%.1f")
        
        st.write("**Calidad del Agua de Origen (Antes de mezclar)**")
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            fuente_agua = st.radio("Fuente de Agua:", ("Agua de Pozo", "Agua de Canal"), horizontal=True)
        with b_col2:
            ph_agua_fuente = st.number_input("pH del Agua (sin tratar)", min_value=0.0, value=7.0, step=0.1, format="%.2f")
        with b_col3:
            ce_agua_fuente = st.number_input("CE del Agua (sin tratar) dS/m", min_value=0.0, value=0.5, step=0.1, format="%.2f")

        st.write("**Mediciones Finales (En el bidón de mezcla)**")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            ph_final = st.number_input("pH final medido:", min_value=0.0, max_value=14.0, value=5.5, step=0.1, format="%.2f")
        with d_col2:
            ce_final = st.number_input("CE final medida (dS/m):", min_value=0.0, value=1.0, step=0.1, format="%.2f")

        observaciones = st.text_area("Notas, Productos Aplicados y Observaciones:", placeholder="Ej: Se usó ácido nítrico. La tarea del día fue Riego con Fertilizante.")
        
        submitted_log = st.form_submit_button("💾 Guardar Registro Final")

        if submitted_log:
            if supabase:
                try:
                    datos_para_insertar = {
                        "Fecha": datetime.now().strftime("%Y-%m-%d"),
                        "Sector": st.session_state.sector_evaluado,
                        "humedad_promedio_medida": st.session_state.humedad_promedio, # DATO CLAVE NUEVO
                        "fuente_agua": fuente_agua,
                        "ph_agua_fuente": ph_agua_fuente,
                        "ce_agua_fuente": ce_agua_fuente,
                        "volumen_total_aplicado_litros": volumen_aplicado,
                        "pH_final": ph_final if volumen_aplicado > 0 else None, # No guardar pH/CE si no se regó
                        "CE_final": ce_final if volumen_aplicado > 0 else None,
                        "Observaciones": f"Sustrato medido: {st.session_state.sustrato_evaluado}. Tarea del día: {tarea_de_hoy}. Notas: {observaciones}"
                    }
                    supabase.table('Riego_Registros').insert(datos_para_insertar).execute()
                    st.success("¡Registro de jornada guardado exitosamente!")
                    st.balloons()
                    # Limpiar estado para la próxima evaluación
                    st.session_state.recommendation_generated = False
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}")
