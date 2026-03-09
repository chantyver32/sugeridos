import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Estilo para reducir espacios superiores ya que no hay título
st.markdown("""
    <style>
        .block-container {padding-top: 1rem;}
        [data-testid="stMetricValue"] {font-size: 1.8rem;}
    </style>
""", unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

mensaje_global = st.empty()

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME
)''')
conn.commit()

# ------------------ FUNCIONES ------------------
def sonido_click():
    st.markdown('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

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

# ------------------ SIDEBAR ------------------
st.sidebar.header("⚙️ Configuración")
with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar borrar todo el historial")
    if st.button("⚠️ RESET TOTAL", type="secondary", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.sidebar.success("Sistema reiniciado.")
        else:
            st.sidebar.error("Confirma primero.")

# ------------------ TABS (SIN TÍTULOS EXTERNOS) ------------------
tab1, tab2, tab3 = st.tabs(["📝 REGISTRO DE PRODUCTOS", "📦 CORTE E INVENTARIO", "📊 ANÁLISIS"])

with tab1:
    # Lógica de estados
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state: st.session_state.buscar_prod = ""

    def limpiar_buscador():
        st.session_state.buscar_prod = ""
        if "sel_prod" in st.session_state: del st.session_state["sel_prod"]

    # Buscador optimizado
    col_busq, col_limpiar = st.columns([4, 1])
    with col_busq:
        buscar = st.text_input("Buscador", placeholder="🔎 ESCRIBE EL NOMBRE DEL PRODUCTO...", key="buscar_prod", label_visibility="collapsed").upper()
    with col_limpiar:
        st.button("🧹 Limpiar", on_click=limpiar_buscador, use_container_width=True)

    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        nombre_input = st.selectbox("Sugerencias:", sugerencias, key="sel_prod") if sugerencias else buscar
        if not sugerencias and buscar: st.info("✨ Producto nuevo detectado")

    with col2:
        f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)

    with col3:
        st.metric("A sumar:", st.session_state.conteo_temp)

    # Botonera de conteo
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("0", use_container_width=True, on_click=resetear)

    if st.button("➕ REGISTRAR EN LISTA (ILIMITADO)", use_container_width=True, type="primary"):
        if nombre_input and str(nombre_input).strip() != "":
            nombre_final = str(nombre_input).strip().upper()
            cant = st.session_state.conteo_temp
            # Guardar en DB inmediatamente
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, str(f_cad))).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, str(f_cad)))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(cant)))
            conn.commit()
            st.session_state.conteo_temp = 0
            st.toast(f"✅ {nombre_final} guardado")
            st.rerun()

    # Tabla de captura actual
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM captura_actual", conn)
    if not df_hoy_captura.empty:
        st.write("---")
        st.subheader("📋 Lista Actual (Sin procesar)")
        df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button("💾 Actualizar Cambios Manuales", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['Producto']:
                        c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (fila['Producto'].strip().upper(), str(fila['Fecha Cad']), int(fila['Cantidad'])))
                conn.commit()
                st.rerun()
        with col_clear:
            if st.button("🗑️ Vaciar Lista Visual (Borrar captura)", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

with tab2:
    st.subheader("🏁 Finalizar Jornada")
    if st.button("🚀 REALIZAR CORTE FINAL Y COMPARAR VENTAS", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actualizado.empty:
            st.warning("⚠️ La lista de registro está vacía.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_list = []
            
            if not df_anterior.empty:
                for _, ant in df_anterior.iterrows():
                    res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                    cant_hoy = res_hoy[0] if res_hoy else 0
                    diff = ant['cantidad'] - cant_hoy
                    if diff > 0:
                        ventas_list.append({"Producto": ant['nombre'], "Caducidad": ant['fecha_cad'], "Había": ant['cantidad'], "Quedan": cant_hoy, "VENDIDOS": diff})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (ant['nombre'], ant['fecha_cad'], ant['cantidad'], cant_hoy, (diff if diff > 0 else 0), ts_mx))

            st.session_state['ultimo_corte'] = pd.DataFrame(ventas_list)
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.balloons()
            st.rerun()

    if 'ultimo_corte' in st.session_state:
        with st.container(border=True):
            st.subheader("📊 Ventas Detectadas en este Corte")
            df_v = st.session_state['ultimo_corte']
            st.table(df_v)
            if st.button("Cerrar Resumen", use_container_width=True):
                del st.session_state['ultimo_corte']
                st.rerun()

    # Alertas y Estado
    c_alert, c_inv = st.columns(2)
    with c_alert:
        st.subheader("⚠️ Caducan Hoy")
        df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        if not df_cad.empty:
            st.error(f"Retirar {int(df_cad['cantidad'].sum())} piezas")
            st.dataframe(df_cad, use_container_width=True, hide_index=True)
        else:
            st.success("Sin caducidades")

    with c_inv:
        st.subheader("🏪 Inventario Real")
        df_inv = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM base_anterior", conn)
        if not df_inv.empty:
            st.metric("Total en tienda", int(df_inv['cantidad'].sum()))
            st.dataframe(df_inv, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("📈 Análisis Histórico")
    df_hist = pd.read_sql("SELECT * FROM historial_ventas", conn)
    if not df_hist.empty:
        df_hist['fecha_corte'] = pd.to_datetime(df_hist['fecha_corte'])
        st.line_chart(df_hist.groupby(df_hist['fecha_corte'].dt.date)['vendidos'].sum())
        st.dataframe(df_hist.sort_values('fecha_corte', ascending=False), use_container_width=True)
    else:
        st.info("Sin datos suficientes.")
