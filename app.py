import streamlit as st
import pandas as pd
from supabase import create_client, Client
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Monitoreo Sensa - NOC", layout="wide", page_icon="📊")

# --- CREDENCIALES DE SUPABASE (YA INTEGRADAS) ---
SUPABASE_URL = "https://jnjovzeihdfbxczqmrlv.supabase.co"
SUPABASE_KEY = "sb_publishable_0WZZihnXo8o77WUmfEFNcA_7CXjythL"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.title("📊 Centro de Operaciones de Red (NOC) - Sensa TV")
st.markdown("Historial de estabilidad, cortes y métricas de tráfico mapeadas desde el MikroTik.")

# --- BOTÓN PARA REFRESCAR DATOS ---
if st.button("🔄 Actualizar Tablero"):
    st.rerun()

# --- CONSULTA DE DATOS A SUPABASE ---
def cargar_datos():
    try:
        # CORRECCIÓN: Cambiado descending=True por desc=True
        respuesta = supabase.table("metricas_sensa").select("*").order("created_at", desc=True).limit(1000).execute()
        if respuesta.data:
            df = pd.DataFrame(respuesta.data)
            # Convertir la fecha a formato datetime y ajustar a zona horaria local
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["Hora"] = df["created_at"].dt.strftime("%H:%M:%S")
            df["Fecha"] = df["created_at"].dt.strftime("%Y-%m-%d")
            df["Hora_Entera"] = df["created_at"].dt.hour
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con el backend: {e}")
        return pd.DataFrame()

df_metricas = cargar_datos()

if df_metricas.empty:
    st.warning("⏳ Esperando más registros del MikroTik en la base de datos... Refrescá en unos instantes.")
else:
    # ==========================================
    # 1. ESTADO ACTUAL (PANEL DE LUCES)
    # ==========================================
    st.subheader("🟢 Estado en Tiempo Real de los Servicios")
    
    # Obtener el último estado de cada host único
    ultimos_estados = df_metricas.sort_values("created_at").groupby("host").last().reset_index()
    
    columnas_luces = st.columns(len(ultimos_estados))
    for idx, row in ultimos_estados.iterrows():
        with columnas_luces[idx]:
            host_name = row["host"]
            estado_actual = row["estado"]
            fecha_cambio = row["created_at"].strftime("%d/%m %H:%M")
            
            if estado_actual == "UP":
                st.success(f"**{host_name}**\n\n🟢 ONLINE\n\n_Último cambio: {fecha_cambio}_")
            else:
                st.error(f"**{host_name}**\n\n🔴 DOWN / CORTE\n\n_Último cambio: {fecha_cambio}_")

    st.markdown("---")

    # ==========================================
    # 2. ANÁLISIS DE HORAS PICO Y MICRO-CORTES
    # ==========================================
    st.subheader("⏳ Historial de Eventos e Incidentes Registrados")
    
    col_izq, col_der = st.columns([2, 1])
    
    with col_izq:
        st.markdown("**Gráfico de Eventos en la Línea de Tiempo**")
        # Gráfico interactivo para ver cuándo ocurren las caídas/levantadas
        fig = px.scatter(
            df_metricas, 
            x="created_at", 
            y="host", 
            color="estado",
            color_discrete_map={"UP": "#2ecc71", "DOWN": "#e74c3c"},
            title="Distribución de Estados en el Tiempo (Puntos rojos indican cortes)",
            labels={"created_at": "Fecha y Hora", "host": "Servidor Evaluado", "estado": "Estado"},
        )
        fig.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        st.markdown("**Distribución por Hora del Día**")
        # Histograma para ver en qué horas se concentran los reportes (frecuencia de cambios)
        fig_horas = px.histogram(
            df_metricas,
            x="Hora_Entera",
            color="estado",
            color_discrete_map={"UP": "#2ecc71", "DOWN": "#e74c3c"},
            title="Frecuencia de Alertas por Franja Horaria",
            labels={"Hora_Entera": "Hora del Día (0-23)", "count": "Cantidad de Eventos"},
            nbins=24
        )
        fig_horas.update_layout(template="plotly_dark", height=400, showlegend=False)
        st.plotly_chart(fig_horas, use_container_width=True)

    st.markdown("---")

    # ==========================================
    # 3. TABLA DE REGISTROS CRUDA
    # ==========================================
    st.subheader("📋 Log de Auditoría Técnica")
    st.markdown("Listado detallado de los últimos movimientos reportados por el router para adjuntar en reportes o auditorías:")
    
    # Formatear tabla limpia para visualización
    tabla_limpia = df_metricas[["created_at", "host", "estado"]].copy()
    tabla_limpia.columns = ["Fecha y Hora del Evento", "Servidor / Destino", "Estado Reportado"]
    
    st.dataframe(tabla_limpia, use_container_width=True, height=300)
