import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Champlitte MX v4", page_icon="🥐", layout="wide")

# Mantenemos tu estilo visual preferido
st.markdown("""
    <style>
        .main { background-color: #f4f7f6; }
        .stTabs [data-baseweb="tab-list"] { gap: 20px; }
        .stTabs [data-baseweb="tab"] {
            font-weight: bold; font-size: 19px; color: #555;
            background-color: #e0e0e0; border-radius: 10px 10px 0 0;
            padding: 10px 30px;
        }
        .stTabs [aria-selected="true"] { 
            background-color: #FF4B4B !important; color: white !important;
        }
        .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; }
    </style>
""", unsafe_allow_html=True)

# Variables de tiempo y contacto
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

# ------------------ FUNCIONES ESENCIALES ------------------
def sonido_click():
    st.markdown('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3"></audio>', unsafe_allow_html=True)

if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0

# ------------------ ESTRUCTURA DE DOS TABS ------------------
tab_operacion, tab_historial = st.tabs(["⚡ OPERACIÓN Y CORTE", "📊 ANALÍTICA Y CONTROL"])

# --- TAB 1: OPERACIÓN (TODO LO QUE NECESITAS PARA EL DÍA) ---
with tab_operacion:
    col_reg, col_corte = st.columns([1.2, 0.8], gap="large")

    with col_reg:
        st.header(f"📝 Registro Diario - {fecha_hoy_mx.strftime('%d/%m/%Y')}")
        
        # Buscador Esencial
        buscar = st.text_input("🔍 Buscar pan...", placeholder="Escribe para buscar o añadir nuevo...").upper()
        
        nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
        sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

        c1, c2 = st.columns(2)
        with c1:
            nombre_input = st.selectbox("Producto:", sugerencias) if sugerencias else buscar
        with c2:
            f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)

        # Teclado Numérico con Sonido
        st.write("**Cantidad:**")
        k1, k2, k3, k4, k5 = st.columns(5)
        if k1.button("＋1"): st.session_state.conteo_temp += 1; sonido_click()
        if k2.button("＋5"): st.session_state.conteo_temp += 5; sonido_click()
        if k3.button("＋10"): st.session_state.conteo_temp += 10; sonido_click()
        if k4.button("＋20"): st.session_state.conteo_temp += 20; sonido_click()
        if k5.button("Borrar", type="secondary"): st.session_state.conteo_temp = 0; sonido_click()

        st.metric("Total por registrar", st.session_state.conteo_temp)

        if st.button("➕ AGREGAR AL CONTEO", use_container_width=True, type="primary"):
            if nombre_input and st.session_state.conteo_temp > 0:
                nombre_final = str(nombre_input).strip().upper()
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), st.session_state.conteo_temp))
                conn.commit()
                st.session_state.conteo_temp = 0
                st.toast(f"✅ {nombre_final} añadido")
                st.rerun()

    with col_corte:
        st.header("🏁 Realizar Corte")
        st.write("Calcula ventas del día comparando con el inventario anterior.")
        
        if st.button("🚀 PROCESAR CORTE Y VENTAS", use_container_width=True, type="primary"):
            df_act = pd.read_sql("SELECT * FROM captura_actual", conn)
            if df_act.empty:
                st.error("No hay registros hoy para comparar.")
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
                st.session_state['reporte_hoy'] = "\n".join(ventas_wa) if ventas_wa else "Sin ventas registradas hoy."
                st.balloons()
                st.rerun()

        # Reporte de WhatsApp Dinámico
        if 'reporte_hoy' in st.session_state:
            with st.container(border=True):
                st.success("✅ ¡Corte finalizado!")
                msg = f"📊 *CORTE CHAMPLITTE*\n📅 {fecha_hoy_mx}\n{'-'*15}\n{st.session_state['reporte_hoy']}\n{'-'*15}\n🥐 *Listo*"
                st.link_button("📲 ENVIAR REPORTE WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg)}", use_container_width=True)
                if st.button("Limpiar Pantalla"): del st.session_state['reporte_hoy']; st.rerun()

    st.divider()
    # Revisión rápida en la misma pestaña
    col_inv, col_alerta = st.columns(2)
    with col_inv:
        st.subheader("🏠 Inventario Real en Tienda")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM base_anterior", conn)
        st.dataframe(df_inv, use_container_width=True, hide_index=True)
        if not df_inv.empty: st.metric("Piezas totales", int(df_inv['Cant'].sum()))
    
    with col_alerta:
        st.subheader("⚠️ Caducan Hoy")
        df_hoy = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        if not df_hoy.empty:
            st.error(f"⚠️ Retirar {int(df_hoy['cantidad'].sum())} piezas")
            st.dataframe(df_hoy, use_container_width=True, hide_index=True)
        else: st.success("✅ Nada caduca hoy")

# --- TAB 2: HISTORIAL Y ANÁLISIS (CONTROL TOTAL) ---
with tab_historial:
    st.header("📊 Análisis Histórico")
    df_h = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    
    if not df_h.empty:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.write("**Top 5 Productos más vendidos**")
            top = df_h.groupby("nombre")["vendidos"].sum().sort_values(ascending=False).head(5)
            st.bar_chart(top)
        with c2:
            st.write("**Ventas por día**")
            df_h['fecha_solo'] = pd.to_datetime(df_h['fecha_corte']).dt.date
            linea = df_h.groupby("fecha_solo")["vendidos"].sum()
            st.line_chart(linea)

        st.subheader("📜 Bitácora Completa")
        st.dataframe(df_h, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay datos históricos.")

# ------------------ SIDEBAR RESET ------------------
with st.sidebar:
    st.title("Admin ⚙️")
    if st.checkbox("Habilitar zona de peligro"):
        if st.button("🗑️ BORRAR TODA LA BASE DE DATOS"):
            c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.rerun()
