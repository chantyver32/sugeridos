import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time
import os

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter


# ------------------ CONFIGURACIÓN GENERAL ------------------

st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

with st.spinner('Iniciando sistema Champlitte... 🥐'):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy_mx = datetime.now(zona_mx).date()

# ------------------ WHATSAPP DESTINOS ------------------

st.sidebar.subheader("📲 Envío de Reportes WhatsApp")

contactos_whatsapp = {
    "Sucursal Costa Verde": "522299359597",
    "Producción": "522281342454",
    "Gerencia": "522283530069"
}

destino = st.sidebar.selectbox("Enviar reportes a:", list(contactos_whatsapp.keys()))
numero_whatsapp = contactos_whatsapp[destino]

# ------------------ BASE DE DATOS ------------------

conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')

c.execute('''
CREATE TABLE IF NOT EXISTS historial_ventas (
nombre TEXT,
fecha_cad DATE,
habia INTEGER,
quedan INTEGER,
vendidos INTEGER,
fecha_corte DATETIME
)
''')

conn.commit()

# ------------------ FUNCION GENERAR EXCEL COSTA VERDE ------------------

def generar_excel_costa_verde(df):

    wb = Workbook()
    ws = wb.active

    ws.merge_cells('A1:F1')
    ws['A1'] = "COSTA VERDE"
    ws['A1'].font = Font(size=20, bold=True)
    ws['A1'].alignment = Alignment(horizontal="center")

    ws.append(["PRODUCTO","CANTIDAD","FECHA"])

    for _, row in df.iterrows():
        ws.append([row["nombre"],row["cantidad"],row["fecha_cad"]])

    for col in range(1,4):
        ws.column_dimensions[get_column_letter(col)].width = 25

    archivo = f"reporte_{fecha_hoy_mx}.xlsx"
    wb.save(archivo)

    return archivo

# ------------------ TABS ------------------

tab1, tab2, tab3 = st.tabs(["📝 Conteo","📦 Inventario y Corte","📊 Análisis"])


# ------------------------------------------------------------
# TAB 1
# ------------------------------------------------------------

with tab1:

    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0

    nombres_prev = [r[0] for r in c.execute(
    "SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]

    nombre_input = st.selectbox("Producto", nombres_prev if nombres_prev else [""])

    f_cad = st.date_input("Caducidad",value=fecha_hoy_mx)

    col1,col2,col3,col4 = st.columns(4)

    if col1.button("+1"):
        st.session_state.conteo_temp += 1

    if col2.button("+5"):
        st.session_state.conteo_temp += 5

    if col3.button("+10"):
        st.session_state.conteo_temp += 10

    if col4.button("Borrar"):
        st.session_state.conteo_temp = 0

    st.metric("Total a registrar",st.session_state.conteo_temp)

    if st.button("➕ Registrar en Inventario"):

        cant = st.session_state.conteo_temp

        if nombre_input:

            c.execute("INSERT INTO captura_actual VALUES (?,?,?)",
            (nombre_input,str(f_cad),cant))

            conn.commit()

            st.session_state.conteo_temp = 0

            st.success("Producto registrado")

            time.sleep(1)

            st.rerun()

    df = pd.read_sql("SELECT * FROM captura_actual",conn)

    st.dataframe(df,use_container_width=True)

# ------------------------------------------------------------
# TAB 2
# ------------------------------------------------------------

with tab2:

    st.header("Inventario actual")

    df_stock = pd.read_sql("SELECT * FROM base_anterior",conn)

    st.dataframe(df_stock,use_container_width=True)

    if st.button("PROCESAR CORTE"):

        df_actual = pd.read_sql("SELECT * FROM captura_actual",conn)

        if df_actual.empty:

            st.warning("No hay conteo")

        else:

            ts = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")

            df_anterior = pd.read_sql("SELECT * FROM base_anterior",conn)

            for _,fila in df_anterior.iterrows():

                res = c.execute(
                "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                (fila["nombre"],fila["fecha_cad"])
                ).fetchone()

                cant_hoy = res[0] if res else 0

                vendidos = fila["cantidad"] - cant_hoy

                if vendidos>0:

                    c.execute("INSERT INTO historial_ventas VALUES (?,?,?,?,?,?)",
                    (fila["nombre"],fila["fecha_cad"],fila["cantidad"],cant_hoy,vendidos,ts))

            c.execute("DELETE FROM base_anterior")

            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")

            c.execute("DELETE FROM captura_actual")

            conn.commit()

            st.success("Corte realizado")

            time.sleep(1)

            st.rerun()

    st.divider()

    st.header("Exportar Reportes")

    df_hist = pd.read_sql("SELECT * FROM historial_ventas",conn)

    if not df_hist.empty:

        csv = df_hist.to_csv(index=False).encode("utf-8")

        st.download_button(
        "⬇ Descargar CSV",
        csv,
        file_name="reporte_ventas.csv",
        mime="text/csv"
        )

        if st.button("📊 Generar Excel Costa Verde"):

            archivo = generar_excel_costa_verde(df_hist)

            with open(archivo,"rb") as f:

                st.download_button(
                "⬇ Descargar Excel",
                f,
                file_name=archivo
                )

        mensaje = "REPORTE DE VENTAS CHAMPLITTE\n\n"

        for _,r in df_hist.iterrows():

            mensaje += f"{r['nombre']} - Vendidos {r['vendidos']}\n"

        link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"

        st.link_button("📲 Enviar Reporte por WhatsApp",link)


# ------------------------------------------------------------
# TAB 3
# ------------------------------------------------------------

with tab3:

    df_hist = pd.read_sql("SELECT * FROM historial_ventas",conn)

    if df_hist.empty:

        st.info("Sin historial")

    else:

        df_hist["fecha_corte"] = pd.to_datetime(df_hist["fecha_corte"]).dt.date

        ventas = df_hist.groupby("fecha_corte")["vendidos"].sum().reset_index()

        st.line_chart(ventas,x="fecha_corte",y="vendidos")

        top = df_hist.groupby("nombre")["vendidos"].sum().sort_values(ascending=False)

        if not top.empty:

            st.subheader("Producto estrella")

            st.metric(top.index[0],int(top.iloc[0]))

            st.bar_chart(top)
