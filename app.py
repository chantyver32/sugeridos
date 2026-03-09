import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------

with st.spinner('Iniciando sistema Champlitte... 🥐'):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy_mx = datetime.now(zona_mx).date()
    numero_whatsapp = "522283530069"

st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

mensaje_global = st.empty()

# ------------------ BASE DE DATOS ------------------

conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')

c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT,
    fecha_cad DATE,
    habia INTEGER,
    quedan INTEGER,
    vendidos INTEGER,
    fecha_corte DATETIME
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

def limpiar_producto():
    st.session_state.conteo_temp = 0
    st.session_state.buscar_producto = ""
    sonido_click()

def mostrar_exito(mensaje, duracion=2):
    mensaje_global.success(mensaje)
    time.sleep(duracion)
    mensaje_global.empty()

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

        else:

            st.sidebar.error("Debes confirmar primero")

# ------------------ TABS ------------------

tab1, tab2, tab3 = st.tabs(["📝 Conteo", "📦 Inventario", "📊 Historial"])

# ------------------------------------------------------------
# TAB 1  CONTEO
# ------------------------------------------------------------

with tab1:

    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0

    if "buscar_producto" not in st.session_state:
        st.session_state.buscar_producto = ""

    buscar = st.text_input("Buscar producto", key="buscar_producto").upper()

    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]

    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    if sugerencias:
        nombre_input = st.selectbox("Producto", sugerencias)
    else:
        nombre_input = buscar

    f_cad = st.date_input("Caducidad", value=fecha_hoy_mx)

    c1,c2,c3,c4 = st.columns(4)

    with c1:
        st.button("+1",on_click=sumar,args=(1,),use_container_width=True)

    with c2:
        st.button("+5",on_click=sumar,args=(5,),use_container_width=True)

    with c3:
        st.button("+10",on_click=sumar,args=(10,),use_container_width=True)

    with c4:
        st.button("Borrar",on_click=resetear,use_container_width=True)

    st.metric("Total",st.session_state.conteo_temp)

    colA,colB = st.columns(2)

    with colA:
        if st.button("Registrar",use_container_width=True):

            if nombre_input:

                nombre_final = nombre_input.strip().upper()
                cant = st.session_state.conteo_temp

                existe = c.execute(
                    "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                    (nombre_final,f_cad)
                ).fetchone()

                if existe:

                    c.execute(
                        "UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?",
                        (cant,nombre_final,f_cad)
                    )

                else:

                    c.execute(
                        "INSERT INTO captura_actual VALUES (?,?,?)",
                        (nombre_final,f_cad,cant)
                    )

                conn.commit()

                st.session_state.conteo_temp = 0

                st.toast(f"{nombre_final} añadido")

                st.rerun()

    with colB:
        st.button("Nuevo producto / limpiar conteo",on_click=limpiar_producto,use_container_width=True)

    df = pd.read_sql("SELECT rowid,nombre,fecha_cad,cantidad FROM captura_actual",conn)

    st.data_editor(
        df,
        column_config={"rowid":None},
        num_rows="dynamic",
        height=400,
        use_container_width=True,
        hide_index=True
    )

# ------------------------------------------------------------
# TAB 2 INVENTARIO Y CADUCIDADES
# ------------------------------------------------------------

with tab2:

    if st.button("REALIZAR CORTE",use_container_width=True):

        df_actual = pd.read_sql("SELECT * FROM captura_actual",conn)
        df_anterior = pd.read_sql("SELECT * FROM base_anterior",conn)

        ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")

        for _,fila_ant in df_anterior.iterrows():

            res_hoy = c.execute(
                "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                (fila_ant['nombre'],fila_ant['fecha_cad'])
            ).fetchone()

            cant_hoy = res_hoy[0] if res_hoy else 0
            diferencia = fila_ant['cantidad'] - cant_hoy

            c.execute(
                "INSERT INTO historial_ventas VALUES (?,?,?,?,?,?)",
                (
                    fila_ant['nombre'],
                    fila_ant['fecha_cad'],
                    int(fila_ant['cantidad']),
                    int(cant_hoy),
                    int(diferencia),
                    ts_mx
                )
            )

        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")

        conn.commit()

        st.success("Corte realizado")

    df_inventario = pd.read_sql(
        "SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Cantidad FROM base_anterior",
        conn
    )

    st.dataframe(df_inventario,use_container_width=True)

    st.divider()

    st.subheader("Filtrar por caducidad")

    if not df_inventario.empty:

        df_inventario["Caducidad"] = pd.to_datetime(df_inventario["Caducidad"]).dt.date

        fecha_filtro = st.date_input("Seleccionar fecha")

        df_filtrado = df_inventario[df_inventario["Caducidad"] == fecha_filtro]

        st.dataframe(df_filtrado,use_container_width=True)

        if not df_filtrado.empty:

            mensaje = f"PRODUCTOS CON CADUCIDAD {fecha_filtro}\n\n"

            for _,row in df_filtrado.iterrows():

                mensaje += (
                    f"{row['Producto']}\n"
                    f"Cantidad: {row['Cantidad']}\n\n"
                )

            link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"

            st.link_button("Enviar filtro a WhatsApp",link,use_container_width=True)

# ------------------------------------------------------------
# TAB 3 HISTORIAL
# ------------------------------------------------------------

with tab3:

    df_hist = pd.read_sql(
        """
        SELECT
        fecha_corte as Fecha,
        nombre as Producto,
        fecha_cad as Caducidad,
        habia as Habia,
        quedan as Quedan,
        vendidos as Vendidos
        FROM historial_ventas
        ORDER BY fecha_corte DESC
        """,
        conn
    )

    st.dataframe(
        df_hist,
        use_container_width=True,
        hide_index=True
    )
