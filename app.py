import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Champlitte MX", page_icon="🥐", layout="wide")

# Estilo CSS Ultra-Limpio
st.markdown("""
    <style>
        .main { background-color: #f4f7f6; }
        .stTabs [data-baseweb="tab-list"] { gap: 20px; }
        .stTabs [data-baseweb="tab"] {
            font-weight: bold; font-size: 20px;
            color: #555; border-radius: 10px 10px 0 0;
            padding: 12px 40px; background-color: #e0e0e0;
        }
        .stTabs [aria-selected="true"] { 
            background-color: #FF4B4B !important; color: white !important;
        }
        .stMetric { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #ddd; }
        div[data-testid="stExpander"] { background-color: white; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()
numero_whatsapp = "522283530069"

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan_v3.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME)')
c.execute('CREATE TABLE IF NOT EXISTS log_movimientos (tipo TEXT, nombre TEXT, cantidad INTEGER, fecha DATETIME)')
conn.commit()

# ------------------ LOGICA ------------------
def registrar_log(tipo, nombre, cantidad):
    c.execute("INSERT INTO log_movimientos VALUES (?, ?, ?, ?)", (tipo, nombre, cantidad, ahora_mx.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0

# ------------------ SIDEBAR ------------------
with st.sidebar:
    st.title("🥐 Champlitte MX")
    st.write(f"📅 **{ahora_mx.strftime('%d/%m/%Y | %H:%M')}**")
    st.divider()
    with st.expander("⚙️ Ajustes Críticos"):
        if st.checkbox("Confirmar Limpieza Total"):
            if st.button("🗑️ BORRAR TODA LA BASE"):
                for t in ["captura_actual", "base_anterior", "historial_ventas", "log_movimientos"]:
                    c.execute(f"DELETE FROM {t}")
                conn.commit()
                st.rerun()

# ------------------ DISEÑO DE DOS TABS ------------------
tab_operacion, tab_control = st.tabs(["⚡ OPERACIÓN DIARIA", "📊 CONTROL Y ARCHIVO"])

# --- TAB 1: REGISTRO Y CORTE (TODO LO QUE IMPORTA HOY) ---
with tab_operacion:
    col_reg, col_corte = st.columns([1.2, 0.8], gap="large")

    with col_reg:
        st.subheader("📝 Registrar Pan en Estante")
        buscar = st.text_input("🔍 Buscar pan...", placeholder="Escribe el nombre...").upper()
        
        # Sugerencias dinámicas
        nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
        sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev
        
        c1, c2 = st.columns(2)
        with c1:
            prod_sel = st.selectbox("Producto:", sugerencias) if sugerencias else buscar
        with c2:
            cad_sel = st.date_input("Caducidad:", value=fecha_hoy_mx)

        # Botonera rápida
        b1, b2, b3, b4, b5 = st.columns(5)
        if b1.button("＋1"): st.session_state.conteo_temp += 1
        if b2.button("＋5"): st.session_state.conteo_temp += 5
        if b3.button("＋10"): st.session_state.conteo_temp += 10
        if b4.button("＋20"): st.session_state.conteo_temp += 20
        if b5.button("Limpiar", type="secondary"): st.session_state.conteo_temp = 0

        st.metric("Piezas por añadir:", st.session_state.conteo_temp)

        if st.button("📥 GUARDAR EN LISTA TEMPORAL", use_container_width=True, type="primary"):
            if prod_sel and st.session_state.conteo_temp > 0:
                nombre_f = str(prod_sel).strip().upper()
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_f, str(cad_sel), st.session_state.conteo_temp))
                registrar_log("REGISTRO", nombre_f, st.session_state.conteo_temp)
                st.session_state.conteo_temp = 0
                st.toast(f"✅ {nombre_f} anotado")
                st.rerun()

    with col_corte:
        st.subheader("🚀 Finalizar y Enviar")
        st.info("Al presionar el botón, se calcularán las ventas y se actualizará el inventario.")
        
        if st.button("🔥 GENERAR CORTE DE VENTAS", use_container_width=True, type="primary"):
            df_act = pd.read_sql("SELECT * FROM captura_actual", conn)
            if df_act.empty:
                st.error("No hay nada registrado para cortar.")
            else:
                df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
                ts = ahora_mx.strftime("%Y-%m-%d %H:%M")
                ventas_list = []
                
                for _, ant in df_ant.iterrows():
                    res = c.execute("SELECT SUM(cantidad) FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                    quedan = res[0] if res[0] else 0
                    vendidos = ant['cantidad'] - quedan
                    if vendidos > 0:
                        ventas_list.append(f"• {ant['nombre']}: *{vendidos}*")
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, max(0, vendidos), ts))
                
                # Actualización de Base
                c.execute("DELETE FROM base_anterior")
                c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                
                # WhatsApp automático
                res_txt = "\n".join(ventas_list) if ventas_list else "Sin ventas detectadas."
                msg = f"📊 *CORTE CHAMPLITTE*\n📅 {fecha_hoy_mx}\n{'-'*15}\n{res_txt}\n{'-'*15}\n✅ *LISTO*"
                st.session_state['last_msg'] = msg
                st.balloons()
                st.rerun()

        if 'last_msg' in st.session_state:
            st.success("¡Corte generado!")
            st.link_button("📲 ENVIAR REPORTE WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(st.session_state['last_msg'])}", use_container_width=True)
            if st.button("Cerrar Aviso"): del st.session_state['last_msg']; st.rerun()

    st.divider()
    # Tabla de revisión rápida
    df_rev = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, cantidad as Cantidad FROM captura_actual", conn)
    if not df_rev.empty:
        st.write("**📋 Revisión de Captura (Lo que hay ahora en estante):**")
        st.dataframe(df_rev, use_container_width=True, hide_index=True)

# --- TAB 2: INVENTARIO, HISTORIAL Y LOGS (TODO LO ARCHIVADO) ---
with tab_control:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 Stock Actual")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM base_anterior", conn)
        if not df_inv.empty:
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
            st.metric("Total en Tienda", int(df_inv['Cant'].sum()))
        else:
            st.info("Inventario vacío.")

    with col2:
        st.subheader("🥐 Más Vendidos")
        df_h = pd.read_sql("SELECT nombre, SUM(vendidos) as total FROM historial_ventas GROUP BY nombre ORDER BY total DESC LIMIT 5", conn)
        if not df_h.empty:
            st.bar_chart(df_h.set_index("nombre"))
        else:
            st.info("Sin historial.")

    st.divider()
    st.subheader("📜 Bitácora de Movimientos")
    df_logs = pd.read_sql("SELECT fecha as Hora, tipo as Acción, nombre as Producto, cantidad as Cant FROM log_movimientos ORDER BY fecha DESC LIMIT 50", conn)
    st.dataframe(df_logs, use_container_width=True, hide_index=True)

# ------------------ FOOTER ------------------
st.sidebar.caption("v3.0 | Optimizado para Champlitte MX")
