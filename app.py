import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import plotly.express as px # Nueva dependencia para gráficas

# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Estilo personalizado
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# ------------------ CONEXIÓN SEGURA A BD ------------------
def get_db_connection():
    conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
    return conn

conn = get_db_connection()
c = conn.cursor()

# Inicialización de tablas
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ LÓGICA DE TIEMPO ------------------
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

# ------------------ INTERFAZ DE USUARIO ------------------
st.title("🥐 Champlitte MX: Control de Inventario")

tab1, tab2, tab3 = st.tabs(["📝 Operación Diaria", "📊 Reportes de Ventas", "⚙️ Configuración"])

with tab1:
    # --- SECCIÓN 1: CAPTURA ---
    st.header(f"📦 Conteo Físico - {fecha_hoy_mx.strftime('%d/%m/%Y')}")
    
    if "reset_key" not in st.session_state: st.session_state.reset_key = 0
    rk = st.session_state.reset_key

    with st.expander("➕ Registrar Pan en Estante", expanded=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        # Sugerencias de nombres existentes
        nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
        
        with col1:
            opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key=f"sel_{rk}")
            nombre_input = st.text_input("Escribe el nombre:", key=f"txt_{rk}").upper() if opcion == "-- Nuevo Producto --" else opcion
        
        with col2:
            f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, key=f"date_{rk}")
            
        with col3:
            cant = st.number_input("Cantidad:", min_value=1, step=1, key=f"num_{rk}")

        if st.button("Añadir al Conteo", type="primary", use_container_width=True):
            if nombre_input:
                nombre_final = nombre_input.strip().upper()
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(cant)))
                conn.commit()
                st.session_state.reset_key += 1
                st.rerun()

    # --- TABLA DE EDICIÓN ---
    df_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if not df_captura.empty:
        st.subheader("📋 Revisión de Captura")
        df_editado = st.data_editor(df_captura, column_config={"rowid": None}, use_container_width=True, hide_index=True)
        
        col_c1, col_c2 = st.columns(2)
        if col_c1.button("💾 Actualizar Cambios", use_container_width=True):
            c.execute("DELETE FROM captura_actual")
            for _, fila in df_editado.iterrows():
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (fila['nombre'], str(fila['fecha_cad']), fila['cantidad']))
            conn.commit()
            st.success("Cambios guardados")

        if col_c2.button("🚀 FINALIZAR CORTE (CALCULAR VENTAS)", type="primary", use_container_width=True):
            # Lógica de cálculo de ventas: Anterior - Actual = Ventas
            df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
            ventas_detectadas = []
            
            for _, ant in df_ant.iterrows():
                # Buscar el mismo pan en la captura actual
                res_actual = c.execute("SELECT SUM(cantidad) FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()[0]
                res_actual = res_actual if res_actual else 0
                
                vendidos = ant['cantidad'] - res_actual
                if vendidos > 0:
                    ventas_detectadas.append((ant['nombre'], ant['fecha_cad'], vendidos, ahora_mx.strftime("%Y-%m-%d %H:%M:%S")))

            if ventas_detectadas:
                c.executemany("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", ventas_detectadas)
            
            # Rotación de inventario
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.balloons()
            st.rerun()

    # --- RESUMEN DE STOCK ACTUAL ---
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("⚠️ Mermas/Vencen Hoy")
        df_mermas = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        st.table(df_mermas) if not df_mermas.empty else st.write("No hay mermas.")
    
    with c2:
        st.subheader("🍞 Stock Disponible")
        df_stock = pd.read_sql("SELECT nombre, SUM(cantidad) as total FROM base_anterior GROUP BY nombre", conn)
        st.dataframe(df_stock, hide_index=True, use_container_width=True)

with tab2:
    st.header("Análisis de Ventas")
    df_hist = pd.read_sql("SELECT * FROM historial_ventas", conn)
    
    if not df_hist.empty:
        # Gráfico simple
        fig = px.bar(df_hist, x='nombre', y='vendidos', title="Productos más vendidos (Histórico)", color='nombre')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Registro Detallado")
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Aún no hay historial de ventas registrado.")

with tab3:
    st.header("Administración")
    if st.button("🗑️ Borrar Todo el Historial y Base"):
        if st.checkbox("Confirmar acción destructiva"):
            c.execute("DROP TABLE IF EXISTS captura_actual")
            c.execute("DROP TABLE IF EXISTS base_anterior")
            c.execute("DROP TABLE IF EXISTS historial_ventas")
            conn.commit()
            st.warning("Base de datos borrada. Recarga la página.")
