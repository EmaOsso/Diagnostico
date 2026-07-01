import streamlit as st
import socket
import time
import re
import streamlit.components.v1 as components

st.set_page_config(page_title="Diagnóstico de Red & Sensa", layout="wide", page_icon="🌐")

st.title("🌐 Panel de Diagnóstico Integral - Sensa & Redes")
st.markdown("Herramienta basada en los procedimientos oficiales de verificación de COLSECOR.")

# --- DICCIONARIO DE DESTINOS ---
DESTINOS_GLOBALES = {
    "Google DNS": "8.8.8.8",
    "Cloudflare DNS": "1.1.1.1",
    "Google Web": "www.google.com",
    "YouTube": "www.youtube.com",
    "Facebook": "www.facebook.com",
    "Instagram": "www.instagram.com"
}

DESTINOS_SENSA = {
    "Sensa Middleware & DRM (AWS)": "aws.sensa.com.ar",
    "Sensa CDN Central (Edge)" : "cdn.sensa.com.ar",
    "Sensa Edge 01": "smt-usr-edge01.sensa.com.ar",
    "Sensa Edge 02": "smt-usr-edge02.sensa.com.ar",
    "Sensa Edge 03": "smt-edge03.sensa.com.ar"
}

# Detectar si es local (para saber si puede usar IPs privadas de ONT)
es_local = "streamlit" not in socket.gethostname().lower()

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración")
modo = st.sidebar.radio("Seleccionar Modo:", ["Cliente (Web / Navegador)", "Local (Técnico / Nodo / ONT)"])
cache_local = st.sidebar.text_input("Caché Sensa Local / Regional (Opcional):", value="", placeholder="Ej: 10.0.0.50")

todos_los_destinos = {**DESTINOS_GLOBALES, **DESTINOS_SENSA}
if cache_local:
    todos_los_destinos["Caché Sensa Local"] = cache_local

# --- FUNCIÓN DE PING TCP MULTIPLATAFORMA (NATIVA) ---
def tcp_ping(host, puerto=443, timeout=3):
    """Mide la latencia simulando un ping mediante la apertura de un socket TCP (compatible con la nube)."""
    inicio = time.time()
    try:
        # Resolver IP si pasan un dominio
        ip_destino = socket.gethostbyname(host)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip_destino, puerto))
        s.close()
        duracion = (time.time() - inicio) * 1000  # Convertir a ms
        return int(duracion), f"Conexión exitosa al puerto {puerto}."
    except socket.timeout:
        return None, "🔴 TIMEOUT - El servidor tardó demasiado en responder."
    except Exception as e:
        # Si el puerto 443 está cerrado pero el host respondió rápido denegando la entrada, el host está vivo
        duracion = (time.time() - inicio) * 1000
        if duracion < (timeout * 1000) - 100:
            return int(duracion), f"Respuesta obtenida (Puerto cerrado/filtrado)."
        return None, f"🔴 ERROR - No se pudo alcanzar el host: {str(e)}"

def evaluar_rango(promedio):
    if promedio is None:
        return "🔴 CORTE TOTAL / TIMEOUT", "error"
    if promedio <= 25:
        return f"🟢 EXCELENTE ({promedio} ms) - Conexión ultra rápida.", "success"
    elif promedio <= 65:
        return f"🟡 NORMAL ({promedio} ms) - Valores estables para navegación y streaming.", "warning"
    else:
        return f"🟠 LATENCIA ALTA ({promedio} ms) - Posible saturación o ruta congestionada.", "warning"

# ==========================================
# OPCIÓN 1: MODO CLIENTE (HTTP NAVEGADOR)
# ==========================================
if modo == "Cliente (Web / Navegador)":
    st.header("⚡ Prueba 1 y 2: Latencia desde el Navegador del Usuario")
    st.info("Mide el tiempo de respuesta HTTP aproximado desde el dispositivo final hacia la infraestructura.")
    
    js_destinos = "{\n"
    for nombre, host in todos_los_destinos.items():
        url = host if host.startswith("http") else f"https://{host}"
        js_destinos += f'        "{nombre}": "{url}",\n'
    js_destinos += "    };"

    js_code = f"""
    <div style="font-family: sans-serif; background-color: #111; color: #FFF; padding: 15px; border-radius: 8px;">
        <h4 style="margin-top:0; color:#ff3344;">Resultados de Conectividad (Última Milla):</h4>
        <ul id="results-list" style="list-style: none; padding-left: 0; font-size: 15px; line-height: 1.8;"></ul>
    </div>

    <script>
    const destinos = {js_destinos}

    async function ping(name, url) {{
        const start = performance.now();
        const list = document.getElementById('results-list');
        try {{
            await fetch(url, {{ mode: 'no-cors', cache: 'no-store' }});
            const duration = Math.round(performance.now() - start);
            let info = duration <= 25 ? '<span style="color:#2ecc71;">🟢 EXCELENTE</span>' : (duration <= 65 ? '<span style="color:#f1c40f;">🟡 NORMAL</span>' : '<span style="color:#e67e22;">🟠 ALTA</span>');
            list.innerHTML += `<li><strong>${{name}}:</strong> ${{info}} (${{duration}} ms)</li>`;
        }} catch (error) {{
            const duration = Math.round(performance.now() - start);
            if (duration < 200) {{
                let info = duration <= 25 ? '<span style="color:#2ecc71;">🟢 EXCELENTE</span>' : '<span style="color:#f1c40f;">🟡 NORMAL</span>';
                list.innerHTML += `<li><strong>${{name}}:</strong> ${{info}} (${{duration}} ms) (HTTP Ack)</li>`;
            }} else {{
                list.innerHTML += `<li><strong>${{name}}:</strong> <span style="color:#e74c3c; font-weight:bold;">🔴 TIMEOUT / CAÍDO</span></li>`;
            }}
        }}
    }}

    async function runAll() {{
        document.getElementById('results-list').innerHTML = "⏳ Evaluando saltos y respuestas hacia servidores...";
        for (const [name, url] of Object.entries(destinos)) {{
            await ping(name, url);
        }}
    }}
    runAll();
    </script>
    """
    if st.button("▶️ Iniciar Verificación de Usuario Final"):
        components.html(js_code, height=400)

# ==========================================
# OPCIÓN 2: MODO LOCAL (TÉCNICO / NODO)
# ==========================================
else:
    st.header("🛠️ Herramientas de Diagnóstico Técnico (Sockets TCP)")
    
    # --- SECCIÓN 1: ONT / ROUTER ---
    st.subheader("🏠 Verificación de Última Milla (Prueba 2: ONT / Gateway)")
    ip_ont = st.text_input("IP de la ONT o Router del Abonado:", value="192.168.0.1")
    puerto_ont = st.number_input("Puerto administrativo de la ONT (80 para HTTP, 443 para HTTPS):", min_value=1, max_value=65535, value=80)
    
    if st.button("🔍 Testear Conectividad a ONT"):
        es_ip_privada = ip_ont.startswith("192.168.") or ip_ont.startswith("10.") or ip_ont.startswith("172.")
        
        if not es_local and es_ip_privada:
            st.error(f"⚠️ No se puede evaluar la ONT local ({ip_ont}) desde los servidores en la Nube. Para hacer esta prueba a la ONT, debés correr esta app localmente en tu PC con 'streamlit run app.py'.")
        else:
            with st.spinner("Analizando calidad del enlace con la ONT..."):
                ms_ont, msg_ont = tcp_ping(ip_ont, puerto=int(puerto_ont))
                msg_eval, tipo_eval = evaluar_rango(ms_ont)
                
                if tipo_eval == "success":
                    st.success(f"Estado de la ONT: {msg_eval}")
                elif tipo_eval == "warning":
                    st.warning(f"Estado de la ONT: {msg_eval}")
                else:
                    st.error(f"Estado de la ONT: {msg_eval}")
                st.info(f"Detalle: {msg_ont}")

    st.markdown("---")

    # --- SECCIÓN 2: MATRIZ CON SOCKETS ---
    st.subheader("🚀 Prueba 3 y 6: Ráfaga TCP con Diagnóstico de Umbrales")
    cat_seleccionada = st.radio("Filtro de Destinos:", ["Solo Servidores Sensa", "Ver Todo (Sensa + Páginas Web)"], horizontal=True)
    dict_filtrado = DESTINOS_SENSA if cat_seleccionada == "Solo Servidores Sensa" else todos_los_destinos
    
    if cache_local and "Caché Sensa Local" not in dict_filtrado:
        dict_filtrado["Caché Sensa Local"] = cache_local

    if st.button("⚡ Ejecutar Matriz"):
        columnas = st.columns(2)
        for idx, (nombre, host) in enumerate(dict_filtrado.items()):
            col = columnas[idx % 2]
            with col:
                with st.spinner(f"Analizando {nombre}..."):
                    # Probamos por el puerto estándar seguro 443 (HTTPS)
                    ms_resultado, detalle_resultado = tcp_ping(host, puerto=443)
                    msg_eval, tipo_eval = evaluar_rango(ms_resultado)
                    
                    if "🟢" in msg_eval:
                        st.success(f"**{nombre}** ({host}) -> {msg_eval}")
                    elif "🟡" in msg_eval or "🟠" in msg_eval:
                        st.warning(f"**{nombre}** ({host}) -> {msg_eval}")
                    else:
                        st.error(f"**{nombre}** ({host}) -> {msg_eval}")
                    
                    with st.expander("Ver bitácora técnica"):
                        st.write(f"Destino evaluado: `{host}`")
                        st.write(f"Resultado socket: {detalle_resultado}")

# ==========================================
# SECCIÓN GLOBAL DE CENTRALES DE ALERTA
# ==========================================
st.markdown("---")
st.subheader("🚨 Central de Verificación de Caídas Globales")
st.markdown("Si detectás timeouts constantes en las pruebas superiores, usá estos accesos directos para verificar si el problema es masivo:")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Infraestructura Sensa / Redes**")
    st.link_button("🌐 Soporte COLSECOR (Tickets)", "https://soporte.colsecor.com.ar")
    st.link_button("☁️ AWS Service Health (Middleware Sensa)", "https://health.aws.amazon.com")
with col2:
    st.markdown("**Servicios de Distribución**")
    st.link_button("📺 Downdetector: YouTube", "https://downdetector.com.ar/problemas/youtube/")
    st.link_button("🔍 Google Workspace Status", "https://www.google.com/appsstatus")
with col3:
    st.markdown("**Redes Sociales Externas**")
    st.link_button("📸 Downdetector: Instagram", "https://downdetector.com.ar/problemas/instagram/")
    st.link_button("📘 Downdetector: Facebook", "https://downdetector.com.ar/problemas/facebook/")
