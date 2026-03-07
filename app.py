import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------

st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

mensaje_global = st.empty()

zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

numero_whatsapp = "522283530069"

# --------- SONIDO CLICK ---------

def sonido_click():
    st.markdown(
        """
        <audio autoplay>
        <source src="https://www.soundjay.com/buttons/sounds/button-16.mp3">
        </audio>
        """,
        unsafe_allow_html=True
    )

# ------------------ BASE DE DATOS ------------------

conn = sqlite3.connect("inventario_pan.db", check_same_thread=False)
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)")
conn.commit()

# ------------------ SIDEBAR RESET ------------------

st.sidebar.header("⚙️ Configuración")

with st.sidebar.expander("🚨 Zona de Peligro"):

    confirmar_reset = st.checkbox("Confirmar que deseo borrar todo")

    if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):

        if confirmar_reset:

            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()

            st.sidebar.success("Base de datos limpiada")
            st.rerun()

        else:
            st.sidebar.error("Debes confirmar primero")

# ------------------ PRODUCTOS MÁS USADOS ------------------

query_productos = """
SELECT nombre FROM base_anterior
UNION
SELECT nombre FROM captura_actual
"""

nombres_prev = [r[0] for r in c.execute(query_productos).fetchall()]

nombres_prev = sorted(list(set(nombres_prev)))

# ------------------ SECCIÓN 1 CAPTURA ------------------

st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

with st.container(border=True):

    col1, col2, col3 = st.columns([2,1,1])

    # -------- PRODUCTO --------

    with col1:

        st.subheader("Producto")

        nombre_input = st.selectbox(
            "Buscar o escribir producto",
            options=[""] + nombres_prev,
            index=0
        )

        nombre_nuevo = st.text_input("O escribir nuevo producto").upper()

        if nombre_nuevo:
            nombre_input = nombre_nuevo

    # -------- CADUCIDAD --------

    with col2:

        f_cad = st.date_input(
            "Fecha de Caducidad",
            value=fecha_hoy_mx,
            min_value=fecha_hoy_mx
        )

    # -------- CONTADOR --------

    with col3:

        st.write("Cantidad que ves")

# -------- CONTADOR RAPIDO --------

if "conteo_temp" not in st.session_state:
    st.session_state.conteo_temp = 0

def sumar(v):
    st.session_state.conteo_temp += v
    sonido_click()

def resetear():
    st.session_state.conteo_temp = 0

c1,c2,c3,c4 = st.columns(4)

with c1:
    st.button("+1", use_container_width=True, on_click=sumar, args=(1,))

with c2:
    st.button("+5", use_container_width=True, on_click=sumar, args=(5,))

with c3:
    st.button("+10", use_container_width=True, on_click=sumar, args=(10,))

with c4:
    st.button("Borrar", use_container_width=True, on_click=resetear)

st.metric("Total contado", st.session_state.conteo_temp)

cant = st.session_state.conteo_temp

# ------------------ BOTONES REGISTRO ------------------

col_reg1, col_reg2, col_reg3 = st.columns(3)

def registrar(reset_producto=False):

    if not nombre_input:
        st.warning("Debes seleccionar producto")
        return

    nombre_final = nombre_input.strip().upper()

    existe = c.execute(
        "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
        (nombre_final, f_cad)
    ).fetchone()

    if existe:

        c.execute(
            "UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?",
            (cant, nombre_final, f_cad)
        )

    else:

        c.execute(
            "INSERT INTO captura_actual VALUES (?,?,?)",
            (nombre_final, f_cad, cant)
        )

    conn.commit()

    sonido_click()

    st.session_state.conteo_temp = 0

    if reset_producto:
        st.rerun()

with col_reg1:
    if st.button("➕ Registrar", use_container_width=True):
        registrar(True)

with col_reg2:
    if st.button("⚡ Registrar y seguir contando", use_container_width=True):
        registrar(False)

with col_reg3:
    if st.button("🧹 Limpiar formulario", use_container_width=True):
        st.session_state.conteo_temp = 0
        st.rerun()

# ------------------ TABLA EDITABLE ------------------

df_hoy_captura = pd.read_sql("SELECT rowid,nombre,fecha_cad,cantidad FROM captura_actual", conn)

if not df_hoy_captura.empty:

    df_hoy_captura["fecha_cad"] = pd.to_datetime(df_hoy_captura["fecha_cad"]).dt.date

    st.subheader("📋 Revisión del conteo")

    df_editado = st.data_editor(
        df_hoy_captura,
        use_container_width=True,
        hide_index=True
    )

    col_save, col_cancel = st.columns(2)

    with col_save:

        if st.button("💾 Guardar cambios"):

            c.execute("DELETE FROM captura_actual")

            for _,fila in df_editado.iterrows():

                c.execute(
                    "INSERT INTO captura_actual VALUES (?,?,?)",
                    (fila["nombre"], fila["fecha_cad"], int(fila["cantidad"]))
                )

            conn.commit()

            mensaje_global.success("Conteo actualizado")
            time.sleep(1)

            st.rerun()

    with col_cancel:

        if st.button("🗑️ Borrar conteo actual"):

            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.rerun()

# ------------------ CORTE ------------------

st.divider()
st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

if st.button("REALIZAR CORTE", use_container_width=True):

    df_actual = pd.read_sql("SELECT * FROM captura_actual", conn)

    if df_actual.empty:

        st.warning("No hay conteo")
        st.stop()

    df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)

    ventas_detectadas = []

    ts = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")

    for _,fila in df_anterior.iterrows():

        res = c.execute(
            "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
            (fila["nombre"], fila["fecha_cad"])
        ).fetchone()

        hoy = res[0] if res else 0

        diff = fila["cantidad"] - hoy

        if diff>0:

            ventas_detectadas.append({
                "Producto":fila["nombre"],
                "Caducidad":fila["fecha_cad"],
                "Había":fila["cantidad"],
                "Quedan":hoy,
                "VENDIDOS":diff
            })

            c.execute(
                "INSERT INTO historial_ventas VALUES (?,?,?,?)",
                (fila["nombre"], fila["fecha_cad"], diff, ts)
            )

    if ventas_detectadas:
        st.session_state["ultimo_corte"]=pd.DataFrame(ventas_detectadas)

    c.execute("DELETE FROM base_anterior")
    c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
    c.execute("DELETE FROM captura_actual")

    conn.commit()

    st.success("Corte realizado")

    st.rerun()

# ------------------ RESULTADO CORTE ------------------

if "ultimo_corte" in st.session_state:

    df_ventas = st.session_state["ultimo_corte"]

    st.subheader("📊 Ventas detectadas")

    st.table(df_ventas)

    mensaje = "📊 CORTE DE VENTAS\n\n"

    for _,row in df_ventas.iterrows():

        mensaje += f"{row['Producto']} | Vendidos: {row['VENDIDOS']}\n"

    link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"

    st.link_button("Enviar WhatsApp", link)

# ------------------ INVENTARIO ------------------

st.divider()

st.header("🏪 Inventario actual")

df_estantes = pd.read_sql("SELECT * FROM base_anterior", conn)

if not df_estantes.empty:

    st.metric("Piezas totales", int(df_estantes["cantidad"].sum()))

    st.dataframe(df_estantes)

else:

    st.info("Sin inventario")

# ------------------ HISTORIAL ------------------

with st.expander("📖 Historial ventas"):

    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)

    st.dataframe(df_hist)

    if not df_hist.empty:

        st.download_button(
            "Descargar CSV",
            df_hist.to_csv(index=False),
            "ventas.csv"
        )
