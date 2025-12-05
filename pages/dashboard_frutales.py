import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Costos Frutales", page_icon="🍇", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .stHeader {
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNCIÓN INTELIGENTE PARA DETECTAR COLUMNAS ---
def detectar_indices_columnas(fila_valores):
    """
    Escanea una fila (cabecera) para encontrar en qué posición están los datos
    de Costo 88m2 y Costo Hectárea.
    """
    idx_88 = -1
    idx_ha = -1
    idx_actividad = -1
    idx_semana = -1
    
    fila_str = [str(x).lower().strip() for x in fila_valores]
    
    for i, val in enumerate(fila_str):
        # Buscar Semana
        if "semana" in val and "lunes" in val:
            idx_semana = i
        
        # Buscar Actividad
        if ("actividad" in val or "insumo" in val or "detalle" in val) and idx_actividad == -1:
            idx_actividad = i
            
        # Buscar Costos (La parte difícil)
        # Costo Ha suele tener "ha" y "total" y "dólares"
        if "total" in val and "ha" in val and ("dólar" in val or "dolar" in val):
            idx_ha = i
        # Costo 88m2 suele ser "costo total (dólares)" sin la palabra Ha (o a veces está antes)
        elif "total" in val and ("dólar" in val or "dolar" in val) and "ha" not in val:
            idx_88 = i
            
    # Fallback (Si no encuentra, usa posiciones comunes del Excel que subiste)
    if idx_semana == -1: idx_semana = 0
    if idx_actividad == -1: idx_actividad = 2
    if idx_ha == -1: idx_ha = 10 # Suele estar al final
    if idx_88 == -1: idx_88 = 9  # Suele estar antes de Ha
    
    return idx_semana, idx_actividad, idx_88, idx_ha

# --- FUNCIÓN DE LIMPIEZA MAESTRA ---
def procesar_hoja_compleja(df_raw, nombre_hoja):
    data = []
    current_month = "General" # Valor por defecto
    current_week = "S/N"
    
    # Índices iniciales
    col_semana_idx = 0
    col_actividad_idx = 2
    col_costo88_idx = 9
    col_costoha_idx = 10
    
    # Iterar filas
    for index, row in df_raw.iterrows():
        row_str = [str(x) for x in row.values]
        row_vals = row.values
        
        # 1. DETECTAR CAMBIO DE MES
        found_month = False
        for cell in row_str:
            if "Mes -" in cell:
                parts = cell.split("-")
                if len(parts) > 1:
                    current_month = parts[1].strip()
                    current_week = "S/N" # Resetear semana al cambiar mes
                    found_month = True
                    break
        if found_month:
            continue

        # 2. DETECTAR CABECERAS (Para recalibrar índices si cambian en proyecciones)
        # Si la fila tiene "Costo Total", re-detectamos columnas
        is_header = False
        for cell in row_str:
            if "Costo Total" in cell:
                col_semana_idx, col_actividad_idx, col_costo88_idx, col_costoha_idx = detectar_indices_columnas(row_vals)
                is_header = True
                break
        if is_header:
            continue

        # 3. EXTRAER DATOS
        try:
            val_semana_raw = row_vals[col_semana_idx]
            val_actividad = row_vals[col_actividad_idx]
            
            # --- LÓGICA FILL FORWARD SEMANA ---
            if not pd.isna(val_semana_raw) and str(val_semana_raw).strip() not in ["", "nan", "None"]:
                current_week = str(val_semana_raw).strip()
            
            # --- EXTRAER COSTOS ---
            # Costo 88m2
            costo88_val = 0.0
            try:
                raw_88 = row_vals[col_costo88_idx]
                if not pd.isna(raw_88):
                    costo88_val = float(raw_88)
            except:
                costo88_val = 0.0
                
            # Costo Ha
            costoha_val = 0.0
            try:
                raw_ha = row_vals[col_costoha_idx]
                if not pd.isna(raw_ha):
                    costoha_val = float(raw_ha)
            except:
                costoha_val = 0.0

            # Validar que sea una fila de datos (tiene que haber algún costo o actividad)
            if costo88_val == 0 and costoha_val == 0 and (pd.isna(val_actividad) or str(val_actividad)=='nan'):
                continue
            
            # Si es una fila de "TOTAL", la saltamos para no duplicar suma
            if str(val_actividad).lower() == "total" or "total" in str(row_vals[0]).lower():
                continue

            data.append({
                "Mes": current_month,
                "Semana": current_week,
                "Actividad": str(val_actividad) if not pd.isna(val_actividad) else "Varios",
                "Costo_88m2": costo88_val,
                "Costo_Ha": costoha_val,
                "Categoria": nombre_hoja
            })
            
        except IndexError:
            continue

    return pd.DataFrame(data)

# --- INTERFAZ PRINCIPAL ---

st.title("🍓 Dashboard de Costos y Proyecciones")
st.markdown("### Análisis Financiero Agrícola")

# Carga de Archivo
uploaded_file = st.sidebar.file_uploader("📂 Sube 'FRUTALES COSTOS (1).xlsx'", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    all_sheets = xls.sheet_names
    
    # Mapeo de hojas
    sheet_mo = next((s for s in all_sheets if "mano" in s.lower() and "obra" in s.lower()), None)
    sheet_insumos = next((s for s in all_sheets if "insumo" in s.lower()), None)
    sheet_maq = next((s for s in all_sheets if "maquinaria" in s.lower()), None)
    sheet_proy = next((s for s in all_sheets if "proyecc" in s.lower()), None)

    # --- BARRA LATERAL ---
    st.sidebar.header("⚙️ Configuración")
    
    # 1. SELECTOR DE UNIDAD (LO QUE PIDIERON TUS AMIGOS)
    tipo_analisis = st.sidebar.radio(
        "📐 Unidad de Análisis:",
        ["Proyecto Actual (88 m²)", "Proyección Hectárea (1 Ha)"],
        index=0
    )
    # Definimos qué columna usar según la elección
    col_uso = "Costo_88m2" if "88" in tipo_analisis else "Costo_Ha"
    
    st.sidebar.divider()
    
    # 2. SELECTOR DE SECCIÓN
    seccion = st.sidebar.radio("📍 Sección:", 
        ["Resumen General", "Mano de Obra", "Insumos", "Maquinaria", "Proyecciones"]
    )
    
    st.sidebar.divider()
    
    # 3. FILTRO DE MES
    meses_orden = ["General", "Septiembre", "Octubre", "Noviembre", "Diciembre", "Enero", "Febrero"]
    mes_seleccionado = st.sidebar.selectbox("📅 Mes:", meses_orden)

    # --- PROCESAMIENTO DE DATOS ---
    # Cargamos todo en un solo DF gigante para el Resumen, o por partes para secciones
    df_mo = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=sheet_mo, header=None), "Mano de Obra") if sheet_mo else pd.DataFrame()
    df_ins = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=sheet_insumos, header=None), "Insumos") if sheet_insumos else pd.DataFrame()
    df_maq = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=sheet_maq, header=None), "Maquinaria") if sheet_maq else pd.DataFrame()
    df_proy = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=sheet_proy, header=None), "Proyecciones") if sheet_proy else pd.DataFrame()
    
    # Unimos las categorías operativas (sin proyecciones futuras, a menos que se seleccione proyecciones)
    df_operativo = pd.concat([df_mo, df_ins, df_maq])

    # --- LÓGICA DE VISUALIZACIÓN ---
    
    if seccion == "Resumen General":
        st.header(f"📊 Resumen General - {tipo_analisis}")
        
        # Usamos df_operativo + df_proy si el usuario quiere ver todo, o solo operativo
        # Para resumen general, solemos mostrar lo ejecutado (MO, Insumos, Maq)
        # Pero si seleccionan meses futuros (Dic/Ene/Feb) que están en proyección, hay que incluirlo.
        
        df_viz = pd.concat([df_operativo, df_proy])
        
        # Filtro Mes
        if mes_seleccionado != "General":
            df_viz = df_viz[df_viz['Mes'] == mes_seleccionado]

        if df_viz.empty or df_viz[col_uso].sum() == 0:
            st.warning(f"⚠️ No hay datos de costos para el mes **{mes_seleccionado}** en la unidad seleccionada.")
        else:
            # KPIs
            total = df_viz[col_uso].sum()
            # Evitar error idxmax si no hay grupos
            cat_mayor = "N/A"
            grouped_cat = df_viz.groupby('Categoria')[col_uso].sum()
            if not grouped_cat.empty:
                cat_mayor = grouped_cat.idxmax()
                
            k1, k2, k3 = st.columns(3)
            k1.metric("Costo Total", f"{total:,.2f}")
            k2.metric("Rubro Mayor Gasto", cat_mayor)
            k3.metric("Registros Analizados", len(df_viz))
            
            st.divider()
            
            # Gráficos
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Gasto por Categoría")
                fig_pie = px.pie(df_viz, values=col_uso, names='Categoria', hole=0.4, 
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with c2:
                st.subheader("Gasto por Mes (Total)")
                # Agrupar por mes ordenado
                df_mes = df_viz.groupby('Mes')[col_uso].sum().reset_index()
                # Ordenar
                df_mes['Sort'] = df_mes['Mes'].apply(lambda x: meses_orden.index(x) if x in meses_orden else 99)
                df_mes = df_mes.sort_values('Sort')
                
                fig_bar = px.bar(df_mes, x='Mes', y=col_uso, color='Mes', text_auto='.2s')
                st.plotly_chart(fig_bar, use_container_width=True)

    elif seccion in ["Mano de Obra", "Insumos", "Maquinaria", "Proyecciones"]:
        # Seleccionar DF correcto
        if seccion == "Mano de Obra": df_active = df_mo
        elif seccion == "Insumos": df_active = df_ins
        elif seccion == "Maquinaria": df_active = df_maq
        elif seccion == "Proyecciones": df_active = df_proy
        
        st.header(f"Análisis: {seccion}")
        st.info(f"Viendo datos en base a: **{tipo_analisis}**")
        
        # Filtro Mes
        if mes_seleccionado != "General":
            df_active = df_active[df_active['Mes'] == mes_seleccionado]
            
        if df_active.empty or df_active[col_uso].sum() == 0:
            st.warning("No se encontraron costos para esta selección.")
        else:
            total_sec = df_active[col_uso].sum()
            st.metric(f"Total {seccion} ({mes_seleccionado})", f"{total_sec:,.2f}")
            
            tab1, tab2 = st.tabs(["📈 Tendencias Semanales", "📋 Detalle"])
            
            with tab1:
                c1, c2 = st.columns(2)
                # Por Semana
                df_active['Semana_Label'] = df_active['Mes'] + " - Sem " + df_active['Semana'].astype(str)
                # Ordenar
                df_active['Sort'] = df_active['Mes'].apply(lambda x: meses_orden.index(x) if x in meses_orden else 99)
                df_active = df_active.sort_values(['Sort', 'Semana'])
                
                df_sem = df_active.groupby('Semana_Label')[col_uso].sum().reset_index()
                
                fig_sem = px.bar(df_sem, x='Semana_Label', y=col_uso, title="Costo por Semana",
                                 color_discrete_sequence=['#3498db'])
                c1.plotly_chart(fig_sem, use_container_width=True)
                
                # Top Actividades
                df_top = df_active.groupby('Actividad')[col_uso].sum().reset_index().sort_values(col_uso, ascending=False).head(8)
                fig_top = px.bar(df_top, y='Actividad', x=col_uso, orientation='h', title="Top Actividades más Caras",
                                 color_discrete_sequence=['#e74c3c'])
                fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
                c2.plotly_chart(fig_top, use_container_width=True)
                
            with tab2:
                # Tabla limpia
                df_show = df_active[['Mes', 'Semana', 'Actividad', col_uso]].copy()
                df_show.columns = ['Mes', 'Semana', 'Actividad', 'Costo']
                st.dataframe(df_show, use_container_width=True)

else:
    st.info("Esperando archivo... Sube 'FRUTALES COSTOS (1).xlsx' en la barra lateral.")