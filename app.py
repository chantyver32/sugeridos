import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
mensaje_global = st.empty()
zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

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
    """Muestra un mensaje verde temporal"""
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
tab1, tab2 = st.tabs(["📦 Inventario", "📊 Análisis de Ventas"])

# ------------------ TAB 1: INVENTARIO ------------------
with tab1:
    st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state:
        st.session_state.buscar_prod = ""

    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]

    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
    # Input con autocompletado y botón de tache
    buscar_input = st.text_input(
        "🔎 Buscar o escribir producto",
        value=st.session_state.get("buscar_prod", ""),
        key="buscar_prod_input"
    )

    # Botón de tache
    if st.button("❌", key="limpiar_buscar"):
        st.session_state.buscar_prod = ""
        st.session_state.buscar_prod_input = ""
        buscar_input = ""
    
    # Actualizar variable de sesión
    st.session_state.buscar_prod = buscar_input

    # Autocompletado
    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]
    sugerencias = [p for p in nombres_prev if st.session_state.buscar_prod.upper() in p.upper()]

    # Mostrar selectbox solo si hay sugerencias
    if sugerencias:
        nombre_input = st.selectbox(
            "Sugerencias",
            [""] + sugerencias,
            index=0,
            key="sel_prod"
        )
        if nombre_input != "":
            st.session_state.buscar_prod = nombre_input
    else:
        nombre_input = st.session_state.buscar_prod

    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key="date_cad")

    with col3:
        st.write("Cantidad que ves")

    # Botones de suma
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("Borrar", use_container_width=True, on_click=resetear)

    st.metric("Total contado", st.session_state.conteo_temp)

    # ------------------ REGISTRAR PRODUCTO ------------------
    cant = st.session_state.conteo_temp
    if st.button("➕ Registrar en el Conteo", use_container_width=True, type="primary"):
        if nombre_input and nombre_input.strip() != "":
            nombre_final = nombre_input.strip().upper()
            existe = c.execute(
                "SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                (nombre_final, f_cad)
            ).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?",
                          (int(cant), nombre_final, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
            conn.commit()
            sonido_click()
            mostrar_exito("✅ Producto agregado")
            st.session_state.conteo_temp = 0

    # ------------------ TABLA EDITABLE ------------------
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if not df_hoy_captura.empty:
        df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
        st.subheader("📋 Revisión del conteo (Edita o elimina filas aquí):")
        df_editado = st.data_editor(
            df_hoy_captura,
            column_config={
                "rowid": None,
                "nombre": st.column_config.TextColumn("Producto"),
                "fecha_cad": st.column_config.DateColumn("Fecha Caducidad"),
                "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0)
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="editor_conteo"
        )
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("💾 Guardar cambios realizados arriba", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['nombre']:
                        c.execute(
                            "INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)",
                            (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad']))
                        )
                conn.commit()
                mostrar_exito("💾 Conteo actualizado")
        with col_cancel:
            if st.button("🗑️ Borrar TODO el conteo actual", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                mostrar_exito("🗑️ Conteo borrado")

    # ------------------ PASO 2: CORTE Y COMPARACIÓN ------------------
    st.divider()
    st.header("🏁 Paso 2: Finalizar y Calcular Ventas")
    if "mostrar_resumen" not in st.session_state:
        st.session_state['mostrar_resumen'] = False

    if st.button("REALIZAR CORTE Y REINICIAR FORMULARIO", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actualizado.empty:
            mostrar_exito("⚠️ No hay nada en el conteo para comparar.")
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
                st.session_state['mostrar_resumen'] = True

            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            mostrar_exito("🏁 Corte realizado y guardado en el historial con éxito")

    # ------------------ RESUMEN DE VENTAS ------------------
    resumen_container = st.container()
    with resumen_container:
        if st.session_state.get('ultimo_corte') is not None and st.session_state['mostrar_resumen']:
            if 'globos_mostrados' not in st.session_state:
                st.balloons()
                st.session_state['globos_mostrados'] = True

            st.subheader("📊 Resumen de ventas detectadas:")
            df_ventas = st.session_state['ultimo_corte']
            st.table(df_ventas)

            mensaje = "📊 *CORTE DE VENTAS CHAMPLITTE*\n"
            mensaje += f"📅 Fecha: {fecha_hoy_mx.strftime('%d/%m/%Y')}\n"
            mensaje += "---------------------------------\n\n"

            for _, row in df_ventas.iterrows():
                mensaje += (
                    f"🍞 *{row['Producto']}*\n"
                    f"📅 Cad: {row['Caducidad']}\n"
                    f"📥 Había: {row['Había']} | 📤 Quedan: {row['Quedan']}\n"
                    f"💰 *VENDIDOS: {row['VENDIDOS']}*\n"
                    "---------------------------------\n"
                )

            link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"
            col_wa, col_close = st.columns(2)
            with col_wa:
                st.link_button("📲 Enviar reporte por WhatsApp", link, use_container_width=True)
            with col_close:
                if st.button("Cerrar Resumen", key="cerrar_resumen", use_container_width=True):
                    st.session_state['mostrar_resumen'] = False

# ------------------ TAB 2: ANÁLISIS ------------------
with tab2:
    st.header("📊 Análisis de Ventas")
    df_hist = pd.read_sql(
        """SELECT nombre as Producto, fecha_cad as Caducidad, habia as Habia, quedan as Quedan,
           vendidos as Vendidos, fecha_corte as Fecha_Hora FROM historial_ventas""",
        conn
    )

    if df_hist.empty:
        st.info("No hay historial de ventas todavía.")
        st.stop()

    df_hist['Fecha_Hora'] = pd.to_datetime(df_hist['Fecha_Hora'])
    df_hist['Fecha'] = df_hist['Fecha_Hora'].dt.date

    # BUSCADOR
    st.subheader("🔎 Buscar en historial")
    buscar = st.text_input("Buscar producto", key="buscar_hist")
    if buscar:
        df_filtrado = df_hist[df_hist["Producto"].str.contains(buscar.upper(), case=False)]
    else:
        df_filtrado = df_hist
    st.dataframe(df_filtrado, use_container_width=True)

    # FILTRO POR FECHA
    st.subheader("📅 Ventas por fecha")
    fechas = df_hist["Fecha"].unique()
    fecha_sel = st.selectbox("Seleccionar fecha", sorted(fechas, reverse=True))
    df_fecha = df_hist[df_hist["Fecha"] == fecha_sel]
    st.dataframe(df_fecha, use_container_width=True)

    # HISTORIAL POR DÍA
    st.subheader("📊 Historial por día")
    ventas_dia = df_hist.groupby("Fecha")["Vendidos"].sum().reset_index()
    st.dataframe(ventas_dia, use_container_width=True)

    # GRAFICA
    st.subheader("📈 Gráfica de ventas")
    grafica = df_hist.groupby("Fecha")["Vendidos"].sum()
    st.line_chart(grafica)

    # PRODUCTO MÁS VENDIDO
    st.subheader("🥐 Producto más vendido")
    top_productos = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False)
    if not top_productos.empty:
        producto_top = top_productos.index[0]
        cantidad_top = int(top_productos.iloc[0])
        st.metric(label="Producto más vendido", value=producto_top, delta=f"{cantidad_top} vendidos")
        st.bar_chart(top_productos)

