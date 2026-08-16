import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, timedelta
import pytz
import urllib.parse
import io
import re
import os
import random
import streamlit.components.v1 as components
from streamlit_mic_recorder import speech_to_text  

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
    
    .btn-wa {
        background-color: #25D366;
        color: white !important;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none !important;
        display: block;
        font-size: 14px;
        font-weight: bold;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .btn-wa:hover { background-color: #128C7E; }
    
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
    div[data-baseweb="popover"] li[aria-selected="true"] { background-color: #3a3b3e !important; font-weight: bold !important; }

    div[data-baseweb="select"] > div {
        background-color: #1a1a1c !important; 
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    div[data-baseweb="select"] > div:focus-within { border-color: #ff4b4b !important; box-shadow: 0 0 0 1px #ff4b4b !important; }
    div[data-baseweb="select"] div { color: #FFFFFF !important; }
    div[data-baseweb="select"] svg { fill: #FFFFFF !important; }

    button[kind="primary"] { background-color: #ff4b4b !important; color: white !important; border: none !important; }
    button[kind="secondary"] { background-color: transparent !important; border: 1px solid rgba(136, 136, 136, 0.5) !important; color: rgba(136, 136, 136, 0.9) !important; }
    button[kind="secondary"]:hover { background-color: rgba(136, 136, 136, 0.1) !important; }
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
                        st.session_state.inicio_popup_mostrado = False 
                        st.session_state.show_toast = "✅ ¡Bienvenid@!"
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")
        return False
    return True

if not verificar_login():
    st.stop()

# ------------------ FUNCIONES GLOBALES ------------------
def sonido_click():
    st.markdown(
        """
        <audio autoplay>
        <source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg">
        </audio>
        """,
        unsafe_allow_html=True
    )

def sumar(valor):
    st.session_state.conteo_temp += valor
    sonido_click()

def resetear():
    st.session_state.conteo_temp = 0
    sonido_click()

def restar_dia():
    st.session_state.voz_input_fech -= timedelta(days=1)
    
def sumar_dia():
    st.session_state.voz_input_fech += timedelta(days=1)

def generar_excel_formato(df, sucursal, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V."):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    sheet = workbook.add_worksheet('SUGERIDOS')

    sheet.hide_gridlines(2)

    color_guinda = '#8C0000'
    color_sombreado_rojo = '#FCE4D6' 
    
    fmt_titulo = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': color_guinda, 'align': 'center', 'valign': 'vcenter', 'font_size': 14, 'border': 1})
    fmt_subtitulo = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 11})
    fmt_etiqueta = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})
    fmt_valor = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})
    fmt_header_tabla = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})
    
    fmt_datos_centro = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})
    fmt_sombreado = workbook.add_format({'bg_color': color_sombreado_rojo, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})

    sheet.set_column('A:A', 15)  
    sheet.set_column('B:B', 35)  
    sheet.set_column('C:C', 12)  
    sheet.set_column('D:D', 22)  

    sheet.set_row(0, 30)
    sheet.merge_range('A1:D1', titulo, fmt_titulo)
    sheet.merge_range('A2:D2', 'SUGERIDOS DEL DÍA', fmt_subtitulo)

    sheet.write('A3', 'SUCURSAL', fmt_etiqueta)
    sheet.merge_range('B3:D3', sucursal.upper(), fmt_valor)
    
    sheet.write('A4', 'ACTUALIZADO', fmt_etiqueta)
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_str = datetime.now(zona_mx).strftime("%d/%m/%Y %H:%M")
    sheet.merge_range('B4:D4', fecha_str, fmt_valor)

    sheet.write('A5', '', fmt_valor)
    sheet.write('B5', 'PRODUCTO', fmt_header_tabla)
    sheet.write('C5', 'CANTIDAD', fmt_header_tabla)
    sheet.write('D5', 'FECHA', fmt_header_tabla)

    row = 5
    if not df.empty:
        col_nombre = 'Producto' if 'Producto' in df.columns else 'nombre'
        col_cant = 'Existencia' if 'Existencia' in df.columns else 'cantidad'
        col_fecha = 'Fecha' if 'Fecha' in df.columns else 'fecha_cad'

        df = df.sort_values(by=col_fecha).reset_index(drop=True)
        fecha_proxima_vencer = df[col_fecha].min()

        for _, fila in df.iterrows():
            formato_actual = fmt_sombreado if fila[col_fecha] == fecha_proxima_vencer else fmt_datos_centro
            
            fecha_str_out = str(fila[col_fecha])
            try:
                if '-' in fecha_str_out:
                    partes = fecha_str_out.split('-')
                    if len(partes) == 3:
                        fecha_str_out = f"{partes[2]}/{partes[1]}/{partes[0]}"
            except Exception:
                pass
            
            sheet.write(row, 0, '', fmt_valor) 
            sheet.write(row, 1, str(fila[col_nombre]), formato_actual) 
            sheet.write(row, 2, fila[col_cant], formato_actual)
            sheet.write(row, 3, fecha_str_out, formato_actual) 
            row += 1

    last_row = row - 1 if row > 5 else 5
    sheet.autofilter(4, 1, last_row, 3)

    writer.close()
    return output.getvalue()

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
        texto = texto.replace("día extra", "").replace("dia extra", "").replace("extra", "")
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

def marcar_vendido(prod_id, prod_nombre):
    with conn.session as s:
        s.execute(text("UPDATE base_anterior SET cantidad = GREATEST(cantidad - 1, 0) WHERE id = :id"), {"id": int(prod_id)})
        s.commit()
    st.session_state.show_toast = f"✅ Venta registrada: se descontó 1 de {prod_nombre}."

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
seleccion_wa = st.sidebar.selectbox("📍 Selecciona la Sucursal", list(opciones_wa.keys()))
numero_whatsapp = opciones_wa[seleccion_wa]
st.sidebar.caption(f"📱 WhatsApp: **{numero_whatsapp}**")

st.sidebar.divider()

st.sidebar.markdown("### 💾 Respaldo de Base de Datos")
st.sidebar.info(f"Guarda o restaura tu stock específicamente para {seleccion_wa}.")
archivo_csv = st.sidebar.file_uploader("⬆️ Subir Respaldo CSV", type=["csv"])

if archivo_csv is not None:
    if st.sidebar.button("🔄 Cargar y Restaurar Stock", use_container_width=True):
        try:
            df_restaurar = pd.read_csv(archivo_csv)
            if 'Producto' in df_restaurar.columns:
                df_restaurar = df_restaurar.rename(columns={'Producto': 'nombre', 'Caducidad': 'fecha_cad', 'Fecha': 'fecha_cad', 'Existencia': 'cantidad'})
            
            with conn.session as s:
                s.execute(text("DELETE FROM base_anterior WHERE sucursal = :suc"), {"suc": seleccion_wa})
                for _, fila in df_restaurar.iterrows():
                    s.execute(text("INSERT INTO base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fec, :can)"),
                              {"suc": seleccion_wa, "nom": str(fila['nombre']).upper(), "fec": str(fila['fecha_cad']), "can": int(fila['cantidad'])})
                s.commit()
            
            st.session_state.show_toast = "✅ Inventario restaurado correctamente para " + seleccion_wa
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"⚠️ Error al restaurar: {e}")

st.sidebar.divider()

if st.session_state.get('usuario_actual', '').lower() == 'admin':
    with st.sidebar.expander("🚨 Zona de Peligro"):
        st.warning("¡ATENCIÓN! Esto borrará el inventario de TODAS las sucursales.")
        confirmar_reset = st.checkbox("Confirmar que deseo borrar toda la base de datos", key="check_reset")
        
        if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
            if confirmar_reset:
                with conn.session as s:
                    s.execute(text("TRUNCATE TABLE captura_actual RESTART IDENTITY"))
                    s.execute(text("TRUNCATE TABLE base_anterior RESTART IDENTITY"))
                    s.execute(text("TRUNCATE TABLE historial_ventas RESTART IDENTITY"))
                    s.commit()
                    
                st.session_state.show_toast = "✅ Base de datos limpiada por completo."
                st.rerun()
            else:
                st.sidebar.error("Debes confirmar primero seleccionando la casilla.")

# ------------------------------------------------------------
# LÓGICA DE CALLBACKS PARA POPUP VOZ 
# ------------------------------------------------------------
def guardar_datos_voz(sucursal):
    cant = st.session_state.voz_input_cant
    prod = st.session_state.voz_input_prod.strip().upper()
    fech = st.session_state.voz_input_fech  
    
    if not prod:
        st.session_state.show_error = "El nombre no puede estar vacío."
        return
        
    with conn.session as s:
        existe_stock = s.execute(text("SELECT cantidad FROM base_anterior WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                                 {"nom": prod, "fec": str(fech), "suc": sucursal}).fetchone()
        if existe_stock:
            s.execute(text("UPDATE base_anterior SET cantidad=cantidad+:can WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                      {"can": int(cant), "nom": prod, "fec": str(fech), "suc": sucursal})
        else:
            s.execute(text("INSERT INTO base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fec, :can)"), 
                      {"suc": sucursal, "nom": prod, "fec": str(fech), "can": int(cant)})
        s.commit()
        
    st.session_state.confirmacion_voz = None
    st.session_state.ultimo_audio_procesado = None
    st.session_state.audio_leido = False
    st.session_state.buscar_prod = ""
    st.session_state.mic_key += 1 
    st.session_state.show_toast = f"✅ Ingreso directo: {int(cant)} {prod}"

# ------------------------------------------------------------
# DEFINICIÓN DE POP-UPS (st.dialog)
# ------------------------------------------------------------
@st.dialog("⚠️ Nueva Captura")
def popup_inicio_captura(sucursal):
    st.markdown(f"¿Deseas iniciar una nueva captura para **{sucursal}**?")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sí, continuar", type="primary", use_container_width=True):
            with conn.session as s:
                s.execute(text("DELETE FROM base_anterior WHERE sucursal = :suc"), {"suc": sucursal})
                s.execute(text("DELETE FROM captura_actual WHERE sucursal = :suc"), {"suc": sucursal})
                s.commit()
            st.session_state.inicio_popup_mostrado = True
            st.session_state.show_toast = f"✅ Base de {sucursal} reiniciada para nueva captura."
            st.rerun()
    with col2:
        if st.button("No, mantener captura actual", type="secondary", use_container_width=True):
            st.session_state.inicio_popup_mostrado = True
            st.rerun()


@st.dialog("🗣️")
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
    
    if "voz_input_fech" not in st.session_state or st.session_state.get("voz_id_original") != datos['original']:
        st.session_state.voz_input_fech = datos['fecha']
        st.session_state.voz_id_original = datos['original']
    
    st.number_input("Cantidad", value=int(datos['cant']), min_value=1, key="voz_input_cant")
    st.text_input("Producto", value=datos['prod'], key="voz_input_prod")
    
    # NUEVO: Botones usando callbacks (on_click) para evitar parpadeo y error de doble renderizado
    st.markdown("**📅 Fecha Sugerida:**")
    col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
    with col_f1:
        st.button("➖ Día", use_container_width=True, on_click=restar_dia)
    with col_f2:
        # NUEVO: Fondo gris clarito y letra blanca para la fecha
        st.markdown(
            f"<div style='text-align: center; font-size: 20px; font-weight: bold; padding: 5px; background: #A9A9A9; border-radius: 5px; border: 1px solid #999; color: white;'>{st.session_state.voz_input_fech.strftime('%d/%m/%Y')}</div>", 
            unsafe_allow_html=True
        )
    with col_f3:
        st.button("➕ Día", use_container_width=True, on_click=sumar_dia)
            
    st.write("") 
    
    col1, col2 = st.columns(2)
    with col1:
        st.button("🥖 Ingreso directo", use_container_width=True, type="primary", on_click=guardar_datos_voz, args=(seleccion_wa,))
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.confirmacion_voz = None
            st.session_state.ultimo_audio_procesado = None 
            st.session_state.audio_leido = False
            st.session_state.mic_key += 1 
            st.rerun()

@st.dialog("✏️")
def popup_manual(nombre_final):
    st.markdown(f"### 📦 {nombre_final}")
    
    fecha_sugerido = fecha_hoy_mx + timedelta(days=1)
    fecha_pasado_manana = fecha_hoy_mx + timedelta(days=2)
    fecha_extra = fecha_hoy_mx + timedelta(days=3)
    
    opcion_fecha = st.radio(
        "📅 Fecha:",
        options=["Sugeridos (Mañana)", "Pasado Mañana", "Extra"], 
        horizontal=True
    )
    
    if opcion_fecha == "Sugeridos (Mañana)":
        f_cad = fecha_sugerido
    elif opcion_fecha == "Pasado Mañana":
        f_cad = fecha_pasado_manana
    else:
        f_cad = fecha_extra

    st.write("")
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    with col_sum1:
        st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with col_sum2:
        st.button("+2", use_container_width=True, on_click=sumar, args=(2,))
    with col_sum3:
        st.button("Borrar", use_container_width=True, on_click=resetear)
        
    st.write("")
    st.markdown(
        f"""
        <div style="margin-bottom: 15px;">
            <span style="color: gray; font-size: 14px;">Total a registrar</span><br>
            <span style="font-size: 28px; color: #1f77b4; font-weight: bold;">{st.session_state.conteo_temp}</span>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    if st.button("🥖 Ingreso directo", use_container_width=True, type="primary"):
        cant = st.session_state.conteo_temp
        if cant > 0:
            with conn.session as s:
                existe_stock = s.execute(text("SELECT cantidad FROM base_anterior WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                                         {"nom": nombre_final, "fec": str(f_cad), "suc": seleccion_wa}).fetchone()
                if existe_stock:
                    s.execute(text("UPDATE base_anterior SET cantidad=cantidad+:can WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                              {"can": int(cant), "nom": nombre_final, "fec": str(f_cad), "suc": seleccion_wa})
                else:
                    s.execute(text("INSERT INTO base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fec, :can)"), 
                              {"suc": seleccion_wa, "nom": nombre_final, "fec": str(f_cad), "can": int(cant)})
                s.commit()
                
            st.session_state.conteo_temp = 0
            st.session_state.buscar_prod = ""
            st.session_state.show_toast = f"✅ Ingreso directo: {int(cant)} {nombre_final}"
            st.rerun()
        else:
            st.warning("Agrega una cantidad mayor a 0.")

# ------------------ TRIGGER DEL POPUP DE INICIO ------------------
if "inicio_popup_mostrado" not in st.session_state:
    st.session_state.inicio_popup_mostrado = False

if not st.session_state.inicio_popup_mostrado:
    popup_inicio_captura(seleccion_wa)

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 Registro", "📦 Archivo", "🖼️ Reporte Visual"])

# ------------------------------------------------------------
# TAB 1: CONTEO
# ------------------------------------------------------------
with tab1:
    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state:
        st.session_state.buscar_prod = ""
    if "mic_key" not in st.session_state:
        st.session_state.mic_key = 0

    st.markdown(f"### 📍 Estás en la sucursal: **{seleccion_wa}**")

    st.markdown("🎤 **Ingreso por Voz**")
    
    texto_capturado = speech_to_text(
        language='es-MX',
        start_prompt="🎙️ Toca para Dictar",
        stop_prompt="🔴 Grabando...",
        use_container_width=True,
        key=f"stt_mic_{st.session_state.mic_key}"
    )

    if texto_capturado and texto_capturado != st.session_state.get("ultimo_audio_procesado"):
        st.session_state.ultimo_audio_procesado = texto_capturado
        prod, cant, fech = analizar_dictado(texto_capturado, fecha_hoy_mx)
        st.session_state.confirmacion_voz = {"prod": prod, "cant": cant, "fecha": fech, "original": texto_capturado}
        st.session_state.audio_leido = False  
        st.rerun()

    if st.session_state.get("confirmacion_voz"):
        popup_voz()
        
    st.divider()

    def on_buscar_prod_change():
        texto = st.session_state.buscar_prod.strip().upper()
        if texto:
            popup_manual(texto)

    st.text_input(
        "Añadir producto", 
        placeholder="🔎 AÑADIR PRODUCTO (Presiona Enter para agregar)...", 
        key="buscar_prod", 
        label_visibility="collapsed",
        on_change=on_buscar_prod_change
    )
    
    if st.session_state.get('enfocar_buscador', False):
        components.html(
            """
            <script>
            setTimeout(function() {
                const textInputs = window.parent.document.querySelectorAll('input[type="text"]');
                if (textInputs.length > 0) {
                    textInputs[0].focus();
                    window.parent.scrollTo(0,0);
                }
            }, 100);
            </script>
            """,
            height=0
        )
        st.session_state.enfocar_buscador = False

    st.divider()
    
    df_hoy_captura = conn.query("SELECT id, nombre, fecha_cad AS \"Fecha\", cantidad FROM captura_actual WHERE sucursal=:suc ORDER BY fecha_cad ASC", params={"suc": seleccion_wa}, ttl=0)
    
    if not df_hoy_captura.empty:
        with st.expander("📋 Productos registrados al momento", expanded=False):
            df_editado = st.data_editor(
                df_hoy_captura, 
                column_config={
                    "id": None,
                    "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY")
                }, 
                num_rows="dynamic", 
                height=300, 
                use_container_width=True, 
                hide_index=True, 
                key="editor_conteo"
            )
            
            if st.button("💾 Guardar Cambios", use_container_width=True):
                with conn.session as s:
                    s.execute(text("DELETE FROM captura_actual WHERE sucursal = :suc"), {"suc": seleccion_wa})
                    for _, fila in df_editado.iterrows():
                        if pd.notna(fila["nombre"]) and str(fila["nombre"]).strip() != "":
                            s.execute(text("INSERT INTO captura_actual (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fec, :can)"), 
                                      {"suc": seleccion_wa, "nom": str(fila["nombre"]).upper(), "fec": str(fila["Fecha"]), "can": int(fila["cantidad"])})
                    s.commit()
                st.session_state.show_toast = "✅ Cambios guardados."
                st.rerun()

# ------------------------------------------------------------
# TAB 2: INVENTARIO Y CORTE
# ------------------------------------------------------------
with tab2:
    st.markdown("### 📦 Gestión de Sugeridos")
    
    # NUEVO: Filtro MUY visible y forzado
    st.markdown("#### 🔍 Filtro de Búsqueda")
    col_filt_1, col_filt_2 = st.columns([1, 2])
    with col_filt_1:
        usar_filtro = st.checkbox("📅 Habilitar filtro por fecha", key="filtro_tab2")
    with col_filt_2:
        if usar_filtro:
            fecha_filtro_edit = st.date_input("Selecciona la fecha:", value=fecha_hoy_mx, format="DD/MM/YYYY", key="date_tab2")
            
    st.divider()
    
    query_str = 'SELECT id, nombre as "Producto", fecha_cad as "Fecha", cantidad as "Existencia" FROM base_anterior WHERE sucursal=:suc '
    params = {"suc": seleccion_wa}
    
    if usar_filtro:
        query_str += "AND fecha_cad = :fec_filtro "
        params["fec_filtro"] = str(fecha_filtro_edit)
        
    query_str += 'ORDER BY fecha_cad ASC'
    
    df_stock = conn.query(query_str, params=params, ttl=0)
    
    with st.expander(f"✏️ Editar Sugeridos de {seleccion_wa}", expanded=False):
        if df_stock.empty:
            st.info("No hay stock registrado para esta selección.")
        else:
            df_editado_stock = st.data_editor(
                df_stock, 
                column_config={
                    "id": None,
                    "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY")
                }, 
                num_rows="dynamic", 
                use_container_width=True, 
                hide_index=True, 
                key="editor_sugeridos"
            )
            
            if st.button("💾 Confirmar Cambios", use_container_width=True, type="primary"):
                with conn.session as s:
                    if usar_filtro:
                        s.execute(text("DELETE FROM base_anterior WHERE sucursal = :suc AND fecha_cad = :fec_filtro"), params)
                    else:
                        s.execute(text("DELETE FROM base_anterior WHERE sucursal = :suc"), {"suc": seleccion_wa})
                        
                    for _, fila in df_editado_stock.iterrows():
                        if pd.notna(fila["Producto"]) and str(fila["Producto"]).strip() != "":
                            s.execute(text("INSERT INTO base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fec, :can)"), 
                                      {
                                          "suc": seleccion_wa, 
                                          "nom": str(fila["Producto"]).upper(), 
                                          "fec": str(fila["Fecha"]), 
                                          "can": int(fila["Existencia"])
                                      })
                    s.commit()
                st.session_state.show_toast = "✅ Sugeridos actualizados correctamente."
                st.rerun()

    st.divider()
    
    st.markdown("### 📥 Descargar Excel Actualizado")
    
    df_stock_final = conn.query('SELECT nombre as "Producto", fecha_cad as "Fecha", cantidad as "Existencia" FROM base_anterior WHERE sucursal=:suc ORDER BY fecha_cad ASC', params={"suc": seleccion_wa}, ttl=0)
    
    if df_stock_final.empty:
        st.warning("No hay datos para generar el Excel.")
    else:
        msg_stock = f""
        link_st = f"https://wa.me/{numero_whatsapp.strip()}?text={urllib.parse.quote(msg_stock)}"
        
        excel_stock = generar_excel_formato(df_stock_final, sucursal=seleccion_wa, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V.")
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button(
                "📗 1. Descargar Excel", 
                data=excel_stock, 
                file_name=f"Sugeridos_{seleccion_wa}_{fecha_hoy_mx}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True
            )
        with col_down2:
            st.link_button("💬 2. Abrir WhatsApp", link_st, use_container_width=True, type="primary")

# ------------------------------------------------------------
# TAB 3: REPORTE VISUAL Y RECOMENDACIONES DE VENTA DINÁMICAS
# ------------------------------------------------------------
with tab3:
    st.markdown(f"### 🖼️ Estrategia y Tarjeta - {seleccion_wa}")
    
    col_filtro1, col_filtro2 = st.columns([1, 2])
    with col_filtro1:
        activar_filtro_visual = st.checkbox("📅 Filtrar Sugeridos por Fecha", key="check_filtro_visual")
        if activar_filtro_visual:
            fecha_filtro_visual = st.date_input("Selecciona fecha:", value=fecha_hoy_mx, format="DD/MM/YYYY", key="date_filtro_visual")
        else:
            fecha_filtro_visual = None
            
    df_visual_completo = conn.query('SELECT id, nombre as "Producto", fecha_cad as "Fecha", cantidad as "Existencia" FROM base_anterior WHERE sucursal=:suc AND cantidad > 0 ORDER BY fecha_cad ASC', params={"suc": seleccion_wa}, ttl=0)
    
    if df_visual_completo.empty:
        st.warning(f"No hay productos sugeridos disponibles para {seleccion_wa}.")
    else:
        # NUEVO: FORZAR ORDENAMIENTO CRONOLÓGICO DESDE PANDAS PARA GARANTIZAR EL ORDEN EN TARJETAS
        df_visual_completo['Fecha_orden'] = pd.to_datetime(df_visual_completo['Fecha'])
        df_visual_completo = df_visual_completo.sort_values(by='Fecha_orden', ascending=True).drop(columns=['Fecha_orden']).reset_index(drop=True)
        
        if activar_filtro_visual and fecha_filtro_visual:
            df_visual_completo['Fecha_obj'] = pd.to_datetime(df_visual_completo['Fecha']).dt.date
            df_visual = df_visual_completo[df_visual_completo['Fecha_obj'] == fecha_filtro_visual].drop(columns=['Fecha_obj'])
        else:
            df_visual = df_visual_completo.copy()
            
        if df_visual.empty:
            st.info("No hay productos sugeridos para la fecha seleccionada.")
        else:
            st.markdown("#### 🎯 Qué ofrecer al cliente")
            st.caption("Aprovecha estos productos de pronta caducidad. Las sugerencias cambian para mantener fresco el guion.")
            
            if st.button("🔄 Generar nuevas frases", use_container_width=True):
                st.rerun()
            
            df_urgentes = df_visual.head(6)
            
            cols = st.columns(3)
            
            for idx, (_, fila) in enumerate(df_urgentes.iterrows()):
                prod_nombre = str(fila['Producto']).upper()
                cant = fila['Existencia']
                prod_id = fila['id']
                
                fecha_str_db = str(fila['Fecha'])
                try:
                    if '-' in fecha_str_db:
                        partes = fecha_str_db.split('-')
                        y, m, d = int(partes[0]), int(partes[1]), int(partes[2])
                        fecha_item = datetime(y, m, d).date()
                        fecha_str = f"{d:02d}/{m:02d}/{y}"
                    else:
                        fecha_item = pd.to_datetime(fecha_str_db).date()
                        fecha_str = fecha_item.strftime("%d/%m/%Y")
                        
                    diferencia_dias = (fecha_item - fecha_hoy_mx).days
                except Exception:
                    diferencia_dias = 0
                    fecha_str = fecha_str_db
                
                if diferencia_dias <= 1:
                    color_borde = "#8C1C31" 
                    label_texto = "SUGERIDO"
                    badge_bg = "#FCE4D6"
                    badge_color = "#8C0000"
                elif diferencia_dias == 2:
                    color_borde = "#E67E22" 
                    label_texto = "PASADO MAÑANA"
                    badge_bg = "#FDEBD0"
                    badge_color = "#A04000"
                else:
                    color_borde = "#27AE60" 
                    label_texto = "EXTRA"
                    badge_bg = "#D5F5E3"
                    badge_color = "#145A32"

                if any(kw in prod_nombre for kw in ["PASTEL"]):
                    guion = random.choice([
                        "¿Ya tiene algo para acompañar el pastel? Podemos complementar con bocadillos o postres. ¿Le gustaría agregar alguno?",
                        "¿Ya tiene todo para la celebración? ¿Desea agregar algún complemento para el festejo?",
                        "¿Es para compartir? Si es para varias personas, puedo recomendarle también una opción de bocadillos para complementar.",
                        "Para acompañar el pastel, ¿prefiere llevar bocadillos o postres?",
                        "¿Ya tiene todo lo necesario para servir? ¿Necesita algún complemento para la celebración?"
                    ])
                elif "ROSCA" in prod_nombre:
                    guion = random.choice([
                        "¿Gusta llevar también bolsa de café o algún bocadillo para acompañar?",
                        "Podemos complementar la rosca con piezas individuales para que alcance mejor."
                    ])
                elif any(kw in prod_nombre for kw in ["PAY"]):
                    guion = random.choice([
                        "Pra compartir, ¿quiere llevar algunas piezas de bocadillos o pan?",
                        "Para acompañar el pay, ¿desea agregar alguna bolsa de café?",
                        "Podemos armar una combinación con diferentes piezas de bocadillos o pan, ¿gusta agregar alguno?"
                    ])
                else:
                    guion = random.choice([
                        "¿Desea complementar su compra con algo más?",
                        "Ya que lleva esto, ¿le gustaría agregar algo para acompañarlo?",
                        "Para que tenga todo completo, ¿necesita algún producto adicional?",
                        "Si es para compartir, podemos agregar algo más, ¿le gustaría?",
                        "¿Le agrego alguna bebida o bocadillo para acompañarlo?",
                        "Antes de cobrarle, ¿necesita alguna bebida o complemento?",
                        "Tenemos bocadillos que combinan muy bien con lo que lleva, ¿quiere agregar alguno?"
                    ])
                
                tarjeta_html = f"<div style='background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); border-left: 5px solid {color_borde}; border-radius: 10px; padding: 20px; width: 100%; box-sizing: border-box; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: left; margin-bottom: 5px;'><p style='margin: 0; color: {color_borde}; font-weight: 900; font-size: 14px; letter-spacing: 1px;'>{label_texto}</p><h3 style='margin: 5px 0 5px 0; font-size: 18px; color: #333;'>{prod_nombre}</h3><p style='margin: 0 0 10px 0; color: {color_borde}; font-weight: bold; font-size: 13px;'>📅 Fecha: {fecha_str}</p><div style='display: flex; align-items: center; margin-bottom: 15px;'><span style='background-color: {badge_bg}; color: {badge_color}; padding: 5px 10px; border-radius: 5px; font-weight: bold; font-size: 14px;'>📦 Quedan: {cant}</span></div><p style='margin: 0; font-size: 12px; color: #666; font-weight: bold;'>🗣️ DILE AL CLIENTE:</p><p style='margin: 5px 0 0 0; font-size: 14px; font-style: italic; color: #444;'>\" {guion} \"</p></div>"
                
                with cols[idx % 3]:
                    st.markdown(tarjeta_html, unsafe_allow_html=True)
                    st.button("✅ Vendido (-1)", key=f"btn_vender_{prod_id}_{cant}", use_container_width=True, on_click=marcar_vendido, args=(prod_id, prod_nombre))
            
            st.divider()

            with st.expander("👀 Ver y Enviar Tarjeta para WhatsApp", expanded=False):
                st.caption("Aquí está la tarjeta lista para compartir por WhatsApp.")
                
                filas_html = ""
                for i, fila in df_visual.iterrows():
                    color_fondo = "#FFFFFF" if i % 2 == 0 else "#FFF5F5"
                    
                    fecha_str_tarjeta = str(fila['Fecha'])
                    try:
                        if '-' in fecha_str_tarjeta:
                            partes = fecha_str_tarjeta.split('-')
                            if len(partes) == 3:
                                fecha_str_tarjeta = f"{partes[2]}/{partes[1]}/{partes[0]}"
                    except:
                        pass

                    filas_html += f"<tr style='background-color: {color_fondo}; border-bottom: 1px solid #f0f0f0;'><td style='padding: 10px; text-align: left; color: #333; font-size: 13px;'>{fila['Producto']}</td><td style='padding: 10px; text-align: center; color: #8C1C31; font-weight: bold; font-size: 14px;'>{fila['Existencia']}</td><td style='padding: 10px; text-align: center; color: #555; font-size: 13px;'>{fecha_str_tarjeta}</td></tr>"
                    
                fecha_hora_actual = datetime.now(zona_mx).strftime("%d/%m/%Y %H:%M")
                
                tarjeta_html_general = f"<div style='background-color: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); width: 100%; max-width: 500px; margin: auto; text-align: center; margin-bottom: 20px;'><h1 style='color: #6D1427; font-family: \"Times New Roman\", serif; font-size: 38px; margin: 0;'>Champlitte</h1><p style='font-family: sans-serif; font-size: 10px; font-weight: bold; letter-spacing: 3px; margin: 0 0 20px 0; color: #000;'>PASTELERÍA</p><h2 style='color: #6D1427; font-family: sans-serif; font-weight: 900; margin: 0; font-size: 22px;'>SUGERIDOS {seleccion_wa.upper()}</h2><p style='font-family: sans-serif; font-size: 12px; font-weight: bold; color: #666; margin: 5px 0 20px 0;'>{fecha_hora_actual}</p><table style='width: 100%; border-collapse: collapse; font-family: sans-serif;'><thead><tr style='background-color: #8C1C31; color: white;'><th style='padding: 12px; text-align: left; font-size: 11px; letter-spacing: 1px;'>PRODUCTO</th><th style='padding: 12px; text-align: center; font-size: 11px; letter-spacing: 1px;'>CANTIDAD</th><th style='padding: 12px; text-align: center; font-size: 11px; letter-spacing: 1px;'>FECHA</th></tr></thead><tbody>{filas_html}</tbody></table></div><p style='text-align: center; color: gray; font-size: 13px; margin-top: 15px; margin-bottom: 20px;'>Reporte generado automáticamente</p>"
                
                st.markdown(tarjeta_html_general, unsafe_allow_html=True)
                
                link_wp = f"https://wa.me/{numero_whatsapp.strip()}"
                boton_wp_html = f"<a href='{link_wp}' target='_blank' style='display: block; width: 100%; max-width: 500px; margin: auto; background-color: #25D366; color: white; text-align: center; padding: 15px; border-radius: 10px; font-size: 18px; font-weight: bold; text-decoration: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: background-color 0.3s;'>📞 Enviar Reporte a {seleccion_wa.upper()}</a><br><br>"
                st.markdown(boton_wp_html, unsafe_allow_html=True)
