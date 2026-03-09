import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

# 1. CONFIGURACIÓN Y ESTILO (TODO EN UNA PANTALLA)
st.set_page_config(page_title="Champlitte MX", page_icon="🥐", layout="wide")

st.markdown("""
    <style>
        .block-container {padding-top: 1rem;}
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            font-weight: bold; font-size: 18px; color: #555;
            background-color: #f0f2f6; border-radius: 10px 10px 0 0;
            padding: 8px 20px;
        }
        .stTabs [aria-selected="true"] { background-color: #FF4B4B !important; color: white !important; }
        .stMetric { background-color: white; border: 1px solid #eee; padding: 10px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# 2. VARIABLES DE ENTORNO
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy = ahora_mx.date()
whatsapp = "522283530069"

# 3. BASE DE DATOS (CONEXIÓN SEGURA)
conn = sqlite3.connect('champlitte_v4.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS stock (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial (nombre TEXT, cant_ant INTEGER, cant_hoy INTEGER, vendidos INTEGER, fecha DATETIME)')
conn.commit()

# 4. ESTADO DE SESIÓN (EVITA ERRORES DE REFRESCO)
if "conteo" not in st.session_state: st.session_state.conteo = 0

# --- ESTRUCTURA DE DOS TABS ---
tab_registro, tab_reportes = st.tabs(["📝 REGISTRO Y CORTE", "📊 INVENTARIO Y RESULTADOS"])

# --- TAB 1: REGISTRO (OPERACIÓN RÁPIDA) ---
with tab_registro:
    col_izq, col_der = st.columns([1.2, 0.8], gap="medium")

    with col_izq:
        st.subheader("🥐 Registrar Pan")
        # Buscador dinámico
        db_nombres = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM stock").fetchall()]
        busc = st.text_input("🔍 Buscar pan...", placeholder="Escribe nombre...").upper()
        
        sug = [n for n in db_nombres if busc in n] if busc else db_nombres
        
        c1, c2 = st.columns(2)
        with c1:
            prod = st.selectbox("Producto:", sug) if sug else busc
        with c2:
            cad = st.date_input("Caducidad:", value=fecha_hoy)

        # Botones de cantidad
        k1, k2, k3, k4 = st.columns(4)
        if k1.button("＋1", use_container_width=True): st.session_state.conteo += 1
        if k2.button("＋5", use_container_width=True): st.session_state.conteo += 5
        if k3.button("＋10", use_container_width=True): st.session_state.conteo += 10
        if k4.button("Reset", type="secondary", use_container_width=True): st.session_state.conteo = 0

        st.metric("Cantidad a Guardar", st.session_state.conteo)

        if st.button("📥 GUARDAR EN LISTA", type="primary", use_container_width=True):
            if prod and st.session_state.conteo > 0:
                # Usamos una tabla temporal en sesión para no saturar la DB antes del corte
                if "lista_hoy" not in st.session_state: st.session_state.lista_hoy = []
                st.session_state.lista_hoy.append({"Producto": str(prod).upper(), "Caducidad": str(cad), "Cantidad": st.session_state.conteo})
                st.session_state.conteo = 0
                st.toast(f"✅ Añadido: {prod}")
            else:
                st.warning("Selecciona producto y cantidad.")

    with col_der:
        st.subheader("🚀 Finalizar Corte")
        if "lista_hoy" in st.session_state and st.session_state.lista_hoy:
            df_temp = pd.DataFrame(st.session_state.lista_hoy)
            st.dataframe(df_temp, use_container_width=True, hide_index=True)
            
            if st.button("🔥 EJECUTAR CORTE Y ENVIAR WA", type="primary", use_container_width=True):
                # LÓGICA DE COMPARACIÓN
                ventas_txt = []
                for item in st.session_state.lista_hoy:
                    # Buscar cuánto había antes en la DB
                    ant = c.execute("SELECT cantidad FROM stock WHERE nombre=? AND fecha_cad=?", (item['Producto'], item['Caducidad'])).fetchone()
                    cant_ant = ant[0] if ant else 0
                    vendidos = max(0, cant_ant - item['Cantidad'])
                    
                    if vendidos > 0:
                        ventas_txt.append(f"• {item['Producto']}: {vendidos} vend.")
                    
                    # Guardar en Historial
                    c.execute("INSERT INTO historial VALUES (?,?,?,?,?)", 
                             (item['Producto'], cant_ant, item['Cantidad'], vendidos, ahora_mx.strftime("%Y-%m-%d %H:%M")))
                
                # Actualizar Stock Real
                c.execute("DELETE FROM stock") # Limpiamos para el nuevo día
                for item in st.session_state.lista_hoy:
                    c.execute("INSERT INTO stock VALUES (?,?,?)", (item['Producto'], item['Caducidad'], item['Cantidad']))
                
                conn.commit()
                
                # Generar mensaje WhatsApp
                res_final = "\n".join(ventas_txt) if ventas_txt else "Sin ventas nuevas."
                msg_wa = f"📊 *CORTE CHAMPLITTE*\n📅 {fecha_hoy}\n{'-'*15}\n{res_final}\n{'-'*15}\n✅ *CORTE LISTO*"
                
                st.session_state.reporte_wa = msg_wa
                del st.session_state.lista_hoy
                st.balloons()
                st.rerun()
        else:
            st.info("La lista de captura está vacía.")

        if "reporte_wa" in st.session_state:
            st.link_button("📲 ENVIAR REPORTE WHATSAPP", f"https://wa.me/{whatsapp}?text={urllib.parse.quote(st.session_state.reporte_wa)}", use_container_width=True)
            if st.button("Limpiar Pantalla"): del st.session_state.reporte_wa; st.rerun()

# --- TAB 2: REPORTES (CONTROL TOTAL) ---
with tab_reportes:
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("📦 Stock en Tienda")
        df_stock = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM stock", conn)
        if not df_stock.empty:
            st.metric("Total Piezas", int(df_stock['Cant'].sum()))
            st.dataframe(df_stock, use_container_width=True, hide_index=True)
        else: st.write("No hay pan en estantes.")

    with c2:
        st.subheader("🏆 Más Vendidos")
        df_top = pd.read_sql("SELECT nombre, SUM(vendidos) as total FROM historial GROUP BY nombre ORDER BY total DESC LIMIT 5", conn)
        if not df_top.empty: st.bar_chart(df_top.set_index("nombre"))
        else: st.write("Sin datos.")

    st.divider()
    st.subheader("📜 Historial de Movimientos")
    df_hist = pd.read_sql("SELECT * FROM historial ORDER BY fecha DESC LIMIT 30", conn)
    st.dataframe(df_hist, use_container_width=True, hide_index=True)

# SIDEBAR PARA RESET
with st.sidebar:
    st.title("Admin 🥐")
    if st.checkbox("Habilitar Borrado Total"):
        if st.button("🗑️ RESET DB"):
            c.execute("DELETE FROM stock"); c.execute("DELETE FROM historial"); conn.commit()
            st.rerun()
