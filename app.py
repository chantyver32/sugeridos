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

def mostrar_exito(mensaje, duracion=2):
    mensaje_global.success(mensaje)
    time.sleep(duracion)
    mensaje_global.empty()

# ------------------ SIDEBAR RESET ------------------
st.sidebar.header("⚙️ Configuración")

with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar que deseo borrar todo", key="check_reset")

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

tab1, tab2, tab3 = st.tabs(["📝 Conteo", "📦 Inventario", "📊 Análisis"])

# ------------------------------------------------------------
# TAB 1
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

    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]

    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1,col2,col3 = st.columns([2,1,1])

    with col1:
        if sugerencias:
            nombre_input = st.selectbox("", sugerencias, key="sel_prod")
        else:
            nombre_input = buscar

    with col2:
        f_cad = st.date_input("", value=fecha_hoy_mx)

    with col3:
        st.write("")

    c1,c2,c3,c4 = st.columns(4)

    with c1:
        st.button("+1",use_container_width=True,on_click=sumar,args=(1,))
    with c2:
        st.button("+5",use_container_width=True,on_click=sumar,args=(5,))
    with c3:
        st.button("+10",use_container_width=True,on_click=sumar,args=(10,))
    with c4:
        st.button("Borrar",use_container_width=True,on_click=resetear)

    st.metric("Total",st.session_state.conteo_temp)

    if st.button("➕ Registrar",use_container_width=True):

        if nombre_input and nombre_input.strip()!="":

            nombre_final = nombre_input.strip().upper()
            cant = st.session_state.conteo_temp

            existe = c.execute(
                "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                (nombre_final,f_cad)
            ).fetchone()

            if existe:
                c.execute(
                    "UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?",
                    (int(cant),nombre_final,f_cad)
                )

            else:
                c.execute(
                    "INSERT INTO captura_actual VALUES (?,?,?)",
                    (nombre_final,f_cad,int(cant))
                )

            conn.commit()

            st.session_state.conteo_temp = 0

            st.toast(f"{nombre_final} añadido")

            st.rerun()

    df_hoy_captura = pd.read_sql("SELECT rowid,nombre,fecha_cad,cantidad FROM captura_actual",conn)

    if not df_hoy_captura.empty:

        df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date

        df_editado = st.data_editor(
            df_hoy_captura,
            column_config={"rowid":None},
            num_rows="dynamic",
            height=500,
            use_container_width=True,
            hide_index=True,
            key="editor_conteo"
        )

        col_s,col_c = st.columns(2)

        with col_s:

            if st.button("💾 Guardar cambios",use_container_width=True):

                c.execute("DELETE FROM captura_actual")

                for _,fila in df_editado.iterrows():

                    if fila['nombre']:

                        c.execute(
                            "INSERT INTO captura_actual VALUES (?,?,?)",
                            (
                                fila['nombre'].strip().upper(),
                                str(fila['fecha_cad']),
                                int(fila['cantidad'])
                            )
                        )

                conn.commit()

                mostrar_exito("Conteo actualizado")

        with col_c:

            if st.button("🧹 Limpiar tabla visual",use_container_width=True):

                st.session_state["editor_conteo"] = pd.DataFrame(
                    columns=["rowid","nombre","fecha_cad","cantidad"]
                )

                st.rerun()

# ------------------------------------------------------------
# TAB 2
# ------------------------------------------------------------

with tab2:

    if st.button("REALIZAR CORTE",type="primary",use_container_width=True):

        df_actualizado = pd.read_sql("SELECT * FROM captura_actual",conn)

        if df_actualizado.empty:

            st.warning("No hay conteo")

        else:

            df_anterior = pd.read_sql("SELECT * FROM base_anterior",conn)

            ventas_detectadas = []

            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")

            if not df_anterior.empty:

                for _,fila_ant in df_anterior.iterrows():

                    res_hoy = c.execute(
                        "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                        (fila_ant['nombre'],fila_ant['fecha_cad'])
                    ).fetchone()

                    cant_hoy = res_hoy[0] if res_hoy else 0

                    diferencia = fila_ant['cantidad'] - cant_hoy

                    if diferencia>0:

                        ventas_detectadas.append({
                            "Producto":fila_ant['nombre'],
                            "Caducidad":fila_ant['fecha_cad'],
                            "Había":fila_ant['cantidad'],
                            "Quedan":cant_hoy,
                            "VENDIDOS":diferencia
                        })

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

            if ventas_detectadas:
                st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)

            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")

            conn.commit()

            st.success("Corte realizado")

    if 'ultimo_corte' in st.session_state:

        st.balloons()

        df_ventas = st.session_state['ultimo_corte']

        st.table(df_ventas)

        mensaje = "CORTE DE VENTAS\n\n"

        for _,row in df_ventas.iterrows():

            mensaje += (
                f"{row['Producto']}\n"
                f"Cad: {row['Caducidad']}\n"
                f"Habia: {row['Había']} | Quedan: {row['Quedan']}\n"
                f"VENDIDOS: {row['VENDIDOS']}\n\n"
            )

        link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"

        col1,col2 = st.columns(2)

        with col1:
            st.link_button("Enviar WhatsApp",link,use_container_width=True)

        with col2:

            if st.button("Cerrar",use_container_width=True):

                del st.session_state['ultimo_corte']

                st.rerun()

# ------------------------------------------------------------
# TAB 3
# ------------------------------------------------------------

with tab3:

    df_hist = pd.read_sql(
        "SELECT nombre as Producto, vendidos as Vendidos, fecha_corte as Fecha FROM historial_ventas",
        conn
    )

    if df_hist.empty:
        st.info("Sin historial")
        st.stop()

    df_hist['Fecha'] = pd.to_datetime(df_hist['Fecha']).dt.date

    buscar_h = st.text_input("Buscar producto")

    if buscar_h:
        df_hist = df_hist[df_hist["Producto"].str.contains(buscar_h.upper())]

    st.dataframe(df_hist,use_container_width=True)

    st.line_chart(df_hist.groupby("Fecha")["Vendidos"].sum())

    top = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False)

    if not top.empty:
        st.metric("Producto más vendido",top.index[0],int(top.iloc[0]))
        st.bar_chart(top)
