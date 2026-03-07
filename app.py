import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# CSS PARA QUITAR ESPACIOS EN BLANCO Y COMPACTAR INTERFAZ
st.markdown("""
    <style>
        /* Eliminar márgenes superiores y reducir espacios */
        .block-container {padding-top: 1rem; padding-bottom: 0rem;}
        div[data-testid="stVerticalBlock"] > div {margin-top: -1rem;}
        .stTabs [data-baseweb="tab-list"] {gap: 5px;}
        .stMetric {padding: 5px; background-color: #f0f2f6; border-radius: 10px;}
        /* Ajustar tamaño de botones en móvil */
        .stButton button {margin-bottom: 2px;}
    </style>
""", unsafe_allow_html=True)

mensaje_global = st.empty()
zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

st.title("Inventario Champlitte 🥐")

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
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

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

# Función para cerrar resumen de un solo clic
def cerrar_resumen():
    if 'ultimo_corte' in st.session_state:
        del st.session_state['ultimo_corte']

# ------------------ SIDEBAR ------------------
st.sidebar.header("⚙️ Configuración")
with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar borrado total")
    if st.button("⚠️ EJECUTAR RESET TOTAL"):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.sidebar.success("Base limpia.")
            st.rerun()

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 Añadir productos", "📦 Inventario", "📊 Análisis"])

with tab1:
    st.header(f"Paso 1: Conteo ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    if "buscar_prod" not in st.session_state: st.session_state.buscar_prod = ""

    def limpiar_buscador():
        st.session_state.buscar_prod = ""
        if "sel_prod" in st.session_state: del st.session_state["sel_prod"]

    col_busq, col_limpiar = st.columns([3, 1])
    with col_busq:
        buscar = st.text_input("🔎 Buscar producto", key="buscar_prod").upper()
    with col_limpiar:
        st.write("##") 
        st.button("🧹 Limpiar", on_click=limpiar_buscador, use_container_width=True)

    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        nombre_input = st.selectbox("Sugerencias:", sugerencias, key="sel_prod") if sugerencias else buscar
    with col2:
        f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    with col3:
        st.metric("Contado", st.session_state.conteo_temp)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("0", use_container_width=True, on_click=resetear)

    if st.button("➕ Registrar en el Conteo", use_container_width=True, type="primary"):
        if nombre_input and nombre_input.strip() != "":
            nombre_final = nombre_input.strip().upper()
            cant = st.session_state.conteo_temp
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
            conn.commit()
            st.session_state.conteo_temp = 0
            st.rerun()

    # TABLA EDITABLE UNIFICADA
    df_hoy_captura = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if not df_hoy_captura.empty:
        st.write("---")
        df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
        
        with st.form("editor_conteo_form"):
            df_editado = st.data_editor(df_hoy_captura, num_rows="dynamic", use_container_width=True, hide_index=True)
            c_save, c_del = st.columns(2)
            if c_save.form_submit_button("💾 Guardar cambios", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['nombre']:
                        c.execute("INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)", (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
                conn.commit()
                st.rerun()
            if c_del.form_submit_button("🗑️ Borrar Todo", use_container_width=True):
                c.execute("DELETE FROM captura_actual"); conn.commit(); st.rerun()

with tab2:
    st.header("🏁 Finalizar y Calcular Ventas")
    if st.button("REALIZAR CORTE Y REINICIAR", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actualizado.empty:
            st.warning("No hay conteo actual.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ventas_detectadas = []
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            if not df_anterior.empty:
                for _, fila_ant in df_anterior.iterrows():
                    res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                    cant_hoy = res_hoy[0] if res_hoy else 0
                    diferencia = fila_ant['cantidad'] - cant_hoy
                    if diferencia > 0:
                        ventas_detectadas.append({"Producto": fila_ant['nombre'], "Caducidad": fila_ant['fecha_cad'], "Había": fila_ant['cantidad'], "Quedan": cant_hoy, "VENDIDOS": diferencia})
                        c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']), int(cant_hoy), int(diferencia), ts_mx))
            if ventas_detectadas:
                st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)
            c.execute("DELETE FROM base_anterior"); c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual"); c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.rerun()

    if 'ultimo_corte' in st.session_state:
        st.balloons()
        st.subheader("📊 Resumen de Ventas")
        df_ventas = st.session_state['ultimo_corte']
        st.table(df_ventas)
        
        mensaje = f"📊 *CORTE CHAMPLITTE* {fecha_hoy_mx}\n"
        for _, row in df_ventas.iterrows():
            mensaje += f"🍞 *{row['Producto']}* | V: {row['VENDIDOS']}\n"
        
        link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"
        col_wa, col_close = st.columns(2)
        col_wa.link_button("📲 WhatsApp", link, use_container_width=True)
        col_close.button("Cerrar Resumen", use_container_width=True, on_click=cerrar_resumen)

    st.divider()
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("⚠️ Caducan Hoy")
        df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        if not df_cad.empty:
            st.error(f"Retirar {int(df_cad['cantidad'].sum())} pzas")
            st.dataframe(df_cad, use_container_width=True, hide_index=True)
        else: st.success("Todo OK")

    with col_right:
        st.subheader("📦 Inventario Actual")
        df_est = pd.read_sql("SELECT nombre, cantidad FROM base_anterior", conn)
        if not df_est.empty:
            st.metric("Piezas en tienda", int(df_est['cantidad'].sum()))
            st.dataframe(df_est, use_container_width=True, hide_index=True)

with tab3:
    st.header("📊 Análisis")
    df_hist = pd.read_sql("SELECT * FROM historial_ventas", conn)
    if not df_hist.empty:
        df_hist['fecha_corte'] = pd.to_datetime(df_hist['fecha_corte'])
        st.line_chart(df_hist.groupby(df_hist['fecha_corte'].dt.date)['vendidos'].sum())
        st.dataframe(df_hist.sort_values(by='fecha_corte', ascending=False), use_container_width=True)
    else:
        st.info("Sin datos.")
