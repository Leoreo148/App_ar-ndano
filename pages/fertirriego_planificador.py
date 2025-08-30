import streamlit as st
import pandas as pd
from datetime import datetime
import json

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Planificador de Fertirriego", page_icon="🧑‍🔬", layout="wide")
st.title("🧑‍🔬 Planificador de Fertirriego")
st.write("Calcule y registre las recetas de nutrientes para cada hilera según la etapa fenológica.")

# --- DATOS DE LA INVESTIGACIÓN (Tabla 3) ---
# Dosis de referencia en Unidades Fertilizantes (UF) por hectárea por semana.
PLAN_FERTIRRIEGO = {
    "Brotación a Pre-floración": {"N": 9, "P2O5": 9, "K2O": 7, "CaO": 6, "MgO": 3},
    "Floración a Cuajado": {"N": 7, "P2O5": 11, "K2O": 11, "CaO": 11, "MgO": 4},
    "Inicio Crecimiento Fruto": {"N": 6, "P2O5": 9, "K2O": 18, "CaO": 17, "MgO": 5},
    "Llenado de Fruto a Envero": {"N": 5, "P2O5": 6, "K2O": 28, "CaO": 9, "MgO": 5},
    "Cosecha": {"N": 3, "P2O5": 3, "K2O": 23, "CaO": 4, "MgO": 3},
    "Post-Cosecha": {"N": 6, "P2O5": 5, "K2O": 8, "CaO": 5, "MgO": 4}
}
PLANTAS_POR_HECTAREA_ESTANDAR = 10000

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

# --- INTERFAZ PRINCIPAL ---
st.header("1. Cálculo de la Receta Diaria")

col1, col2 = st.columns(2)
with col1:
    etapas_relevantes = ["Brotación a Pre-floración", "Floración a Cuajado"]
    etapa_seleccionada = st.selectbox(
        "Seleccione la Etapa Fenológica Actual:",
        options=etapas_relevantes
    )
with col2:
    sectores_del_fundo = [
        'Hilera 1 (21 Emerald)',
        'Hilera 2 (23 Biloxi/Emerald)',
        'Hilera 3 (22 Biloxi)'
    ]
    sector_seleccionado = st.selectbox("Seleccione la Hilera a Preparar:", options=sectores_del_fundo)

# Lógica para obtener el número de plantas
try:
    num_plantas_actual = int(sector_seleccionado.split('(')[1].split(' ')[0])
except:
    num_plantas_actual = 20 # Fallback

st.divider()

# Mostrar la recomendación y el cálculo
if etapa_seleccionada and sector_seleccionado:
    dosis_semanal_ha = PLAN_FERTIRRIEGO[etapa_seleccionada]
    
    st.subheader(f"Recomendación para: '{etapa_seleccionada}'")
    st.write("Dosis de referencia según investigación (UF/ha/semana):")
    st.json(dosis_semanal_ha)

    st.subheader(f"Dosis Calculada para '{sector_seleccionado}' ({num_plantas_actual} plantas)")
    st.info("La siguiente tabla muestra los **gramos de nutriente puro** que se deben aplicar **por día** en el bidón de esta hilera.")

    dosis_diaria_bidon = {}
    for nutriente, valor_uf in dosis_semanal_ha.items():
        # (UF/ha/semana * 1000 g/kg) / (plantas/ha) / (7 dias/semana) * (N° plantas en la hilera)
        gramos_dia = (valor_uf * 1000 / PLANTAS_POR_HECTAREA_ESTANDAR / 7) * num_plantas_actual
        dosis_diaria_bidon[f"Gramos de {nutriente} / día"] = f"{gramos_dia:.2f} g"
    
    st.dataframe(pd.DataFrame.from_dict(dosis_diaria_bidon, orient='index', columns=["Dosis Diaria Calculada"]), use_container_width=True)


st.divider()

# --- Formulario de Registro ---
with st.expander("📝 Registrar Preparación de Mezcla", expanded=True):
    with st.form("registro_fertirriego_form"):
        st.header("2. Registro de Preparación")
        
        responsables_equipo = ["Alumno 1", "Alumno 2", "Alumno 3", "Alumno 4", "Alumno 5", "Alumno 6", "Alumno 7"]
        responsables_seleccionados = st.multiselect("Seleccione los Responsables de la Mezcla:", options=responsables_equipo)
        
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            ph_final = st.number_input("pH final medido en el bidón:", min_value=0.0, max_value=14.0, value=5.5, step=0.1, format="%.2f")
        with fcol2:
            ce_final = st.number_input("CE final medida en el bidón (dS/m):", min_value=0.0, value=0.8, step=0.1, format="%.2f")
            
        observaciones = st.text_area("Observaciones (filtraciones, disolución de productos, etc.):")
        
        submitted = st.form_submit_button("✅ Guardar Registro de Preparación")
        
        if submitted:
            if not responsables_seleccionados:
                st.warning("Por favor, seleccione al menos un responsable.")
            elif supabase:
                try:
                    datos_para_insertar = {
                        "Fecha": datetime.now().strftime("%Y-%m-%d"),
                        "Sector": sector_seleccionado,
                        "Etapa_Fenologica": etapa_seleccionada,
                        "Responsables": responsables_seleccionados,
                        "pH_final": ph_final,
                        "CE_final": ce_final,
                        "Observaciones": observaciones
                    }
                    supabase.table('Riego_Registros').insert(datos_para_insertar).execute() 
                    st.success("¡Registro de fertirriego guardado exitosamente!")
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}")


