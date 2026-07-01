import streamlit as st
import subprocess
import platform
import socket
import time
import streamlit.components.v1 as components

st.set_page_config(page_title="Diagnóstico de Red & Sensa", layout="wide", page_icon="🌐")

st.title("🌐 Panel de Diagnóstico Integral - Sensa & Redes")
st.markdown("Herramienta basada en los procedimientos oficiales de verificación de COLSECOR.")

# --- DICCIONARIO DE DESTINOS ACTUALIZADO (Sensa + Globales) ---
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

# --- DETECCIÓN DE ENTORNO ---
es_local = "streamlit" not in socket.gethostname().lower()

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración")
modo = st.sidebar.radio("Seleccionar Modo:", ["Cliente (Web / Navegador)", "Local (Técnico / Nodo / ONT)"])

cache_local = st.sidebar.text_input("Caché Sensa Local / Regional (Opcional):", value="", placeholder="Ej: 10.0.0.50 o cache.asociada.com")

if modo == "Local (Técnico / Nodo / ONT)" and not es_local:
    st.sidebar.warning("⚠️ Modo Nube detectado. Las pruebas de la pestaña 'Local' se ejecutarán desde los servidores de Streamlit Cloud.")

# Unificar destinos según lo configurado
todos_los_destinos = {**DESTINOS_GLOBALES, **DESTINOS_SENSA}
if cache_local:
    todos_los_destinos["Caché Sensa Local"] = cache_local

# ==========================================
# OPCIÓN 1: MODO CLIENTE (HTTP PING DESDE NAVEGADOR)
# ==========================================
if modo == "Cliente (Web / Navegador)":
    st.header("⚡ Prueba 1 y 2: Latencia desde el Navegador del Usuario")
    st.info("Mide el tiempo de respuesta HTTP aproximado desde el dispositivo final (Smart TV, PC o Celular) hacia la infraestructura.")
    
    # Construcción dinámica de destinos para JS
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
            let color = duration < 50 ? '#2ecc71' : (duration < 120 ? '#f1c40f' : '#e74c3c');
            list.innerHTML += `<li>✅ <strong>${{name}}:</strong> <span style="color:${{color}}; font-weight:bold;">${{duration}} ms</span></li>`;
        }} catch (error) {{
            const duration = Math.round(performance.now() - start);
            if (duration < 200) {{
                let color = duration < 50 ? '#2ecc71' : '#f1c40f';
                list.innerHTML += `<li>✅ <strong>${{name}}:</strong> <span style="color:${{color}}; font-weight:bold;">${{duration}} ms (HTTP Ack)</span></li>`;
            }} else {{
                list.innerHTML += `<li>❌ <strong>${{name}}:</strong> <span style="color:#e74c3c; font-weight:bold;">Error / Tiempo de espera agotado</span></li>`;
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
# OPCIÓN 2: MODO LOCAL (DIAGNÓSTICO ICMP / ONT / TRAZAS)
# ==========================================
else:
    st.header("🛠️ Herramientas de Diagnóstico Técnico (ICMP y Trazas)")
    st.markdown("Cumple con las **Pruebas 2, 3, 4, 6 y 7** de la guía oficial de COLSECOR para detección de buffereo.")
    
    def ejecutar_comando(comando):
        try:
            resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
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

    ip_ont = st.text_input("IP de la ONT o Router del Abonado:", value=detector_gateway())
    
    if st.button("🔍 Testear Conectividad a ONT"):
        with st.spinner("Analizando calidad del enlace con la ONT..."):
            res_ont = ping_cmd(ip_ont)
            st.code(res_ont)
            if "ms" in res_ont or "ttl" in res_ont.lower():
                st.success("🟢 Enlace LAN/WiFi con la ONT stable. Si hay degradación, es un tema de la fibra o del transporte superior.")
            else:
                st.error("🔴 Pérdida total hacia la ONT. Revisar cableado, potencia óptica o saturación del equipo local.")

    st.markdown("---")

    # --- SECCIÓN 2: PING CDN & AWS ---
    st.subheader("🚀 Prueba 3 y 6: Ráfaga ICMP a Infraestructura Sensa y Red")
    
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
                    if "ttl" in resultado_ping.lower() or "tiempo=" in resultado_ping.lower() or "time=" in resultado_ping.lower():
                        st.success(f"🟢 {nombre} ({host}) - Responde")
                    else:
                        st.error(f"🔴 {nombre} ({host}) - Sin respuesta / Jitter alto")
                    with st.expander(f"Ver consola de {nombre}"):
                        st.code(resultado_ping)

    st.markdown("---")

    # --- SECCIÓN 3: TRACEROUTE ---
    st.subheader("🗺️ Prueba 4 y 7: Trazas de Ruta (Detección de saltos/saturación)")
    destino_para_trace = st.selectbox("Seleccioná el servidor a trazar:", list(dict_filtrado.keys()))
    host_trace = dict_filtrado[destino_para_trace]
    
    if st.button("🗺️ Lanzar Traceroute"):
        st.warning("Analizando la ruta salto por salto. Esto puede demorar hasta 40 segundos...")
        with st.spinner(f"Ejecutando traza hacia {destino_para_trace} ({host_trace})..."):
            resultado_trace = trace_cmd(host_trace)
            st.code(resultado_trace)
