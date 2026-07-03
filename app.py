import streamlit as st
import pandas as pd
from supabase import create_client, Client
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Monitoreo Sensa - NOC", layout="wide", page_icon="📊")

# --- CREDENCIALES DE SUPABASE ---
SUPABASE_URL = "https://jnjovzeihdfbxczqmrlv.supabase.co"
SUPABASE_KEY = "sb_publishable_0WZZihnXo8o77WUmfEFNcA_7CXjythL"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.title("📊 Centro de Operaciones de Red (NOC) - Sensa TV")
st.markdown("Historial de estabilidad, cortes y métricas de tráfico mapeadas desde el MikroTik.")

if st.button("🔄 Actualizar Tablero"):
    st.rerun()

# --- CONSULTA DE DATOS A SUPABASE ---
def cargar_datos():
    try:
        respuesta = supabase.table("metricas_sensa").select("*").order("created_at", desc=True).limit(2000).execute()
        if respuesta.data:
            df = pd.DataFrame(respuesta.data)
            
            # Forzar conversión limpia de fecha y redondear al minuto para alinear los hosts en el gráfico
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["created_at"] = df["created_at"].dt.round("min")
            
            df["Hora"] = df["created_at"].dt.strftime("%H:%M")
            df["Fecha"] = df["created_at"].dt.strftime("%Y-%m-%d")
            df["Hora_Entera"] = df["created_at"].dt.hour
            
            # Extraer solo números limpios de la columna latencia por si quedó basura de formato anterior
            df["latencia"] = pd.to_numeric(df.astype(str)["latencia"].str.extract(r'(\d+)', expand=False), errors='coerce')
            
            # Ordenar cronológicamente para que Plotly dibuje las líneas de corrido sin saltos
            df = df.sort_values("created_at").reset_index(drop=True)
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
    ultimos_estados = df_metricas.sort_values("created_at").groupby("host").last().reset_index()
    
    columnas_luces = st.columns(len(ultimos_estados))
    for idx, row in ultimos_estados.iterrows():
        with columnas_luces[idx]:
            host_name = row["host"]
            estado_actual = row["estado"]
            lat_actual = row["latencia"]
            fecha_cambio = row["created_at"].strftime("%d/%m %H:%M")
            
            str_lat = f"{int(lat_actual)} ms" if not pd.isna(lat_actual) else "N/A"
            
            if estado_actual == "UP":
                st.success(f"**{host_name}**\n\n🟢 ONLINE ({str_lat})\n\n_Muestreo: {fecha_cambio}_")
            else:
                st.error(f"**{host_name}**\n\n🔴 DOWN / CORTE\n\n_Muestreo: {fecha_cambio}_")

    st.markdown("---")

    # ==========================================
    # 2. GRÁFICO HISTÓRICO DE LATENCIAS (HORAS PICO)
    # ==========================================
    st.subheader("📈 Evolución de Latencia y Comportamiento en Horas Pico")
    st.markdown("Este gráfico analiza las variaciones de milisegundos en el tiempo. Picos altos en la curva indican congestión o saturación de rutas.")
    
    # Filtramos registros con latencia válida para el gráfico continuo
    df_lineas = df_metricas[df_metricas["latencia"].notna()].copy()
    
    if not df_lineas.empty:
        fig_lineas = px.line(
            df_lineas,
            x="created_at",
            y="latencia",
            color="host",
            title="Milisegundos (RTT) continuos por Servidor",
            labels={"created_at": "Tiempo", "latencia": "Latencia (ms)", "host": "Servidor"},
        )
        fig_lineas.update_layout(template="plotly_dark", height=450)
        st.plotly_chart(fig_lineas, use_container_width=True)
    else:
        st.info("Recolectando suficientes datos de latencia para dibujar las líneas continuas...")

    st.markdown("---")

    # ==========================================
    # 3. ANÁLISIS DE CORTES E INCIDENTES
    # ==========================================
    col_izq, col_der = st.columns([2, 1])
    
    with col_izq:
        st.subheader("🚨 Historial de Eventos Registrados")
        fig_puntos = px.scatter(
            df_metricas, 
            x="created_at", 
            y="host", 
            color="estado",
            color_discrete_map={"UP": "#2ecc71", "DOWN": "#e74c3c"},
            title="Distribución de Estados (Puntos rojos indican caídas completas)",
            labels={"created_at": "Fecha y Hora", "host": "Servidor", "estado": "Estado"},
        )
        fig_puntos.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_puntos, use_container_width=True)

    with col_der:
        st.subheader("📊 Alertas por Franja Horaria")
        fig_horas = px.histogram(
            df_metricas[df_metricas["estado"] == "DOWN"],
            x="Hora_Entera",
            title="Concentración de Cortes según la Hora",
            labels={"Hora_Entera": "Hora del Día (0-23)"},
            color_discrete_sequence=["#e74c3c"],
            nbins=24
        )
        fig_horas.update_layout(template="plotly_dark", height=350, showlegend=False)
        if not df_metricas[df_metricas["estado"] == "DOWN"].empty:
            st.plotly_chart(fig_horas, use_container_width=True)
        else:
            st.success("¡Sin cortes registrados en el historial de franjas!")

    st.markdown("---")

    # ==========================================
    # 4. TABLA DE AUDITORÍA
    # ==========================================
    st.subheader("📋 Log de Auditoría Técnica")
    tabla_limpia = df_metricas[["created_at", "host", "estado", "latencia"]].copy()
    tabla_limpia = tabla_limpia.sort_values("created_at", ascending=False) # Mostrar lo más nuevo arriba en la tabla
    tabla_limpia.columns = ["Fecha y Hora", "Servidor / Destino", "Estado", "Latencia (ms)"]
    st.dataframe(tabla_limpia, use_container_width=True, height=250)
