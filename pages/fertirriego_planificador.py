import streamlit as st
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registro de Riego", page_icon="💧", layout="wide")
st.title("💧 Registro de Jornada de Riego y Fertirriego")
st.write("Registre aquí las mediciones y acciones realizadas durante la jornada de riego, según el cronograma.")

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

# --- SECCIÓN 1: LÓGICA Y VISUALIZACIÓN DEL CRONOGRAMA ---
st.header("📅 Tarea del Día")

# Definimos el cronograma (Lunes=0, Martes=1, ..., Domingo=6)
CRONOGRAMA = {
    0: "Riego Acidificado",
    1: "Riego con Fertilizante",
    2: "Riego Acidificado",
    3: "Riego con Fertilizante",
    4: "Riego Acidificado",
    5: "Lavado de Sales",
    6: "Día de Descanso / Sin tarea programada"
}

# Obtenemos el día de la semana actual
dia_actual_idx = datetime.now().weekday()
tarea_de_hoy = CRONOGRAMA.get(dia_actual_idx, "Tarea no definida")
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
nombre_dia_hoy = dias_semana[dia_actual_idx]

st.info(f"**Hoy es {nombre_dia_hoy}:** La tarea programada es **{tarea_de_hoy}**.")

st.divider()

# --- SECCIÓN 2: FORMULARIO DE REGISTRO DE LA JORNADA ---
st.header("📝 Formulario de Registro")

with st.form("registro_riego_form"):
    
    # --- A. Datos Generales ---
    st.subheader("A. Datos Generales")
    sectores_del_fundo = [
        'Hilera 1 (21 Emerald)',
        'Hilera 2 (23 Biloxi/Emerald)',
        'Hilera 3 (22 Biloxi)'
    ]
    sector_seleccionado = st.selectbox("Seleccione la Hilera a Regar:", options=sectores_del_fundo)
    
    # --- B. Calidad del Agua de Origen ---
    st.subheader("B. Calidad del Agua de Origen (Antes de mezclar)")
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1:
        fuente_agua = st.radio("Fuente de Agua:", ("Agua de Pozo", "Agua de Canal"), horizontal=True)
    with b_col2:
        ph_agua_fuente = st.number_input("pH del Agua (sin tratar)", min_value=0.0, value=7.0, step=0.1, format="%.2f")
    with b_col3:
        ce_agua_fuente = st.number_input("CE del Agua (sin tratar) dS/m", min_value=0.0, value=0.5, step=0.1, format="%.2f")

    # --- C. Ejecución y Notas ---
    st.subheader("C. Ejecución y Notas")
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        volumen_aplicado = st.number_input("Volumen Total Aplicado (Litros)", min_value=0.0, value=20.0, step=0.5, format="%.1f")
    with c_col2:
        siguio_cronograma = st.checkbox("¿Se siguió la tarea del cronograma sin cambios?", value=True)
    
    observaciones = st.text_area(
        "Notas, Productos Aplicados y Observaciones:",
        placeholder="Ej: Se usó ácido fosfórico para bajar pH. Se aplicaron 750ml/planta con jarra."
    )

    # --- D. Mediciones Finales ---
    st.subheader("D. Mediciones Finales (En el bidón de mezcla)")
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        ph_final = st.number_input("pH final medido:", min_value=0.0, max_value=14.0, value=5.5, step=0.1, format="%.2f")
    with d_col2:
        ce_final = st.number_input("CE final medida (dS/m):", min_value=0.0, value=1.0, step=0.1, format="%.2f")

    # --- Botón de Envío ---
    submitted = st.form_submit_button("✅ Guardar Registro de la Jornada")
    
    # --- Lógica de Guardado ---
    if submitted:
        if not sector_seleccionado:
            st.warning("Por favor, seleccione una hilera.")
        elif supabase:
            try:
                # El diccionario DEBE coincidir con los nombres de tus columnas en Supabase
                datos_para_insertar = {
                    "Fecha": datetime.now().strftime("%Y-%m-%d"),
                    "Sector": sector_seleccionado,
                    "ph_agua_fuente": ph_agua_fuente,
                    "ce_agua_fuente": ce_agua_fuente,
                    "fuente_agua": fuente_agua,
                    "volumen_total_aplicado_litros": volumen_aplicado, # Asegúrate de añadir esta columna
                    "siguio_cronograma": siguio_cronograma,
                    "Observaciones": observaciones, # Usamos la columna existente para las notas
                    "pH_final": ph_final,
                    "CE_final": ce_final
                }
                supabase.table('Riego_Registros').insert(datos_para_insertar).execute()
                st.success(f"¡Registro para la '{sector_seleccionado}' guardado exitosamente!")
                st.balloons()
            except Exception as e:
                st.error(f"Error al guardar en Supabase: {e}")