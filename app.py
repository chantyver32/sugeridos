import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Champlitte Pro", page_icon="🥐", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 10px 10px 0px 0px;
        padding: 8px 16px;
        font-weight: bold;
        border: 1px solid #eee;
    }
    .stButton>button {
        border-radius: 12px;
        transition: all 0.3s;
    }
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #eee;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE BASE DE DATOS ---
def get_connection():
    conn = sqlite3.connect('champlitte_v4.db', check_same_thread=False)
    return conn

conn = get_connection()
c = conn.cursor()

# Tablas actualizadas para mejor trazabilidad
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte TEXT)')
conn.commit()

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

# --- INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["➕ REGISTRAR INVENTARIO", "📦 STOCK / CORTE", "📊 HISTORIAL"])

with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    # Obtener lista de nombres conocidos para el selectbox
    sugerencias = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col_main, col_side = st.columns([2, 1])
    with col_main:
        st.markdown("### 🥖 Producto")
        nombre_input = st.selectbox("Existentes:", [""] + sorted(sugerencias), label_visibility="collapsed")
        nombre_nuevo = st.text_input("O nuevo:", placeholder="NOMBRE DEL PRODUCTO").upper()
        nombre_final = nombre_nuevo if nombre_nuevo else nombre_input

    with col_side:
        st.markdown("### 📅 Caducidad")
        f_cad = st.date_input("Vence el:", value=fecha_hoy_mx, label_visibility="collapsed")

    # Teclado Numérico
    st.markdown(f"<div class='metric-card'><h1>🔢 {st.session_state.conteo_temp} piezas</h1></div>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("＋ 1", use_container_width=True): st.session_state.conteo_temp += 1
    if c2.button("＋ 5", use_container_width=True): st.session_state.conteo_temp += 5
    if c3.button("＋ 10", use_container_width=True): st.session_state.conteo_temp += 10
    if c4.button("❌ BORRAR", use_container_width=True): st.session_state.conteo_temp = 0

    if st.button("📥 AGREGAR A LISTA DE CONTEO", type="primary", use_container_width=True):
        if nombre_final and st.session_state.conteo_temp > 0:
            # Si el producto y fecha ya están en captura, sumarlos en lugar de duplicar fila
            c.execute("SELECT cantidad FROM captura_actual WHERE nombre = ? AND fecha_cad = ?", (nombre_final.strip().upper(), str(f_cad)))
            existente = c.fetchone()
            if existente:
                nueva_cant = existente[0] + st.session_state.conteo_temp
                c.execute("UPDATE captura_actual SET cantidad = ? WHERE nombre = ? AND fecha_cad = ?", (nueva_cant, nombre_final.strip().upper(), str(f_cad)))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final.strip().upper(), str(f_cad), int(st.session_state.conteo_temp)))
            
            conn.commit()
            st.toast(f"✅ {nombre_final} registrado")
            st.session_state.conteo_temp = 0
            time.sleep(0.5)
            st.rerun()
        else:
            st.warning("Falta nombre o cantidad.")

    # Mostrar lo capturado actualmente
    df_cap = pd.read_sql("SELECT rowid as id, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if not df_cap.empty:
        with st.exp
