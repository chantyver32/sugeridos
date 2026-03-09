import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Estilo CSS Avanzado (Tu diseño favorito optimizado)
st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom: 2px solid #ddd; }
        .stTabs [data-baseweb="tab"] {
            font-weight: bold;
            font-size: 18px;
            color: #444;
            background-color: #eee;
            border-radius: 8px 8px 0px 0px;
            padding: 10px 25px;
            transition: 0.3s;
        }
        .stTabs [aria-selected="true"] { 
            background-color: #FF4B4B !important; 
            color: white !important;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
        }
        .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #eee; box-shadow: 0px 2px 5px rgba(0,0,0,0.05); }
        .stButton>button { border-radius: 8px; }
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

# ------------------ FUNCIONES DE LOGICA ------------------
def registrar_log(tipo, nombre, cantidad):
    c.execute("INSERT INTO log_movimientos VALUES (?, ?, ?, ?)", (tipo, nombre, cantidad, datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def sumar(valor):
    st.session_state.conteo_temp += valor

def resetear():
    st.session_state.conteo_temp = 0

# ------------------ SIDEBAR ------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/992/992747.png", width=100)
    st.title("🥐 Champlitte Admin")
    st.info(f"📅 Fecha: {fecha_hoy_mx}")
    
    with st.expander("🚨 Zona Crítica"):
        confirmar_reset = st.checkbox("Confirmar borrado total")
        if st.button("🗑️ RESETEAR SISTEMA", use_container_width=True, type="secondary"):
            if confirmar_reset:
                for table in ["captura_actual", "base_anterior", "historial_ventas", "log_movimientos"]:
                    c.execute(f"DELETE FROM {table}")
                conn.commit()
                st.snow()
                st.rerun()

# ------------------ TABS PRINCIPALES ------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 REGISTRO", 
    "📦 CORTE Y STOCK", 
    "📊 RENDIMIENTO", 
    "📜 MOVIMIENTOS"
])

# --- TAB 1: REGISTRO ---
with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    col_entry, col_preview = st.columns([2, 1])
    
    with col_entry:
        st.subheader("Entrada de Producto")
        buscar = st.text_input("🔍 Buscar pan...", placeholder="Ej: CROISSANT").upper()
        
        nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
        sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

        c1, c2 = st.columns(2)
        with c1:
            nombre_input = st.selectbox("Producto:", sugerencias) if sugerencias else buscar
        with c2:
            f_cad = st.date_input("Fecha Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)

        st.write("**Cantidad a añadir:**")
        b1, b2, b3, b4, b5 = st.columns(5)
        with b1: st.button("＋1", on_click=sumar, args=(1,), use_container_width=True)
        with b2: st.button("＋5", on_click=sumar, args=(5,), use_container_width=True)
        with b3: st.button("＋10", on_click=sumar, args=(10,), use_container_width=True)
        with b4: st.button("＋20", on_click=sumar, args=(20,), use_container_width=True)
        with b5: st.button("Borrar", on_click=resetear, use_container_width=True)

        if st.button("✅ AGREGAR A LA LISTA TEMPORAL", use_container_width=True, type="primary"):
            if nombre_input and st.session_state.conteo_temp > 0:
                nombre_f = str(nombre_input).strip().upper()
                existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_f, str(f_cad))).fetchone()
                if existe:
                    c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (st.session_state.conteo_temp, nombre_f, str(f_cad)))
                else:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_f, str(f_cad), st.session_state.conteo_temp))
                
                registrar_log("REGISTRO", nombre_f, st.session_state.conteo_temp)
                st.session_state.conteo_temp = 0
                st.toast(f"✅ {nombre_f} añadido correctamente", icon="🥐")
                st.rerun()
            else:
                st.error("Por favor, selecciona un producto y una cantidad mayor a 0.")

    with col_preview:
        st.metric("Total por registrar", st.session_state.conteo_temp)
        st.info("💡 Haz clic en los botones para sumar cantidad rápidamente.")

    st.divider()
    df_cap = pd.read_sql("SELECT rowid, nombre as Producto, fecha_cad as Caducidad, cantidad as Cantidad FROM captura_actual", conn)
    if not df_cap.empty:
        st.subheader("📋 Lista de Captura Actual")
        df_editado = st.data_editor(df_cap, column_config={"rowid": None}, use_container_width=True, hide_index=True, key="editor_cap")
        if st.button("🗑️ Vaciar Lista Temporal", type="secondary"):
            c.execute("DELETE FROM captura_actual"); conn.commit(); st.rerun()

# --- TAB 2: CORTE E INVENTARIO ---
with tab2:
    col_corte, col_alertas = st.columns([1, 1])
    
    with col_corte:
        st.subheader("🏁 Finalizar Jornada")
        st.write("Esta acción comparará lo que había con lo que acabas de registrar para calcular la venta.")
        if st.button("🚀 PROCESAR CORTE DE VENTAS", type="primary", use_container_width=True):
            df_act = pd.read_sql("SELECT * FROM captura_actual", conn)
            if df_act.empty:
                st.warning("⚠️ No hay productos en 'Registro' para comparar.")
            else:
                df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
                ts = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M")
                ventas_finales = []
                
                # Calcular ventas
                for _, ant in df_ant.iterrows():
                    res = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                    quedan = res[0] if res else 0
                    vendidos = ant['cantidad'] - quedan
                    if vendidos > 0:
                        ventas_finales.append({"Producto": ant['nombre'], "Vendidos": vendidos})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, max(0, vendidos), ts))
                
                # Rotar inventarios
                c.execute("DELETE FROM base_anterior")
                c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.session_state['resumen_corte'] = pd.DataFrame(ventas_finales)
                st.balloons()
                st.rerun()

    if 'resumen_corte' in st.session_state:
        with st.container(border=True):
            st.subheader("📊 Resumen de Ventas Calculadas")
            df_v = st.session_state['resumen_corte']
            st.dataframe(df_v, use_container_width=True, hide_index=True)
            
            # Reporte WhatsApp Pro
            msg = f"🥐 *CHAMPLITTE MX - REPORTE DE VENTAS*\n📅 *Fecha:* {fecha_hoy_mx}\n" + "━" * 15 + "\n"
            for _, r in df_v.iterrows():
                msg += f"• {r['Producto']}: *{r['Vendidos']} piezas*\n"
            msg += "━" * 15 + "\n✅ *Corte realizado con éxito*"
            
            st.link_button("📲 ENVIAR REPORTE POR WHATSAPP", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg)}", use_container_width=True)
            if st.button("Cerrar Resumen"): del st.session_state['resumen_corte']; st.rerun()

    with col_alertas:
        st.subheader("🏪 Inventario Real en Tienda")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Cad.], cantidad as Cantidad FROM base_anterior", conn)
        if not df_inv.empty:
            st.metric("Piezas Totales en Estante", int(df_inv['Cantidad'].sum()))
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
        else:
            st.info("El estante está vacío. Registra productos en la pestaña anterior.")

# --- TAB 3: ANÁLISIS ---
with tab3:
    st.subheader("📈 Estadísticas de Venta")
    df_h = pd.read_sql("SELECT * FROM historial_ventas", conn)
    if not df_h.empty:
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Ventas Totales (Histórico)", f"{int(df_h['vendidos'].sum())} pzas")
        col_m2.metric("Producto Estrella", df_h.groupby("nombre")["vendidos"].sum().idxmax())
        
        st.write("---")
        st.write("**Top 10 Más Vendidos**")
        top_10 = df_h.groupby("nombre")["vendidos"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_10)
    else:
        st.info("Se mostrarán gráficas una vez que realices tu primer corte.")

# --- TAB 4: MOVIMIENTOS ---
with tab4:
    st.subheader("📜 Auditoría de Movimientos")
    st.write("Aquí puedes ver quién agregó qué y en qué momento.")
    df_logs = pd.read_sql("SELECT fecha as [Fecha/Hora], tipo as [Acción], nombre as Producto, cantidad as Cantidad FROM log_movimientos ORDER BY fecha DESC", conn)
    if not df_logs.empty:
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No hay movimientos registrados aún.")

# ------------------ FOOTER ------------------
st.sidebar.markdown("---")
st.sidebar.caption("© 2026 Champlitte MX | v2.5.1")
