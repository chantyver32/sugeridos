import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Champlitte Pro", page_icon="🥐", layout="wide")

# --- ESTILOS CSS PARA UN LOOK MODERNO ---
st.markdown("""
    <style>
    /* Fondo y tipografía */
    .main { background-color: #f8f9fa; }
    
    /* Estilo de los Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 10px 10px 0px 0px;
        padding: 10px 20px;
        font-weight: bold;
    }

    /* Botones principales */
    .stButton>button {
        border-radius: 12px;
        height: 3.5em;
        background-color: #ffffff;
        color: #1f1f1f;
        border: 1px solid #ddd;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
    }
    
    /* Botón de Guardar / Corte */
    div[data-testid="stFormSubmitButton"] button, .main-btn button {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
    }

    /* Tarjetas de información */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE BASE DE DATOS ---
zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

conn = sqlite3.connect('champlitte_v3.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# --- INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["➕ REGISTRAR", "📦 STOCK / CORTE", "📊 HISTORIAL"])

with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    # Selector de productos con memoria
    sugerencias = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    with st.container():
        col_main, col_side = st.columns([2, 1])
        
        with col_main:
            st.markdown("### 🥖 ¿Qué pan estás contando?")
            nombre_input = st.selectbox("Selecciona:", [""] + sugerencias, label_visibility="collapsed")
            nombre_nuevo = st.text_input("O escribe uno nuevo:", placeholder="NOMBRE DEL PRODUCTO").upper()
            nombre_final = nombre_nuevo if nombre_nuevo else nombre_input

        with col_side:
            st.markdown("### 📅 Caducidad")
            f_cad = st.date_input("Fecha:", value=fecha_hoy_mx, label_visibility="collapsed")

    st.markdown("---")
    
    # Teclado Numérico Estilo Punto de Venta
    st.markdown(f"<div style='text-align: center;'><h1>🔢 {st.session_state.conteo_temp} piezas</h1></div>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("＋ 1"): st.session_state.conteo_temp += 1
    if c2.button("＋ 5"): st.session_state.conteo_temp += 5
    if c3.button("＋ 10"): st.session_state.conteo_temp += 10
    if c4.button("❌ BORRAR"): st.session_state.conteo_temp = 0

    if st.button("📥 GUARDAR EN LISTA", type="primary", use_container_width=True):
        if nombre_final and st.session_state.conteo_temp > 0:
            c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final.strip().upper(), str(f_cad), int(st.session_state.conteo_temp)))
            conn.commit()
            st.toast(f"Agregado: {nombre_final}")
            st.session_state.conteo_temp = 0
            time.sleep(0.5)
            st.rerun()
    
    # Lista rápida de lo que se va capturando
    df_cap = pd.read_sql("SELECT rowid as id, nombre, cantidad FROM captura_actual", conn)
    if not df_cap.empty:
        with st.expander("📝 Ver lista de captura actual", expanded=True):
            st.dataframe(df_cap, hide_index=True, use_container_width=True)
            if st.button("🗑️ Vaciar lista de captura"):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

with tab2:
    # Resumen de inventario actual
    df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📦 Stock en Tienda")
        if not df_ant.empty:
            st.dataframe(df_ant, use_container_width=True, hide_index=True)
        else:
            st.info("No hay stock registrado. Realiza un corte para iniciar.")

    with col2:
        st.markdown("### ⚠️ Caducan Hoy")
        df_vence = df_ant[df_ant['fecha_cad'] <= str(fecha_hoy_mx)]
        if not df_vence.empty:
            st.error(f"¡Atención! Hay {df_vence['cantidad'].sum()} piezas por vencer.")
            st.table(df_vence[['nombre', 'cantidad']])
        else:
            st.success("Sin caducidades para hoy.")

    st.markdown("---")
    st.markdown("### 🏁 Finalizar Turno")
    st.write("Esto comparará lo que 'Había' contra lo que acabas de 'Registrar' para calcular las ventas.")
    
    if st.button("🚀 HACER CORTE Y ENVIAR WHATSAPP", type="primary", use_container_width=True):
        df_hoy = pd.read_sql("SELECT nombre, fecha_cad, SUM(cantidad) as total FROM captura_actual GROUP BY nombre, fecha_cad", conn)
        
        if df_hoy.empty:
            st.warning("⚠️ No has registrado nada nuevo en la pestaña REGISTRAR.")
        else:
            ts = datetime.now(zona_mx).strftime("%d/%m %H:%M")
            reporte = f"📊 *CORTE CHAMPLITTE* ({ts})\n"
            reporte += "--------------------------\n"
            
            for _, ant in df_ant.iterrows():
                match = df_hoy[(df_hoy['nombre'] == ant['nombre']) & (df_hoy['fecha_cad'] == ant['fecha_cad'])]
                quedan = int(match['total'].values[0]) if not match.empty else 0
                vendidos = ant['cantidad'] - quedan
                
                if vendidos > 0:
                    c.execute("INSERT INTO historial_ventas VALUES (?,?,?,?,?,?)", 
                              (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, vendidos, ts))
                    reporte += f"🥐 *{ant['nombre']}*: {vendidos} vendidos\n"

            # Reemplazar stock anterior con lo contado hoy
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT nombre, fecha_cad, cantidad FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            
            st.balloons()
            st.link_button("📲 ENVIAR REPORTE A WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(reporte)}", use_container_width=True)
            time.sleep(1)

with tab3:
    st.markdown("### 📊 Historial de Movimientos")
    df_h = pd.read_sql("SELECT * FROM historial_ventas ORDER BY rowid DESC LIMIT 100", conn)
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True, hide_index=True)
        if st.button("🗑️ Limpiar Todo el Historial"):
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.rerun()
    else:
        st.info("Aún no hay ventas registradas.")
