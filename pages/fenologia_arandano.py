import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client

# --- Configuración de la Página ---
st.set_page_config(page_title="Fenología del Arándano", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica del Arándano")
st.write("Registre las mediciones de crecimiento y estado para cada planta de la hilera seleccionada.")

# --- Archivo de Configuración ---
HILERAS = {
    'Hilera 1 (21 Emerald)': 21,
    'Hilera 2 (23 Biloxi/Emerald)': 23,
    'Hilera 3 (22 Biloxi)': 22
}
ETAPAS_FENOLOGICAS = [
    'Yema Hinchada', 'Punta Verde', 'Salida de Hojas', 
    'Hojas Extendidas', 'Inicio de Floración', 'Plena Flor', 
    'Caída de Pétalos', 'Fruto Verde', 'Pinta', 'Cosecha'
]

# --- Conexión a Supabase ---
@st.cache_resource
def init_supabase_connection():
    try:
        # --- CORRECCIÓN AQUÍ ---
        # El cliente de Supabase usa 'ascending=True' en lugar de 'desc=False'
        response = supabase.table('Fenologia_Arandano').select("*").order('Fecha', ascending=True).execute()
        df = pd.DataFrame(response.data)
        
        if df.empty:
            return pd.DataFrame()

        df['Fecha'] = pd.to_datetime(df['Fecha'])
        # Asegurar que los datos estén ordenados para el cálculo
        df = df.sort_values(by=['Hilera', 'Numero_de_Planta', 'Fecha'])

        # --- CÁLCULO DE TASA DE CRECIMIENTO ---
        # 1. Agrupar por cada planta individual
        grouped = df.groupby(['Hilera', 'Numero_de_Planta'])

        # 2. Calcular la diferencia (diff) con la fila anterior
        df['Altura_Anterior'] = grouped['Altura_Planta_cm'].shift(1)
        df['Fecha_Anterior'] = grouped['Fecha'].shift(1)

        # 3. Calcular los días pasados
        df['Dias_Pasados'] = (df['Fecha'] - df['Fecha_Anterior']).dt.days

        # 4. Calcular el crecimiento en cm
        df['Crecimiento_cm'] = df['Altura_Planta_cm'] - df['Altura_Anterior']

        # 5. Calcular la Tasa de Crecimiento Diario (TCD)
        # (Solo si han pasado días y el crecimiento es positivo)
        df['Tasa_Crecimiento_cm_dia'] = 0.0
        mask = (df['Dias_Pasados'] > 0) & (df['Crecimiento_cm'] > 0)
        df.loc[mask, 'Tasa_Crecimiento_cm_dia'] = df['Crecimiento_cm'] / df['Dias_Pasados']
        
        # Limpiar valores infinitos si los hubiera
        df.replace([pd.NA, pd.NaT, float('inf'), float('-inf')], pd.NA, inplace=True)
        
        # También cambiaré esto para ser 100% consistente con pandas
        return df.sort_values(by='Fecha', ascending=False) # Devolver ordenado por fecha (más reciente primero)

    except Exception as e: