import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

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
# Usamos check_same_thread=False para evitar errores en servidores Streamlit
conn = sqlite3.connect('inventario_pan_final.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ ESTADO DE SESIÓN ------------------
if "conteo_temp" not in st.session_state: 
    st.session_state.conteo_temp = 0

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 1. AÑADIR PRODUCTOS", "📦 2. CORTE E INVENTARIO", "📊 3. ANÁLISIS Y MOVIMIENTOS"])

# --- TAB 1: AÑADIR PRODUCTOS ---
with tab1:
    st.header(f"📝 Registro de Conteo ({fecha_hoy_mx.strftime('%d/%m/%Y')})")
    
    col_input, col_preview = st.columns([1.2, 0.8], gap="large")

    with col_input:
        buscar = st.text_input("🔍 Buscar pan...", placeholder="Escribe para filtrar o añadir...").upper()
        
        # Obtener lista de nombres existentes para sugerencias
        res_nombres = c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()
        nombres_prev = [r[0] for r in res_nombres]
        sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

        c1, c2 = st.columns(2)
        with c1:
            # Si hay sugerencias, usamos selectbox, si no, usamos lo que el usuario escribió
            nombre_input = st.selectbox("Selecciona producto:", sugerencias) if sugerencias else buscar
        with c2:
            f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx)

        st.write("**Teclado Numérico:**")
        k1, k2, k3, k4, k5 = st.columns(5)
        if k1.button("＋1"): st.session_state.conteo_temp += 1
        if k2.button("＋5"): st.session_state.conteo_temp += 5
        if k3.button("＋10"): st.session_state.conteo_temp += 10
        if k4.button("＋20"): st.session_state.conteo_temp += 20
        if k5.button("Cero", type="secondary"): st.session_state.conteo_temp = 0

        st.metric("Total por registrar", st.session_state.conteo_temp)

        if st.button("➕ AGREGAR A LA LISTA", use_container_width=True, type="primary"):
            if nombre_input and st.session_state.conteo_temp > 0:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (str(nombre_input).strip().upper(), str(f_cad), st.session_state.conteo_temp))
                conn.commit()
                st.session_state.conteo_temp = 0
                st.rerun()
            else:
                st.warning("Escribe un nombre y una cantidad válida.")

    with col_preview:
        st.subheader("📋 Lista Actual (Por procesar)")
        df_hoy = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM captura_actual", conn)
        st.dataframe(df_hoy, use_container_width=True, hide_index=True)
        if not df_hoy.empty:
            if st.button("🗑️ Vaciar lista"):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

# --- TAB 2: CORTE E INVENTARIO ---
with tab2:
    st.header("🏁 Procesar Corte de Ventas")
    
    col_acc, col_inv = st.columns([1, 1], gap="large")

    with col_acc:
        st.info("El 'Corte' compara lo que había en tienda contra lo que acabas de contar.")
        if st.button("🚀 EJECUTAR CORTE Y GENERAR REPORTE", use_container_width=True, type="primary"):
            df_cap = pd.read_sql("SELECT * FROM captura_actual", conn)
            if df_cap.empty:
                st.warning("⚠️ No hay productos en la lista actual para procesar.")
            else:
                df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
                ts = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
                ventas_wa = []
                
                # Calcular ventas: (Lo que había) - (Lo que hay ahora)
                for _, ant in df_ant.iterrows():
                    # Buscar si el producto que "había" aparece en el "conteo actual"
                    res = c.execute("SELECT SUM(cantidad) FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                    quedan = res[0] if res[0] is not None else 0
                    vendidos = ant['cantidad'] - quedan
                    
                    if vendidos > 0:
                        ventas_wa.append(f"• *{ant['nombre']}*: {vendidos} vend.")
                        c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", 
                                  (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, vendidos, ts))
                
                # Actualizar Base Anterior: Lo que hoy contamos es lo que "habrá" mañana
                c.execute("DELETE FROM base_anterior")
                c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                
                st.session_state['msg_reporte'] = "\n".join(ventas_wa) if ventas_wa else "Sin ventas detectadas."
                st.balloons()
                st.rerun()

        if 'msg_reporte' in st.session_state:
            st.success("✅ Corte realizado con éxito")
            msg_final = f"📊 *CORTE CHAMPLITTE*\n📅 {fecha_hoy_mx}\n{'-'*15}\n{st.session_state['msg_reporte']}\n{'-'*15}\n✅ *Fin del reporte*"
            st.link_button("📲 ENVIAR REPORTE WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg_final)}", use_container_width=True)
            if st.button("Limpiar Pantalla"): 
                del st.session_state['msg_reporte']
                st.rerun()

    with col_inv:
        st.subheader("🏪 Stock Actual en Tienda")
        df_stock = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cant FROM base_anterior", conn)
        st.dataframe(df_stock, use_container_width=True, hide_index=True)
        
        # Alerta de Caducidad
        df_cad = df_stock[df_stock['[Cad.]'] == str(fecha_hoy_mx)]
        if not df_cad.empty:
            st.error(f"⚠️ RETIRAR HOY: {int(df_cad['Cant'].sum())} piezas caducadas")

# --- TAB 3: ANÁLISIS ---
with tab3:
    st.header("📊 Historial y Rendimiento")
    df_h = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    
    if not df_h.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Top 5 Más Vendidos**")
            top_5 = df_h.groupby("nombre")["vendidos"].sum().sort_values(ascending=False).head(5)
            st.bar_chart(top_5)
        with c2:
            st.write("**Ventas por día**")
            df_h['fecha_solo'] = pd.to_datetime(df_h['fecha_corte']).dt.date
            ventas_dia = df_h.groupby("fecha_solo")["vendidos"].sum()
            st.line_chart(ventas_dia)

        st.subheader("📜 Bitácora de Movimientos")
        st.dataframe(df_h, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay datos de ventas procesados.")

# --- SIDEBAR ---
with st.sidebar:
    st.title("Admin ⚙️")
    st.divider()
    if st.checkbox("Habilitar Zona de Peligro"):
        st.warning("Estas acciones no se pueden deshacer.")
        if st.button("🗑️ BORRAR TODA LA BASE DE DATOS"):
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.success("Datos eliminados")
            st.rerun()
