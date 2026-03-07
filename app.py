import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

# ------------------ CONFIGURACIÓN DE ZONA HORARIA (MÉXICO) ------------------
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ SIDEBAR RESET ------------------
st.sidebar.header("⚙️ Configuración")

with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar borrar todo")

    if st.button("⚠️ EJECUTAR RESET TOTAL"):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.sidebar.success("Base de datos limpiada.")
            st.rerun()

# ------------------ PASO 1 CAPTURA ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

with st.container(border=True):

    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]

    col1, col2, col3 = st.columns([2,1,1])

    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev)

        if opcion == "-- Nuevo Producto --":
            nombre_input = st.text_input("Nombre del pan").upper()
        else:
            nombre_input = opcion

    with col2:
        f_cad = st.date_input("Fecha de Caducidad", value=fecha_hoy_mx)

    with col3:
        cant = st.number_input("Cantidad", min_value=1, value=1)

    if st.button("➕ Registrar en Conteo"):

        if nombre_input.strip() != "":

            existe = c.execute(
                "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                (nombre_input, f_cad)
            ).fetchone()

            if existe:
                c.execute(
                    "UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?",
                    (cant, nombre_input, f_cad)
                )
            else:
                c.execute(
                    "INSERT INTO captura_actual VALUES (?, ?, ?)",
                    (nombre_input, f_cad, cant)
                )

            conn.commit()
            st.rerun()

# ------------------ TABLA CAPTURA ------------------
df_hoy_captura = pd.read_sql(
    "SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn
)

if not df_hoy_captura.empty:

    df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date

    st.subheader("📋 Revisión del conteo")

    df_editado = st.data_editor(
        df_hoy_captura,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic"
    )

# ------------------ PASO 2 CORTE ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

if st.button("REALIZAR CORTE"):

    df_actual = pd.read_sql("SELECT * FROM captura_actual", conn)
    df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)

    ventas_detectadas = []
    ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")

    for _, fila_ant in df_anterior.iterrows():

        res_hoy = c.execute(
            "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
            (fila_ant['nombre'], fila_ant['fecha_cad'])
        ).fetchone()

        cant_hoy = res_hoy[0] if res_hoy else 0
        diferencia = fila_ant['cantidad'] - cant_hoy

        if diferencia > 0:

            ventas_detectadas.append({
                "Producto": fila_ant['nombre'],
                "VENDIDOS": diferencia
            })

            c.execute(
                "INSERT INTO historial_ventas VALUES (?, ?, ?, ?)",
                (fila_ant['nombre'], fila_ant['fecha_cad'], diferencia, ts_mx)
            )

    if ventas_detectadas:

        df_ventas = pd.DataFrame(ventas_detectadas)
        st.session_state['ultimo_corte'] = df_ventas

        mensaje = f"📊 Ventas Champlitte\n📅 {fecha_hoy_mx.strftime('%d/%m/%Y')}\n\n"

        total = 0

        for _, row in df_ventas.iterrows():
            mensaje += f"{row['Producto']} : {row['VENDIDOS']}\n"
            total += row['VENDIDOS']

        mensaje += f"\nTotal vendidos: {total}"

        st.session_state['mensaje_whatsapp'] = mensaje

    c.execute("DELETE FROM base_anterior")
    c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
    c.execute("DELETE FROM captura_actual")

    conn.commit()

    st.success("Corte realizado")
    st.rerun()

# ------------------ RESUMEN CORTE ------------------
if 'ultimo_corte' in st.session_state:

    st.subheader("📊 Resumen ventas")
    st.table(st.session_state['ultimo_corte'])

    if 'mensaje_whatsapp' in st.session_state:

        numero = "522283530069"

        link = "https://wa.me/" + numero + "?text=" + urllib.parse.quote(
            st.session_state['mensaje_whatsapp']
        )

        st.link_button("📲 Enviar ventas por WhatsApp", link)

# ------------------ ALERTAS ------------------
st.divider()

col_left, col_right = st.columns(2)

with col_left:

    st.header("⚠️ Alertas de Caducidad")

    fecha_str = fecha_hoy_mx.strftime('%Y-%m-%d')

    df_caducan_hoy = pd.read_sql(
        "SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad=?",
        conn,
        params=(fecha_str,)
    )

    if not df_caducan_hoy.empty:

        st.dataframe(df_caducan_hoy)

        mensaje_alerta = f"⚠️ Caducan hoy\n\n"

        for _, row in df_caducan_hoy.iterrows():
            mensaje_alerta += f"{row['Producto']} - {row['Cantidad']}\n"

        link = "https://wa.me/522283530069?text=" + urllib.parse.quote(mensaje_alerta)

        st.link_button("⚠️ Enviar alerta WhatsApp", link)

with col_right:

    st.header("🏪 Inventario Actual")

    df_estantes = pd.read_sql(
        "SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior",
        conn
    )

    if not df_estantes.empty:

        st.metric("Total piezas", int(df_estantes["Cantidad"].sum()))
        st.dataframe(df_estantes)

        mensaje_inv = "📦 Inventario Champlitte\n\n"

        for _, row in df_estantes.iterrows():
            mensaje_inv += f"{row['Producto']} - {row['Cantidad']}\n"

        link = "https://wa.me/522283530069?text=" + urllib.parse.quote(mensaje_inv)

        st.link_button("📦 Enviar inventario WhatsApp", link)

# ------------------ HISTORIAL ------------------
st.divider()

with st.expander("📖 Historial General"):

    df_hist = pd.read_sql(
        "SELECT * FROM historial_ventas ORDER BY fecha_corte DESC",
        conn
    )

    st.dataframe(df_hist)

    if not df_hist.empty:

        st.subheader("📊 Productos más vendidos")

        ventas_producto = df_hist.groupby("nombre")["vendidos"].sum().reset_index()

        st.bar_chart(ventas_producto.set_index("nombre"))

        csv = df_hist.to_csv(index=False).encode('utf-8')

        st.download_button(
            "📥 Descargar CSV",
            data=csv,
            file_name=f"ventas_{fecha_hoy_mx}.csv"
        )
