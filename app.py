import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Champlitte MX v4", page_icon="🥐", layout="wide")

# Estilo visual Champlitte
st.markdown("""
    <style>
        .main { background-color: #f4f7f6; }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            font-weight: bold; font-size: 16px; color: #444;
            background-color: #e8e8e8; border-radius: 8px 8px 0 0;
            padding: 10px 20px;
        }
        .stTabs [aria-selected="true"] { 
            background-color: #FF4B4B !important; color: white !important;
        }
        .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; }
    </style>
""", unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()
numero_whatsapp = "522283530069"

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan_final.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ FUNCIONES ------------------
def sonido_click():
    st.markdown('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3"></audio>', unsafe_allow_html=True)

if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0

# ------------------ TABS (LOS TRES PASOS) ------------------
tab1, tab2, tab3 = st.tabs(["📝 1. AÑADIR PRODUCTOS", "📦 2. CORTE E INVENTARIO", "📊 3. ANÁLISIS Y MOVIMIENTOS"])

# --- TAB 1: AÑADIR PRODUCTOS ---
with tab1:
    st.header(f"📝 Registro de Conteo ({fecha_hoy_mx.strftime('%d/%m/%Y')})")
    
    col_input, col_preview = st.columns([1.2, 0.8], gap="large")

    with col_input:
        buscar = st.text_input("🔍 Buscar pan...", placeholder="Escribe para filtrar o añadir...").upper()
        
        nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
        sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

        c1, c2 = st.columns(2)
        with c1:
            nombre_input = st.selectbox("Producto:", sugerencias) if sugerencias else buscar
        with c2:
            f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)

        st.write("**Teclado Numérico:**")
        k1, k2, k3, k4, k5 = st.columns(5)
        if k1.button("＋1"): st.session_state.conteo_temp += 1; sonido_click()
        if k2.button("＋5"): st.session_state.conteo_temp += 5; sonido_click()
        if k3.button("＋10"): st.session_state.conteo_temp += 10; sonido_click()
        if k4.button("＋20"): st.session_state.conteo_temp += 20; sonido_click()
        if k5.button("Cero", type="secondary"): st.session_state.conteo_temp = 0

        st.metric("Total por registrar", st.session_state.conteo_temp)

        if st.button("➕ AGREGAR A LA LISTA", use_container_width=True, type="primary"):
            if nombre_input and st.session_state.conteo_temp > 0:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (str(nombre_input).strip().upper(), str(f_cad), st.session_state.conteo_temp))
                conn.commit()
                st.session_state.conteo_temp = 0
                st.toast("✅ Producto añadido")
                st.rerun()

    with col_preview:
        st.subheader("📋 Lista Actual")
        df_hoy = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM captura_actual", conn)
        st.dataframe(df_hoy, use_container_width=True, hide_index=True)
        if not df_hoy.empty:
            if st.button("🗑️ Vaciar lista"):
                c.execute("DELETE FROM captura_actual"); conn.commit(); st.rerun()

# --- TAB 2: CORTE E INVENTARIO ---
with tab2:
    st.header("🏁 Procesar Corte de Ventas")
    
    col_acc, col_inv = st.columns([1, 1], gap="large")

    with col_acc:
        st.info("Al presionar este botón, compararemos lo que había con lo que acabas de contar.")
        if st.button("🚀 EJECUTAR CORTE Y GENERAR REPORTE", use_container_width=True, type="primary"):
            df_cap = pd.read_sql("SELECT * FROM captura_actual", conn)
            if df_cap.empty:
                st.warning("⚠️ Primero añade productos en el Paso 1.")
            else:
                df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
                ts = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
                ventas_wa = []
                
                for _, ant in df_ant.iterrows():
                    res = c.execute("SELECT SUM(cantidad) FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                    quedan = res[0] if res[0] is not None else 0
                    vendidos = ant['cantidad'] - quedan
                    if vendidos > 0:
                        ventas_wa.append(f"• *{ant['nombre']}*: {vendidos} vend.")
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, max(0, vendidos), ts))
                
                c.execute("DELETE FROM base_anterior"); c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual"); c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.session_state['msg_reporte'] = "\n".join(ventas_wa) if ventas_wa else "Sin ventas nuevas."
                st.balloons()
                st.rerun()

        if 'msg_reporte' in st.session_state:
            st.success("✅ Corte exitoso")
            msg_final = f"📊 *CORTE CHAMPLITTE*\n📅 {fecha_hoy_mx}\n{'-'*15}\n{st.session_state['msg_reporte']}\n{'-'*15}\n✅ *Listo*"
            st.link_button("📲 ENVIAR REPORTE WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg_final)}", use_container_width=True)
            if st.button("Cerrar Aviso"): del st.session_state['msg_reporte']; st.rerun()

    with col_inv:
        st.subheader("🏪 Inventario Real en Tienda")
        df_stock = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM base_anterior", conn)
        st.dataframe(df_stock, use_container_width=True, hide_index=True)
        
        # Alerta de Caducidad
        df_cad = df_stock[df_stock['[Cad.]'] == str(fecha_hoy_mx)]
        if not df_cad.empty:
            st.error(f"⚠️ RETIRAR HOY: {int(df_cad['Cant'].sum())} pzas")

# --- TAB 3: ANÁLISIS Y MOVIMIENTOS ---
with tab3:
    st.header("📊 Historial y Rendimiento")
    df_h = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    
    if not df_h.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Top 5 Vendidos**")
            st.bar_chart(df_h.groupby("nombre")["vendidos"].sum().sort_values(ascending=False).head(5))
        with c2:
            st.write("**Ventas por día**")
            df_h['fecha'] = pd.to_datetime(df_h['fecha_corte']).dt.date
            st.line_chart(df_h.groupby("fecha")["vendidos"].sum())

        st.subheader("📜 Bitácora Completa")
        st.dataframe(df_h, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos registrados.")

# --- SIDEBAR ---
with st.sidebar:
    st.title("Admin ⚙️")
    if st.checkbox("Zona Peligro"):
        if st.button("🗑️ RESET DB"):
            c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas"); conn.commit(); st.rerun()
