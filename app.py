import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Champlitte Pro", page_icon="🥐", layout="wide")

# Configuración de zona horaria y datos de contacto
zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

# Estilo personalizado para mejorar la visibilidad en móviles
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# ------------------ BASE DE DATOS (PERSISTENTE) ------------------
# El archivo 'inventario_pan.db' se crea en la carpeta del proyecto y sobrevive a cierres de app.
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME
)''')
conn.commit()

# ------------------ FUNCIONES DE AYUDA ------------------
def registrar_en_db(nombre, fecha, cant):
    nombre = nombre.strip().upper()
    existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre, str(fecha))).fetchone()
    if existe:
        c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre, str(fecha)))
    else:
        c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre, str(fecha), int(cant)))
    conn.commit()

# ------------------ INTERFAZ PRINCIPAL ------------------
st.title("Champlitte: Control de Inventario Infinito 🥐")

tab1, tab2, tab3 = st.tabs(["📝 Registro", "📦 Inventario y Corte", "📊 Historial"])

# --- TAB 1: REGISTRO DE PRODUCTOS ---
with tab1:
    st.subheader("Añadir productos al estante")
    
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    # Buscador con memoria de productos anteriores
    nombres_sugeridos = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col_nom, col_f = st.columns([2, 1])
    with col_nom:
        nombre_sel = st.selectbox("Producto (Selecciona o escribe)", [""] + nombres_sugeridos, index=0)
        nombre_nuevo = st.text_input("O escribe producto nuevo:").upper()
        nombre_final = nombre_nuevo if nombre_nuevo else nombre_sel

    with col_f:
        f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx)

    # Teclado numérico rápido
    st.write(f"### Cantidad a sumar: **{st.session_state.conteo_temp}**")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("+1"): st.session_state.conteo_temp += 1
    if c2.button("+5"): st.session_state.conteo_temp += 5
    if c3.button("+10"): st.session_state.conteo_temp += 10
    if c4.button("Reset", type="secondary"): st.session_state.conteo_temp = 0

    if st.button("📥 GUARDAR PRODUCTO", type="primary"):
        if nombre_final and st.session_state.conteo_temp > 0:
            registrar_en_db(nombre_final, f_cad, st.session_state.conteo_temp)
            st.success(f"Guardado: {nombre_final} ({st.session_state.conteo_temp} pzs)")
            st.session_state.conteo_temp = 0
            time.sleep(1)
            st.rerun()
        else:
            st.error("Falta nombre o cantidad")

# --- TAB 2: INVENTARIO Y CORTE ---
with tab2:
    col_inv, col_alerta = st.columns(2)
    
    with col_inv:
        st.header("📦 En Estante (Ahora)")
        df_inv = pd.read_sql("SELECT * FROM base_anterior", conn)
        if not df_inv.empty:
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
            # Botón WhatsApp Inventario
            msg_inv = "📦 *CHAMPLITTE: INVENTARIO ACTUAL*\n" + "\n".join([f"- {r['nombre']}: {r['cantidad']} (Cad: {r['fecha_cad']})" for _, r in df_inv.iterrows()])
            st.link_button("📲 Enviar Inventario a WA", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg_inv)}")
        else:
            st.info("No hay inventario registrado.")

    with col_alerta:
        st.header("⚠️ Caducan Hoy")
        df_cad = pd.read_sql("SELECT * FROM base_anterior WHERE fecha_cad <= ?", conn, params=(str(fecha_hoy_mx),))
        if not df_cad.empty:
            st.warning(f"Hay {len(df_cad)} productos por vencer.")
            st.table(df_cad)
        else:
            st.success("Nada caduca hoy.")

    st.divider()
    st.header("🏁 Finalizar Turno / Hacer Corte")
    st.write("Al hacer el corte, compararemos lo que 'Había' contra lo que acabas de contar en 'Registro'.")
    
    if st.button("🚀 EJECUTAR CORTE DE VENTAS", type="primary"):
        df_hoy = pd.read_sql("SELECT * FROM captura_actual", conn)
        df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
        
        if df_hoy.empty:
            st.error("Primero debes capturar el conteo actual en la pestaña 'Registro'.")
        else:
            # Lógica de cálculo de ventas
            ts = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            reporte_wa = f"📊 *CORTE CHAMPLITTE* ({ts})\n"
            
            for _, ant in df_ant.iterrows():
                # Buscar si el producto que había sigue estando en el nuevo conteo
                hoy = df_hoy[(df_hoy['nombre'] == ant['nombre']) & (df_hoy['fecha_cad'] == ant['fecha_cad'])]
                quedan = hoy['cantidad'].values[0] if not hoy.empty else 0
                vendidos = ant['cantidad'] - quedan
                
                if vendidos > 0:
                    c.execute("INSERT INTO historial_ventas VALUES (?,?,?,?,?,?)", 
                              (ant['nombre'], ant['fecha_cad'], ant['cantidad'], quedan, vendidos, ts))
                    reporte_wa += f"✅ {ant['nombre']}: *Vendido {vendidos}*\n"

            # Actualizar base: Lo que contamos hoy pasa a ser la "base anterior" para mañana
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            
            st.balloons()
            st.success("Corte completado y guardado permanentemente.")
            st.link_button("📲 Enviar Reporte de Ventas", f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(reporte_wa)}")
            time.sleep(2)
            st.rerun()

# --- TAB 3: ANÁLISIS E HISTORIAL ---
with tab3:
    st.header("📊 Historial Acumulado")
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    
    if not df_hist.empty:
        # Filtro de búsqueda
        busqueda = st.text_input("Filtrar historial por nombre:").upper()
        if busqueda:
            df_hist = df_hist[df_hist['nombre'].str.contains(busqueda)]
            
        st.dataframe(df_hist, use_container_width=True)
        
        # Resumen total
        total_v = df_hist['vendidos'].sum()
        st.metric("Total de piezas vendidas (Histórico)", f"{total_v} pzs")
        
        if st.button("🗑️ Limpiar Historial (Cuidado)"):
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.rerun()
    else:
        st.info("Aún no hay ventas registradas en el historial.")

# --- SIDEBAR (ZONA DE PELIGRO) ---
with st.sidebar:
    st.title("Opciones")
    if st.button("🧹 Borrar Conteo Actual (Paso 1)"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()
