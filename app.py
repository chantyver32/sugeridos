import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
# Animación de carga inicial
with st.spinner('Iniciando sistema Champlitte... 🥐'):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy_mx = datetime.now(zona_mx).date()
    numero_whatsapp = "522283530069"

st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

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

# ------------------ SIDEBAR: CONFIGURACIÓN Y RESET ------------------
st.sidebar.header("⚙️ Configuración")
with st.sidebar.expander("🚨 Zona de Peligro"):
    st.write("Esta acción borrará todo el historial y el inventario actual.")
    confirmar_reset = st.checkbox("Confirmar que deseo borrar todo", key="check_reset")
    if st.button("⚠️ EJECUTAR RESET TOTAL", type="secondary", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.sidebar.success("Base de datos limpiada con éxito.")
        else:
            st.sidebar.error("Primero debes marcar la casilla de confirmación.")

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 Añadir productos", "📦 Inventario", "📊 Análisis de Ventas"])

with tab1:
    st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state:
        st.session_state.buscar_prod = ""

    def limpiar_buscador():
        st.session_state.buscar_prod = ""
        if "sel_prod" in st.session_state:
            del st.session_state["sel_prod"]

    # --- BUSCADOR Y BOTÓN LIMPIAR (ESPACIO OPTIMIZADO) ---
    col_busq, col_limpiar = st.columns([4, 1])
    with col_busq:
        buscar = st.text_input("Buscar", placeholder="🔎 BUSCAR O ESCRIBIR PRODUCTO...", key="buscar_prod", label_visibility="collapsed").upper()
    with col_limpiar:
        st.button("🧹 Limpiar", on_click=limpiar_buscador, use_container_width=True)

    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]

    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if sugerencias:
            nombre_input = st.selectbox("Sugerencias:", sugerencias, key="sel_prod")
        else:
            st.info("✨ Producto nuevo")
            nombre_input = buscar

    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key="date_cad")

    with col3:
        st.write("Cantidad que ves")

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("Borrar Cantidad", use_container_width=True, on_click=resetear)

    st.metric("Total contado", st.session_state.conteo_temp)

    if st.button("➕ Registrar en el Conteo", use_container_width=True, type="primary"):
        if nombre_input and nombre_input.strip() != "":
            with st.spinner('Registrando...'):
                nombre_final = nombre_input.strip().upper()
                cant = st.session_state.conteo_temp
                existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad)).fetchone()
                if existe:
                    c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad))
                else:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
                conn.commit()
                sonido_click()
                st.toast(f"✅ {nombre_final} añadido", icon="🍞")
                st.session_state.conteo_temp = 0
                st.rerun()

    df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if not df_hoy_captura.empty:
        st.write("---")
        df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
        df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, num_rows="dynamic", use_container_width=True, hide_index=True, key="editor_conteo")
        
        col_s, col_c = st.columns(2)
        with col_s:
            if st.button("💾 Guardar cambios", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['nombre']:
                        c.execute("INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)", (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
                conn.commit()
                mostrar_exito("💾 Conteo actualizado")
        with col_c:
            if st.button("🗑️ Borrar TODO el conteo", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

with tab2:
    st.divider()
    st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

    if st.button("REALIZAR CORTE Y REINICIAR FORMULARIO", type="primary", use_container_width=True):
        with st.spinner('Calculando ventas...'):
            df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
            if df_actualizado.empty:
                st.warning("⚠️ No hay nada en el conteo para comparar.")
            else:
                df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
                ventas_detectadas = []
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
                            ventas_detectadas.append({
                                "Producto": fila_ant['nombre'],
                                "Caducidad": fila_ant['fecha_cad'],
                                "Había": fila_ant['cantidad'],
                                "Quedan": cant_hoy,
                                "VENDIDOS": diferencia
                            })
                        c.execute(
                            "INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)",
                            (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']),
                             int(cant_hoy), int(diferencia), ts_mx)
                        )

                if ventas_detectadas:
                    st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)

                c.execute("DELETE FROM base_anterior")
                c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.success("🏁 Corte realizado con éxito")

    # ------------------ MOSTRAR RESUMEN (CIERRE CON UN CLIC) ------------------
    if 'ultimo_corte' in st.session_state:
        with st.container(border=True):
            st.balloons()
            st.subheader("📊 Resumen de ventas detectadas:")
            df_ventas = st.session_state['ultimo_corte']
            st.table(df_ventas)

            mensaje = "📊 *CORTE DE VENTAS CHAMPLITTE*\n"
            mensaje += f"📅 Fecha: {fecha_hoy_mx.strftime('%d/%m/%Y')}\n"
            mensaje += "---------------------------------\n\n"
            for _, row in df_ventas.iterrows():
                mensaje += (f"🍞 *{row['Producto']}*\n📅 Cad: {row['Caducidad']}\n📥 Había: {row['Había']} | 📤 Quedan: {row['Quedan']}\n💰 *VENDIDOS: {row['VENDIDOS']}*\n---------------------------------\n")

            link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"
            col_wa, col_close = st.columns(2)
            with col_wa:
                st.link_button("📲 Enviar reporte por WhatsApp", link, use_container_width=True)
            with col_close:
                if st.button("❌ CERRAR RESUMEN", type="primary", use_container_width=True):
                    del st.session_state['ultimo_corte']
                    st.rerun()

    st.divider()
    col_left, col_right = st.columns(2)
    with col_left:
        st.header("⚠️ Alertas de Caducidad")
        fecha_str = fecha_hoy_mx.strftime('%Y-%m-%d')
        df_caducan_hoy = pd.read_sql("SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(fecha_str,))
        if not df_caducan_hoy.empty:
            st.error(f"¡Atención! Retirar {int(df_caducan_hoy['Cantidad'].sum())} piezas.")
            st.dataframe(df_caducan_hoy, use_container_width=True, hide_index=True)
            mensaje_alerta = "⚠️ PRODUCTOS QUE CADUCAN HOY\n\n"
            for _, row in df_caducan_hoy.iterrows():
                mensaje_alerta += f"Producto: {row['Producto']}\nCantidad: {row['Cantidad']}\n-----------------\n"
            st.link_button("⚠️ Enviar tabla de caducidad por WhatsApp", "https://wa.me/" + numero_whatsapp + "?text=" + urllib.parse.quote(mensaje_alerta))
        else:
            st.success("✅ Todo bien hoy.")

    with col_right:
        st.header("🏪 Inventario Actual")
        df_estantes = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Caducidad], cantidad as Cantidad FROM base_anterior", conn)
        if not df_estantes.empty:
            st.metric("Piezas totales", f"{int(df_estantes['Cantidad'].sum())}")
            st.dataframe(df_estantes, use_container_width=True, hide_index=True)
            mensaje_inv = "📦 INVENTARIO ACTUAL\n\n"
            for _, row in df_estantes.iterrows():
                mensaje_inv += f"Producto: {row['Producto']}\nCaducidad: {row['Fecha Caducidad']}\nCantidad: {row['Cantidad']}\n-----------------\n"
            st.link_button("📦 Enviar tabla de inventario por WhatsApp", "https://wa.me/" + numero_whatsapp + "?text=" + urllib.parse.quote(mensaje_inv))
        else:
            st.info("Sin inventario.")

    with st.expander("📖 Historial General"):
        df_hist = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, habia as Había, quedan as Quedan, vendidos as Vendidos, fecha_corte as Fecha_Hora FROM historial_ventas ORDER BY fecha_corte DESC", conn)
        st.dataframe(df_hist, use_container_width=True)

with tab3:
    st.header("📊 Análisis de Ventas")
    with st.spinner('Cargando análisis...'):
        df_hist = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, habia as Habia, quedan as Quedan, vendidos as Vendidos, fecha_corte as Fecha_Hora FROM historial_ventas", conn)

    if df_hist.empty:
        st.info("No hay historial de ventas todavía.")
        st.stop()

    df_hist['Fecha_Hora'] = pd.to_datetime(df_hist['Fecha_Hora'])
    df_hist['Fecha'] = df_hist['Fecha_Hora'].dt.date

    st.subheader("🔎 Buscar en historial")
    buscar_h = st.text_input("Buscar producto", key="buscar_hist")
    df_filtrado = df_hist[df_hist["Producto"].str.contains(buscar_h.upper(), case=False)] if buscar_h else df_hist
    st.dataframe(df_filtrado, use_container_width=True)

    st.subheader("📅 Ventas por fecha")
    fechas = df_hist["Fecha"].unique()
    fecha_sel = st.selectbox("Seleccionar fecha", sorted(fechas, reverse=True))
    st.dataframe(df_hist[df_hist["Fecha"] == fecha_sel], use_container_width=True)

    st.subheader("📈 Gráfica de ventas")
    st.line_chart(df_hist.groupby("Fecha")["Vendidos"].sum())

    st.subheader("🥐 Producto más vendido")
    top_productos = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False)
    if not top_productos.empty:
        st.metric(label="Producto más vendido", value=top_productos.index[0], delta=f"{int(top_productos.iloc[0])} vendidos")
        st.bar_chart(top_productos)
