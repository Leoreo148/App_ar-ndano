import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

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

# --- FUNCIÓN DE LIMPIEZA MAESTRA ---
def procesar_hoja_compleja(df_raw, nombre_hoja):
    """
    Lee hojas con formato de reporte (bloques de Mes - Mes).
    Extrae: Mes, Semana, Actividad, Costo Total (Dólares).
    """
    data = []
    current_month = "Desconocido"
    
    # Convertimos todo a string para buscar patrones, excepto los NaN
    # Iteramos por las filas buscando encabezados de sección
    
    # Identificar columnas clave (basado en los CSVs subidos)
    # Buscamos la columna que tenga "Semana" y "Costo Total"
    col_semana_idx = -1
    col_costo_idx = -1
    col_actividad_idx = -1
    
    # Barrido inicial para encontrar índices de columnas probables
    # Asumimos que la estructura es consistente en las primeras 20 filas
    for r in range(min(20, len(df_raw))):
        row_vals = [str(x).lower() for x in df_raw.iloc[r].values]
        for i, val in enumerate(row_vals):
            if "semana" in val and "lunes" in val:
                col_semana_idx = i
            if "costo total" in val and "dólar" in val:
                col_costo_idx = i
            if "actividad" in val or "insumo" in val or "detalle" in val:
                col_actividad_idx = i
    
    # Si no encontramos cabeceras claras, usamos índices por defecto basados en tus archivos
    if col_semana_idx == -1: col_semana_idx = 0
    if col_actividad_idx == -1: col_actividad_idx = 2
    # El costo suele estar hacia el final, columna J o K (índice 9 o 10)
    if col_costo_idx == -1: col_costo_idx = 9 

    # Iterar filas
    for index, row in df_raw.iterrows():
        # Convertir fila a lista de strings para análisis
        row_str = [str(x) for x in row.values]
        first_cell = str(row_raw := row.values[0]).strip()
        
        # 1. DETECTAR CAMBIO DE MES
        # Buscamos "Mes - Septiembre" en cualquier celda de la fila
        found_month = False
        for cell in row_str:
            if "Mes -" in cell:
                # Extraer nombre del mes (ej: "Septiembre")
                parts = cell.split("-")
                if len(parts) > 1:
                    current_month = parts[1].strip()
                    found_month = True
                    break
        if found_month:
            continue # Saltamos la fila del título del mes

        # 2. SALTAR CABECERAS REPETIDAS
        if "Semana" in str(row.values[col_semana_idx]) or "Rubro" in str(row.values[col_semana_idx]):
            continue
            
        # 3. EXTRAER DATOS
        try:
            val_semana = row.values[col_semana_idx]
            val_costo = row.values[col_costo_idx]
            val_actividad = row.values[col_actividad_idx]
            
            # Validar que sea una fila de datos (Semana debe ser número, Costo debe existir)
            # A veces la semana viene como '1', '2' o está vacía en filas consecutivas
            
            # Limpieza básica de costo
            if pd.isna(val_costo) or str(val_costo).strip() == '' or str(val_costo).lower() == 'nan':
                continue
                
            costo_float = 0.0
            try:
                costo_float = float(val_costo)
            except:
                continue # Si el costo no es número, saltamos (ej: fila de TOTAL)

            # Si llegamos aquí, es un dato válido
            data.append({
                "Mes": current_month,
                "Semana": val_semana if not pd.isna(val_semana) else "S/N",
                "Actividad": str(val_actividad) if not pd.isna(val_actividad) else "Varios",
                "Costo_USD": costo_float,
                "Categoria": nombre_hoja
            })
            
        except IndexError:
            continue

    return pd.DataFrame(data)

def procesar_indicadores(df):
    """Limpia la hoja de Indicadores Económicos"""
    # Buscar fila de cabecera real
    header_idx = -1
    for i, row in df.iterrows():
        row_str = [str(x).lower() for x in row.values]
        if "flujo - efectivo neto" in row_str or "flujo de egresos" in row_str:
            header_idx = i
            break
    
    if header_idx != -1:
        df.columns = df.iloc[header_idx]
        df = df.iloc[header_idx+1:]
    
    # Normalizar columnas
    cols_map = {}
    for c in df.columns:
        c_str = str(c).lower()
        if "mes" in c_str: cols_map[c] = "Mes_Num"
        elif "egresos" in c_str: cols_map[c] = "Egresos"
        elif "ingresos" in c_str: cols_map[c] = "Ingresos"
        elif "acumulado" in c_str: cols_map[c] = "Acumulado"
        elif "neto" in c_str: cols_map[c] = "Neto"
    
    df = df.rename(columns=cols_map)
    
    # Filtrar solo filas con datos numéricos en Mes
    df = df[pd.to_numeric(df['Mes_Num'], errors='coerce').notna()]
    
    # Convertir a numeros
    for col in ["Egresos", "Ingresos", "Acumulado", "Neto"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- INTERFAZ PRINCIPAL ---

st.title("🍓 Dashboard de Costos Agrícolas (Frutales)")
st.write("Visualización integrada de Mano de Obra, Insumos, Maquinaria y Proyecciones.")

# Carga de Archivo
uploaded_file = st.sidebar.file_uploader("📂 Sube el archivo 'FRUTALES COSTOS.xlsx'", type=["xlsx"])

if uploaded_file:
    # Leer todas las hojas
    xls = pd.ExcelFile(uploaded_file)
    all_sheets = xls.sheet_names
    
    # Mapeo inteligente de hojas (por si cambian un poco el nombre)
    sheet_mo = next((s for s in all_sheets if "mano" in s.lower() and "obra" in s.lower()), None)
    sheet_insumos = next((s for s in all_sheets if "insumo" in s.lower()), None)
    sheet_maq = next((s for s in all_sheets if "maquinaria" in s.lower()), None)
    sheet_proy = next((s for s in all_sheets if "proyecc" in s.lower()), None)
    sheet_ind = next((s for s in all_sheets if "indicador" in s.lower()), None)

    # --- BARRA LATERAL: NAVEGACIÓN Y FILTROS ---
    st.sidebar.divider()
    seccion = st.sidebar.radio("📍 Ir a Sección:", 
        ["Resumen Ejecutivos (KPIs)", "Mano de Obra", "Insumos", "Maquinaria", "Proyecciones", "Indicadores Económicos"]
    )
    
    st.sidebar.divider()
    # Filtro de Mes
    meses_orden = ["Septiembre", "Octubre", "Noviembre", "Diciembre", "Enero", "Febrero"]
    opciones_mes = ["General"] + meses_orden
    mes_seleccionado = st.sidebar.selectbox("📅 Filtrar por Mes:", opciones_mes)

    # --- LÓGICA DE PROCESAMIENTO SEGÚN SECCIÓN ---
    
    if seccion == "Resumen Ejecutivos (KPIs)":
        st.header("📊 Resumen General de Costos")
        
        # Cargar y procesar todo para el resumen
        df_total = pd.DataFrame()
        
        if sheet_mo:
            df_mo = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=sheet_mo, header=None), "Mano de Obra")
            df_total = pd.concat([df_total, df_mo])
        if sheet_insumos:
            df_ins = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=sheet_insumos, header=None), "Insumos")
            df_total = pd.concat([df_total, df_ins])
        if sheet_maq:
            df_maq = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=sheet_maq, header=None), "Maquinaria")
            df_total = pd.concat([df_total, df_maq])
            
        if not df_total.empty:
            # Filtrar por mes si aplica
            if mes_seleccionado != "General":
                df_viz = df_total[df_total['Mes'] == mes_seleccionado]
            else:
                df_viz = df_total
            
            col1, col2, col3 = st.columns(3)
            total_gasto = df_viz['Costo_USD'].sum()
            cat_mayor = df_viz.groupby('Categoria')['Costo_USD'].sum().idxmax()
            mes_pico = df_viz.groupby('Mes')['Costo_USD'].sum().idxmax()
            
            col1.metric("Gasto Total (USD)", f"${total_gasto:,.2f}")
            col2.metric("Rubro Más Costoso", cat_mayor)
            col3.metric("Mes con Mayor Gasto", mes_pico)
            
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Distribución por Rubro")
                fig_pie = px.pie(df_viz, values='Costo_USD', names='Categoria', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                st.subheader("Evolución Mensual Total")
                # Ordenar meses cronológicamente
                df_mes = df_viz.groupby('Mes')['Costo_USD'].sum().reset_index()
                # Truco para ordenar meses: crear columna indice
                df_mes['Mes_Index'] = df_mes['Mes'].apply(lambda x: meses_orden.index(x) if x in meses_orden else 99)
                df_mes = df_mes.sort_values('Mes_Index')
                
                fig_bar = px.bar(df_mes, x='Mes', y='Costo_USD', text_auto='.2s', color='Mes')
                st.plotly_chart(fig_bar, use_container_width=True)

    elif seccion in ["Mano de Obra", "Insumos", "Maquinaria", "Proyecciones"]:
        # Determinar hoja y título
        mapa_seccion = {
            "Mano de Obra": (sheet_mo, "👷"),
            "Insumos": (sheet_insumos, "🧪"),
            "Maquinaria": (sheet_maq, "🚜"),
            "Proyecciones": (sheet_proy, "📈")
        }
        target_sheet, icon = mapa_seccion[seccion]
        
        st.header(f"{icon} Análisis de {seccion}")
        
        if target_sheet:
            df = procesar_hoja_compleja(pd.read_excel(uploaded_file, sheet_name=target_sheet, header=None), seccion)
            
            if df.empty:
                st.warning("No se encontraron datos legibles en esta hoja.")
            else:
                # Filtro de Mes
                if mes_seleccionado != "General":
                    df = df[df['Mes'] == mes_seleccionado]
                    st.info(f"Mostrando datos filtrados para: **{mes_seleccionado}**")
                
                # --- KPIS DE SECCIÓN ---
                total_seccion = df['Costo_USD'].sum()
                promedio_semanal = df.groupby(['Mes', 'Semana'])['Costo_USD'].sum().mean()
                
                k1, k2 = st.columns(2)
                k1.metric("Costo Total Seleccionado", f"${total_seccion:,.2f}")
                k2.metric("Promedio Gasto Semanal", f"${promedio_semanal:,.2f}")
                
                st.divider()
                
                # --- GRÁFICOS ---
                tab1, tab2, tab3 = st.tabs(["📊 Tendencia Semanal", "🏆 Top Actividades", "📄 Tabla de Datos"])
                
                with tab1:
                    st.subheader("Gasto por Semana")
                    # Agrupar por Mes y Semana para que no se mezclen las semanas 1 de dif meses
                    df['Semana_Label'] = df['Mes'] + " - Sem " + df['Semana'].astype(str)
                    
                    # Ordenar por el orden de los meses
                    df['Mes_Index'] = df['Mes'].apply(lambda x: meses_orden.index(x) if x in meses_orden else 99)
                    df = df.sort_values(['Mes_Index', 'Semana'])
                    
                    df_sem = df.groupby('Semana_Label')['Costo_USD'].sum().reset_index()
                    
                    fig_sem = px.bar(df_sem, x='Semana_Label', y='Costo_USD', 
                                     title="Costo Total por Semana",
                                     labels={'Semana_Label': 'Semana', 'Costo_USD': 'Costo (USD)'},
                                     color='Costo_USD', color_continuous_scale='Blues')
                    st.plotly_chart(fig_sem, use_container_width=True)
                    
                with tab2:
                    st.subheader("En qué se gasta más")
                    df_act = df.groupby('Actividad')['Costo_USD'].sum().reset_index().sort_values('Costo_USD', ascending=False).head(10)
                    fig_act = px.bar(df_act, y='Actividad', x='Costo_USD', orientation='h',
                                     title="Top Actividades / Ítems más costosos",
                                     color='Costo_USD', color_continuous_scale='Reds')
                    fig_act.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_act, use_container_width=True)
                    
                with tab3:
                    st.dataframe(df[['Mes', 'Semana', 'Actividad', 'Costo_USD']], use_container_width=True)
        else:
            st.error(f"No se encontró la hoja correspondiente a {seccion} en el Excel.")

    elif seccion == "Indicadores Económicos":
        st.header("📉 Flujo de Caja e Indicadores")
        
        if sheet_ind:
            df_ind = procesar_indicadores(pd.read_excel(uploaded_file, sheet_name=sheet_ind, header=None))
            
            if not df_ind.empty:
                st.write("Evolución del Flujo de Caja Acumulado")
                
                # Gráfico Combinado: Barras (Neto) + Línea (Acumulado)
                fig = go.Figure()
                
                # Barras de Ingresos y Egresos
                fig.add_trace(go.Bar(
                    x=df_ind['Mes_Num'], y=df_ind['Ingresos'],
                    name='Ingresos', marker_color='green', opacity=0.6
                ))
                fig.add_trace(go.Bar(
                    x=df_ind['Mes_Num'], y=df_ind['Egresos'] * -1, # Negativo para que salga abajo
                    name='Egresos', marker_color='red', opacity=0.6
                ))
                
                # Línea de Acumulado
                fig.add_trace(go.Scatter(
                    x=df_ind['Mes_Num'], y=df_ind['Acumulado'],
                    name='Flujo Acumulado', mode='lines+markers',
                    line=dict(color='blue', width=3)
                ))
                
                fig.update_layout(title="Ingresos vs Egresos y Saldo Acumulado", barmode='overlay')
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(df_ind, use_container_width=True)
            else:
                st.warning("La hoja de indicadores no tiene el formato esperado.")
        else:
            st.error("No se encontró la hoja 'Indicador economico'.")

else:
    # Pantalla de bienvenida
    st.info("👈 Sube tu archivo Excel en la barra lateral para ver los gráficos.")
    st.markdown("""
    ### Instrucciones:
    1. Haz clic en **'Browse files'** a la izquierda.
    2. Selecciona **FRUTALES COSTOS.xlsx**.
    3. ¡Listo! Navega por las pestañas para ver tus costos.
    """)