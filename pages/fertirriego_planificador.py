import streamlit as st
from datetime import datetime
import numpy as np

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Riego Inteligente", page_icon="🧠💧", layout="wide")
st.title("🧠💧 Riego Inteligente Basado en Humedad y Cronograma")
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
        "volumen_riego_completo_ml": 500,
        "volumen_riego_ligero_ml": 250 # Riego para incorporar fertilizante con alta humedad
    },
    "Cascarilla de Arroz": {
        "umbral_humedad": 45.0, # Se seca más rápido, necesita riego antes
        "volumen_riego_completo_ml": 750,
        "volumen_riego_ligero_ml": 350
    }
}

# --- Lógica del cronograma ---
CRONOGRAMA = {0: "Riego Acidificado", 1: "Riego con Fertilizante", 2: "Riego Acidificado", 3: "Riego con Fertilizante", 4: "Riego Acidificado", 5: "Lavado de Sales", 6: "Descanso"}
dia_actual_idx = datetime.now().weekday()
tarea_de_hoy = CRONOGRAMA.get(dia_actual_idx, "N/A")
es_dia_de_fertilizante = "Fertilizante" in tarea_de_hoy

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
st.info(f"Tarea programada para hoy según cronograma: **{tarea_de_hoy}**")

with st.form("evaluacion_humedad_form"):
    eval_col1, eval_col2 = st.columns(2)
    with eval_col1:
        sectores_del_fundo = [
            'Hilera 1 (21 Emerald)',
            'Hilera 2 (Coco y Cascarilla)',
            'Hilera 3 (22 Biloxi)'
        ]
        sector_seleccionado = st.selectbox("Seleccione la Hilera a Evaluar:", options=sectores_del_fundo, key="sector")
    
    with eval_col2:
        if "Hilera 2" in sector_seleccionado:
            sustrato_seleccionado = st.radio("En la Hilera 2, ¿qué sustrato está midiendo?", ("Fibra de Coco", "Cascarilla de Arroz"), horizontal=True, key="sustrato")
        else:
            sustrato_seleccionado = "Fibra de Coco"
    
    st.write("Ingrese 6 lecturas de humedad (%) de 6 plantas al azar:")
    lecturas_cols = st.columns(6)
    lecturas = [st.number_input(f"Lec. {i+1}", min_value=0.0, max_value=100.0, step=1.0, key=f"lec_{i}") for i in range(6)]
            
    submitted_eval = st.form_submit_button("✅ Calcular y Obtener Recomendación")

    if submitted_eval:
        if any(l == 0.0 for l in lecturas):
            st.warning("Por favor, ingrese las 6 lecturas de humedad.")
        else:
            st.session_state.humedad_promedio = np.mean(lecturas)
            st.session_state.sector_evaluado = sector_seleccionado
            st.session_state.sustrato_evaluado = sustrato_seleccionado
            
            config = SUSTRATO_CONFIG[sustrato_seleccionado]
            umbral = config["umbral_humedad"]
            num_plantas = int(sector_seleccionado.split('(')[1].split(' ')[0])

            # --- LÓGICA DE DECISIÓN MEJORADA ---
            if es_dia_de_fertilizante:
                if st.session_state.humedad_promedio < umbral:
                    st.session_state.recomendacion_texto = f"💧 **RIEGO COMPLETO CON FERTILIZANTE.** Hoy toca fertilizar y el sustrato ({st.session_state.humedad_promedio:.1f}%) está seco (Umbral: {umbral}%)."
                    st.session_state.volumen_sugerido = config["volumen_riego_completo_ml"] * num_plantas / 1000
                else:
                    st.session_state.recomendacion_texto = f"💧 **RIEGO LIGERO CON FERTILIZANTE.** Hoy toca fertilizar. Aunque el sustrato ({st.session_state.humedad_promedio:.1f}%) está húmedo (Umbral: {umbral}%), se debe aplicar un riego reducido para incorporar los nutrientes."
                    st.session_state.volumen_sugerido = config["volumen_riego_ligero_ml"] * num_plantas / 1000
            else: # Días sin fertilizante
                if st.session_state.humedad_promedio < umbral:
                    st.session_state.recomendacion_texto = f"💧 **RECOMENDACIÓN: PROCEDER CON RIEGO.** El sustrato ({st.session_state.humedad_promedio:.1f}%) está por debajo del umbral de {umbral}%."
                    st.session_state.volumen_sugerido = config["volumen_riego_completo_ml"] * num_plantas / 1000
                else:
                    st.session_state.recomendacion_texto = f"✅ **RECOMENDACIÓN: NO REGAR.** El sustrato ({st.session_state.humedad_promedio:.1f}%) tiene suficiente humedad (Umbral: {umbral}%)."
                    st.session_state.volumen_sugerido = 0
            
            st.session_state.recommendation_generated = True

# ======================================================================================
# PASO 2 Y 3: MOSTRAR RECOMENDACIÓN Y REGISTRAR ACCIÓN
# ======================================================================================
if st.session_state.recommendation_generated:
    st.divider()
    st.header("Paso 2: Recomendación")
    st.info(st.session_state.recomendacion_texto)
    
    st.divider()
    st.header("Paso 3: Registrar Acción Realizada")
    st.write(f"Registro para: **{st.session_state.sector_evaluado} ({st.session_state.sustrato_evaluado})**")

    with st.form("registro_accion_form"):
        volumen_aplicado = st.number_input("Volumen Total Realmente Aplicado (Litros)", min_value=0.0, value=st.session_state.volumen_sugerido, step=0.5, format="%.1f")
        
        st.write("**Calidad del Agua de Origen (Antes de mezclar)**")
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            fuente_agua = st.radio("Fuente de Agua:", ("Agua de Pozo", "Agua de Canal"), horizontal=True, key="fuente_agua")
        with b_col2:
            ph_agua_fuente = st.number_input("pH del Agua (sin tratar)", min_value=0.0, value=7.0, step=0.1, format="%.2f", key="ph_fuente")
        with b_col3:
            ce_agua_fuente = st.number_input("CE del Agua (sin tratar) dS/m", min_value=0.0, value=0.5, step=0.1, format="%.2f", key="ce_fuente")

        st.write("**Mediciones Finales (En el bidón de mezcla)**")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            ph_final = st.number_input("pH final medido:", min_value=0.0, max_value=14.0, value=5.5, step=0.1, format="%.2f", key="ph_final")
        with d_col2:
            ce_final = st.number_input("CE final medida (dS/m):", min_value=0.0, value=1.0, step=0.1, format="%.2f", key="ce_final")

        observaciones = st.text_area("Notas, Productos Aplicados y Observaciones:", placeholder="Ej: Se usó ácido nítrico. La tarea del día fue Riego con Fertilizante.", key="obs")
        
        submitted_log = st.form_submit_button("💾 Guardar Registro Final")

        if submitted_log:
            if supabase:
                try:
                    datos_para_insertar = {
                        "Fecha": datetime.now().strftime("%Y-%m-%d"),
                        "Sector": st.session_state.sector_evaluado,
                        "humedad_promedio_medida": st.session_state.humedad_promedio,
                        "fuente_agua": fuente_agua,
                        "ph_agua_fuente": ph_agua_fuente,
                        "ce_agua_fuente": ce_agua_fuente,
                        "volumen_total_aplicado_litros": volumen_aplicado,
                        "pH_final": ph_final if volumen_aplicado > 0 else None,
                        "CE_final": ce_final if volumen_aplicado > 0 else None,
                        "Observaciones": f"Sustrato medido: {st.session_state.sustrato_evaluado}. Tarea del día: {tarea_de_hoy}. Notas: {observaciones}"
                    }
                    supabase.table('Riego_Registros').insert(datos_para_insertar).execute()
                    st.success("¡Registro de jornada guardado exitosamente!")
                    st.balloons()
                    # Limpiar estado para la próxima evaluación
                    st.session_state.recommendation_generated = False
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}")

