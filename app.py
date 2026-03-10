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

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME 
)''')
conn.commit()

# ------------------ FUNCIÓN EXCEL (IDÉNTICO A LA IMAGEN) ------------------
def generar_excel_formato(df, titulo="PASTELERÍA CHAMPLITTE, S.A. DE C.V."):
    """
    Genera un archivo Excel replicando con exactitud la estructura de celdas y diseño de la foto.
    """
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    sheet = workbook.add_worksheet('SUGERIDOS')

    # Ocultar las líneas de la cuadrícula de fondo para que se vea limpio
    sheet.hide_gridlines(2)

    # --- DEFINICIÓN DE FORMATOS ---
    color_guinda = '#8C1515'
    
    fmt_header_rojo = workbook.add_format({
        'bold': True, 'font_color': 'white', 'bg_color': color_guinda,
        'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'border': 1
    })
    fmt_sub_header = workbook.add_format({
        'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10
    })
    fmt_label = workbook.add_format({
        'bold': True, 'align': 'left', 'valign': 'vcenter', 'border': 1, 'font_size': 9
    })
    fmt_data_gray = workbook.add_format({
        'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_size': 9
    })
    fmt_col_title = workbook.add_format({
        'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 9
    })
    fmt_data_center = workbook.add_format({
        'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 9
    })
    fmt_data_left = workbook.add_format({
        'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_size': 9
    })

    # --- AJUSTE DE COLUMNAS ---
    sheet.set_column('A:A', 14)  # Col A: SUCURSAL / FECHA / ELABORA
    sheet.set_column('B:B', 22)  # Col B: DESCRIPCIÓN (Parte 1)
    sheet.set_column('C:C', 22)  # Col C: DESCRIPCIÓN (Parte 2)
    sheet.set_column('D:D', 12)  # Col D: CANTIDAD
    sheet.set_column('E:E', 22)  # Col E: FECHA CADUCIDAD
    sheet.set_column('F:F', 28)  # Col F: VENDEDOR

    # --- ENCABEZADOS SUPERIORES ---
    # Fila 1 (Título que abarca de la A a la F)
    sheet.merge_range('A1:F1', titulo, fmt_header_rojo)
    sheet.set_row(0, 32)
    
    # Fila 2 (Subtítulo)
    sheet.merge_range('A2:F2', "SUGERIDOS DEL DÍA", fmt_sub_header)

    # Filas 3, 4 y 5 (Datos Generales)
    sheet.write('A3', " SUCURSAL", fmt_label)
    sheet.merge_range('B3:F3', "", fmt_data_gray) # Espacio para sucursal
    
    sheet.write('A4', " FECHA", fmt_label)
    sheet.merge_range('B4:F4', " " + str(datetime.now(zona_mx).strftime("%d/%m/%Y")), fmt_data_gray)
    
    sheet.write('A5', " ELABORA", fmt_label)
    sheet.merge_range('B5:F5', " PEDRO GARCÍA", fmt_data_gray)

    # --- ENCABEZADOS DE TABLA (Fila 6) ---
    # En la imagen, B y C están fusionados para Descripción, A queda fuera de la tabla
    sheet.merge_range('B6:C6', "DESCRIPCIÓN", fmt_col_title)
    sheet.write('D6', "CANTIDAD", fmt_col_title)
    sheet.write('E6', "FECHA DE CADUCIDAD", fmt_col_title)
    sheet.write('F6', "VENDEDOR", fmt_col_title)

    # --- LLENADO DE DATOS ---
    row = 6
    if not df.empty:
        col_n = 'Producto' if 'Producto' in df.columns else 'nombre'
        col_c = 'Existencia' if 'Existencia' in df.columns else 'cantidad'
        col_f = 'Caducidad' if 'Caducidad' in df.columns else 'fecha_cad'

        for _, fila in df.iterrows():
            sheet.merge_range(row, 1, row, 2, " " + str(fila[col_n]), fmt_data_left) # B y C fusionados
            sheet.write(row, 3, fila[col_c], fmt_data_center)                        # D
            sheet.write(row, 4, str(fila[col_f]), fmt_data_center)                   # E
            sheet.write(row, 5, "PEDRO GARCÍA", fmt_data_center)                     # F (Vendedor fijo)
            row += 1
    
    # Rellenar filas vacías para que el cuadro llegue hasta abajo (como un formato impreso real)
    for r in range(row, 26):
        sheet.merge_range(r, 1, r, 2, "", fmt_data_left)
        sheet.write(r, 3, "", fmt_data_center)
        sheet.write(r, 4, "", fmt_data_center)
        sheet.write(r, 5, "", fmt_data_center)

    writer.close()
    return output.getvalue()

# ------------------ FUNCIONES AUXILIARES ------------------
def sumar(valor):
    st.session_state.conteo_temp += valor

def resetear():
    st.session_state.conteo_temp = 0

# ------------------ SIDEBAR ------------------
st.sidebar.header("⚙️ Configuración")
numero_whatsapp = st.sidebar.text_input("📱 WhatsApp", value="522283530069")

with st.sidebar.expander("🚨 Zona de Peligro"):
    if st.button("⚠️ RESET TOTAL"):
        c.execute("DELETE FROM captura_actual")
        c.execute("DELETE FROM base_anterior")
        c.execute("DELETE FROM historial_ventas")
        conn.commit()
        st.rerun()

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 Conteo", "📦 Inventario y Corte", "📊 Análisis"])

# TAB 1: CONTEO
with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    buscar = st.text_input("🔎 BUSCAR PRODUCTO...").upper()
    
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2 = st.columns(2)
    with col1:
        nombre_input = st.selectbox("Producto", sugerencias) if sugerencias else st.text_input("Nuevo Producto", value=buscar)
    with col2:
        f_cad = st.date_input("Caducidad", value=fecha_hoy_mx)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", on_click=sumar, args=(1,), use_container_width=True)
    with c2: st.button("+5", on_click=sumar, args=(5,), use_container_width=True)
    with c3: st.button("+10", on_click=sumar, args=(10,), use_container_width=True)
    with c4: st.button("Borrar", on_click=resetear, use_container_width=True)

    st.metric("A registrar", st.session_state.conteo_temp)

    if st.button("➕ Registrar en Inventario", use_container_width=True, type="primary"):
        if nombre_input:
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_input, str(f_cad))).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?", (st.session_state.conteo_temp, nombre_input, str(f_cad)))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?,?,?)", (nombre_input, str(f_cad), st.session_state.conteo_temp))
            conn.commit()
            st.session_state.conteo_temp = 0
            st.success(f"Registrado: {nombre_input}")
            time.sleep(1)
            st.rerun()

    st.divider()
    df_hoy = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    st.data_editor(df_hoy, use_container_width=True, hide_index=True)

# TAB 2: INVENTARIO Y CORTE
with tab2:
    st.header("📦 Stock Actual")
    df_stock = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Existencia FROM base_anterior", conn)
    
    if not df_stock.empty:
        st.dataframe(df_stock, use_container_width=True, hide_index=True)
        
        # Botones de Exportación
        excel_data = generar_excel_formato(df_stock)
        st.download_button("📗 Descargar Excel Sugeridos", data=excel_data, file_name=f"Sugeridos_{fecha_hoy_mx}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    st.divider()
    if st.button("🚀 REALIZAR CORTE DE VENTAS", type="primary", use_container_width=True):
        df_cap = pd.read_sql("SELECT * FROM captura_actual", conn)
        df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
        ts = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
        
        if not df_ant.empty:
            for _, f_ant in df_ant.iterrows():
                f_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (f_ant['nombre'], f_ant['fecha_cad'])).fetchone()
                cant_hoy = f_hoy[0] if f_hoy else 0
                ventas = f_ant['cantidad'] - cant_hoy
                if ventas > 0:
                    c.execute("INSERT INTO historial_ventas VALUES (?,?,?,?,?,?)", (f_ant['nombre'], f_ant['fecha_cad'], f_ant['cantidad'], cant_hoy, ventas, ts))
        
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.success("Corte realizado. Inventario actualizado.")
        st.rerun()

# TAB 3: ANÁLISIS
with tab3:
    df_hist = pd.read_sql("SELECT * FROM historial_ventas", conn)
    if not df_hist.empty:
        st.write("Historial de Ventas")
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("No hay historial aún.")
