import streamlit as st
import pandas as pd
import sqlite3
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
    
    st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Contenedores para mensajes
msg_conteo = st.empty()
msg_tabla = st.empty()
msg_corte = st.empty()

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME 
)''')
c.execute("CREATE INDEX IF NOT EXISTS idx_nombre1 ON captura_actual(nombre)")
c.execute("CREATE INDEX IF NOT EXISTS idx_nombre2 ON base_anterior(nombre)")
conn.commit()

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

def generar_excel_formato(df, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V."):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    sheet = workbook.add_worksheet('SUGERIDOS')

    sheet.hide_gridlines(2)

    color_guinda = '#8C0000'
    
    fmt_titulo = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': color_guinda, 'align': 'center', 'valign': 'vcenter', 'font_size': 14, 'border': 1})
    fmt_subtitulo = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 11})
    fmt_etiqueta = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})
    fmt_valor = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})
    fmt_header_tabla = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})
    fmt_datos_centro = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10})

    sheet.set_column('A:A', 15)  
    sheet.set_column('B:B', 35)  
    sheet.set_column('C:C', 12)  
    sheet.set_column('D:D', 22)  
    sheet.set_column('E:E', 20)  

    sheet.set_row(0, 30)
    sheet.merge_range('A1:E1', titulo, fmt_titulo)
    sheet.merge_range('A2:E2', 'SUGERIDOS DEL DÍA', fmt_subtitulo)

    sheet.write('A3', 'SUCURSAL', fmt_etiqueta)
    sheet.merge_range('B3:E3', 'COSTA VERDE', fmt_valor)
    
    sheet.write('A4', 'FECHA', fmt_etiqueta)
    fecha_str = datetime.now(pytz.timezone('America/Mexico_City')).strftime("%d/%m/%Y")
    sheet.merge_range('B4:E4', fecha_str, fmt_valor)
    
    sheet.write('A5', 'ELABORA', fmt_etiqueta)
    sheet.merge_range('B5:E5', 'PEDRO GARCÍA', fmt_valor)

    sheet.write('A6', '', fmt_valor)
    sheet.write('B6', 'DESCRIPCIÓN', fmt_header_tabla)
    sheet.write('C6', 'CANTIDAD', fmt_header_tabla)
    sheet.write('D6', 'FECHA DE CADUCIDAD', fmt_header_tabla)
    sheet.write('E6', 'VENDEDOR', fmt_header_tabla)

    row = 6
    if not df.empty:
        col_nombre = 'Producto' if 'Producto' in df.columns else 'nombre'
        col_cant = 'Existencia' if 'Existencia' in df.columns else 'cantidad'
        col_fecha = 'Caducidad' if 'Caducidad' in df.columns else 'fecha_cad'

        for _, fila in df.iterrows():
            sheet.write(row, 0, '', fmt_valor) 
            sheet.write(row, 1, str(fila[col_nombre]), fmt_datos_centro) 
            sheet.write(row, 2, fila[col_cant], fmt_datos_centro)
            sheet.write(row, 3, str(fila[col_fecha]), fmt_datos_centro)
            sheet.write(row, 4, 'PEDRO GARCÍA', fmt_datos_centro) 
            row += 1

    last_row = row - 1 if row > 6 else 6
    sheet.autofilter(5, 1, last_row, 4)

    writer.close()
    return output.getvalue()

def analizar_dictado(texto, fecha_base):
    texto = texto.lower()
    
    nums = {"un": "1", "uno": "1", "una": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5"}
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
    elif "mañana" in texto:
        fecha_calc = fecha_base + timedelta(days=1)
        texto = texto.replace("mañana", "")
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
st.sidebar.header("⚙️ Configuración")

# Opción 1: Lista desplegable para números de WhatsApp
opciones_wa = {
    "Contacto Principal": "522283530069",
    "Contacto Secundario": "522299359597", # Cambia por el número real
    "Contacto 3": "520987654321"           # Cambia por el número real
}
seleccion_wa = st.sidebar.selectbox("📱 Selecciona el WhatsApp destino", list(opciones_wa.keys()))
numero_whatsapp = opciones_wa[seleccion_wa]

st.sidebar.divider()

# Opción 2: Espacio para adjuntar CSV y restaurar el inventario (MODIFICADO AQUÍ)
st.sidebar.subheader("💾 Respaldo de Base de Datos")
st.sidebar.info("Guarda o restaura tu stock (bóveda) mediante un archivo CSV para mantenerlo fijo y no perderlo.")
archivo_csv = st.sidebar.file_uploader("⬆️ Subir Respaldo CSV", type=["csv"])

if archivo_csv is not None:
    if st.sidebar.button("🔄 Cargar y Restaurar Stock", use_container_width=True):
        try:
            # Leer el CSV
            df_restaurar = pd.read_csv(archivo_csv)
            
            # Ajustar nombres de columnas si vienen del formato de exportación
            if 'Producto' in df_restaurar.columns:
                df_restaurar = df_restaurar.rename(columns={'Producto': 'nombre', 'Caducidad': 'fecha_cad', 'Existencia': 'cantidad'})
            
            # Limpiar la tabla de base_anterior e insertar la nueva data
            c.execute("DELETE FROM base_anterior")
            for _, fila in df_restaurar.iterrows():
                c.execute("INSERT INTO base_anterior (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)", 
                          (str(fila['nombre']).upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
            conn.commit()
            
            st.sidebar.success("✅ Inventario restaurado correctamente")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"⚠️ Error al restaurar: {e}")

st.sidebar.divider()

with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar que deseo borrar todo", key="check_reset")
    if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.sidebar.success("✅ Base de datos limpiada por completo")
            time.sleep(1)
            st.rerun()
        else:
            st.sidebar.error("Debes confirmar primero")

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 Conteo", "📦 Inventario y Corte", "📊 Análisis"])

# ------------------------------------------------------------
# TAB 1: CONTEO
# ------------------------------------------------------------
with tab1:
    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state:
        st.session_state.buscar_prod = ""

    def limpiar_buscador():
        st.session_state.buscar_prod = ""
        if "sel_prod" in st.session_state:
            del st.session_state["sel_prod"]

    # Buscador
    buscar = st.text_input("Buscar", placeholder="🔎 BUSCAR PRODUCTO...", key="buscar_prod", label_visibility="collapsed").upper()
    st.button("🧹 Limpiar Búsqueda", on_click=limpiar_buscador, use_container_width=True)

    # --- ENTRADA POR VOZ INTELIGENTE ---
    with st.expander("🎤 Entrada por Voz Inteligente (Clic para desplegar)", expanded=False):
        audio_val = st.audio_input("Dictar (Ej. '3 conchas para el 15 de marzo')")
        
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
                except ImportError:
                    st.error("⚠️ Faltan dependencias. Asegúrate de tener SpeechRecognition en tu requirements.txt")
                except Exception as e:
                    st.toast("❌ No pude entender el audio o hubo mucho ruido de fondo.")

    # --- CUADRO DE CONFIRMACIÓN EDITABLE ---
    if st.session_state.get("confirmacion_voz"):
        datos = st.session_state.confirmacion_voz
        
        # --- SCRIPT DE LECTURA EN VOZ ALTA (VOZ FEMENINA) ---
        if not st.session_state.get("audio_leido", False):
            js_tts = f"""
            <script>
                function speakText() {{
                    const utterance = new SpeechSynthesisUtterance("{datos['original']}");
                    utterance.lang = 'es-MX';
                    utterance.rate = 1.0;
                    
                    let voices = window.speechSynthesis.getVoices();
                    let femaleVoice = voices.find(v => v.lang.includes('es') && (v.name.includes('Female') || v.name.includes('Mujer') || v.name.includes('Sabina') || v.name.includes('Paulina') || v.name.includes('Elena') || v.name.includes('Monica')));
                    
                    if (!femaleVoice) {{
                        femaleVoice = voices.find(v => v.lang.includes('es-MX'));
                    }}
                    if (femaleVoice) {{
                        utterance.voice = femaleVoice;
                    }}
                    window.speechSynthesis.speak(utterance);
                }}
                
                if (speechSynthesis.getVoices().length === 0) {{
                    speechSynthesis.onvoiceschanged = speakText;
                }} else {{
                    speakText();
                }}
            </script>
            """
            components.html(js_tts, height=0)
            st.session_state.audio_leido = True
            
        st.success(f"🗣️ **Confirmado:** '{datos['original']}'")
        st.write("✏️ *Puedes corregir los datos antes de registrar:*")
        
        edit_prod = st.text_input("Producto", value=datos['prod']).upper()
        edit_cant = st.number_input("Cantidad", value=int(datos['cant']), min_value=1)
        edit_fech = st.date_input("Caducidad", value=datos['fecha'])
        
        col_voz_1, col_voz_2 = st.columns(2)
        
        with col_voz_1:
            if st.button("📝 Guardar en Conteo (Para Corte)", use_container_width=True, type="primary"):
                if edit_prod and edit_prod.strip() != "":
                    prod_final = edit_prod.strip()
                    existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (prod_final, str(edit_fech))).fetchone()
                    if existe:
                        c.execute("UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?", (int(edit_cant), prod_final, str(edit_fech)))
                    else:
                        c.execute("INSERT INTO captura_actual VALUES (?,?,?)", (prod_final, str(edit_fech), int(edit_cant)))
                    conn.commit()
                    st.success(f"✅ {edit_cant} {prod_final} a Conteo.")
                    st.session_state.confirmacion_voz = None
                    st.session_state.audio_leido = False
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("El nombre no puede estar vacío.")
                    
        with col_voz_2:
            if st.button("🥖 Ingresar Producción Directa al Stock", use_container_width=True):
                if edit_prod and edit_prod.strip() != "":
                    prod_final = edit_prod.strip()
                    existe_stock = c.execute("SELECT cantidad FROM base_anterior WHERE nombre=? AND fecha_cad=?", (prod_final, str(edit_fech))).fetchone()
                    if existe_stock:
                        c.execute("UPDATE base_anterior SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?", (int(edit_cant), prod_final, str(edit_fech)))
                    else:
                        c.execute("INSERT INTO base_anterior VALUES (?,?,?)", (prod_final, str(edit_fech), int(edit_cant)))
                    conn.commit()
                    st.success(f"✅ {edit_cant} {prod_final} añadidos directamente al inventario general.")
                    st.session_state.confirmacion_voz = None
                    st.session_state.audio_leido = False
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("El nombre no puede estar vacío.")

        if st.button("❌ Cancelar / Reintentar", use_container_width=True):
            st.session_state.confirmacion_voz = None
            st.session_state.audio_leido = False
            st.rerun()
        
        st.divider()

    # --- ENTRADA MANUAL NORMAL ---
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    nombre_input = st.selectbox("Seleccionar producto", sugerencias, key="sel_prod") if sugerencias else buscar
    f_cad = st.date_input("Caducidad", value=fecha_hoy_mx)

    st.write("")
    
    # Botones de suma y borrar
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    with col_sum1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with col_sum2: st.button("+2", use_container_width=True, on_click=sumar, args=(2,))
    with col_sum3: st.button("Borrar", use_container_width=True, on_click=resetear)

    st.write("") 
    
    # --- MÉTRICA Y BOTÓN DE REGISTRO ---
    st.metric("Total a registrar", st.session_state.conteo_temp)

    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("➕ Registrar en Conteo (Para Corte)", use_container_width=True, type="primary"):
            if nombre_input and nombre_input.strip() != "":
                nombre_final = nombre_input.strip().upper()
                cant = st.session_state.conteo_temp
                if cant > 0:
                    existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, str(f_cad))).fetchone()
                    if existe:
                        c.execute("UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, str(f_cad)))
                    else:
                        c.execute("INSERT INTO captura_actual VALUES (?,?,?)", (nombre_final, str(f_cad), int(cant)))
                    conn.commit()
                    st.session_state.conteo_temp = 0
                    st.success(f"✅ {nombre_final} registrado para el próximo corte.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Agrega una cantidad mayor a 0.")

    with col2:
        if st.button("🥖 Sumar directamente al Stock Actual", use_container_width=True):
            if nombre_input and nombre_input.strip() != "":
                nombre_final = nombre_input.strip().upper()
                cant = st.session_state.conteo_temp
                if cant > 0:
                    existe_stock = c.execute("SELECT cantidad FROM base_anterior WHERE nombre=? AND fecha_cad=?", (nombre_final, str(f_cad))).fetchone()
                    if existe_stock:
                        c.execute("UPDATE base_anterior SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, str(f_cad)))
                    else:
                        c.execute("INSERT INTO base_anterior VALUES (?,?,?)", (nombre_final, str(f_cad), int(cant)))
                    conn.commit()
                    st.session_state.conteo_temp = 0
                    st.success(f"✅ {cant} de {nombre_final} se sumaron directamente a tu inventario activo.")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.warning("Agrega una cantidad mayor a 0.")

    st.divider()
    st.subheader("🛒 Captura de Conteo Actual (Pendiente de Corte)")
    
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    
    df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, num_rows="dynamic", height=300, use_container_width=True, hide_index=True, key="editor_conteo")

    if st.button("💾 Guardar Cambios en Tabla", use_container_width=True):
        c.execute("DELETE FROM captura_actual")
        for _, fila in df_editado.iterrows():
            if pd.notna(fila["nombre"]) and str(fila["nombre"]).strip() != "":
                c.execute("INSERT INTO captura_actual VALUES (?,?,?)", (str(fila["nombre"]).upper(), str(fila["fecha_cad"]), int(fila["cantidad"])))
        conn.commit()
        st.success("✅ Tabla de conteo guardada y actualizada")
        time.sleep(1.5)

# ------------------------------------------------------------
# TAB 2: INVENTARIO Y CORTE
# ------------------------------------------------------------
with tab2:
    st.header("📦 Stock Actual en Estantes")
    df_stock = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Existencia FROM base_anterior", conn)
    
    if df_stock.empty:
        st.info("No hay stock registrado. Realiza un corte inicial o usa el botón de sumar al stock en la pestaña de Conteo.")
    else:
        fechas_stock = sorted(df_stock['Caducidad'].unique())
        
        filtro_st_fecha = st.multiselect("Filtrar stock por Caducidad:", fechas_stock, default=fechas_stock)
            
        df_stock_filt = df_stock[df_stock['Caducidad'].isin(filtro_st_fecha)]
        st.dataframe(df_stock_filt, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📥 Exportar Reportes")
        
        msg_stock = "🍞 *INVENTARIO DISPONIBLE - CHAMPLITTE*\n\nAdjunto archivo de Excel con los detalles.\n\n"
        link_st = f"https://wa.me/{numero_whatsapp.strip()}?text={urllib.parse.quote(msg_stock)}"
        
        excel_stock = generar_excel_formato(df_stock_filt, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V.")

        st.info("💡 **Tip para WhatsApp:** Descarga el Excel primero y luego abre WhatsApp para arrastrar el archivo al chat.")
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button("📗 1. Descargar Excel", data=excel_stock, file_name=f"Sugeridos_{fecha_hoy_mx}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_down2:
            st.link_button("💬 2. Abrir WhatsApp", link_st, use_container_width=True, type="primary")

    st.divider()
    st.header("🚀 Realizar Corte de Ventas")
    st.write("Compara el **Conteo de hoy** contra el **Stock actual** para calcular ventas.")
    
    if st.button("PROCESAR CORTE AHORA", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        
        if df_actualizado.empty:
            st.warning("⚠️ No hay datos en la tabla de CONTEO para comparar. Captura tu conteo final primero.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            
            if not df_anterior.empty:
                for _, fila_ant in df_anterior.iterrows():
                    res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                    cant_hoy = res_hoy[0] if res_hoy else 0
                    diferencia = fila_ant['cantidad'] - cant_hoy
                    
                    if diferencia > 0:
                        c.execute("INSERT INTO historial_ventas VALUES (?,?,?,?,?,?)", (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']), int(cant_hoy), int(diferencia), ts_mx))
                        
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            
            conn.commit()
            st.balloons()
            st.success("✅ ¡Corte procesado con éxito! El inventario se ha actualizado.")
            time.sleep(2)
            st.rerun()

# ------------------------------------------------------------
# TAB 3: ANÁLISIS
# ------------------------------------------------------------
with tab3:
    df_hist = pd.read_sql("SELECT nombre as Producto, vendidos as Vendidos, fecha_corte as Fecha, fecha_cad as Caducidad FROM historial_ventas", conn)
    
    if df_hist.empty:
        st.info("Aún no hay historial de ventas.")
    else:
        df_hist['Fecha'] = pd.to_datetime(df_hist['Fecha']).dt.date
        
        buscar_h = st.text_input("Buscar producto en historial").upper()
        fecha_filtro = st.date_input("Filtrar por día de corte", value=None)
            
        if buscar_h:
            df_hist = df_hist[df_hist["Producto"].str.contains(buscar_h, na=False)]
        if fecha_filtro:
            df_hist = df_hist[df_hist["Fecha"] == fecha_filtro]
            
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        st.divider()
        
        ventas_dia = df_hist.groupby("Fecha")["Vendidos"].sum().reset_index()
        st.line_chart(ventas_dia, x="Fecha", y="Vendidos")
        
        top = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False)
        
        if not top.empty:
            st.subheader("🏆 Producto Estrella")
            st.metric(top.index[0], f"{int(top.iloc[0])} vendidos")
            st.bar_chart(top)
