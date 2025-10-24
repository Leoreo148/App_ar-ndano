import streamlit as st
from datetime import datetime
import pandas as pd
import pytz # Para la zona horaria

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestor de Fertirriego", page_icon="🧑‍🔬", layout="wide")
st.title("🧑‍🔬 Gestor de Fertirriego")
st.write("Registre la preparación de Soluciones Madre y la aplicación diaria de riegos.")

# --- ZONA HORARIA DE PERÚ (SOLUCIÓN AL BUG DE LA HORA) ---
try:
    TZ_PERU = pytz.timezone('America/Lima')
except ImportError:
    st.error("Se necesita la librería 'pytz'. Instálala con: pip install pytz")
    TZ_PERU = None

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

# --- EL "CEREBRO": BASE DE DATOS DE FERTILIZANTES (Basado en tu Excel) ---
FERTILIZANTES_DB = {
    # --- Grupo 1: Compatibles (Para Solución Madre) ---
    "Urea": {"grupo": 1, "nutrientes": ["N"]},
    "Fosfato Monoamonico (MAP)": {"grupo": 1, "nutrientes": ["N", "P"]},
    "Sulfato de Potasio": {"grupo": 1, "nutrientes": ["K", "S"]},
    "Sulfato de Manganeso": {"grupo": 1, "nutrientes": ["Mn", "S"]},
    "Acido Bórico": {"grupo": 1, "nutrientes": ["B"]},
    "Sulfato de Zinc": {"grupo": 1, "nutrientes": ["Zn", "S"]},
    "Sulfato de Cobre": {"grupo": 1, "nutrientes": ["Cu", "S"]},
    
    # --- Grupo 2: Incompatibles (Calcio) ---
    "Nitrato de Calcio": {"grupo": 2, "nutrientes": ["N", "Ca"]},
    
    # --- Grupo 3: Manejo Especial (Magnesio) ---
    "Sulfato de Magnesio": {"grupo": 3, "nutrientes": ["Mg", "S"]},
    "Nitrato de Magnesio": {"grupo": 3, "nutrientes": ["N", "Mg"]},

    # --- Ácidos (Grupo especial 0) ---
    "Ácido Nítrico": {"grupo": 0, "nutrientes": ["N"]},
    "Ácido Fosfórico": {"grupo": 0, "nutrientes": ["P"]},
}

# Listas filtradas para los menús desplegables
PRODUCTOS_COMPATIBLES = sorted([f for f, d in FERTILIZANTES_DB.items() if d["grupo"] == 1 or d["grupo"] == 0])
PRODUCTOS_INCOMPATIBLES = sorted([f for f, d in FERTILIZANTES_DB.items() if d["grupo"] == 2 or d["grupo"] == 3])

# --- Inicializar Session State para productos ---
if 'productos_compatibles' not in st.session_state:
    st.session_state.productos_compatibles = []
if 'productos_adicionales' not in st.session_state:
    st.session_state.productos_adicionales = []

# ======================================================================================
# --- ESTRUCTURA DE PESTAÑAS: MÓDULO 1 Y MÓDULO 2 ---
# ======================================================================================
tab1, tab2 = st.tabs(["Preparar Solución Madre (Semanal)", "Registro de Riego Diario"])

# ======================================================================================
# MÓDULO 1: PREPARAR SOLUCIÓN MADRE (Pestaña 1)
# ======================================================================================
with tab1:
    st.header("Módulo 1: Preparar Solución Madre (Bidón 200L)")
    st.write("Use este formulario una vez por semana (o cada vez que prepare el bidón celeste) para registrar la mezcla base de productos compatibles.")

    with st.form("solucion_madre_form", clear_on_submit=True):
        st.subheader("1. Datos Generales de la Solución")
        col1, col2 = st.columns(2)
        with col1:
            fecha_preparacion = st.date_input("Fecha de Preparación", datetime.now(TZ_PERU) if TZ_PERU else datetime.now())
            nombre_solucion = st.text_input("Nombre o Apodo de la Solución", placeholder="Ej: Mezcla NPK Semana 43")
        with col2:
            volumen_total = st.number_input("Volumen Total de la Solución (Litros)", min_value=1.0, value=200.0)
        
        st.subheader("2. Mediciones del Agua (Antiguas)")
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            ph_agua_fuente = st.number_input("pH del Agua (Fuente)", min_value=0.0, value=7.0, step=0.1, format="%.2f")
        with mcol2:
            ce_agua_fuente = st.number_input("CE del Agua (Fuente) dS/m", min_value=0.0, value=0.5, step=0.1, format="%.2f")

        st.subheader("3. Fertilizantes Compatibles (Grupo 1)")
        
        # --- Lógica para añadir productos dinámicamente ---
        if 'num_compatibles' not in st.session_state:
            st.session_state.num_compatibles = 1

        def add_compatible():
            st.session_state.num_compatibles += 1
        
        for i in range(st.session_state.num_compatibles):
            pcol1, pcol2, pcol3 = st.columns([2, 1, 3])
            with pcol1:
                st.selectbox("Producto Compatible", PRODUCTOS_COMPATIBLES, key=f"comp_prod_{i}")
            with pcol2:
                st.number_input("Dosis (gramos)", min_value=0.0, step=10.0, key=f"comp_dosis_{i}")
        st.button("Añadir otro producto compatible", on_click=add_compatible)
        
        st.subheader("4. Mediciones Finales (Nuevas)")
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            ph_final = st.number_input("pH Final de la Solución", min_value=0.0, max_value=14.0, value=5.5, step=0.1, format="%.2f")
        with fcol2:
            ce_final = st.number_input("CE Final de la Solución (dS/m)", min_value=0.0, value=1.5, step=0.1, format="%.2f")

        # --- Botón de Envío del Módulo 1 ---
        submitted_madre = st.form_submit_button("💾 Guardar Solución Madre")

        if submitted_madre:
            if not nombre_solucion:
                st.warning("Por favor, ingrese un nombre o apodo para la solución.")
            elif supabase:
                # Recolectar productos
                productos_json = []
                for i in range(st.session_state.num_compatibles):
                    producto_nombre = st.session_state[f"comp_prod_{i}"]
                    producto_dosis = st.session_state[f"comp_dosis_{i}"]
                    if producto_dosis > 0:
                        productos_json.append({
                            "producto": producto_nombre,
                            "dosis_gramos_total": producto_dosis,
                            "nutrientes": FERTILIZANTES_DB.get(producto_nombre, {}).get("nutrientes", [])
                        })
                
                try:
                    datos_para_insertar = {
                        "fecha_preparacion": fecha_preparacion.strftime("%Y-%m-%d"),
                        "nombre_solucion": nombre_solucion,
                        "volumen_total_litros": volumen_total,
                        "ph_agua_fuente": ph_agua_fuente,
                        "ce_agua_fuente": ce_agua_fuente,
                        "productos_compatibles": productos_json, # ¡Guardamos el JSON!
                        "ph_final_solucion": ph_final,
                        "ce_final_solucion": ce_final
                    }
                    supabase.table('Soluciones_Madre').insert(datos_para_insertar).execute()
                    st.success(f"¡Solución Madre '{nombre_solucion}' guardada exitosamente!")
                    st.session_state.num_compatibles = 1 # Reiniciar
                except Exception as e:
                    st.error(f"Error al guardar en Supabase (Soluciones_Madre): {e}")

# ======================================================================================
# MÓDULO 2: REGISTRO DE RIEGO DIARIO (Pestaña 2)
# ======================================================================================
with tab2:
    st.header("Módulo 2: Registro de Riego Diario")
    st.write("Use este formulario todos los días para registrar la aplicación de riego.")

    # --- Cargar Soluciones Madre para el desplegable (Tu "idea bacán") ---
    @st.cache_data(ttl=300)
    def cargar_soluciones_madre():
        if not supabase:
            return {}
        try:
            response = supabase.table('Soluciones_Madre').select('id, nombre_solucion').order('fecha_preparacion', desc=True).limit(20).execute()
            soluciones = response.data
            # Crear un diccionario {Nombre: id}
            return {s['nombre_solucion']: s['id'] for s in soluciones}
        except Exception as e:
            st.error(f"Error al cargar Soluciones Madre: {e}")
            return {}

    soluciones_madre_dict = cargar_soluciones_madre()
    if not soluciones_madre_dict:
        st.warning("No se encontraron Soluciones Madre. Por favor, registre una en la Pestaña 1.")
        st.stop()

    with st.form("riego_diario_form", clear_on_submit=True):
        st.subheader("1. Datos Generales del Riego")
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            fecha_riego = st.date_input("Fecha del Riego", datetime.now(TZ_PERU) if TZ_PERU else datetime.now())
        with dcol2:
            # Hileras 1 y 2 (la 3 se fue)
            sector_seleccionado = st.selectbox("Hilera Regada:", 
                                               options=['Hilera 1 (21 Emerald)', 'Hilera 2 (23 Coco y Cascarilla)'])

        st.subheader("2. Aplicación de Solución Madre")
        scol1, scol2 = st.columns(2)
        with scol1:
            # ¡Tu "idea bacán" en acción!
            solucion_nombre_sel = st.selectbox("Solución Madre Utilizada:", 
                                               options=list(soluciones_madre_dict.keys()))
        with scol2:
            volumen_aplicado = st.number_input("Volumen de Sol. Madre Aplicado (Litros)", min_value=0.0, step=1.0)

        st.subheader("3. Aplicación Adicional (Incompatibles - Grupo 2/3)")
        
        # --- Lógica para añadir productos adicionales ---
        if 'num_adicionales' not in st.session_state:
            st.session_state.num_adicionales = 0 # Empezar en 0, solo añadir si es necesario

        def add_adicional():
            st.session_state.num_adicionales += 1
        
        if st.session_state.num_adicionales == 0:
            st.button("Añadir Producto Adicional (Ej: Calcio)", on_click=add_adicional)
        else:
            for i in range(st.session_state.num_adicionales):
                pcol1, pcol2, pcol3 = st.columns([2, 1, 1])
                with pcol1:
                    st.selectbox("Producto Adicional/Incompatible", PRODUCTOS_INCOMPATIBLES, key=f"adic_prod_{i}")
                with pcol2:
                    st.number_input("Dosis (gramos)", min_value=0.0, step=1.0, key=f"adic_dosis_{i}")
                with pcol3:
                    st.number_input("Vol. Agua (L)", min_value=0.0, step=1.0, key=f"adic_vol_{i}", help="Volumen de agua usado para esta mezcla separada (ej: en balde)")
        
        st.subheader("4. Mediciones Finales (Opcional si es lo mismo que la S. Madre)")
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            ph_final_diario = st.number_input("pH Final (en punto de riego)", min_value=0.0, max_value=14.0, value=5.5, step=0.1, format="%.2f")
        with fcol2:
            ce_final_diario = st.number_input("CE Final (en punto de riego) (dS/m)", min_value=0.0, value=1.5, step=0.1, format="%.2f")

        observaciones = st.text_area("Observaciones del Día:", placeholder="Ej: Se aplicó Calcio en balde separado. El bidón celeste sigue a 1/2 capacidad.")

        # --- Botón de Envío del Módulo 2 ---
        submitted_diario = st.form_submit_button("💾 Guardar Riego del Día")

        if submitted_diario:
            if not solucion_nombre_sel:
                st.warning("Debe seleccionar una Solución Madre.")
            elif supabase:
                # Recolectar productos adicionales
                productos_adicionales_json = []
                for i in range(st.session_state.num_adicionales):
                    producto_nombre = st.session_state[f"adic_prod_{i}"]
                    producto_dosis = st.session_state[f"adic_dosis_{i}"]
                    producto_vol = st.session_state[f"adic_vol_{i}"]
                    if producto_dosis > 0:
                        productos_adicionales_json.append({
                            "producto": producto_nombre,
                            "dosis_gramos": producto_dosis,
                            "volumen_agua_litros": producto_vol,
                            "nutrientes": FERTILIZANTES_DB.get(producto_nombre, {}).get("nutrientes", [])
                        })
                
                try:
                    datos_para_insertar = {
                        "Fecha": fecha_riego.strftime("%Y-%m-%d"),
                        "Sector": sector_seleccionado,
                        "id_solucion_madre": soluciones_madre_dict[solucion_nombre_sel], # ¡Guardamos el ID!
                        "volumen_total_aplicado_litros": volumen_aplicado,
                        "productos_adicionales_incompatibles": productos_adicionales_json, # ¡Guardamos el JSON!
                        "pH_final": ph_final_diario,
                        "CE_final": ce_final_diario,
                        "Observaciones": observaciones
                    }
                    supabase.table('Riego_Registros').insert(datos_para_insertar).execute()
                    st.success(f"¡Riego diario para '{sector_seleccionado}' guardado exitosamente!")
                    st.session_state.num_adicionales = 0 # Reiniciar
                except Exception as e:
                    st.error(f"Error al guardar en Supabase (Riego_Registros): {e}")

    # --- Mostrar últimos registros ---
    st.divider()
    st.subheader("Últimos Riegos Diarios Registrados")
    @st.cache_data(ttl=60)
    def cargar_riegos_diarios():
        try:
            response = supabase.table('Riego_Registros').select("*").order('Fecha', desc=True).limit(10).execute()
            return pd.DataFrame(response.data)
        except Exception as e:
            st.error(f"Error al cargar historial de riegos: {e}")
            return pd.DataFrame()

    df_riegos = cargar_riegos_diarios()
    if not df_riegos.empty:
        st.dataframe(df_riegos, use_container_width=True)
    else:
        st.info("Aún no hay registros de riegos diarios.")

