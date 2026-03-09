import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# --- CONFIGURACIÓN Y PERSISTENCIA ---
st.set_page_config(page_title="Champlitte Pro", page_icon="🥐", layout="wide")

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

# Conexión persistente: Los datos no se borran al cerrar la app
conn = sqlite3.connect('inventario_pan_v2.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME
)''')
conn.commit()

# --- ESTILOS ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📝 REGISTRO", "📦 STOCK Y CORTE", "📊 HISTORIAL"])

with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    # Sugerencias de productos existentes para evitar duplicados
    nombres_sugeridos = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    c_nom, c_f = st.columns([2, 1])
    with c_nom:
        nombre_sel = st.selectbox("Elegir producto:", [""] + nombres_sugeridos)
        nombre_nuevo = st.text_input("O escribir nombre nuevo:").upper()
        nombre_final = nombre_nuevo if nombre_nuevo else nombre_sel

    with c_f:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx)

    st.write(f"### Cantidad: **{st.session_state.conteo_temp}**")
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("+1"): st.session_state.conteo_temp += 1
    if b2.button("+5"): st.session_state.conteo_temp += 5
    if b3.button("+10"): st.session_state.conteo_temp += 10
    if b4.button("BORRAR"): st.session_state.conteo_temp = 0

    if st.button("💾 GUARDAR Y REGISTRAR OTRO", type="primary", use_container_width=True):
        if nombre_final and st.session_state.conteo_temp > 0:
            nombre_final = nombre_final.strip().upper()
            # Insertar en tabla de captura actual (ilimitada)
            c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(st.session_state.conteo_temp)))
            conn.commit()
            st.toast(f"✅ {nombre_final} guardado")
            st.session_state.conteo_temp = 0
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Faltan datos")

    st.divider()
    df_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if not df_captura.empty:
        st.write("📋 **Lista de captura actual (antes del corte):**")
        st.dataframe(df_captura, hide_index=True, use_container_width=True)

with tab2:
    c_inv, c_cad = st.columns(2)
    
    with c_inv:
        st.write("### 📦 Inventario en tienda")
        df_stock = pd.read_sql("SELECT * FROM base_anterior", conn)
        if not df_stock.empty:
            st.dataframe(df_stock, hide_index=True, use_container_width=True)
            msg_stock = "📦 *STOCK CHAMPLITTE*\n" + "\n".join([f"• {r['nombre']}: {r['cantidad']}" for _, r in df_stock.iterrows()])
            st.link_button("📲 Enviar Stock por WA", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg_stock)}")
        else:
            st.info("Sin stock registrado.")

    with c_cad:
        st.write("### ⚠️ Próximos a caducar")
        df_vence = pd.read_sql("SELECT * FROM base_anterior WHERE fecha_cad <= ?", conn, params=(str(fecha_hoy_mx),))
        if not df_vence.empty:
            st.warning(f"Retirar {len(df_vence)} productos.")
            st.table(df_vence)
        else:
            st.success("Nada caduca hoy.")

    st.divider()
    if st.button("🚀 REALIZAR CORTE DE VENTAS (WhatsApp)", type="primary", use_container_width=True):
        df_hoy = pd.read_sql("SELECT nombre, fecha_cad, SUM(cantidad) as total FROM captura_actual GROUP BY nombre, fecha_cad", conn)
        df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
        
        if df_hoy.empty:
            st.warning("No hay conteo nuevo para comparar.")
        else:
            ts = datetime.now(zona_mx).strftime("%d/%m %H:%M")
            reporte = f"📊 *CORTE VENTAS* ({ts})\n"
            
            for _, ant in df_ant.iterrows():
                # Comparar lo que había vs lo que se capturó hoy
                coincidencia = df_hoy[(df_hoy['nombre'] == ant['nombre']) & (df_hoy['fecha_cad'] == ant['fecha_cad'])]
                quedan = int(coincidencia['total'].values[0]) if not coincidencia.empty else 0
                vendidos = ant['cantidad'] - quedan
                
                if vendidos > 0:
                    c.execute("INSERT INTO historial_ventas VALUES (?,?,?,?,?,?)", 
                              (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, vendidos, ts))
                    reporte += f"🥐 *{ant['nombre']}*: Vendidos {vendidos}\n"

            # Actualización física de la base
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT nombre, fecha_cad, cantidad FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            
            st.balloons()
            st.link_button("📲 ENVIAR REPORTE POR WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(reporte)}")
            time.sleep(1)
            st.rerun()

with tab3:
    df_h = pd.read_sql("SELECT * FROM historial_ventas ORDER BY rowid DESC", conn)
    if not df_h.empty:
        st.write("### Historial de Ventas")
        busc = st.text_input("Buscar producto en historial:").upper()
        if busc:
            df_h = df_h[df_h['nombre'].str.contains(busc)]
        st.dataframe(df_h, use_container_width=True)
        
        if st.button("🗑️ Vaciar Historial"):
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.rerun()
    else:
        st.info("No hay ventas registradas aún.")
