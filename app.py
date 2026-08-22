import re
import time
import libsql_experimental as libsql
import urllib.parse
from datetime import datetime, timedelta
import pytz
import pandas as pd
import streamlit as st
from streamlit_mic_recorder import speech_to_text

# ==========================================
# CONFIGURACIÓN Y BASE DE DATOS
# ==========================================
st.set_page_config(page_title="Control de Stock", page_icon="📦", layout="wide")

EMPAQUES = {
    "Cubiletes": {"categoria": "Dulce", "piezas_x_paq": 16},
    "Tutis": {"categoria": "Dulce", "piezas_x_paq": 27},
    "Volován de Jamón": {"categoria": "Salado", "piezas_x_paq": 9},
    "Volován de Cochinita": {"categoria": "Salado", "piezas_x_paq": 9},
    "Volován de Picadillo": {"categoria": "Salado", "piezas_x_paq": 9},
    "Volován de Pierna": {"categoria": "Salado", "piezas_x_paq": 9},
    "Chorizo Hojaldrado": {"categoria": "Salado", "piezas_x_paq": 20},
    "Salchicha Hojaldrada": {"categoria": "Salado", "piezas_x_paq": 20},
    "Hojaldra Jamón": {"categoria": "Mixta", "piezas_x_paq": 48},
}

PASTELES_C = [
    "PASTEL CARLOS V CHICO", "PASTEL CHOCOFERRERO CHICO", "PASTEL FRESAS C/CREMA CHICO", 
    "PASTEL MACADAMIA CHICO", "PASTEL MILKYWAY CH", "PASTEL MOKA ALM CHICO", 
    "PASTEL PIÑA COCO CHICO", "PASTEL ZANAHORIA CHICO", "PASTEL DE CHEESECAKE CH"
]
PASTELES_G = [
    "PASTEL CARLOS V GRANDE", "PASTEL CHOCOFERRERO GRANDE", "PASTEL FRESAS C/CREMA GRANDE", 
    "PASTEL MACADAMIA GRANDE", "PASTEL MILKYWAY GRANDE", "PASTEL MOKA ALMENDRA GRANDE"
]

def get_hora_mexico():
    tz_mexico = pytz.timezone('America/Mexico_City')
    return datetime.now(tz_mexico)

def crear_conexion():
    """Conexión centralizada a Turso usando los secrets de Streamlit."""
    url = st.secrets["TURSO_DATABASE_URL"]
    auth_token = st.secrets["TURSO_AUTH_TOKEN"]
    return libsql.connect(database=url, auth_token=auth_token)

def init_db():
    conn = crear_conexion()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    username TEXT UNIQUE, 
                    password TEXT
                )''')
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('admin', 'admin')")
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('urano', 'urano')")
    c.execute("UPDATE usuarios SET password = 'urano' WHERE username = 'urano'")
    
    c.execute('''CREATE TABLE IF NOT EXISTS entradas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto TEXT,
                    paquetes INTEGER,
                    piezas_totales INTEGER,
                    fecha_caducidad TEXT,
                    fecha_registro TEXT,
                    fecha_actualizacion TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS horneado (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto TEXT,
                    paquetes INTEGER,
                    piezas_totales INTEGER,
                    fecha_hora TEXT,
                    fecha_actualizacion TEXT,
                    fecha_caducidad TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cocacola (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto TEXT,
                    cantidad INTEGER,
                    fecha_caducidad TEXT,
                    fecha_registro TEXT,
                    fecha_actualizacion TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS malteadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto TEXT,
                    cantidad INTEGER,
                    fecha_caducidad TEXT,
                    fecha_registro TEXT,
                    fecha_actualizacion TEXT
                )''')
                
    # Nuevas tablas para Pastelería y Sugeridos
    c.execute('''CREATE TABLE IF NOT EXISTS pasteleria_diaria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto TEXT,
                    linea TEXT,
                    proyectado INTEGER DEFAULT 0,
                    v12 INTEGER DEFAULT 0,
                    v4 INTEGER DEFAULT 0,
                    v8 INTEGER DEFAULT 0,
                    fecha TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pasteles_sugeridos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto TEXT,
                    categoria TEXT,
                    cantidad INTEGER DEFAULT 0,
                    fecha_registro TEXT
                )''')

    def agregar_columna_segura(tabla, columna, tipo):
        c.execute(f"PRAGMA table_info({tabla})")
        columnas_actuales = [col[1] for col in c.fetchall()]
        if columna not in columnas_actuales:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")

    agregar_columna_segura("entradas", "fecha_actualizacion", "TEXT")
    agregar_columna_segura("horneado", "fecha_actualizacion", "TEXT")
    agregar_columna_segura("horneado", "fecha_caducidad", "TEXT")
    agregar_columna_segura("cocacola", "fecha_actualizacion", "TEXT")

    conn.commit()
    conn.close()

init_db()

# ==========================================
# FUNCIONES AUXILIARES Y GENERACIÓN HTML
# ==========================================
def calcular_stock_detallado():
    conn = crear_conexion()
    c = conn.cursor()
    c.execute("SELECT producto, fecha_caducidad, SUM(piezas_totales) FROM entradas GROUP BY producto, fecha_caducidad")
    entradas_data = c.fetchall()
    
    c.execute("SELECT producto, fecha_caducidad, SUM(piezas_totales) FROM horneado GROUP BY producto, fecha_caducidad")
    salidas_data = c.fetchall()
    
    salidas_dict = {f"{prod}_{cad}": total or 0 for prod, cad, total in salidas_data}
    stock_detallado = []
    
    for prod in EMPAQUES.keys():
        encontro_stock = False
        for prod_e, cad_e, total_ent in entradas_data:
            if prod_e == prod:
                key = f"{prod}_{cad_e}"
                total_sal = salidas_dict.get(key, 0)
                disp = total_ent - total_sal
                if disp > 0:
                    encontro_stock = True
                    pz_x_paq = EMPAQUES[prod]["piezas_x_paq"]
                    stock_detallado.append({
                        "producto": prod,
                        "caducidad": cad_e,
                        "paquetes": disp // pz_x_paq,
                        "piezas_sueltas": disp % pz_x_paq,
                        "piezas_totales": disp
                    })
        if not encontro_stock:
            stock_detallado.append({
                "producto": prod,
                "caducidad": "-",
                "paquetes": 0,
                "piezas_sueltas": 0,
                "piezas_totales": 0
            })
            
    conn.close()
    return stock_detallado

def get_fechas_disp(producto):
    stock = calcular_stock_detallado()
    fechas = [item["caducidad"] for item in stock if item["producto"] == producto and item["piezas_totales"] > 0]
    fechas.sort(key=lambda date_str: datetime.strptime(date_str, '%d/%m/%Y'))
    return fechas

def generar_html_tabla(titulo, subtitulo, columnas, claves_datos, datos, fecha_str, sucursal=""):
    WINE = "#8b1c31"
    html = f"""<div style="background-color: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); max-width: 900px; margin: auto; margin-bottom: 20px;">
    <div style="text-align: center; color: {WINE}; font-family: 'Georgia', serif;">
    <h1 style="margin: 0; font-size: 32px; font-weight: bold;">Champlitte {sucursal.title() if sucursal else ''}</h1>
    <h4 style="margin: 5px 0 15px 0; color: #333; letter-spacing: 2px; font-size: 12px; font-family: sans-serif; font-weight: bold;">{subtitulo}</h4>
    <h2 style="margin: 0; font-size: 24px; font-weight: bold;">{titulo}</h2>
    <p style="color: #666; font-size: 12px; margin-top: 5px; font-family: sans-serif;">{fecha_str}</p>
    </div>
    <div style="overflow-x: auto;">
    <table style="width: 100%; border-collapse: collapse; margin-top: 20px; font-family: sans-serif; font-size: 14px; min-width: 600px;">
    <thead>
    <tr style="background-color: {WINE}; color: white; text-align: center; font-size: 12px;">
    """
    for i, col in enumerate(columnas):
        rad_l = "border-top-left-radius: 8px;" if i == 0 else ""
        rad_r = "border-top-right-radius: 8px;" if i == len(columnas)-1 else ""
        html += f'<th style="padding: 12px; {rad_l} {rad_r}">{col}</th>\n'
        
    html += "</tr>\n</thead>\n<tbody>\n"

    row_color_alt = False
    for row in datos:
        bg_color = "#fffafb" if row_color_alt else "#ffffff"
        row_color_alt = not row_color_alt
        html += f'<tr style="background-color: {bg_color}; border-bottom: 1px solid #f0f0f0; text-align: center; color: {WINE}; font-weight: bold; font-size: 13px;">\n'
        
        for idx, clave in enumerate(claves_datos):
            val = row.get(clave, "-")
            style = "padding: 12px; "
            if idx == 0:
                style += "text-align: left; font-weight: normal; color: #333;"
            elif clave == "totales" or (clave == "cantidad" and isinstance(val, (int, float))):
                style += f"font-weight: bold; color: {WINE};"
            elif clave == "linea":
                bg_badge = "#f8eef0" if "Dulce" in str(val) else WINE
                color_badge = WINE if "Dulce" in str(val) else "white"
                if "Mixta" in str(val): bg_badge, color_badge = "#a02846", "white"
                val = f'<span style="background-color: {bg_badge}; color: {color_badge}; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{val.upper()}</span>'
            else:
                style += "font-weight: normal; color: #555;"
                
            html += f'<td style="{style}">{val}</td>\n'
        html += "</tr>\n"

    if not datos:
        html += f'<tr><td colspan="{len(columnas)}" style="padding: 20px; text-align: center; color: #666; font-style: italic;">No hay registros.</td></tr>\n'

    html += "</tbody>\n</table>\n</div>\n</div>"
    return html

def procesar_texto_voz(texto):
    texto_norm = texto.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    mapa_numeros = {
        "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, 
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, 
        "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, 
        "quince": 15, "dieciseis": 16, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50
    }
    for palabra in sorted(mapa_numeros.keys(), key=len, reverse=True):
        texto_norm = re.sub(rf'\b{palabra}\b', str(mapa_numeros[palabra]), texto_norm)
        
    prod_encontrado = None
    aliases = {
        "hojaldra": "Hojaldra Jamón", "volovan de jamon": "Volován de Jamón",
        "cochinita": "Volován de Cochinita", "picadillo": "Volován de Picadillo",
        "pierna": "Volován de Pierna", "chorizo": "Chorizo Hojaldrado",
        "salchicha": "Salchicha Hojaldrada", "cubilete": "Cubiletes",
        "tuti": "Tutis", "jamon": "Volován de Jamón"
    }
    for alias, prod_real in aliases.items():
        if alias in texto_norm:
            prod_encontrado = prod_real
            break

    paquetes, piezas = 0, 0
    match_paq = re.search(r'(\d+)\s*(paquete|paquetes|caja|cajas|paq|pq)', texto_norm)
    if match_paq: paquetes = int(match_paq.group(1))
    match_pz = re.search(r'(\d+)\s*(pieza|piezas|suelta|sueltas|pz)', texto_norm)
    if match_pz: piezas = int(match_pz.group(1))
    if paquetes == 0 and piezas == 0:
        match_any = re.search(r'(\d+)', texto_norm)
        if match_any: paquetes = int(match_any.group(1)) 

    fecha_detectada = None
    meses_dict = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }
    match_fecha = re.search(r'(\d+)\s*(?:de\s*)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)', texto_norm)
    if match_fecha:
        dia = int(match_fecha.group(1))
        mes = meses_dict[match_fecha.group(2)]
        anio = get_hora_mexico().year
        try: fecha_detectada = datetime(anio, mes, dia).date()
        except ValueError: pass 
            
    return prod_encontrado, paquetes, piezas, fecha_detectada

def boton_whatsapp_bonito(url, texto):
    html_wa = f"""
    <a href="{url}" target="_blank" style="background-color: #25D366; color: white; text-align: center; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-family: sans-serif; display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; box-sizing: border-box; font-size: 16px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 16 16"><path d="M11.42 9.49c-.19-.09-1.1-.54-1.27-.61s-.29-.09-.41.1-.48.61-.59.73-.21.14-.4.05a5.1 5.1 0 0 1-1.5-.92 5.54 5.54 0 0 1-1.04-1.29c-.11-.18 0-.28.09-.38.08-.09.19-.21.28-.32a1.36 1.36 0 0 0 .19-.32.54.54 0 0 0-.03-.52c-.05-.09-.41-1-.56-1.37-.15-.36-.3-.31-.41-.31h-.35a.68.68 0 0 0-.49.23 2.06 2.06 0 0 0-.64 1.53c0 1.22 1.25 2.4 1.42 2.63.17.23 1.79 2.73 4.33 3.82.6.26 1.07.41 1.44.53.6.19 1.15.16 1.58.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.15-1.18-.06-.1-.23-.15-.42-.24zM8 14.5a6.5 6.5 0 1 1 0-13 6.5 6.5 0 0 1 0 13zM8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0z"/></svg>
        {texto}
    </a><br>
    """
    st.markdown(html_wa, unsafe_allow_html=True)

# ==========================================
# DIÁLOGOS DE CONFIRMACIÓN
# ==========================================
@st.dialog("Confirmar Entrada de Mercancía")
def dialog_confirmar_entrada_manual(producto, paquetes, piezas_sueltas, piezas_totales, caducidad):
    st.write(f"**Producto:** {producto}\n**Total General:** {piezas_totales} piezas\n**Caducidad:** {caducidad.strftime('%d/%m/%Y')}")
    if st.button("✅ Confirmar y Guardar", use_container_width=True):
        fecha_ahora = get_hora_mexico().strftime("%d/%m/%Y %H:%M:%S")
        cad_str = caducidad.strftime("%d/%m/%Y")
        conn = crear_conexion()
        c = conn.cursor()
        c.execute("INSERT INTO entradas (producto, paquetes, piezas_totales, fecha_caducidad, fecha_registro, fecha_actualizacion) VALUES (?, ?, ?, ?, ?, ?)",
                  (producto, paquetes, piezas_totales, cad_str, fecha_ahora, fecha_ahora))
        conn.commit()
        conn.close()
        st.toast("Guardado exitosamente.", icon="✅")
        time.sleep(1.5)
        st.rerun()

@st.dialog("Confirmar Horneado")
def dialog_confirmar_horneado_manual(producto, paquetes, piezas_sueltas, piezas_totales, caducidad):
    st.write(f"**A hornear:** {producto}\n**Total General:** {piezas_totales} piezas\n**Caducidad elegida:** {caducidad}")
    if st.button("🔥 Confirmar Horneado", use_container_width=True):
        fecha_ahora = get_hora_mexico().strftime("%d/%m/%Y %H:%M:%S")
        conn = crear_conexion()
        c = conn.cursor()
        c.execute("INSERT INTO horneado (producto, paquetes, piezas_totales, fecha_hora, fecha_actualizacion, fecha_caducidad) VALUES (?, ?, ?, ?, ?, ?)",
                  (producto, paquetes, piezas_totales, fecha_ahora, fecha_ahora, caducidad))
        conn.commit()
        conn.close()
        st.toast("Horneado registrado.", icon="✅")
        time.sleep(1.5)
        st.rerun()

@st.dialog("Confirmar Registro Refrescos/Malteadas")
def dialog_confirmar_generico_manual(producto, cantidad, caducidad, tabla):
    st.write(f"**Presentación:** {producto}\n**Cantidad:** {cantidad} piezas\n**Caducidad:** {caducidad.strftime('%d/%m/%Y')}")
    if st.button("✅ Confirmar y Guardar", use_container_width=True):
        fecha_ahora = get_hora_mexico().strftime("%d/%m/%Y %H:%M:%S")
        cad_str = caducidad.strftime("%d/%m/%Y")
        conn = crear_conexion()
        c = conn.cursor()
        c.execute(f"INSERT INTO {tabla} (producto, cantidad, fecha_caducidad, fecha_registro, fecha_actualizacion) VALUES (?, ?, ?, ?, ?)",
                  (producto, cantidad, cad_str, fecha_ahora, fecha_ahora))
        conn.commit()
        conn.close()
        st.toast("Guardado exitosamente.", icon="✅")
        time.sleep(1.5)
        st.rerun()

# ==========================================
# SISTEMA DE LOGIN Y NAVEGACIÓN
# ==========================================
def verificar_login():
    if "autenticado" not in st.session_state: st.session_state.autenticado = False
    if "show_nav_dialog" not in st.session_state: st.session_state.show_nav_dialog = False

    if not st.session_state.autenticado:
        st.markdown("### 📦 Control de Stock")
        with st.form("form_login"):
            usuario_input = st.text_input("👤 Usuario:")
            password_input = st.text_input("🔑 Contraseña:", type="password")
            if st.form_submit_button("Iniciar Sesión", use_container_width=True):
                conn = crear_conexion()
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (usuario_input.strip(), password_input))
                user = c.fetchone()
                conn.close()
                if user:
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = usuario_input.strip()
                    st.session_state.show_nav_dialog = True
                    st.toast("¡Bienvenid@!", icon="👋")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
        return False
    return True

if not verificar_login():
    st.stop()

if st.session_state.get("show_nav_dialog", False):
    @st.dialog("👋 ¿Qué acción vas a realizar?")
    def inicio_rapido_dialog():
        if st.button("📥 Registrar Entrada", use_container_width=True):
            st.session_state.menu_radio = "📥 Entradas"
            st.session_state.show_nav_dialog = False
            st.rerun()
        if st.button("🥐 Hornear", use_container_width=True):
            st.session_state.menu_radio = "🥐 Horneado"
            st.session_state.show_nav_dialog = False
            st.rerun()
        if st.button("🍰 Gestión de Pastelería", use_container_width=True):
            st.session_state.menu_radio = "🍰 Pastelería"
            st.session_state.show_nav_dialog = False
            st.rerun()
    inicio_rapido_dialog()
    st.stop()

# ==========================================
# BARRA LATERAL (SIDEBAR)
# ==========================================
st.sidebar.markdown("### 🏢 Datos de Sesión")
st.sidebar.caption(f"👤 Conectado como: **{st.session_state.get('usuario_actual', 'Usuario')}**")
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.autenticado = False
    if "usuario_actual" in st.session_state: del st.session_state["usuario_actual"]
    st.rerun()

st.sidebar.divider()
opciones_wa = {
    "URANO": "522291653665", "COSTA DE ORO": "522292780850", "COSTA VERDE": "522299359597",
    "DÍAZ MIRÓN": "522291302759", "EJÉRCITO MEXICANO": "522299272107", "PLAZA RÍO": "522299864120",
    "PLAYAS DEL CONCHAL": "522291794020", "COYOL": "522299398334", "LA PLACITA": "522299208481",
    "CUAUHTÉMOC": "522291651340", "MARIO MOLINA": "522291780851", "RAFAEL CUERVO": "522291980229",
    "RÍO MEDIO": "522291005852", "DIVERPLAZA": "522293763180", "BOLÍVAR": "522291002947",
    "CIRCUNVALACIÓN": "522299393726", "J.B. LOBOS": "522299201956", "YÁÑEZ": "522293764940",
    "PALACIO DE HIERRO": "522299272100", "CIUDAD INDUSTRIAL": "522299200278", "DONATO CASAS": "522291653833",
    "LAS VEGAS": "522291932980", "PUENTE MORENO": "522296893999", "CONDESA": "522299863464",
    "MURILLO VIDAL": "522286886443", "ARAUCARIAS": "522281177133", "ÁVILA CAMACHO": "522288170989",
    "EMILIANO ZAPATA": "522969628525"
}
seleccion_wa = st.sidebar.selectbox("📍 Selecciona Sucursal", list(opciones_wa.keys()), index=0)
numero_whatsapp = opciones_wa.get(seleccion_wa, "")

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
if "menu_radio" not in st.session_state: st.session_state.menu_radio = "📥 Entradas"

opciones_menu = ["📥 Entradas", "🥐 Horneado", "🍰 Pastelería", "🎯 Sugeridos", "🥤 Coca-Cola", "🥛 Malteadas", "📄 Formatos"]
seccion = st.radio("Navegación", opciones_menu, horizontal=True, key="menu_radio", label_visibility="collapsed")

# ------------------------------------------
# SECCIÓN 1: ENTRADAS
# ------------------------------------------
if seccion == "📥 Entradas":
    st.header("Registrar Nueva Mercancía")
    with st.form("form_entrada", clear_on_submit=True):
        prod_sel = st.selectbox("Producto", list(EMPAQUES.keys()), index=None)
        c1, c2 = st.columns(2)
        cant_paq = c1.number_input("Paquetes", min_value=0, step=1, value=None)
        cant_piezas = c2.number_input("Piezas sueltas", min_value=0, step=1, value=None)
        caducidad_sel = st.date_input("Fecha de Caducidad", value=None, format="DD/MM/YYYY")
            
        if st.form_submit_button("Revisar y Registrar", use_container_width=True):
            val_paq = cant_paq or 0
            val_pz = cant_piezas or 0
            if prod_sel and (val_paq > 0 or val_pz > 0) and caducidad_sel:
                pz_totales = (val_paq * EMPAQUES[prod_sel]["piezas_x_paq"]) + val_pz
                dialog_confirmar_entrada_manual(prod_sel, val_paq, val_pz, pz_totales, caducidad_sel)
            else:
                st.error("Registra al menos 1 paquete/pieza y caducidad.")

# ------------------------------------------
# SECCIÓN 2: HORNEADO
# ------------------------------------------
elif seccion == "🥐 Horneado":
    st.header("Horneado de Mercancía")
    prod_hornear = st.selectbox("Producto a Hornear", list(EMPAQUES.keys()), index=None)
    if prod_hornear:
        fechas_disp = get_fechas_disp(prod_hornear)
        if not fechas_disp:
            st.warning(f"No hay inventario registrado para {prod_hornear}")
        else:
            with st.form("form_horneado", clear_on_submit=True):
                cad_hornear = st.selectbox("Seleccionar Caja/Caducidad", fechas_disp)
                c1, c2 = st.columns(2)
                cant_hornear_paq = c1.number_input("Paquetes", min_value=0, step=1, value=None)
                cant_hornear_pz = c2.number_input("Piezas", min_value=0, step=1, value=None)
                
                if st.form_submit_button("Revisar y Hornear", use_container_width=True):
                    v_paq, v_pz = cant_hornear_paq or 0, cant_hornear_pz or 0
                    if (v_paq > 0 or v_pz > 0) and cad_hornear:
                        pz_a_hornear = (v_paq * EMPAQUES[prod_hornear]["piezas_x_paq"]) + v_pz
                        stock = calcular_stock_detallado()
                        disp_pz = sum([i["piezas_totales"] for i in stock if i["producto"] == prod_hornear and i["caducidad"] == cad_hornear])
                        if pz_a_hornear > disp_pz:
                            st.warning(f"⚠️ Stock insuficiente en la caducidad {cad_hornear}. Solo hay {disp_pz} pz.")
                        else:
                            dialog_confirmar_horneado_manual(prod_hornear, v_paq, v_pz, pz_a_hornear, cad_hornear)
                    else:
                        st.error("Completa cantidad.")

    st.markdown("---")
    st.subheader("🖼️ Reportes Visuales")
    stock_actual = calcular_stock_detallado()
    datos_resumen = []
    
    for prod in EMPAQUES.keys():
        stock_prod = [item for item in stock_actual if item['producto'] == prod and item['piezas_totales'] > 0]
        if stock_prod:
            total_pz = sum(item['piezas_totales'] for item in stock_prod)
            try: prox_horneo = min(stock_prod, key=lambda x: datetime.strptime(x['caducidad'], '%d/%m/%Y'))['caducidad']
            except ValueError: prox_horneo = stock_prod[0]['caducidad']
            datos_resumen.append({"producto": prod, "totales": total_pz, "prox_horneo": prox_horneo})
            
    fecha_mex = get_hora_mexico().strftime('%d/%m/%Y - %H:%M')
    html_resumen = generar_html_tabla(
        "RESUMEN (TOTALES)", "CONTROL DE BOCADILLOS", 
        ["PRODUCTO", "TOTAL (PIEZAS)", "PRÓXIMO HORNEO"], ["producto", "totales", "prox_horneo"],
        datos_resumen, fecha_mex, seleccion_wa
    )
    st.markdown(html_resumen, unsafe_allow_html=True)

# ------------------------------------------
# SECCIÓN 3: PASTELERÍA (NUEVA PESTAÑA)
# ------------------------------------------
elif seccion == "🍰 Pastelería":
    st.header("Proyectado y Ventas de Pastelería")
    fecha_hoy = get_hora_mexico().strftime("%d/%m/%Y")
    
    conn = crear_conexion()
    c = conn.cursor()
    # Recuperamos los datos que ya se guardaron hoy para pre-cargar los inputs
    c.execute("SELECT producto, proyectado, v12, v4, v8 FROM pasteleria_diaria WHERE fecha = ?", (fecha_hoy,))
    datos_hoy = {row[0]: {"proyectado": row[1], "v12": row[2], "v4": row[3], "v8": row[4]} for row in c.fetchall()}
    
    with st.form("form_pasteleria"):
        st.markdown(f"**Fecha actual:** {fecha_hoy}")
        st.subheader("🟢 Línea C (Chicos)")
        cols = st.columns([2, 1, 1, 1, 1])
        cols[0].write("**Producto**")
        cols[1].write("**Proyectado**")
        cols[2].write("**Ventas 12:00 p.m.**")
        cols[3].write("**Ventas 04:00 p.m.**")
        cols[4].write("**Ventas 08:00 p.m.**")
        
        inputs_pasteles = {}
        for pastel in PASTELES_C + PASTELES_G:
            if pastel == PASTELES_G[0]:
                st.divider()
                st.subheader("🟢 Línea G (Grandes)")
            
            c_prod, c_proy, c_12, c_4, c_8 = st.columns([2, 1, 1, 1, 1])
            c_prod.write(pastel)
            
            val_bd = datos_hoy.get(pastel, {"proyectado":0, "v12":0, "v4":0, "v8":0})
            
            p = c_proy.number_input("P", min_value=0, step=1, value=val_bd["proyectado"], key=f"p_{pastel}", label_visibility="collapsed")
            v12 = c_12.number_input("12", min_value=0, step=1, value=val_bd["v12"], key=f"12_{pastel}", label_visibility="collapsed")
            v4 = c_4.number_input("4", min_value=0, step=1, value=val_bd["v4"], key=f"4_{pastel}", label_visibility="collapsed")
            v8 = c_8.number_input("8", min_value=0, step=1, value=val_bd["v8"], key=f"8_{pastel}", label_visibility="collapsed")
            
            linea = "C" if pastel in PASTELES_C else "G"
            inputs_pasteles[pastel] = {"linea": linea, "p": p, "v12": v12, "v4": v4, "v8": v8, "v_old": val_bd}
            
        if st.form_submit_button("💾 Guardar Ventas y Actualizar Sugeridos", type="primary", use_container_width=True):
            for pastel, data in inputs_pasteles.items():
                v_tot_nuevo = data["v12"] + data["v4"] + data["v8"]
                v_tot_viejo = data["v_old"]["v12"] + data["v_old"]["v4"] + data["v_old"]["v8"]
                delta_ventas = v_tot_nuevo - v_tot_viejo
                
                # 1. Guardar estado del día en pasteleria_diaria
                if pastel in datos_hoy:
                    c.execute("""UPDATE pasteleria_diaria SET proyectado=?, v12=?, v4=?, v8=? 
                                 WHERE producto=? AND fecha=?""", 
                              (data["p"], data["v12"], data["v4"], data["v8"], pastel, fecha_hoy))
                else:
                    c.execute("""INSERT INTO pasteleria_diaria (producto, linea, proyectado, v12, v4, v8, fecha) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                              (pastel, data["linea"], data["p"], data["v12"], data["v4"], data["v8"], fecha_hoy))
                
                # 2. Descontar DELTA automático en pasteles_sugeridos (FIFO: descontar a los más antiguos)
                if delta_ventas > 0:
                    c.execute("SELECT id, cantidad FROM pasteles_sugeridos WHERE producto = ? AND cantidad > 0 ORDER BY id ASC", (pastel,))
                    pendientes = c.fetchall()
                    restante = delta_ventas
                    for sug_id, cant_disp in pendientes:
                        if restante <= 0: break
                        if cant_disp <= restante:
                            c.execute("UPDATE pasteles_sugeridos SET cantidad = 0 WHERE id = ?", (sug_id,))
                            restante -= cant_disp
                        else:
                            c.execute("UPDATE pasteles_sugeridos SET cantidad = cantidad - ? WHERE id = ?", (restante, sug_id))
                            restante = 0

            conn.commit()
            st.success("¡Ventas registradas y stock de sugeridos descontado!")
            time.sleep(1.5)
            st.rerun()

    # Visualización de las "Diferencias"
    st.markdown("---")
    st.subheader(f"📊 Diferencia proyectado {fecha_hoy}")
    c.execute("SELECT producto, linea, proyectado, v12, v4, v8 FROM pasteleria_diaria WHERE fecha = ?", (fecha_hoy,))
    filas = c.fetchall()
    
    if filas:
        datos_dif = []
        for f in filas:
            vendidos_totales = f[3] + f[4] + f[5]
            diferencia = vendidos_totales - f[2] # Formula: Vendidos - Proyectado
            datos_dif.append({"LÍNEA": f[1], "PRODUCTO": f[0], "DIFERENCIA": diferencia})
            
        df_dif = pd.DataFrame(datos_dif)
        st.dataframe(df_dif, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se han guardado datos para el proyectado de hoy.")
        
    conn.close()

# ------------------------------------------
# SECCIÓN 4: SUGERIDOS (NUEVA PESTAÑA)
# ------------------------------------------
elif seccion == "🎯 Sugeridos":
    st.header("Gestión de Sugeridos (Próximos a Vencer)")
    
    with st.form("form_sugeridos"):
        prod_sug = st.selectbox("Pastel", PASTELES_C + PASTELES_G)
        cat_sug = st.selectbox("Categoría", ["Pasado", "Mañana", "Extra"])
        cant_sug = st.number_input("Cantidad a sugerir", min_value=1, step=1)
        
        if st.form_submit_button("Agregar a Sugeridos", type="secondary"):
            conn = crear_conexion()
            c = conn.cursor()
            c.execute("INSERT INTO pasteles_sugeridos (producto, categoria, cantidad, fecha_registro) VALUES (?, ?, ?, ?)",
                      (prod_sug, cat_sug, cant_sug, get_hora_mexico().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
            conn.close()
            st.toast("Agregado a la lista de sugeridos", icon="✅")
            time.sleep(1)
            st.rerun()
            
    st.divider()
    st.subheader("📋 Stock Sugerido Actual (Pendientes por vender)")
    
    conn = crear_conexion()
    df_sugeridos = pd.read_sql("SELECT id, producto, categoria, cantidad, fecha_registro FROM pasteles_sugeridos WHERE cantidad > 0 ORDER BY fecha_registro ASC", conn)
    
    if not df_sugeridos.empty:
        # Se muestra la tabla permitiendo edición manual por si hay mermas
        st.caption("Esta tabla se resta automáticamente al capturar ventas en la pestaña 'Pastelería'. También puedes ajustar manualmente aquí.")
        edited_sug = st.data_editor(
            df_sugeridos,
            column_config={
                "id": None,
                "producto": st.column_config.TextColumn("Producto", disabled=True),
                "categoria": st.column_config.TextColumn("Categoría", disabled=True),
                "cantidad": st.column_config.NumberColumn("Piezas por Vender", min_value=0, step=1),
                "fecha_registro": st.column_config.TextColumn("Fecha de Ingreso", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="edit_sugeridos"
        )
        if st.button("💾 Guardar Ajustes Manuales"):
            c = conn.cursor()
            for i in range(len(edited_sug)):
                row = edited_sug.iloc[i]
                c.execute("UPDATE pasteles_sugeridos SET cantidad = ? WHERE id = ?", (int(row['cantidad']), int(row['id'])))
            conn.commit()
            st.success("Cantidades actualizadas.")
            time.sleep(1)
            st.rerun()
    else:
        st.info("No hay pasteles sugeridos pendientes. ¡Excelente trabajo!")
    conn.close()

# ------------------------------------------
# SECCIÓN 5: COCA-COLA / MALTEADAS / FORMATOS
# ------------------------------------------
elif seccion in ["🥤 Coca-Cola", "🥛 Malteadas"]:
    tabla = "cocacola" if seccion == "🥤 Coca-Cola" else "malteadas"
    opciones = ["Coca-Cola 3 L", "Coca-Cola 600 ml"] if tabla == "cocacola" else ["Fresa", "Vainilla", "Chocolate"]
    
    st.header(f"Inventario de {seccion.split(' ')[1]}")
    with st.form(f"form_{tabla}", clear_on_submit=True):
        prod_sel = st.selectbox("Producto/Sabor", opciones, index=None)
        cant = st.number_input("Piezas", min_value=1, step=1, value=None)
        cad = st.date_input("Fecha de Caducidad", value=None, format="DD/MM/YYYY")
        if st.form_submit_button("Revisar y Registrar", use_container_width=True):
            if prod_sel and cant and cad:
                dialog_confirmar_generico_manual(prod_sel, cant, cad, tabla)
            else:
                st.error("Completa todos los campos.")

elif seccion == "📄 Formatos":
    st.header("Formatos Operativos")
    with st.expander("🌡️ Formato de Temperaturas", expanded=False):
        st.info("Formato de congelación (PEPS de -18°C a -25°C).")
        hoy = get_hora_mexico().date()
        dias_lunes = (0 - hoy.weekday()) % 7 or 7
        inicio = (hoy + timedelta(days=dias_lunes)) if hoy.weekday() != 6 else (hoy + timedelta(days=1))
        dias_sem = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        df_t = pd.DataFrame([{"DÍA": dias_sem[i], "FECHA": (inicio + timedelta(days=i)).strftime("%d/%m/%Y"), "HORA": "", "TEMPERATURA": "", "PERSONA": ""} for i in range(7)])
        st.dataframe(df_t, hide_index=True, use_container_width=True)
