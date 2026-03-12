import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time
import io

# ------------------ CONFIGURACIÓN GENERAL ------------------
with st.spinner('Iniciando sistema Champlitte... 🥐'):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy_mx = datetime.now(zona_mx).date()
    
    st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# --- TRUCO CSS PARA MÓVILES ---
# Esto evita que Streamlit ponga las columnas una debajo de la otra en celulares
st.markdown("""
    <style>
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
        }
        div[data-testid="column"] {
            width: auto !important;
            min-width: 0 !important;
        }
    }
    /* Ajuste fino para la altura del contenedor de la métrica */
    [data-testid="stMetric"] {
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Contenedores para mensajes específicos debajo de los botones
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
    """
    Genera un Excel replicando exactamente el formato visual y filtros de la imagen.
    """
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    sheet = workbook.add_worksheet('SUGERIDOS')

    # Ocultar líneas de cuadrícula para aspecto de reporte limpio
    sheet.hide_gridlines(2)

    # --- FORMATOS (TODOS CENTRADOS) ---
    color_guinda = '#8C0000'
    
    fmt_titulo = workbook.add_format({
        'bold': True, 'font_color': 'white', 'bg_color': color_guinda,
        'align': 'center', 'valign': 'vcenter', 'font_size': 14, 'border': 1
    })
    fmt_subtitulo = workbook.add_format({
        'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 11
    })
    fmt_etiqueta = workbook.add_format({
        'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10
    })
    fmt_valor = workbook.add_format({
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10
    })
    fmt_header_tabla = workbook.add_format({
        'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10
    })
    fmt_datos_centro = workbook.add_format({
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10
    })

    # --- ANCHOS DE COLUMNA ---
    sheet.set_column('A:A', 15)  # Etiquetas (SUCURSAL, FECHA, ELABORA) y celda vacía abajo
    sheet.set_column('B:B', 35)  # DESCRIPCIÓN
    sheet.set_column('C:C', 12)  # CANTIDAD
    sheet.set_column('D:D', 22)  # FECHA DE CADUCIDAD
    sheet.set_column('E:E', 20)  # VENDEDOR

    # --- ENCABEZADOS PRINCIPALES ---
    sheet.set_row(0, 30)
    sheet.merge_range('A1:E1', titulo, fmt_titulo)
    sheet.merge_range('A2:E2', 'SUGERIDOS DEL DÍA', fmt_subtitulo)

    # --- BLOQUE DE INFORMACIÓN GENERAL ---
    sheet.write('A3', 'SUCURSAL', fmt_etiqueta)
    sheet.merge_range('B3:E3', 'COSTA VERDE', fmt_valor)
    
    sheet.write('A4', 'FECHA', fmt_etiqueta)
    fecha_str = datetime.now(pytz.timezone('America/Mexico_City')).strftime("%d/%m/%Y")
    sheet.merge_range('B4:E4', fecha_str, fmt_valor)
    
    sheet.write('A5', 'ELABORA', fmt_etiqueta)
    sheet.merge_range('B5:E5', 'PEDRO GARCÍA', fmt_valor)

    # --- ENCABEZADOS DE TABLA (FILA 6) ---
    sheet.write('A6', '', fmt_valor) # Celda debajo de "ELABORA" (vacía con borde)
    sheet.write('B6', 'DESCRIPCIÓN', fmt_header_tabla)
    sheet.write('C6', 'CANTIDAD', fmt_header_tabla)
    sheet.write('D6', 'FECHA DE CADUCIDAD', fmt_header_tabla)
    sheet.write('E6', 'VENDEDOR', fmt_header_tabla)

    # --- LLENADO DE DATOS DESDE LA BASE DE DATOS ---
    row = 6
    if not df.empty:
        col_nombre = 'Producto' if 'Producto' in df.columns else 'nombre'
        col_cant = 'Existencia' if 'Existencia' in df.columns else 'cantidad'
        col_fecha = 'Caducidad' if 'Caducidad' in df.columns else 'fecha_cad'

        for _, fila in df.iterrows():
            sheet.write(row, 0, '', fmt_valor) # Columna A vacía para mantener la cuadrícula
            sheet.write(row, 1, str(fila[col_nombre]), fmt_datos_centro) # Cambiado a centrado
            sheet.write(row, 2, fila[col_cant], fmt_datos_centro)
            sheet.write(row, 3, str(fila[col_fecha]), fmt_datos_centro)
            sheet.write(row, 4, 'PEDRO GARCÍA', fmt_datos_centro) # Vendedor fijo
            row += 1

    # --- AGREGAR FILTROS (AUTOFILTER) ---
    # Aplica filtro desde la fila 6 (índice 5), Columna B (índice 1) hasta Columna E (índice 4)
    last_row = row - 1 if row > 6 else 6
    sheet.autofilter(5, 1, last_row, 4)

    writer.close()
    return output.getvalue()

# ------------------ SIDEBAR RESET & CONFIG ------------------
st.sidebar.header("⚙️ Configuración")

numero_whatsapp = st.sidebar.text_input("📱 Número WhatsApp (con código de país, ej. 52228...)", value="522283530069")

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

    col_busq, col_limpiar = st.columns([4,1])
    with col_busq:
        buscar = st.text_input(
            "Buscar",
            placeholder="🔎 BUSCAR O ESCRIBIR PRODUCTO...",
            key="buscar_prod",
            label_visibility="collapsed"
        ).upper()
    with col_limpiar:
        st.button("🧹", on_click=limpiar_buscador, use_container_width=True)

    # --- ENTRADA POR VOZ ---
    audio_val = st.audio_input("🎤 Dictar producto (opcional)")
    if audio_val is not None:
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(audio_val) as source:
                audio_data = r.record(source)
                texto_voz = r.recognize_google(audio_data, language="es-MX")
                # Si reconoció algo, actualizamos la caja de texto y recargamos
                if texto_voz:
                    st.session_state.buscar_prod = texto_voz.upper()
                    st.rerun()
        except ImportError:
            st.error("⚠️ Faltan dependencias para voz. Ejecuta en tu terminal: pip install SpeechRecognition")
        except Exception as e:
            st.toast("❌ No se pudo entender el audio o hubo un error.")

    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2,1,1])
    with col1:
        if sugerencias:
            nombre_input = st.selectbox("Seleccionar producto", sugerencias, key="sel_prod")
        else:
            nombre_input = buscar
    with col2:
        f_cad = st.date_input("Caducidad", value=fecha_hoy_mx)
    with col3:
        st.write("")

    # --- MODIFICACIÓN DE LOS BOTONES: SOLO +1, +2, -1 y Borrar ---
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+2", use_container_width=True, on_click=sumar, args=(2,))
    with c3: st.button("-1", use_container_width=True, on_click=sumar, args=(-1,))
    with c4: st.button("Borrar", use_container_width=True, on_click=resetear)
    # ------------------------------------------------

    st.write("") # Un poco de espacio
    
    # --- MÉTRICA Y BOTÓN DE REGISTRO EN LA MISMA LÍNEA ---
    col_metric, col_btn = st.columns([1, 2], vertical_alignment="bottom")
    
    with col_metric:
        st.metric("Total a registrar", st.session_state.conteo_temp)

    with col_btn:
        # Botón de Registro
        if st.button("➕ Registrar en Inventario", use_container_width=True, type="primary"):
            if nombre_input and nombre_input.strip() != "":
                nombre_final = nombre_input.strip().upper()
                cant = st.session_state.conteo_temp
                
                existe = c.execute(
                    "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                    (nombre_final, str(f_cad))
                ).fetchone()
                
                if existe:
                    c.execute("UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, str(f_cad)))
                else:
                    c.execute("INSERT INTO captura_actual VALUES (?,?,?)", (nombre_final, str(f_cad), int(cant)))
                
                conn.commit()
                st.session_state.conteo_temp = 0
                # Notificación verde justo abajo
                st.success(f"✅ {nombre_final} registrado correctamente")
                time.sleep(1)
                st.rerun()

    st.divider()
    st.subheader("🛒 Captura de hoy (sin procesar)")
    
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    
    df_editado = st.data_editor(
        df_hoy_captura,
        column_config={"rowid": None},
        num_rows="dynamic",
        height=300,
        use_container_width=True,
        hide_index=True,
        key="editor_conteo"
    )

    # Botón de Guardar Tabla
    if st.button("💾 Guardar Cambios en Tabla", use_container_width=True):
        c.execute("DELETE FROM captura_actual")
        for _, fila in df_editado.iterrows():
            if pd.notna(fila["nombre"]) and str(fila["nombre"]).strip() != "":
                c.execute("INSERT INTO captura_actual VALUES (?,?,?)", (str(fila["nombre"]).upper(), str(fila["fecha_cad"]), int(fila["cantidad"])))
        conn.commit()
        # Notificación verde justo abajo
        st.success("✅ Tabla de conteo guardada y actualizada")
        time.sleep(1.5)

# ------------------------------------------------------------
# TAB 2: INVENTARIO Y CORTE
# ------------------------------------------------------------
with tab2:
    st.header("📦 Stock Actual en Estantes")
    df_stock = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Existencia FROM base_anterior", conn)
    
    if df_stock.empty:
        st.info("No hay stock registrado en la base anterior. Realiza un corte para cargar inventario.")
    else:
        fechas_stock = sorted(df_stock['Caducidad'].unique())
        col_st1, col_st2 = st.columns([2,1])
        
        with col_st1:
            filtro_st_fecha = st.multiselect("Filtrar stock por Caducidad:", fechas_stock, default=fechas_stock)
            
        df_stock_filt = df_stock[df_stock['Caducidad'].isin(filtro_st_fecha)]
        st.dataframe(df_stock_filt, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📥 Exportar Reportes")
        
        # Generar texto para WhatsApp
        msg_stock = "🍞 *INVENTARIO DISPONIBLE - CHAMPLITTE*\n\n"
        for _, r in df_stock_filt.iterrows():
            msg_stock += (f"▫️ *{r['Producto']}*\n   Cad: {r['Caducidad']} | Stock: *{r['Existencia']} pza*\n\n")
        
        link_st = f"https://wa.me/{numero_whatsapp.strip()}?text={urllib.parse.quote(msg_stock)}"
        
        # Generar archivos
        csv_stock = df_stock_filt.to_csv(index=False).encode('utf-8')
        excel_stock = generar_excel_formato(df_stock_filt, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V.")

        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            st.link_button("💬 Enviar Resumen Texto a WhatsApp", link_st, use_container_width=True, type="primary")
        with col_w2:
            st.download_button("📊 Descargar formato CSV", data=csv_stock, file_name=f"inventario_{fecha_hoy_mx}.csv", mime="text/csv", use_container_width=True)
        with col_w3:
            st.download_button("📗 Descargar Excel Sugeridos", data=excel_stock, file_name=f"Sugeridos_{fecha_hoy_mx}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    st.divider()
    st.header("🚀 Realizar Corte de Ventas")
    st.write("Compara el **Conteo de hoy** contra el **Stock actual** para calcular ventas.")
    
    # Botón de Procesar Corte
    if st.button("PROCESAR CORTE AHORA", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        
        if df_actualizado.empty:
            st.warning("⚠️ No hay datos en la pestaña de CONTEO. Captura algo primero.")
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
                        
                df_resumen = pd.read_sql(f"SELECT nombre as Producto, fecha_cad as Caducidad, habia as Había, quedan as Quedan, vendidos as VENDIDOS FROM historial_ventas WHERE fecha_corte = '{ts_mx}'", conn)
                st.session_state['ultimo_corte'] = df_resumen
                
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            
            conn.commit()
            st.balloons()
            # Notificación verde justo abajo
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
        col_a, col_b = st.columns(2)
        
        with col_a:
            buscar_h = st.text_input("Buscar producto en historial").upper()
        with col_b:
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
