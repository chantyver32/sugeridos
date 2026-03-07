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
tab1, tab2, tab3 = st.tabs(["📝 Añadir productos", "📦 Inventario", "📊 Análisis de Ventas"])

with tab1:
    # ------------------ PASO 1: CAPTURA FÍSICA ------------------
    st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

    # Inicializar estados de sesión
    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state:
        st.session_state.buscar_prod = ""

    # Función para limpiar buscador
    def limpiar_buscador():
        st.session_state.buscar_prod = ""
        if "sel_prod" in st.session_state:
            del st.session_state["sel_prod"]

    # --- BUSCADOR Y BOTÓN LIMPIAR ---
    col_busq, col_limpiar = st.columns([3, 1])
    with col_busq:
        buscar = st.text_input("🔎 Buscar o escribir producto", key="buscar_prod").upper()
    
    with col_limpiar:
        st.write("##") # Alineación
        st.button("🧹 Limpiar Texto", on_click=limpiar_buscador, use_container_width=True)

    # --- LÓGICA DE FILTRADO ---
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

    # Botones de suma
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("Borrar Cantidad", use_container_width=True, on_click=resetear)

    st.metric("Total contado", st.session_state.conteo_temp)

    # ------------------ REGISTRAR PRODUCTO ------------------
    if st.button("➕ Registrar en el Conteo", use_container_width=True, type="primary"):
        if nombre_input and nombre_input.strip() != "":
            nombre_final = nombre_input.strip().upper()
            cant = st.session_state.conteo_temp
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
        st.write("---")
        df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
        st.subheader("📋 Revisión del conteo:")
        df_editado = st.data_editor(
            df_hoy_captura,
            column_config={
                "rowid": None,
                "nombre": st.column_config.TextColumn("Producto"),
                "fecha_cad": st.column_config.DateColumn("Fecha Caducidad"),
                "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0)
            },
            num_rows="dynamic", use_container_width=True, hide_index=True, key="editor_conteo"
        )
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("💾 Guardar cambios", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['nombre']:
                        c.execute("INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)",
                                 (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
                conn.commit()
                mostrar_exito("💾 Conteo actualizado")
        with col_cancel:
            if st.button("🗑️ Borrar TODO el conteo", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

with tab2:
    # ------------------ PASO 2: CORTE Y COMPARACIÓN ------------------
    st.header("🏁 Paso 2: Finalizar y Calcular Ventas")
    
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
                    res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?",
                                      (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                    cant_hoy = res_hoy[0] if res_hoy else 0
                    diferencia = fila_ant['cantidad'] - cant_hoy
                    if diferencia > 0:
                        ventas_detectadas.append({
                            "Producto": fila_ant['nombre'], "Caducidad": fila_ant['fecha_cad'],
                            "Había": fila_ant['cantidad'], "Quedan": cant_hoy, "VENDIDOS": diferencia
                        })
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)",
                             (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']),
                              int(cant_hoy), int(diferencia), ts_mx))

            if ventas_detectadas:
                st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)
                st.session_state['mostrar_resumen'] = True

            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            mostrar_exito("🏁 Corte realizado con éxito")

    # --- RESUMEN, ALERTAS E INVENTARIO (Dentro de tab2) ---
    if st.session_state.get('mostrar_resumen'):
        st.balloons()
        st.subheader("📊 Resumen de ventas detectadas:")
        df_v = st.session_state['ultimo_corte']
        st.table(df_v)
        if st.button("Cerrar Resumen"):
            st.session_state['mostrar_resumen'] = False
            st.rerun()

    st.divider()
    c_l, c_r = st.columns(2)
    with c_l:
        st.header("⚠️ Alertas de Caducidad")
        df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", 
                           conn, params=(fecha_hoy_mx.strftime('%Y-%m-%d'),))
        if not df_cad.empty:
            st.error(f"Retirar {int(df_cad['cantidad'].sum())} piezas.")
            st.dataframe(df_cad, use_container_width=True)
        else:
            st.success("✅ Sin caducidades hoy.")

    with c_r:
        st.header("🏪 Inventario Actual")
        df_inv = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM base_anterior", conn)
        st.dataframe(df_inv, use_container_width=True)

with tab3:
    # ------------------ ANÁLISIS (TAB 3) ------------------
    st.header("📊 Análisis de Ventas")
    df_hist = pd.read_sql("SELECT * FROM historial_ventas", conn)
    if not df_hist.empty:
        st.line_chart(df_hist.groupby("fecha_corte")["vendidos"].sum())
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Sin datos históricos.")
    # ---------------- BUSCADOR ----------------
    st.subheader("🔎 Buscar en historial")
    buscar = st.text_input("Buscar producto", key="buscar_hist")
    if buscar:
        df_filtrado = df_hist[df_hist["Producto"].str.contains(buscar.upper(), case=False)]
    else:
        df_filtrado = df_hist
    st.dataframe(df_filtrado, use_container_width=True)

    # ---------------- FILTRO POR FECHA ----------------
    st.subheader("📅 Ventas por fecha")
    fechas = df_hist["Fecha"].unique()
    fecha_sel = st.selectbox("Seleccionar fecha", sorted(fechas, reverse=True))
    df_fecha = df_hist[df_hist["Fecha"] == fecha_sel]
    st.dataframe(df_fecha, use_container_width=True)

    # ---------------- HISTORIAL POR DIA ----------------
    st.subheader("📊 Historial por día")
    ventas_dia = df_hist.groupby("Fecha")["Vendidos"].sum().reset_index()
    st.dataframe(ventas_dia, use_container_width=True)

    # ---------------- GRAFICA ----------------
    st.subheader("📈 Gráfica de ventas")
    grafica = df_hist.groupby("Fecha")["Vendidos"].sum()
    st.line_chart(grafica)

    # ---------------- PRODUCTO MÁS VENDIDO ----------------
    st.subheader("🥐 Producto más vendido")
    top_productos = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False)
    if not top_productos.empty:
        producto_top = top_productos.index[0]
        cantidad_top = int(top_productos.iloc[0])
        st.metric(label="Producto más vendido", value=producto_top, delta=f"{cantidad_top} vendidos")
        st.bar_chart(top_productos)

