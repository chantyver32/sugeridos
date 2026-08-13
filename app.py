import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, timedelta
import pytz
import urllib.parse
import io
import re
import os
import streamlit.components.v1 as components
from streamlit_mic_recorder import speech_to_text 
from PIL import Image, ImageDraw, ImageFont # <-- IMPORTACIONES DE IMAGEN AÑADIDAS

# ------------------ CONFIGURACIÓN GENERAL ------------------
with st.spinner('Iniciando sistema Champlitte... 🥐'):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy_mx = datetime.now(zona_mx).date()
    
    st.set_page_config(page_title="Sugeridos", page_icon="🥐", layout="wide")

# CSS personalizado 
st.markdown("""
    <style>
    ul[role="listbox"] li[aria-selected="true"] {
        background-color: transparent !important;
        font-weight: bold !important;
    }
    .block-container { padding-top: 3rem; padding-bottom: 1rem; }
    .main { background-color: #f5f7f9; }
    
    .stButton > button, 
    .stFormSubmitButton > button { 
        width: 100%; 
        border-radius: 8px; 
        font-weight: bold; 
        transition: none !important;
        -webkit-transition: none !important;
    }
    
    .stButton > button:focus, .stButton > button:active,
    .stFormSubmitButton > button:focus, .stFormSubmitButton > button:active {
        box-shadow: none !important;
        outline: none !important;
        transform: none !important;
    }

    [data-testid="stElementContainer"], 
    [data-testid="stForm"] {
        transition: none !important;
        animation: none !important;
    }
    
    div[data-testid="stMetricValue"] { font-size: 28px; color: #1f77b4; }
    div[data-testid="stMetricDelta"] { font-size: 30px !important; font-weight: bold !important; }
    div[data-testid="stMetricDelta"] svg { width: 35px !important; height: 35px !important; }

    div[data-baseweb="popover"] > div {
        background-color: #1a1a1c !important; 
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.8) !important;
    }
    div[data-baseweb="popover"] ul { background-color: transparent !important; }
    div[data-baseweb="popover"] li {
        background-color: transparent !important;
        color: #FFFFFF !important;
        font-size: 14px !important;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }
    div[data-baseweb="popover"] li:hover { background-color: #2d2d30 !important; }
    div[data-baseweb="popover"] li[aria-selected="true"] {
        background-color: #3a3b3e !important; 
        font-weight: bold !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #1a1a1c !important; 
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    div[data-baseweb="select"] > div:focus-within {
        border-color: #ff4b4b !important; 
        box-shadow: 0 0 0 1px #ff4b4b !important;
    }
    div[data-baseweb="select"] div { color: #FFFFFF !important; }
    div[data-baseweb="select"] svg { fill: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# ------------------ SISTEMA DE NOTIFICACIONES POST-RERUN ------------------
if "show_toast" in st.session_state:
    st.toast(st.session_state.show_toast)
    del st.session_state.show_toast
if "show_success" in st.session_state:
    st.success(st.session_state.show_success)
    del st.session_state.show_success
if "show_error" in st.session_state:
    st.error(st.session_state.show_error)
    del st.session_state.show_error
if "show_warning" in st.session_state:
    st.warning(st.session_state.show_warning)
    del st.session_state.show_warning

# ------------------ DICCIONARIO EMPAQUES (PARA REPORTE) ------------------
EMPAQUES = {
    "CUBILETE": {"categoria": "Dulce", "piezas_x_paq": 16},
    "TUTI": {"categoria": "Dulce", "piezas_x_paq": 27},
    "JAMÓN": {"categoria": "Salado", "piezas_x_paq": 9},
    "COCHINITA": {"categoria": "Salado", "piezas_x_paq": 9},
    "PICADILLO": {"categoria": "Salado", "piezas_x_paq": 9},
    "PIERNA": {"categoria": "Salado", "piezas_x_paq": 9},
    "CHORIZO": {"categoria": "Salado", "piezas_x_paq": 20},
    "SALCHICHA": {"categoria": "Salado", "piezas_x_paq": 20},
    "HOJALDRA": {"categoria": "Mixta", "piezas_x_paq": 48},
}

# ------------------ BASE DE DATOS (SUPABASE) ------------------
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    try:
        db_url = st.secrets["DATABASE_URL"]
    except:
        pass
        
conn = st.connection("supabase", type="sql", url=db_url)

with conn.session as s:
    s.execute(text('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT
    )'''))
    s.execute(text('''CREATE TABLE IF NOT EXISTS captura_actual (
        id SERIAL PRIMARY KEY, sucursal TEXT, nombre TEXT, fecha_cad DATE, cantidad INTEGER
    )'''))
    s.execute(text('''CREATE TABLE IF NOT EXISTS base_anterior (
        id SERIAL PRIMARY KEY, sucursal TEXT, nombre TEXT, fecha_cad DATE, cantidad INTEGER
    )'''))
    s.execute(text('''CREATE TABLE IF NOT EXISTS historial_ventas (
        id SERIAL PRIMARY KEY, sucursal TEXT, nombre TEXT, fecha_cad DATE, 
        habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte TIMESTAMP 
    )'''))
    s.commit()

# ------------------ SISTEMA DE LOGIN ------------------
def verificar_login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown("### 🥐 Sugeridos")
        st.markdown("### Control de Acceso")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("form_login"):
                usuario_input = st.text_input("👤 Usuario:", key="login_usr")
                password_input = st.text_input("🔑 Contraseña:", type="password", key="login_pwd")
                btn_login = st.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary")
                
                if btn_login:
                    df_check = conn.query("SELECT * FROM usuarios WHERE username = :u AND password = :p", 
                                          params={"u": usuario_input.strip(), "p": password_input}, ttl=0)
                    if not df_check.empty:
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = usuario_input.strip()
                        st.session_state.show_toast = "✅ ¡Bienvenid@!"
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")
        return False
    return True

if not verificar_login():
    st.stop()

# ------------------ FUNCIONES LOGICAS ------------------
def sonido_click():
    st.markdown(
        """
        <audio autoplay>
        <source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg">
        </audio>
        """,
        unsafe_allow_html=True
    )

def analizar_dictado(texto, fecha_base):
    texto = texto.lower()
    
    nums = {"un": "1", "uno": "1", "una": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5", "seis": "6"}
    for k, v in nums.items():
        texto = re.sub(rf'\b{k}\b', v, texto)

    cantidad = 1
    fecha_calc = fecha_base
    meses = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, 
             "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
    
    match_fecha = re.search(r'(\d{1,2})\s*(?:de\s*)?(' + '|'.join(meses.keys()) + r')', texto)
    
    if match_fecha:
        dia = int(match_fecha.group(1))
        mes = meses[match_fecha.group(2)]
        try:
            fecha_calc = fecha_base.replace(month=mes, day=dia)
            if fecha_calc < fecha_base and (fecha_base.month - fecha_calc.month) > 5:
                fecha_calc = fecha_calc.replace(year=fecha_calc.year + 1)
        except ValueError:
            pass
        texto = texto.replace(match_fecha.group(0), "")
    elif "extra" in texto:
        fecha_calc = fecha_base + timedelta(days=3)
        texto = texto.replace("extra", "")
    elif "pasado mañana" in texto or "día más" in texto or "dia mas" in texto:
        fecha_calc = fecha_base + timedelta(days=2)
        texto = texto.replace("pasado mañana", "").replace("día más", "").replace("diamas", "")
    elif "mañana" in texto or "sugerido" in texto:
        fecha_calc = fecha_base + timedelta(days=1)
        texto = texto.replace("mañana", "").replace("sugerido", "")
    elif "hoy" in texto:
        texto = texto.replace("hoy", "")
        
    match_cant = re.search(r'\b(\d+)\b', texto)
    if match_cant:
        cantidad = int(match_cant.group(1))
        texto = texto.replace(match_cant.group(1), "", 1)
        
    basura = ["para el", "para", "caduca el", "caduca", "cantidad", "agregar", "registrar", "de"]
    for p in basura:
        texto = re.sub(rf'\b{p}\b', '', texto)
        
    producto = re.sub(r'\s+', ' ', texto).strip().upper()
    return producto, cantidad, fecha_calc

def guardar_manual(sucursal, prod, cant, fech):
    with conn.session as s:
        existe = s.execute(text("SELECT cantidad FROM base_anterior WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                           {"nom": prod, "fec": str(fech), "suc": sucursal}).fetchone()
        if existe:
            s.execute(text("UPDATE base_anterior SET cantidad=cantidad+:can WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                      {"can": int(cant), "nom": prod, "fec": str(fech), "suc": sucursal})
        else:
            s.execute(text("INSERT INTO base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fec, :can)"), 
                      {"suc": sucursal, "nom": prod, "fec": str(fech), "can": int(cant)})
        s.commit()
    st.session_state.show_toast = f"✅ Guardado: {cant} {prod}"

# ------------------ FUNCIONES IMAGEN Y BOTON WA ------------------
def get_font(names, size):
    for name in names:
        try: return ImageFont.truetype(name, size)
        except: continue
    return ImageFont.load_default()

def dibujar_logo_texto(draw, width, color_vino, color_texto_oscuro):
    font_champlitte = get_font(["DejaVuSerif-Bold.ttf", "georgiab.ttf", "Times-Bold.ttf", "arialbd.ttf"], 75)
    font_pasteleria = get_font(["DejaVuSans-Bold.ttf", "arialbd.ttf", "Helvetica-Bold.ttf"], 22)
    draw.text((width//2, 60), "Champlitte", fill=color_vino, font=font_champlitte, anchor="mm")
    draw.text((width//2, 130), "PASTELERÍA", fill=color_texto_oscuro, font=font_pasteleria, anchor="mm")

def generar_plantilla_sugeridos(datos, fecha_str):
    width = 900
    espacio_logo = 175 
    header_height = 130
    table_header_height = 45
    row_height = 55
    total_height = espacio_logo + header_height + table_header_height + (max(1, len(datos)) * row_height) + 40

    img = Image.new('RGB', (width, total_height), color=(255, 253, 251))
    draw = ImageDraw.Draw(img)

    WINE, WINE_LIGHT, TEXT_DARK, WHITE = (128, 21, 43), (160, 40, 70), (40, 40, 40), (255, 255, 255)
    ROW_ALT, LINE_COLOR = (253, 243, 243), (235, 220, 225) 

    font_title = get_font(["DejaVuSans-Bold.ttf", "arialbd.ttf"], 42)
    font_sub = get_font(["DejaVuSans.ttf", "arial.ttf"], 18)
    font_th = get_font(["DejaVuSans-Bold.ttf", "arialbd.ttf"], 13)
    font_td = get_font(["DejaVuSans.ttf", "arial.ttf"], 15)
    font_badge = get_font(["DejaVuSans-Bold.ttf", "arialbd.ttf"], 11)

    dibujar_logo_texto(draw, width, WINE, TEXT_DARK)

    y = espacio_logo
    draw.text((width//2, y + 35), "SUGERIDOS", fill=WINE, font=font_title, anchor="mm")
    draw.text((width//2, y + 85), fecha_str, fill=TEXT_DARK, font=font_sub, anchor="mm")

    y += header_height
    draw.rectangle([0, y, width, y + table_header_height], fill=WINE)
    
    col_prod, col_linea, col_cant, col_totales = 200, 520, 680, 820
    draw.text((col_prod, y + 22), "PRODUCTO", fill=WHITE, font=font_th, anchor="mm")
    draw.text((col_linea, y + 22), "CATEGORÍA", fill=WHITE, font=font_th, anchor="mm")
    draw.text((col_cant, y + 22), "PAQUETE + PIEZAS", fill=WHITE, font=font_th, anchor="mm")
    draw.text((col_totales, y + 22), "TOTAL (PIEZAS)", fill=WHITE, font=font_th, anchor="mm")

    y += table_header_height
    if not datos:
        draw.rectangle([0, y, width, y + row_height], fill=WHITE)
        draw.text((width//2, y + (row_height//2)), "No hay sugeridos registrados", fill=TEXT_DARK, font=font_td, anchor="mm")
        y += row_height
    else:
        for item in datos:
            bg_color = WHITE if datos.index(item) % 2 == 0 else ROW_ALT
            draw.rectangle([0, y, width, y + row_height], fill=bg_color)
            draw.line([420, y, 420, y + row_height], fill=LINE_COLOR, width=1)
            draw.line([600, y, 600, y + row_height], fill=LINE_COLOR, width=1)
            draw.line([750, y, 750, y + row_height], fill=LINE_COLOR, width=1)

            draw.text((30, y + (row_height//2)), str(item.get("producto", "")), fill=TEXT_DARK, font=font_td, anchor="lm")

            linea_texto = str(item.get("linea", ""))
            badge_bg = WINE_LIGHT if "Mixta" in linea_texto else ((252, 230, 230) if "Dulce" in linea_texto else WINE)
            badge_text = WHITE if "Mixta" in linea_texto else (WINE if "Dulce" in linea_texto else WHITE)

            badge_w, badge_h = 130, 26
            badge_x = col_linea - (badge_w//2)
            badge_y = y + (row_height//2) - (badge_h//2)
            if linea_texto != "-":
                draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=13, fill=badge_bg)
                draw.text((col_linea, y + (row_height//2)), linea_texto.upper(), fill=badge_text, font=font_badge, anchor="mm")

            draw.text((col_cant, y + (row_height//2)), str(item.get("cantidad", "")), fill=TEXT_DARK, font=font_th, anchor="mm")
            draw.text((col_totales, y + (row_height//2)), str(item.get("totales", "0")), fill=WINE, font=font_th, anchor="mm")

            draw.line([0, y + row_height, width, y + row_height], fill=LINE_COLOR, width=1)
            y += row_height

    img.save("reporte_sugeridos.png")
    return "reporte_sugeridos.png"

def boton_whatsapp_bonito(url, texto):
    html_wa = f"""
    <a href="{url}" target="_blank" style="background-color: #25D366; color: white; text-align: center; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-family: sans-serif; display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; box-sizing: border-box; font-size: 16px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 16 16"><path d="M11.42 9.49c-.19-.09-1.1-.54-1.27-.61s-.29-.09-.41.1-.48.61-.59.73-.21.14-.4.05a5.1 5.1 0 0 1-1.5-.92 5.54 5.54 0 0 1-1.04-1.29c-.11-.18 0-.28.09-.38.08-.09.19-.21.28-.32a1.36 1.36 0 0 0 .19-.32.54.54 0 0 0-.03-.52c-.05-.09-.41-1-.56-1.37-.15-.36-.3-.31-.41-.31h-.35a.68.68 0 0 0-.49.23 2.06 2.06 0 0 0-.64 1.53c0 1.22 1.25 2.4 1.42 2.63.17.23 1.79 2.73 4.33 3.82.6.26 1.07.41 1.44.53.6.19 1.15.16 1.58.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.15-1.18-.06-.1-.23-.15-.42-.24zM8 14.5a6.5 6.5 0 1 1 0-13 6.5 6.5 0 0 1 0 13zM8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0z"/></svg>
        {texto}
    </a>
    <br>
    """
    st.markdown(html_wa, unsafe_allow_html=True)

# ------------------ SIDEBAR ------------------
st.sidebar.markdown("### 🏢 Datos de Sesión")
st.sidebar.caption(f"👤 Conectado como: **{st.session_state.get('usuario_actual', 'Usuario')}**")
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.autenticado = False
    if "usuario_actual" in st.session_state:
        del st.session_state["usuario_actual"]
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

# Pre-seleccionar Urano por defecto
lista_tiendas = list(opciones_wa.keys())
idx_defecto = lista_tiendas.index("URANO") if "URANO" in lista_tiendas else 0
seleccion_wa = st.sidebar.selectbox("📍 Selecciona la Sucursal", lista_tiendas, index=idx_defecto)
numero_whatsapp = opciones_wa[seleccion_wa]
st.sidebar.caption(f"📱 WhatsApp: **{numero_whatsapp}**")

st.sidebar.divider()

if st.session_state.get('usuario_actual', '').lower() == 'admin':
    with st.sidebar.expander("🚨 Zona de Peligro"):
        st.warning("¡ATENCIÓN! Esto borrará el inventario.")
        confirmar_reset = st.checkbox("Confirmar reseteo", key="check_reset")
        if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
            if confirmar_reset:
                with conn.session as s:
                    s.execute(text("TRUNCATE TABLE captura_actual RESTART IDENTITY"))
                    s.execute(text("TRUNCATE TABLE base_anterior RESTART IDENTITY"))
                    s.execute(text("TRUNCATE TABLE historial_ventas RESTART IDENTITY"))
                    s.commit()
                st.session_state.show_toast = "✅ Base de datos limpiada por completo."
                st.rerun()

# ------------------------------------------------------------
# DEFINICIÓN DE POP-UPS (st.dialog)
# ------------------------------------------------------------
def guardar_datos_voz(sucursal):
    cant = st.session_state.voz_input_cant
    prod = st.session_state.voz_input_prod.strip().upper()
    fech = st.session_state.voz_input_fech
    if not prod:
        st.session_state.show_error = "El nombre no puede estar vacío."
        return
    guardar_manual(sucursal, prod, cant, fech)
    st.session_state.confirmacion_voz = None
    st.session_state.audio_leido = False

@st.dialog("🗣️ Confirmar Dictado")
def popup_voz():
    datos = st.session_state.get("confirmacion_voz")
    if not datos:
        st.rerun()
        return
        
    if not st.session_state.get("audio_leido", False):
        js_tts = f"""
        <script>
            function speakText() {{
                const utterance = new SpeechSynthesisUtterance("{datos['original']}");
                utterance.lang = 'es-MX';
                utterance.rate = 1.0;
                window.speechSynthesis.speak(utterance);
            }}
            speakText();
        </script>
        """
        components.html(js_tts, height=0)
        st.session_state.audio_leido = True
        
    st.success(f"**Escuché:** '{datos['original']}'")
    st.number_input("Cantidad", value=int(datos['cant']), min_value=1, key="voz_input_cant")
    st.text_input("Producto", value=datos['prod'], key="voz_input_prod")
    st.date_input("Fecha", value=datos['fecha'], key="voz_input_fech")
    
    st.button("🥖 Ingreso directo", use_container_width=True, type="primary", on_click=guardar_datos_voz, args=(seleccion_wa,))

@st.dialog("✏️ Entrada Manual")
def popup_manual(nombre_final):
    st.markdown(f"### 📦 {nombre_final}")
    
    fecha_sugerido = fecha_hoy_mx + timedelta(days=1)
    fecha_dia_mas = fecha_hoy_mx + timedelta(days=2)
    fecha_extra = fecha_hoy_mx + timedelta(days=3) 

    cant_manual = st.number_input("Cantidad a registrar:", min_value=1, value=1, key="cant_manual_in")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"Sugerido\n({fecha_sugerido.strftime('%d/%m')})", use_container_width=True):
            guardar_manual(seleccion_wa, nombre_final, cant_manual, fecha_sugerido)
            st.rerun()
    with col2:
        if st.button(f"Día más\n({fecha_dia_mas.strftime('%d/%m')})", use_container_width=True):
            guardar_manual(seleccion_wa, nombre_final, cant_manual, fecha_dia_mas)
            st.rerun()
    with col3:
        if st.button(f"Extra\n({fecha_extra.strftime('%d/%m')})", use_container_width=True):
            guardar_manual(seleccion_wa, nombre_final, cant_manual, fecha_extra)
            st.rerun()

# ------------------------------------------------------------
# INTERFAZ PRINCIPAL (TABS)
# ------------------------------------------------------------
st.title("🥐 Sugeridos - Champlitte")

tab1, tab2, tab3 = st.tabs(["📝 Captura", "📋 Datos Excel", "🖼️ Reporte Visual"])

# ---------- PESTAÑA 1: CAPTURA ----------
with tab1:
    st.header("Registrar Nuevo Sugerido")
    tipo_entrada = st.radio("Método:", ["✍️ Manual", "🗣️ Voz"], horizontal=True)
    
    if tipo_entrada == "🗣️ Voz":
        st.info("💡 Dicta ej: 'Sugerido dos cubiletes para mañana'")
        texto_capturado = speech_to_text(
            language='es-MX',                 
            start_prompt="🎙️ Toca para Dictar", 
            stop_prompt="🔴 Grabando...",     
            use_container_width=True,         
            just_once=True,                   
            key='boton_dictado_sugeridos'             
        )
        if texto_capturado:
            prod, cant, fech = analizar_dictado(texto_capturado, fecha_hoy_mx)
            st.session_state.confirmacion_voz = {
                'original': texto_capturado,
                'prod': prod,
                'cant': cant,
                'fecha': fech
            }
            popup_voz()
    
    else: # Modo Manual
        producto_buscado = st.text_input("🔍 Buscar o registrar producto manualmente:", placeholder="Ej. Cubiletes")
        if st.button("Abrir registro manual", type="secondary", use_container_width=True):
            if producto_buscado:
                popup_manual(producto_buscado.upper())
            else:
                st.warning("Escribe un producto primero.")

# ---------- PESTAÑA 2: DATOS EXCEL ----------
with tab2:
    st.subheader("📋 Resumen Rápido de Inventario")
    df_resumen = conn.query("SELECT nombre, cantidad, fecha_cad FROM base_anterior WHERE sucursal = :suc", params={"suc": seleccion_wa}, ttl=0)

    if not df_resumen.empty:
        st.dataframe(df_resumen, use_container_width=True)
    else:
        st.info(f"No hay sugeridos registrados actualmente para {seleccion_wa}.")

# ---------- PESTAÑA 3: REPORTE VISUAL ----------
with tab3:
    st.header("Generar Reporte Visual")
    
    df_resumen = conn.query("SELECT nombre, cantidad FROM base_anterior WHERE sucursal = :suc", params={"suc": seleccion_wa}, ttl=0)
    
    datos_plantilla = []
    fecha_img_str = datetime.now(zona_mx).strftime('%d %m %Y - %H:%M')
    
    if not df_resumen.empty:
        # Agrupar por nombre por si hay repetidos en la BD para sacar el total
        df_agrupado = df_resumen.groupby('nombre')['cantidad'].sum().reset_index()
        
        for index, row in df_agrupado.iterrows():
            prod_db = str(row['nombre']).upper()
            totales = int(row['cantidad'])
            
            linea = "-"
            cant_texto = f"{totales} pz"
            
            # Buscar coincidencia en diccionario para calcular paquetes
            for p_key, p_data in EMPAQUES.items():
                if p_key in prod_db:
                    linea = p_data["categoria"]
                    pz_x_paq = p_data["piezas_x_paq"]
                    paquetes = totales // pz_x_paq
                    sueltas = totales % pz_x_paq
                    
                    if paquetes > 0 and sueltas == 0:
                        cant_texto = f"{paquetes} pq"
                    elif paquetes == 0 and sueltas > 0:
                        cant_texto = f"{sueltas} pz"
                    else:
                        cant_texto = f"{paquetes} pq + {sueltas} pz"
                    break
                    
            datos_plantilla.append({
                "producto": prod_db,
                "linea": linea,
                "cantidad": cant_texto,
                "totales": totales
            })
            
    ruta_img = generar_plantilla_sugeridos(datos_plantilla, fecha_img_str)
    st.image(ruta_img, caption="Reporte generado automáticamente", use_container_width=True)
    
    if seleccion_wa:
        mensaje_wa = f"Sugeridos ({seleccion_wa} | {fecha_img_str})"
        url_wa = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje_wa)}"
        boton_whatsapp_bonito(url_wa, f"Enviar Reporte a {seleccion_wa}")
    else:
        st.info("ℹ️ Selecciona una sucursal en el menú lateral para enviar por WhatsApp.")
