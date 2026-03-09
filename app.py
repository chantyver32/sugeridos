import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Champlitte MX v3.5", page_icon="🥐", layout="wide")

# Estilo CSS Maestro (Combinación de limpieza y énfasis)
st.markdown("""
    <style>
        .main { background-color: #f4f7f6; }
        .stTabs [data-baseweb="tab-list"] { gap: 20px; }
        .stTabs [data-baseweb="tab"] {
            font-weight: bold; font-size: 18px;
            color: #555; border-radius: 10px 10px 0 0;
            padding: 12px 40px; background-color: #e8e8e8;
            transition: 0.3s;
        }
        .stTabs [aria-selected="true"] { 
            background-color: #FF4B4B !important; color: white !important;
            box-shadow: 0px 4px 10px rgba(255, 75, 75, 0.3);
        }
        .stMetric { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #ddd; }
        .stButton>button { border-radius: 8px; font-weight: bold; }
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
c.execute('CREATE TABLE IF NOT EXISTS log_movimientos (tipo TEXT, nombre TEXT, cantidad INTEGER, fecha DATETIME)')
conn.commit()

# ------------------ FUNCIONES ESPECIALES ------------------
def sonido_click():
    st.markdown('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3"></audio>', unsafe_allow_html=True)

def registrar_log(tipo, nombre, cantidad):
    c.execute("INSERT INTO log_movimientos VALUES (?, ?, ?, ?)", (tipo, nombre, cantidad, ahora_mx.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0

# ------------------ SIDEBAR ------------------
with st.sidebar:
    st.title("🥐 Champlitte Admin")
    st.write(f"📅 **{ahora_mx.strftime('%d/%m/%Y | %H:%M')}**")
    st.divider()
    with st.expander("⚙️ Gestión de Base de Datos"):
        confirmar = st.checkbox("Confirmar Reseteo")
        if st.button("🗑️ BORRAR TODO", use_container_width=True):
            if confirmar:
                for t in ["captura_actual", "base_anterior", "historial_ventas", "log_movimientos"]:
                    c.execute(f"DELETE FROM {t}")
                conn.commit()
                st.rerun()

# ------------------ SISTEMA DE DOS PESTAÑAS ------------------
tab_operacion, tab_control = st.tabs(["⚡ REGISTRO Y CORTE", "📊 INVENTARIO Y RESULTADOS"])

# --- PESTAÑA 1: OPERACIÓN DIARIA ---
with tab_operacion:
    col_reg, col_corte = st.columns([1.1, 0.9], gap="large")

    with col_reg:
        st.subheader("📝 Nuevo Registro")
        buscar = st.text_input("🔎 Buscar o escribir producto...", key="busq").upper()
        
        # Lógica de sugerencias
        nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
        sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev
        
        c1, c2 = st.columns(2)
        with c1:
            prod_sel = st.selectbox("Seleccionar:", sugerencias) if sugerencias else buscar
        with c2:
            cad_sel = st.date_input("Caducidad:", value=fecha_hoy_mx)

        # Botonera Rápida con Sonido
        st.write("🔢 **Cantidad a sumar:**")
        k1, k2, k3, k4, k5 = st.columns(5)
        if k1.button("＋1"): st.session_state.conteo_temp += 1; sonido_click()
        if k2.button("＋5"): st.session_state.conteo_temp += 5; sonido_click()
        if k3.button("＋10"): st.session_state.conteo_temp += 10; sonido_click()
        if k4.button("＋20"): st.session_state.conteo_temp += 20; sonido_click()
        if k5.button("Borrar", type="secondary"): st.session_state.conteo_temp = 0

        st.metric("Total por subir", f"{st.session_state.conteo_temp} pzas")

        if st.button("➕ REGISTRAR EN LISTA", use_container_width=True, type="primary"):
            if prod_sel and st.session_state.conteo_temp > 0:
                nombre_f = str(prod_sel).strip().upper()
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_f, str(cad_sel), st.session_state.conteo_temp))
                registrar_log("REGISTRO", nombre_f, st.session_state.conteo_temp)
                st.session_state.conteo_temp = 0
                st.toast(f"✅ {nombre_f} añadido", icon="🥐")
                conn.commit()
                st.rerun()

    with col_corte:
        st.subheader("🚀 Finalizar Jornada")
        st.info("Esto comparará el stock anterior con lo registrado hoy para calcular ventas.")
        
        if st.button("🔥 EJECUTAR CORTE DE VENTAS", use_container_width=True, type="primary"):
            df_act = pd.read_sql("SELECT * FROM captura_actual", conn)
            if df_act.empty:
                st.error("No hay datos en la lista actual.")
            else:
                df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
                ts = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
                ventas_list = []
                
                for _, ant in df_ant.iterrows():
                    # Buscar si el producto sigue en el estante hoy
                    res = c.execute("SELECT SUM(cantidad) FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                    quedan = res[0] if res[0] is not None else 0
                    vendidos = ant['cantidad'] - quedan
                    
                    if vendidos > 0:
                        ventas_list.append(f"🍞 *{ant['nombre']}*: {vendidos} vend.")
                    
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", 
                             (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, max(0, vendidos), ts))
                
                # Rotar Inventario
                c.execute("DELETE FROM base_anterior")
                c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                
                # Crear Reporte
                res_txt = "\n".join(ventas_list) if ventas_list else "Sin ventas registradas."
                msg = f"📊 *REPORTE CHAMPLITTE*\n📅 {fecha_hoy_mx}\n{'-'*15}\n{res_txt}\n{'-'*15}\n✅ *CORTE FINALIZADO*"
                st.session_state['msg_wa'] = msg
                st.balloons()
                st.rerun()

        if 'msg_wa' in st.session_state:
            with st.container(border=True):
                st.success("¡Ventas calculadas con éxito!")
                st.link_button("📲 ENVIAR POR WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(st.session_state['msg_wa'])}", use_container_width=True)
                if st.button("Cerrar Aviso"): del st.session_state['msg_wa']; st.rerun()

    st.divider()
    # Revisión en tiempo real de lo que se está capturando
    df_temp = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Cant FROM captura_actual", conn)
    if not df_temp.empty:
        st.write("📋 **Lista actual (Por procesar):**")
        st.dataframe(df_temp, use_container_width=True, hide_index=True)

# --- PESTAÑA 2: CONTROL Y ARCHIVO ---
with tab_control:
    col_inv, col_top = st.columns(2)
    
    with col_inv:
        st.subheader("📦 Stock en Tienda")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM base_anterior", conn)
        if not df_inv.empty:
            st.metric("Total de piezas en estante", int(df_inv['Cant'].sum()))
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
            
            # Alerta de Caducidad Hoy
            df_hoy = df_inv[df_inv['[Cad.]'] == str(fecha_hoy_mx)]
            if not df_hoy.empty:
                st.error(f"⚠️ RETIRAR HOY: {int(df_hoy['Cant'].sum())} piezas")
        else:
            st.info("No hay inventario registrado.")

    with col_top:
        st.subheader("🏆 Más Vendidos (Histórico)")
        df_h = pd.read_sql("SELECT nombre, SUM(vendidos) as total FROM historial_ventas GROUP BY nombre ORDER BY total DESC LIMIT 5", conn)
        if not df_h.empty:
            st.bar_chart(df_h.set_index("nombre"))
        else:
            st.info("Esperando datos del primer corte...")

    st.divider()
    with st.expander("📜 Ver Bitácora de Movimientos y Ventas"):
        df_full = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
        st.dataframe(df_full, use_container_width=True)

# ------------------ FOOTER ------------------
st.sidebar.markdown("---")
st.sidebar.caption("Champlitte MX | Smart Inventory v3.5")
