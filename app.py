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

    c1, c2, c3, c4 = st.columns(4)

    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("Borrar", use_container_width=True, on_click=resetear)

    st.metric("Total a registrar", st.session_state.conteo_temp)

    if st.button("➕ Registrar en Inventario", use_container_width=True, type="primary"):

        if nombre_input and nombre_input.strip() != "":

            nombre_final = nombre_input.strip().upper()
            cant = st.session_state.conteo_temp

            existe = c.execute(
                "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                (nombre_final, str(f_cad))
            ).fetchone()

            if existe:
                c.execute(
                    "UPDATE captura_actual SET cantidad=cantidad+? WHERE nombre=? AND fecha_cad=?",
                    (int(cant), nombre_final, str(f_cad))
                )
            else:
                c.execute(
                    "INSERT INTO captura_actual VALUES (?,?,?)",
                    (nombre_final, str(f_cad), int(cant))
                )

            conn.commit()
            st.session_state.conteo_temp = 0
            st.toast(f"{nombre_final} añadido")
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

    if st.button("💾 Guardar Cambios en Tabla", use_container_width=True):

        c.execute("DELETE FROM captura_actual")

        for _, fila in df_editado.iterrows():

            if pd.notna(fila["nombre"]) and str(fila["nombre"]).strip() != "":

                c.execute(
                    "INSERT INTO captura_actual VALUES (?,?,?)",
                    (str(fila["nombre"]).upper(), str(fila["fecha_cad"]), int(fila["cantidad"]))
                )

        conn.commit()

        mostrar_exito("Conteo actualizado")

# ------------------------------------------------------------
# TAB 2: INVENTARIO Y CORTE
# ------------------------------------------------------------

with tab2:

    st.header("📦 Stock Actual en Estantes")

    df_stock = pd.read_sql(
        "SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Existencia FROM base_anterior",
        conn
    )

    if df_stock.empty:

        st.info("No hay stock registrado en la base anterior. Realiza un corte para cargar inventario.")

    else:

        fechas_stock = sorted(df_stock['Caducidad'].unique())

        col_st1, col_st2 = st.columns([2,1])

        with col_st1:
            filtro_st_fecha = st.multiselect(
                "Filtrar stock por Caducidad:",
                fechas_stock,
                default=fechas_stock
            )

        df_stock_filt = df_stock[df_stock['Caducidad'].isin(filtro_st_fecha)]

        st.dataframe(df_stock_filt, use_container_width=True, hide_index=True)

        # ---------------- BOTON WHATSAPP STOCK ----------------

        msg_stock = "🍞 *INVENTARIO DISPONIBLE - CHAMPLITTE*\n\n"

        for _, r in df_stock_filt.iterrows():

            msg_stock += (
                f"▫️ *{r['Producto']}*\n"
                f"   Cad: {r['Caducidad']} | Stock: *{r['Existencia']} pza*\n\n"
            )

        link_st = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg_stock)}"

        st.link_button(
            "📲 Enviar Stock Actual a WhatsApp",
            link_st,
            use_container_width=True,
            type="primary"
        )

    st.divider()

    # ---------------- CORTE ----------------

    st.header("🚀 Realizar Corte de Ventas")

    st.write("Compara el **Conteo de hoy** contra el **Stock actual** para calcular ventas.")

    if st.button("PROCESAR CORTE AHORA", type="primary", use_container_width=True):

        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)

        if df_actualizado.empty:

            st.warning("⚠️ No hay datos en la pestaña de CONTEO. Captura algo primero.")

        else:

            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)

            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")

            if not df_anterior.empty:

                for _, fila_ant in df_anterior.iterrows():

                    res_hoy = c.execute(
                        "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                        (fila_ant['nombre'], fila_ant['fecha_cad'])
                    ).fetchone()

                    cant_hoy = res_hoy[0] if res_hoy else 0

                    diferencia = fila_ant['cantidad'] - cant_hoy

                    if diferencia > 0:

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

                df_resumen = pd.read_sql(
                    f"SELECT nombre as Producto, fecha_cad as Caducidad, habia as Había, quedan as Quedan, vendidos as VENDIDOS FROM historial_ventas WHERE fecha_corte = '{ts_mx}'",
                    conn
                )

                st.session_state['ultimo_corte'] = df_resumen

            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")

            conn.commit()

            st.success("✅ Corte exitoso. El conteo de hoy pasó a ser el Stock Actual.")

            st.rerun()

# ------------------------------------------------------------
# TAB 3: ANÁLISIS
# ------------------------------------------------------------

with tab3:

    df_hist = pd.read_sql(
        "SELECT nombre as Producto, vendidos as Vendidos, fecha_corte as Fecha, fecha_cad as Caducidad FROM historial_ventas",
        conn
    )

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
