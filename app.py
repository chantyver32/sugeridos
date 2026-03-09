import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Estilo para eliminar espacios superiores y mejorar la estética de los tabs
st.markdown("""
    <style>
        .block-container {padding-top: 1rem;}
        .stTabs [data-baseweb="tab-list"] {gap: 8px;}
        .stTabs [data-baseweb="tab"] {
            background-color: #f0f2f6;
            border-radius: 4px 4px 0px 0px;
            padding: 10px 20px;
        }
        .stTabs [aria-selected="true"] {background-color: #e1e4e8 !important;}
    </style>
""", unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME
)''')
conn.commit()

# ------------------ FUNCIONES AUXILIARES ------------------
def sonido_click():
    st.markdown('<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

def sumar(valor):
    st.session_state.conteo_temp += valor
    sonido_click()

def resetear():
    st.session_state.conteo_temp = 0
    sonido_click()

# ------------------ SIDEBAR ------------------
st.sidebar.header("⚙️ Panel de Control")
with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar borrado total")
    if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.rerun()

# ------------------ TABS PRINCIPALES ------------------
tab1, tab2, tab3 = st.tabs(["📝 REGISTRO DE PRODUCTOS", "📦 CORTE E INVENTARIO", "📊 ANÁLISIS DE VENTAS"])

# --- TAB 1: REGISTRO (CAPTURA ILIMITADA) ---
with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    col_busq, col_limpiar = st.columns([4, 1])
    with col_busq:
        buscar = st.text_input("Buscar", placeholder="🔎 ESCRIBE EL NOMBRE DEL PAN...", key="buscar_prod", label_visibility="collapsed").upper()
    with col_limpiar:
        if st.button("🧹 Limpiar", use_container_width=True):
            st.session_state.buscar_prod = ""
            st.rerun()

    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        nombre_input = st.selectbox("Producto:", sugerencias, key="sel_prod") if sugerencias else buscar
    with c2:
        f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    with c3:
        st.metric("A registrar:", st.session_state.conteo_temp)

    # Botones de conteo rápido
    b1, b2, b3, b4 = st.columns(4)
    with b1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with b2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with b3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with b4: st.button("Borrar", use_container_width=True, on_click=resetear)

    if st.button("➕ GUARDAR EN LISTA TEMPORAL", use_container_width=True, type="primary"):
        if nombre_input:
            nombre_f = str(nombre_input).strip().upper()
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_f, str(f_cad))).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(st.session_state.conteo_temp), nombre_f, str(f_cad)))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_f, str(f_cad), int(st.session_state.conteo_temp)))
            conn.commit()
            st.session_state.conteo_temp = 0
            st.toast(f"✅ {nombre_f} añadido a la lista")
            st.rerun()

    # Mostrar lo que se lleva capturado
    df_captura = pd.read_sql("SELECT rowid, nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM captura_actual", conn)
    if not df_captura.empty:
        st.divider()
        st.subheader("📋 Productos listos para el corte")
        df_editado = st.data_editor(df_captura, column_config={"rowid": None}, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        ca, cb = st.columns(2)
        with ca:
            if st.button("💾 Guardar cambios en lista", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, f in df_editado.iterrows():
                    if f['Producto']: c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (f['Producto'].upper(), str(f['Fecha Cad']), int(f['Cantidad'])))
                conn.commit()
                st.rerun()
        with cb:
            if st.button("🗑️ Vaciar toda la lista", use_container_width=True):
                c.execute("DELETE FROM captura_actual"); conn.commit(); st.rerun()

# --- TAB 2: CORTE, WHATSAPP E INVENTARIO ---
with tab2:
    st.subheader("🏁 Procesar Corte de Ventas")
    if st.button("🚀 FINALIZAR Y CALCULAR VENTAS DEL DÍA", type="primary", use_container_width=True):
        df_act = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_act.empty:
            st.warning("⚠️ No hay productos en la lista del Tab 1 para comparar.")
        else:
            df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_hoy = []
            
            for _, ant in df_ant.iterrows():
                res = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                quedan = res[0] if res else 0
                vendidos = ant['cantidad'] - quedan
                if vendidos > 0:
                    ventas_hoy.append({"Producto": ant['nombre'], "Caducidad": ant['fecha_cad'], "Había": ant['cantidad'], "Quedan": quedan, "VENDIDOS": vendidos})
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, (vendidos if vendidos > 0 else 0), ts))
            
            st.session_state['resumen_corte'] = pd.DataFrame(ventas_hoy)
            c.execute("DELETE FROM base_anterior"); c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual"); c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.balloons()
            st.rerun()

    # Resumen de ventas y Botón WhatsApp
    if 'resumen_corte' in st.session_state:
        with st.container(border=True):
            st.subheader("📊 Resumen del Corte")
            df_v = st.session_state['resumen_corte']
            st.table(df_v)
            
            msg = f"📊 *CORTE CHAMPLITTE* - {fecha_hoy_mx}\n"
            for _, r in df_v.iterrows():
                msg += f"🍞 {r['Producto']} | V: *{r['VENDIDOS']}*\n"
            
            st.link_button("📲 Enviar reporte por WhatsApp", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg)}", use_container_width=True)
            if st.button("Cerrar Resumen"): del st.session_state['resumen_corte']; st.rerun()

    st.divider()
    
    # Alertas y Estado Actual
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("⚠️ Caducan Hoy")
        df_cad = pd.read_sql("SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        if not df_cad.empty:
            st.error(f"Retirar {int(df_cad['Cantidad'].sum())} piezas")
            st.dataframe(df_cad, use_container_width=True, hide_index=True)
            msg_cad = "⚠️ *CADUCIDADES HOY*\n" + "\n".join([f"- {r['Producto']}: {r['Cantidad']}" for _, r in df_cad.iterrows()])
            st.link_button("📲 Avisar Caducidad", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg_cad)}", use_container_width=True)
        else:
            st.success("✅ Sin productos por caducar hoy")

    with col_b:
        st.subheader("🏪 Inventario en Tienda")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad], cantidad as Cantidad FROM base_anterior", conn)
        if not df_inv.empty:
            st.metric("Piezas en estante", int(df_inv['Cantidad'].sum()))
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
        else:
            st.info("Inventario vacío.")

# --- TAB 3: ANÁLISIS ---
with tab3:
    st.subheader("📈 Historial y Rendimiento")
    df_h = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    
    if not df_h.empty:
        # Gráfica de Ventas
        df_h['fecha_corte'] = pd.to_datetime(df_h['fecha_corte'])
        ventas_diarias = df_h.groupby(df_h['fecha_corte'].dt.date)['vendidos'].sum()
        st.line_chart(ventas_diarias)
        
        # Top Productos
        st.subheader("🥐 Productos más vendidos")
        top = df_h.groupby("nombre")["vendidos"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top)
        
        # Buscador en historial
        st.subheader("🔍 Historial Completo")
        busc_h = st.text_input("Filtrar historial por nombre:").upper()
        df_f = df_h[df_h['nombre'].str.contains(busc_h)] if busc_h else df_h
        st.dataframe(df_f, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay datos históricos para mostrar.")
