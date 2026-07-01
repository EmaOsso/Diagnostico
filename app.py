import streamlit as st
import subprocess
import platform
import socket
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

es_local = "streamlit" not in socket.gethostname().lower()

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración")
modo = st.sidebar.radio("Seleccionar Modo:", ["Cliente (Web / Navegador)", "Local (Técnico / Nodo / ONT)"])
cache_local = st.sidebar.text_input("Caché Sensa Local / Regional (Opcional):", value="", placeholder="Ej: 10.0.0.50")

todos_los_destinos = {**DESTINOS_GLOBALES, **DESTINOS_SENSA}
if cache_local:
    todos_los_destinos["Caché Sensa Local"] = cache_local

# --- FUNCIÓN PARA ANALIZAR LATENCIA ---
def evaluar_latencia(resultado_texto):
    """Analiza la salida del comando ping y determina el estado."""
    if not resultado_texto or "unreachable" in resultado_texto.lower() or "lost = 4" in resultado_texto.lower() or "100% loss" in resultado_texto.lower() or "tiempo de espera agotado" in resultado_texto.lower():
        return "🔴 CORTE TOTAL / TIMEOUT", "error"
    
    # 1. Intento para formato Windows (Media = XXms o Average = XXms)
    valores_win = re.findall(r'(?:Media|Average|media|average) = (\d+)ms', resultado_texto)
    if valores_win:
        promedio = int(valores_win[-1])
    else:
        # 2. Intento para formato Linux (rtt min/avg/max/mdev = min/avg/max/mdev ms)
        # Buscamos los números después del signo '=' o la barra '/'
        valores_linux = re.findall(r'(?:rtt|round-trip)\s+min/avg/max/.+?=\s*[\d\.]+/([\d\.]+)/', resultado_texto)
        if valores_linux:
            promedio = int(float(valores_linux[0]))
        else:
            # 3. Tercer intento por si viene en formato "time=XX ms" línea por línea
            valores_linea = re.findall(r'(?:time|tiempo)[=<]([\d\.]+)\s*ms', resultado_texto)
            if valores_linea:
                # Sacamos un promedio matemático de las líneas obtenidas
                promedio = int(sum(float(x) for x in valores_linea) / len(valores_linea))
            else:
                return "⚪ No se pudo calcular el promedio (revisar consola inferior).", "info"
    
    # Evaluación de los umbrales basados en el promedio obtenido
    if promedio <= 25:
        return f"🟢 EXCELENTE ({promedio} ms) - Conexión ultra rápida.", "success"
    elif promedio <= 65:
        return f"🟡 NORMAL ({promedio} ms) - Valores estables para navegación y streaming.", "warning"
    else:
        return f"🟠 LATENCIA ALTA ({promedio} ms) - Posible saturación, jitter o ruta congestionada.", "warning"

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
    st.header("🛠️ Herramientas de Diagnóstico Técnico (ICMP y Trazas)")
    
    def ejecutar_comando(comando):
        try:
            resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
            return resultado.stdout if resultado.stdout else resultado.stderr
        except subprocess.TimeoutExpired:
            return "❌ Error: Tiempo de espera agotado (Timeout)."
        except Exception as e:
            return f"❌ Error de ejecución: {str(e)}"

    def ping_cmd(host, conteo=4):
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        return ejecutar_comando(['ping', param, str(conteo), host])

    def trace_cmd(host):
        comando = ['tracert', host] if platform.system().lower() == 'windows' else ['traceroute', host]
        return ejecutar_comando(comando)

    # --- SECCIÓN 1: ONT / ROUTER ---
    st.subheader("🏠 Verificación de Última Milla (Prueba 2: ONT / Gateway)")
    
    def detectar_gateway():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_loc = s.getsockname()[0]
            s.close()
            partes = ip_loc.split('.')
            partes[-1] = '1'
            return '.'.join(partes)
        except:
            return "192.168.1.1"

    ip_ont = st.text_input("IP de la ONT o Router del Abonado:", value=detectar_gateway())
    
    if st.button("🔍 Testear Conectividad a ONT"):
        with st.spinner("Analizando calidad del enlace con la ONT..."):
            res_ont = ping_cmd(ip_ont)
            msg, tipo = evaluar_latencia(res_ont)
            if tipo == "success" or tipo == "warning":
                st.success(f"Estado de la ONT: {msg}")
            else:
                st.error(f"Estado de la ONT: {msg}")
            with st.expander("Ver salida detallada de la ONT"):
                st.code(res_ont)

    st.markdown("---")

    # --- SECCIÓN 2: PING CON EVALUACIÓN ---
    st.subheader("🚀 Prueba 3 y 6: Ráfaga ICMP con Diagnóstico de Umbrales")
    cat_seleccionada = st.radio("Filtro de Destinos:", ["Solo Servidores Sensa", "Ver Todo (Sensa + Páginas Web)"], horizontal=True)
    dict_filtrado = DESTINOS_SENSA if cat_seleccionada == "Solo Servidores Sensa" else todos_los_destinos
    
    if cache_local and "Caché Sensa Local" not in dict_filtrado:
        dict_filtrado["Caché Sensa Local"] = cache_local

    if st.button("⚡ Ejecutar Matriz ICMP"):
        columnas = st.columns(2)
        for idx, (nombre, host) in enumerate(dict_filtrado.items()):
            col = columnas[idx % 2]
            with col:
                with st.spinner(f"Haciendo ping a {nombre}..."):
                    resultado_ping = ping_cmd(host, conteo=4)
                    msg_eval, tipo_eval = evaluar_latencia(resultado_ping)
                    
                    # Mostrar cartel dinámico según el resultado analizado
                    if "🟢" in msg_eval:
                        st.success(f"**{nombre}** ({host}) -> {msg_eval}")
                    elif "🟡" in msg_eval or "🟠" in msg_eval:
                        st.warning(f"**{nombre}** ({host}) -> {msg_eval}")
                    else:
                        st.error(f"**{nombre}** ({host}) -> {msg_eval}")
                        
                    with st.expander(f"Ver consola de {nombre}"):
                        st.code(resultado_ping)

    st.markdown("---")

    # --- SECCIÓN 3: TRACEROUTE ---
    st.subheader("🗺️ Prueba 4 y 7: Trazas de Ruta")
    destino_para_trace = st.selectbox("Seleccioná el servidor a trazar:", list(dict_filtrado.keys()))
    host_trace = dict_filtrado[destino_para_trace]
    
    if st.button("🗺️ Lanzar Traceroute"):
        st.warning("Analizando la ruta salto por salto. Por favor aguardá...")
        with st.spinner(f"Ejecutando traza hacia {destino_para_trace}..."):
            resultado_trace = trace_cmd(host_trace)
            st.code(resultado_trace)

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
