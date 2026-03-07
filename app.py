import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz


# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Estilo personalizado para mejorar la visibilidad en dispositivos móviles
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

# ------------------ CONEXIÓN SEGURA A BD ------------------
def init_db():
    conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
    conn.commit()
    return conn

conn = init_db()

# ------------------ LÓGICA DE TIEMPO ------------------
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

# ------------------ INTERFAZ DE USUARIO ------------------
st.title("🥐 Champlitte MX: Control de Inventario")

tab1, tab2, tab3 = st.tabs(["📝 Operación Diaria", "📊 Reportes de Ventas", "⚙️ Configuración"])

with tab1:
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.header(f"📦 Conteo Físico")
        st.caption(f"Fecha de operación: {fecha_hoy_mx.strftime('%d/%m/%Y')}")
        
        # Reset de inputs mediante session_state
        if "reset_key" not in st.session_state: st.session_state.reset_key = 0
        rk = st.session_state.reset_key

        with st.container(border=True):
            # Obtener nombres para autocompletado
            nombres_prev = [r[0] for r in conn.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
            
            opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key=f"sel_{rk}")
            nombre_input = st.text_input("Nombre del pan:", key=f"txt_{rk}").upper() if opcion == "-- Nuevo Producto --" else opcion
            
            c1, c2 = st.columns(2)
            f_cad = c1.date_input("Caducidad:", value=fecha_hoy_mx, key=f"date_{rk}")
            cant = c2.number_input("Cantidad física:", min_value=1, step=1, key=f"num_{rk}")

            if st.button("➕ Añadir al Conteo", type="primary"):
                if nombre_input and nombre_input != "-- Nuevo Producto --":
                    conn.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_input.strip().upper(), str(f_cad), int(cant)))
                    conn.commit()
                    st.session_state.reset_key += 1
                    st.rerun()
                else:
                    st.error("Por favor, ingresa un nombre válido.")

    with col_right:
        st.header("📋 Revisión de Captura")
        df_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
        
        if not df_captura.empty:
            df_editado = st.data_editor(
                df_captura, 
                column_config={"rowid": None}, 
                use_container_width=True, 
                hide_index=True,
                key="editor_captura"
            )
            
            if st.button("🚀 FINALIZAR CORTE (CALCULAR VENTAS)"):
                # 1. Obtener lo que había antes
                df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
                ventas_detectadas = []
                
                # 2. Lógica: Para cada item que había en el estante...
                for _, ant in df_ant.iterrows():
                    # Buscar cuánto queda hoy del mismo pan y misma fecha de caducidad
                    res_actual = conn.execute(
                        "SELECT SUM(cantidad) FROM captura_actual WHERE nombre=? AND fecha_cad=?", 
                        (ant['nombre'], ant['fecha_cad'])
                    ).fetchone()[0]
                    
                    res_actual = res_actual if res_actual is not None else 0
                    vendidos = ant['cantidad'] - res_actual
                    
                    if vendidos > 0:
                        ventas_detectadas.append((ant['nombre'], ant['fecha_cad'], vendidos, ahora_mx.strftime("%Y-%m-%d %H:%M:%S")))

                # 3. Guardar ventas y rotar tablas
                if ventas_detectadas:
                    conn.executemany("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", ventas_detectadas)
                
                conn.execute("DELETE FROM base_anterior")
                conn.execute("INSERT INTO base_anterior SELECT nombre, fecha_cad, cantidad FROM captura_actual")
                conn.execute("DELETE FROM captura_actual")
                conn.commit()
                
                st.balloons()
                st.success("¡Corte finalizado! El inventario actual es ahora tu nueva base.")
                st.rerun()
        else:
            st.info("No hay datos capturados hoy. Empieza registrando el pan que ves en el estante.")

    # --- RESUMEN DE STOCK ACTUAL ---
    st.divider()
    st.subheader("🍞 Estado Actual del Estante (Base Anterior)")
    df_resumen = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM base_anterior ORDER BY fecha_cad ASC", conn)
    
    if not df_resumen.empty:
        c1, c2, c3 = st.columns(3)
        total_piezas = df_resumen['cantidad'].sum()
        mermas_hoy = df_resumen[df_resumen['fecha_cad'] == str(fecha_hoy_mx)]['cantidad'].sum()
        
        c1.metric("Total Piezas", f"{total_piezas} pz")
        c2.metric("Mermas (Hoy)", f"{mermas_hoy} pz", delta_color="inverse")
        c3.metric("Variedad", f"{len(df_resumen['nombre'].unique())} tipos")
        
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
    else:
        st.warning("El estante está vacío en el sistema. Realiza un corte para inicializar.")

with tab2:
    st.header("Análisis de Ventas")
    df_hist = pd.read_sql("SELECT * FROM historial_ventas", conn)
    
    if not df_hist.empty:
        # Gráfico por producto
        df_agrupado = df_hist.groupby('nombre')['vendidos'].sum().reset_index()
        fig = px.bar(df_agrupado, x='nombre', y='vendidos', 
                     title="Total Unidades Vendidas por Producto",
                     color='vendidos', color_continuous_scale='Viridis')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Registro Detallado")
        st.dataframe(df_hist.sort_values(by='fecha_corte', ascending=False), use_container_width=True)
    else:
        st.info("Aún no hay historial de ventas. Finaliza un corte en la pestaña de Operación.")

with tab3:
    st.header("Administración del Sistema")
    st.warning("Zona de peligro: Estas acciones no se pueden deshacer.")
    
    if st.button("🗑️ Limpiar Base de Datos Completa"):
        if st.checkbox("Confirmar que deseo borrar TODO el historial"):
            conn.execute("DROP TABLE IF EXISTS captura_actual")
            conn.execute("DROP TABLE IF EXISTS base_anterior")
            conn.execute("DROP TABLE IF EXISTS historial_ventas")
            conn.commit()
            st.error("Datos borrados. Por favor, reinicia la aplicación.")
            st.stop()
