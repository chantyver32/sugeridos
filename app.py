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

# ------------------ CONFIGURACIÓN GENERAL ------------------
with st.spinner('Iniciando sistema Champlitte... 🥐'):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy_mx = datetime.now(zona_mx).date()
    
    st.set_page_config(page_title="Sugeridos", page_icon="🥐", layout="wide")

# CSS personalizado (Se eliminó el truco del audio nativo para evitar conflictos)
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
        padding: 15px 20px;
        text-align: center;
        text-decoration: none !important;
        display: block;
        font-size: 16px;
        font-weight: bold;
        border-radius: 8px;
        margin: 10px auto;
        max-width: 600px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .btn-wa:hover { background-color: #128C7E; color: white !important;}
    
    /* ESTILOS DE SELECTORES OSCUROS */
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

# ------------------ FUNCIONES ------------------
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

def generar_excel_formato(df, sucursal, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V.", elabora="PEDRO GARCÍA"):
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
    
    sheet.write('A4', 'FECHA', fmt_etiqueta)
    fecha_str = datetime.now(pytz.timezone('America/Mexico_City')).strftime("%d/%m/%Y")
    sheet.merge_range('B4:D4', fecha_str, fmt_valor)
    
    sheet.write('A5', 'ELABORA', fmt_etiqueta)
    sheet.merge_range('B5:D5', elabora, fmt_valor)

    sheet.write('A6', '', fmt_valor)
    sheet.write('B6', 'DESCRIPCIÓN', fmt_header_tabla)
    sheet.write('C6', 'CANTIDAD', fmt_header_tabla)
    sheet.write('D6', 'FECHA', fmt_header_tabla)

    row = 6
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

    last_row = row - 1 if row > 6 else 6
    sheet.autofilter(5, 1, last_row, 3)

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
    "URANO": "522281342454", "COSTA DE ORO": "522292780850", "COSTA VERDE": "522299359597",
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
st.sidebar.info(f"Guarda o restaura tu stock para {seleccion_wa}.")
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
    st.session_state.ultimo_audio_procesado = None # Reseteamos para que pueda dictar lo mismo de nuevo si quiere
    st.session_state.audio_leido = False
    st.session_state.buscar_prod = ""
    st.session_state.show_toast = f"✅ Ingreso directo: {int(cant)} {prod}"

# ------------------------------------------------------------
# POP-UPS (st.dialog)
# ------------------------------------------------------------
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
    
    col1, col2 = st.columns(2)
    with col1:
        st.button("🥖 Ingresar", use_container_width=True, type="primary", on_click=guardar_datos_voz, args=(seleccion_wa,))
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.confirmacion_voz = None
            st.session_state.ultimo_audio_procesado = None # Para que pueda reintentar
            st.session_state.audio_leido = False
            st.rerun()

@st.dialog("✏️ Registrar Manualmente")
def popup_manual(nombre_final):
    st.markdown(f"### 📦 Producto: {nombre_final}")
    
    cant = st.number_input("Cantidad", min_value=1, step=1, key="man_cant")
    fech = st.date_input("Fecha", value=fecha_hoy_mx, key="man_fech")
    
    if st.button("Guardar", type="primary", use_container_width=True):
        with conn.session as s:
            existe = s.execute(text("SELECT cantidad FROM base_anterior WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                                     {"nom": nombre_final, "fec": str(fech), "suc": seleccion_wa}).fetchone()
            if existe:
                s.execute(text("UPDATE base_anterior SET cantidad=cantidad+:can WHERE nombre=:nom AND fecha_cad=:fec AND sucursal=:suc"), 
                          {"can": cant, "nom": nombre_final, "fec": str(fech), "suc": seleccion_wa})
            else:
                s.execute(text("INSERT INTO base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fec, :can)"), 
                          {"suc": seleccion_wa, "nom": nombre_final, "fec": str(fech), "can": cant})
            s.commit()
            
        st.session_state.show_toast = f"✅ Guardado: {cant} de {nombre_final}"
        st.rerun()

# ------------------------------------------------------------
# INTERFAZ PRINCIPAL Y BOTÓN DE VOZ CORREGIDO
# ------------------------------------------------------------
st.header(f"Gestión de Inventario - {seleccion_wa}")

# 1. Componente del botón (sin just_once para que no se bloquee)
texto_capturado = speech_to_text(
    language='es-MX',
    start_prompt="🎙️ Toca para Dictar",
    stop_prompt="🔴 Grabando...",
    use_container_width=True,
    key='stt_mic_unico'
)

# 2. Candado de ejecución: Verifica que haya texto y que sea diferente a la última corrida
if texto_capturado and texto_capturado != st.session_state.get("ultimo_audio_procesado"):
    
    st.session_state.ultimo_audio_procesado = texto_capturado
    
    prod, cant, fec = analizar_dictado(texto_capturado, fecha_hoy_mx)
    st.session_state.confirmacion_voz = {
        'original': texto_capturado,
        'prod': prod,
        'cant': cant,
        'fecha': fec
    }
    
    # Recarga manual obligatoria para que el script abra el popup
    st.rerun()

# 3. Disparar Pop-up si hay datos confirmados en memoria
if st.session_state.get("confirmacion_voz"):
    popup_voz()

