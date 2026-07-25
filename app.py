import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, timedelta
import pytz
import urllib.parse
import time
import io
import re
import streamlit.components.v1 as components

# ------------------ CONFIGURACIÓN GENERAL ------------------
with st.spinner('Iniciando sistema Champlitte... 🥐'):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy_mx = datetime.now(zona_mx).date()
    
    st.set_page_config(page_title="Sugeridos Champlitte", page_icon="🥐", layout="wide")

# ------------------ CONEXIÓN A SUPABASE ------------------
conn = st.connection("supabase", type="sql")

# Inicialización de tablas con columna "sucursal"
with conn.session as s:
    s.execute(text('''CREATE TABLE IF NOT EXISTS sug_captura_actual 
                 (id SERIAL PRIMARY KEY, sucursal TEXT, nombre TEXT, fecha_cad DATE, cantidad INTEGER)'''))
                 
    s.execute(text('''CREATE TABLE IF NOT EXISTS sug_base_anterior 
                 (id SERIAL PRIMARY KEY, sucursal TEXT, nombre TEXT, fecha_cad DATE, cantidad INTEGER)'''))
                 
    s.execute(text('''CREATE TABLE IF NOT EXISTS sug_historial_ventas 
                 (id SERIAL PRIMARY KEY, sucursal TEXT, nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte TIMESTAMP)'''))
    s.commit()

# ------------------ FUNCIONES ------------------
def sonido_click():
    st.markdown(
        """<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg"></audio>""",
        unsafe_allow_html=True
    )

def sumar(valor):
    st.session_state.conteo_temp += valor
    sonido_click()

def resetear():
    st.session_state.conteo_temp = 0
    sonido_click()

def generar_excel_formato(df, sucursal, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V.", elabora="PEDRO ANTONIO GARCÍA TRUJILLO"):
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
    sheet.write('D6', 'FECHA DE CADUCIDAD', fmt_header_tabla)

    row = 6
    if not df.empty:
        col_nombre = 'Producto' if 'Producto' in df.columns else 'nombre'
        col_cant = 'Existencia' if 'Existencia' in df.columns else 'cantidad'
        col_fecha = 'Caducidad' if 'Caducidad' in df.columns else 'fecha_cad'

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

# ------------------ SIDEBAR & SUCURSALES ------------------
st.sidebar.header("⚙️ Configuración")

datos_sucursales = {
        "URANO": "522299272100",
        "COSTA DE ORO": "522299272100",
        "COSTA VERDE": "522299359597",
        "DÍAZ MIRÓN": "522291302759",
        "EJÉRCITO MEXICANO": "522299272107",
        "PLAZA RÍO": "522299864120",
        "PLAYAS DEL CONCHAL": "522291794020",
        "COYOL": "522299398334",
        "LA PLACITA": "522299208481",
        "CUAUHTÉMOC": "522291651340",
        "MARIO MOLINA": "522291780851",
        "RAFAEL CUERVO": "522291980229",
        "RÍO MEDIO": "522291005852",
        "DIVERPLAZA": "522293763180",
        "BOLÍVAR": "522291002947",
        "CIRCUNVALACIÓN": "522299393726",
        "J.B. LOBOS": "522299201956",
        "YÁÑEZ": "522293764940",
        "PALACIO DE HIERRO": "522299272100",
        "CIUDAD INDUSTRIAL": "522299200278",
        "DONATO CASAS": "522291653833",
        "LAS VEGAS": "522291932980",
        "PUENTE MORENO": "522296893999",
        "CONDESA": "522299863464",
        "MURILLO VIDAL": "522286886443",
        "ARAUCARIAS": "522281177133",
        "ÁVILA CAMACHO": "522288170989",
        "EMILIANO ZAPATA": "522969628525"
}

sucursal_in = st.sidebar.selectbox("📍 Selecciona tu sucursal:", list(datos_sucursales.keys()))
numero_wa = datos_sucursales[sucursal_in]
st.sidebar.caption(f"📱 WhatsApp enlazado: **{numero_wa}**")

st.sidebar.divider()

st.sidebar.subheader("💾 Respaldo de Base de Datos")
st.sidebar.info(f"Guarda o restaura el stock específicamente para {sucursal_in}.")
archivo_csv = st.sidebar.file_uploader("⬆️ Subir Respaldo CSV", type=["csv"])

if archivo_csv is not None:
    if st.sidebar.button("🔄 Restaurar Stock", use_container_width=True):
        try:
            df_restaurar = pd.read_csv(archivo_csv)
            if 'Producto' in df_restaurar.columns:
                df_restaurar = df_restaurar.rename(columns={'Producto': 'nombre', 'Caducidad': 'fecha_cad', 'Existencia': 'cantidad'})
            
            with conn.session as s:
                s.execute(text("DELETE FROM sug_base_anterior WHERE sucursal = :suc"), {"suc": sucursal_in})
                for _, fila in df_restaurar.iterrows():
                    s.execute(text("INSERT INTO sug_base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fc, :cant)"), 
                              {"suc": sucursal_in, "nom": str(fila['nombre']).upper(), "fc": str(fila['fecha_cad']), "cant": int(fila['cantidad'])})
                s.commit()
            
            st.sidebar.success(f"✅ Inventario restaurado para {sucursal_in}")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"⚠️ Error al restaurar: {e}")

st.sidebar.divider()

# --- ZONA DE PELIGRO ACTUALIZADA (GLOBAL Y CON DISEÑO EXACTO) ---
with st.sidebar.expander("🚨 Zona de Peligro (Formatear Nube)", expanded=False):
    st.warning("⚠️ ESTE BOTÓN BORRA TODAS LAS TABLAS PARA ACTUALIZAR LA ESTRUCTURA.")
    confirmar_borrado = st.checkbox("Confirmar el formateo total")
    if st.button("⚠️ EJECUTAR REINICIO Y ACTUALIZACIÓN", use_container_width=True):
        if not confirmar_borrado:
            st.error("Debes confirmar primero")
        else:
            with conn.session as s:
                # Este comando formatea por completo las tres tablas de los Sugeridos
                s.execute(text("DROP TABLE IF EXISTS sug_captura_actual, sug_base_anterior, sug_historial_ventas CASCADE"))
                s.commit()
            st.success("✅ Base de datos formateada. Reiniciando para aplicar nueva estructura...")
            time.sleep(2)
            st.rerun()
# ----------------------------------------------------------------

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 Conteo", "📦 Inventario y Corte", "📊 Análisis"])

# ------------------------------------------------------------
# TAB 1: CONTEO
# ------------------------------------------------------------
with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state: st.session_state.buscar_prod = ""

    def limpiar_buscador():
        st.session_state.buscar_prod = ""
        if "sel_prod" in st.session_state: del st.session_state["sel_prod"]

    buscar = st.text_input("Buscar", placeholder="🔎 BUSCAR PRODUCTO...", key="buscar_prod", label_visibility="collapsed").upper()
    st.button("🧹 Limpiar Búsqueda", on_click=limpiar_buscador, use_container_width=True)

    with st.expander("🎤 **Ingreso por Voz** (Clic para desplegar)", expanded=False):
        audio_val = st.audio_input("Di algo como: 3 brownies para el 15 de octubre.")
        if audio_val is not None:
            audio_bytes = audio_val.getvalue()
            if st.session_state.get("ultimo_audio") != audio_bytes:
                st.session_state.ultimo_audio = audio_bytes
                try:
                    import speech_recognition as sr
                    r = sr.Recognizer()
                    with sr.AudioFile(audio_val) as source:
                        audio_data = r.record(source)
                        texto_voz = r.recognize_google(audio_data, language="es-MX")
                        if texto_voz:
                            prod, cant, fech = analizar_dictado(texto_voz, fecha_hoy_mx)
                            st.session_state.confirmacion_voz = {"prod": prod, "cant": cant, "fecha": fech, "original": texto_voz}
                            st.session_state.audio_leido = False  
                            st.rerun()
                except Exception as e:
                    st.toast("❌ No pude entender el audio o hubo mucho ruido.")

    if st.session_state.get("confirmacion_voz"):
        datos = st.session_state.confirmacion_voz
        if not st.session_state.get("audio_leido", False):
            js_tts = f"""<script>
                const utterance = new SpeechSynthesisUtterance("{datos['original']}");
                utterance.lang = 'es-MX'; window.speechSynthesis.speak(utterance);
            </script>"""
            components.html(js_tts, height=0)
            st.session_state.audio_leido = True
            
        st.success(f"🗣️ **Confirmado:** '{datos['original']}'")
        edit_cant = st.number_input("Cantidad", value=int(datos['cant']), min_value=1)
        edit_prod = st.text_input("Producto", value=datos['prod']).upper()
        edit_fech = st.date_input("Caducidad", value=datos['fecha'])
        
        col_voz_1, col_voz_2 = st.columns(2)
        with col_voz_1:
            if st.button("📝 Guardar en Conteo", use_container_width=True, type="primary"):
                if edit_prod.strip():
                    with conn.session as s:
                        existe = conn.query("SELECT cantidad FROM sug_captura_actual WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc", 
                                            params={"suc": sucursal_in, "nom": edit_prod.strip(), "fc": str(edit_fech)}, ttl=0)
                        if not existe.empty:
                            s.execute(text("UPDATE sug_captura_actual SET cantidad=cantidad+:c WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc"), 
                                      {"c": int(edit_cant), "suc": sucursal_in, "nom": edit_prod.strip(), "fc": str(edit_fech)})
                        else:
                            s.execute(text("INSERT INTO sug_captura_actual (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fc, :c)"), 
                                      {"suc": sucursal_in, "nom": edit_prod.strip(), "fc": str(edit_fech), "c": int(edit_cant)})
                        s.commit()
                    st.success(f"✅ Añadido a Conteo.")
                    st.session_state.confirmacion_voz = None
                    time.sleep(1)
                    st.rerun()
                    
        with col_voz_2:
            if st.button("🥖 Ingresar al Stock Directo", use_container_width=True):
                if edit_prod.strip():
                    with conn.session as s:
                        existe = conn.query("SELECT cantidad FROM sug_base_anterior WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc", 
                                            params={"suc": sucursal_in, "nom": edit_prod.strip(), "fc": str(edit_fech)}, ttl=0)
                        if not existe.empty:
                            s.execute(text("UPDATE sug_base_anterior SET cantidad=cantidad+:c WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc"), 
                                      {"c": int(edit_cant), "suc": sucursal_in, "nom": edit_prod.strip(), "fc": str(edit_fech)})
                        else:
                            s.execute(text("INSERT INTO sug_base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fc, :c)"), 
                                      {"suc": sucursal_in, "nom": edit_prod.strip(), "fc": str(edit_fech), "c": int(edit_cant)})
                        s.commit()
                    st.success(f"✅ Sumado al inventario activo.")
                    st.session_state.confirmacion_voz = None
                    time.sleep(1)
                    st.rerun()

        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.confirmacion_voz = None
            st.rerun()
        st.divider()

    df_nombres = conn.query("SELECT nombre FROM sug_base_anterior WHERE sucursal=:suc UNION SELECT nombre FROM sug_captura_actual WHERE sucursal=:suc", params={"suc": sucursal_in}, ttl=0)
    nombres_prev = df_nombres['nombre'].tolist() if not df_nombres.empty else []
    
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev
    nombre_input = st.selectbox("Seleccionar producto", sugerencias, key="sel_prod") if sugerencias else buscar
    
    fecha_sugerido = fecha_hoy_mx + timedelta(days=1)
    fecha_dia_mas = fecha_hoy_mx + timedelta(days=2)
    
    opcion_fecha = st.radio("📅 Fecha de Caducidad:", options=["Sugerido (Mañana)", "Día Más (Pasado Mañana)"], horizontal=True)
    f_cad = fecha_sugerido if opcion_fecha == "Sugerido (Mañana)" else fecha_dia_mas

    col_sum1, col_sum2, col_sum3 = st.columns(3)
    with col_sum1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with col_sum2: st.button("+2", use_container_width=True, on_click=sumar, args=(2,))
    with col_sum3: st.button("Borrar", use_container_width=True, on_click=resetear)

    st.metric("Total a registrar", st.session_state.conteo_temp)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Registrar en Conteo", use_container_width=True, type="primary"):
            if nombre_input and st.session_state.conteo_temp > 0:
                with conn.session as s:
                    existe = conn.query("SELECT cantidad FROM sug_captura_actual WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc", 
                                        params={"suc": sucursal_in, "nom": nombre_input.strip().upper(), "fc": str(f_cad)}, ttl=0)
                    if not existe.empty:
                        s.execute(text("UPDATE sug_captura_actual SET cantidad=cantidad+:c WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc"), 
                                  {"c": st.session_state.conteo_temp, "suc": sucursal_in, "nom": nombre_input.strip().upper(), "fc": str(f_cad)})
                    else:
                        s.execute(text("INSERT INTO sug_captura_actual (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fc, :c)"), 
                                  {"suc": sucursal_in, "nom": nombre_input.strip().upper(), "fc": str(f_cad), "c": st.session_state.conteo_temp})
                    s.commit()
                st.session_state.conteo_temp = 0
                st.success(f"✅ Registrado para {sucursal_in}.")
                time.sleep(1)
                st.rerun()

    with col2:
        if st.button("🥖 Sumar al Stock Actual", use_container_width=True):
            if nombre_input and st.session_state.conteo_temp > 0:
                with conn.session as s:
                    existe = conn.query("SELECT cantidad FROM sug_base_anterior WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc", 
                                        params={"suc": sucursal_in, "nom": nombre_input.strip().upper(), "fc": str(f_cad)}, ttl=0)
                    if not existe.empty:
                        s.execute(text("UPDATE sug_base_anterior SET cantidad=cantidad+:c WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc"), 
                                  {"c": st.session_state.conteo_temp, "suc": sucursal_in, "nom": nombre_input.strip().upper(), "fc": str(f_cad)})
                    else:
                        s.execute(text("INSERT INTO sug_base_anterior (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fc, :c)"), 
                                  {"suc": sucursal_in, "nom": nombre_input.strip().upper(), "fc": str(f_cad), "c": st.session_state.conteo_temp})
                    s.commit()
                st.session_state.conteo_temp = 0
                st.success("✅ Sumado al inventario activo.")
                time.sleep(1)
                st.rerun()

    st.divider()
    st.subheader(f"🛒 Captura Actual de {sucursal_in}")
    df_hoy_captura = conn.query("SELECT id, nombre, fecha_cad, cantidad FROM sug_captura_actual WHERE sucursal=:suc", params={"suc": sucursal_in}, ttl=0)
    df_editado = st.data_editor(df_hoy_captura, column_config={"id": None}, num_rows="dynamic", use_container_width=True, hide_index=True, key="editor_conteo")

    if st.button("💾 Guardar Cambios en Tabla", use_container_width=True):
        with conn.session as s:
            s.execute(text("DELETE FROM sug_captura_actual WHERE sucursal = :suc"), {"suc": sucursal_in})
            for _, fila in df_editado.iterrows():
                if pd.notna(fila["nombre"]) and str(fila["nombre"]).strip() != "":
                    s.execute(text("INSERT INTO sug_captura_actual (sucursal, nombre, fecha_cad, cantidad) VALUES (:suc, :nom, :fc, :c)"), 
                              {"suc": sucursal_in, "nom": str(fila["nombre"]).upper(), "fc": str(fila["fecha_cad"]), "c": int(fila["cantidad"])})
            s.commit()
        st.success("✅ Tabla guardada.")
        time.sleep(1)

# ------------------------------------------------------------
# TAB 2: INVENTARIO Y CORTE
# ------------------------------------------------------------
with tab2:
    st.header(f"📦 Stock en {sucursal_in}")
    df_stock = conn.query("SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Existencia FROM sug_base_anterior WHERE sucursal=:suc", params={"suc": sucursal_in}, ttl=0)
    
    if df_stock.empty:
        st.info("No hay stock registrado para esta sucursal.")
    else:
        fechas_stock = sorted(df_stock['Caducidad'].unique())
        filtro_st_fecha = st.multiselect("Filtrar stock por Caducidad:", fechas_stock, default=fechas_stock)
        df_stock_filt = df_stock[df_stock['Caducidad'].isin(filtro_st_fecha)]
        st.dataframe(df_stock_filt, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📥 Exportar Reportes")
        elabora_input = st.text_input("👨‍🍳 Elaborado por:", value="PEDRO ANTONIO GARCÍA TRUJILLO").upper()
        msg_stock = f"🍞 *SUGERIDOS - CHAMPLITTE ({sucursal_in})*\n\nAdjunto archivo de Excel.\n\n"
        link_st = f"https://wa.me/{numero_wa}?text={urllib.parse.quote(msg_stock)}"
        excel_stock = generar_excel_formato(df_stock_filt, sucursal=sucursal_in, elabora=elabora_input)
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button("📗 Descargar Excel", data=excel_stock, file_name=f"Sugeridos_{sucursal_in.replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_down2:
            st.link_button("💬 Abrir WhatsApp", link_st, use_container_width=True, type="primary")

    st.divider()
    st.header("🚀 Realizar Corte de Ventas")
    if st.button("PROCESAR CORTE AHORA", type="primary", use_container_width=True):
        df_actualizado = conn.query("SELECT * FROM sug_captura_actual WHERE sucursal=:suc", params={"suc": sucursal_in}, ttl=0)
        
        if df_actualizado.empty:
            st.warning("⚠️ No hay datos capturados para comparar.")
        else:
            df_anterior = conn.query("SELECT * FROM sug_base_anterior WHERE sucursal=:suc", params={"suc": sucursal_in}, ttl=0)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            
            with conn.session as s:
                if not df_anterior.empty:
                    for _, fila_ant in df_anterior.iterrows():
                        res_hoy = conn.query("SELECT cantidad FROM sug_captura_actual WHERE sucursal=:suc AND nombre=:nom AND fecha_cad=:fc", 
                                             params={"suc": sucursal_in, "nom": fila_ant['nombre'], "fc": fila_ant['fecha_cad']}, ttl=0)
                        cant_hoy = res_hoy.iloc[0]['cantidad'] if not res_hoy.empty else 0
                        diferencia = fila_ant['cantidad'] - cant_hoy
                        
                        if diferencia > 0:
                            s.execute(text("INSERT INTO sug_historial_ventas (sucursal, nombre, fecha_cad, habia, quedan, vendidos, fecha_corte) VALUES (:suc, :nom, :fc, :hab, :qued, :vend, :fcor)"), 
                                      {"suc": sucursal_in, "nom": fila_ant['nombre'], "fc": str(fila_ant['fecha_cad']), "hab": int(fila_ant['cantidad']), "qued": int(cant_hoy), "vend": int(diferencia), "fcor": ts_mx})
                
                s.execute(text("DELETE FROM sug_base_anterior WHERE sucursal = :suc"), {"suc": sucursal_in})
                s.execute(text("INSERT INTO sug_base_anterior (sucursal, nombre, fecha_cad, cantidad) SELECT sucursal, nombre, fecha_cad, cantidad FROM sug_captura_actual WHERE sucursal = :suc"), {"suc": sucursal_in})
                s.execute(text("DELETE FROM sug_captura_actual WHERE sucursal = :suc"), {"suc": sucursal_in})
                s.commit()
                
            st.balloons()
            st.success("✅ ¡Corte procesado con éxito!")
            time.sleep(2)
            st.rerun()

# ------------------------------------------------------------
# TAB 3: ANÁLISIS
# ------------------------------------------------------------
with tab3:
    df_hist = conn.query("SELECT nombre as Producto, vendidos as Vendidos, fecha_corte as Fecha, fecha_cad as Caducidad FROM sug_historial_ventas WHERE sucursal=:suc", params={"suc": sucursal_in}, ttl=0)
    
    if df_hist.empty:
        st.info("Aún no hay historial de ventas en esta sucursal.")
    else:
        df_hist['Fecha'] = pd.to_datetime(df_hist['Fecha']).dt.date
        buscar_h = st.text_input("Buscar producto en historial").upper()
        fecha_filtro = st.date_input("Filtrar por día de corte", value=None)
            
        if buscar_h: df_hist = df_hist[df_hist["Producto"].str.contains(buscar_h, na=False)]
        if fecha_filtro: df_hist = df_hist[df_hist["Fecha"] == fecha_filtro]
            
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        st.divider()
        
        ventas_dia = df_hist.groupby("Fecha")["Vendidos"].sum().reset_index()
        st.line_chart(ventas_dia, x="Fecha", y="Vendidos")
        top = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False)
        
        if not top.empty:
            st.subheader("🏆 Producto Estrella")
            st.metric(top.index[0], f"{int(top.iloc[0])} vendidos")
            st.bar_chart(top)
