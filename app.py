import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Estilo para ocultar títulos y ajustar márgenes
st.markdown("""
    <style>
    .stApp [data-testid="stHeader"] {display:none;}
    .block-container {padding-top: 2rem;}
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
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def sumar(valor):
    st.session_state.conteo_temp += valor
    sonido_click()

def resetear_contador():
    st.session_state.conteo_temp = 0

def mostrar_exito(mensaje, duracion=2):
    mensaje_global.success(mensaje)
    time.sleep(duracion)
    mensaje_global.empty()

# ------------------ SIDEBAR ------------------
st.sidebar.header("⚙️ Configuración")
with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar borrar TODO el historial", key="check_reset")
    if st.button("⚠️ EJECUTAR RESET TOTAL", type="secondary", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.sidebar.success("Base de datos limpiada.")
            st.rerun()

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 AÑADIR PRODUCTOS", "📦 INVENTARIO Y CORTE", "📊 ANÁLISIS"])

with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    # Buscador optimizado
    col_busq, col_limpiar = st.columns([4, 1])
    with col_busq:
        buscar = st.text_input("Buscador", placeholder="🔎 BUSCAR O ESCRIBIR PRODUCTO...", key="buscar_prod", label_visibility="collapsed").upper()
    with col_limpiar:
        if st.button("🧹 Limpiar", use_container_width=True):
            st.session_state.buscar_prod = ""
            st.rerun()

    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        nombre_input = st.selectbox("Producto:", sugerencias, key="sel_prod") if sugerencias else buscar
    with col2:
        f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    with col3:
        st.metric("A añadir", st.session_state.conteo_temp)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("Borrar Cantidad", use_container_width=True, on_click=resetear_contador)

    if st.button("➕ REGISTRAR EN LISTA TEMPORAL", use_container_width=True, type="primary"):
        if nombre_input and str(nombre_input).strip() != "":
            nombre_final = str(nombre_input).strip().upper()
            cant = st.session_state.conteo_temp
            # Sumar si ya existe en la captura actual para no repetir filas
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, str(f_cad))).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, str(f_cad)))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(cant)))
            conn.commit()
            st.session_state.conteo_temp = 0
            st.toast(f"✅ {nombre_final} en lista")
            st.rerun()

    st.write("---")
    st.subheader("📋 Lista de Captura Actual (Ilimitada)")
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM captura_actual", conn)
    
    if not df_hoy_captura.empty:
        df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        col_s, col_vaciar = st.columns(2)
        with col_s:
            if st.button("💾 Guardar cambios en lista", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['Producto']:
                        c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (fila['Producto'].strip().upper(), str(fila['Fecha Cad']), int(fila['Cantidad'])))
                conn.commit()
                st.success("Lista actualizada")
        with col_vaciar:
            if st.button("🗑️ Vaciar lista sin borrar DB", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

with tab2:
    st.header(f"Corte del día: {fecha_hoy_mx.strftime('%d/%m/%Y')}")
    
    if st.button("🚀 FINALIZAR CAPTURA Y REALIZAR CORTE", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actualizado.empty:
            st.warning("⚠️ La lista de captura está vacía. Agrega productos en la pestaña anterior.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_detectadas = []

            # Comparar inventario anterior con el nuevo conteo
            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                diferencia = fila_ant['cantidad'] - cant_hoy
                
                if diferencia > 0:
                    ventas_detectadas.append({"Producto": fila_ant['nombre'], "Caducidad": fila_ant['fecha_cad'], "Había": fila_ant['cantidad'], "Quedan": cant_hoy, "VENDIDOS": diferencia})
                
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']), int(cant_hoy), int(max(0, diferencia)), ts_mx))

            st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)
            # El conteo de hoy se vuelve la base de mañana
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.balloons()

    if 'ultimo_corte' in st.session_state:
        with st.container(border=True):
            st.subheader("📊 Ventas del Corte")
            df_v = st.session_state['ultimo_corte']
            st.table(df_v)
            if st.button("❌ CERRAR RESUMEN"):
                del st.session_state['ultimo_corte']
                st.rerun()

    col_alert, col_inv = st.columns(2)
    with col_alert:
        st.subheader("⚠️ Caducan Hoy")
        df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        st.dataframe(df_cad, use_container_width=True, hide_index=True) if not df_cad.empty else st.success("Nada caduca hoy")

    with col_inv:
        st.subheader("📦 Stock en Estantes")
        df_inv = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM base_anterior", conn)
        st.dataframe(df_inv, use_container_width=True, hide_index=True)

with tab3:
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    if not df_hist.empty:
        st.subheader("📈 Rendimiento Histórico")
        st.line_chart(df_hist.groupby("fecha_corte")["vendidos"].sum())
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Aún no hay datos de ventas.")
