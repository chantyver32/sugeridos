import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE PÁGINA (ESTILO LIMPIO) ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# CSS para ocultar menús de Streamlit y limpiar la interfaz
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stButton>button {border-radius: 8px;}
    </style>
    """, unsafe_allow_html=True)

st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

# ------------------ CONFIGURACIÓN DE ZONA HORARIA (MÉXICO) ------------------
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ LÓGICA DE BORRADO DE CAMPOS ------------------
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

def limpiar_campos():
    st.session_state.reset_counter += 1

# ------------------ SECCIÓN 1: CAPTURA FÍSICA (PASO 1) ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

with st.container(border=True):
    k = st.session_state.reset_counter
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key=f"sel_{k}")
        if opcion == "-- Nuevo Producto --":
            nombre_input = st.text_input("Nombre del pan:", key=f"txt_{k}").upper()
        else:
            nombre_input = opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key=f"date_{k}")
    
    with col3:
        cant = st.number_input("Cantidad física:", min_value=1, value=1, step=1, key=f"num_{k}")

    col_reg, col_limp = st.columns(2)
    with col_reg:
        if st.button("➕ Registrar en el Conteo", use_container_width=True, type="primary"):
            if nombre_input and nombre_input.strip() != "":
                nombre_final = nombre_input.strip().upper()
                existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad)).fetchone()
                if existe:
                    c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad))
                else:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
                conn.commit()
                limpiar_campos()
                st.rerun()
    
    with col_limp:
        if st.button("🧹 Limpiar Formulario", use_container_width=True):
            limpiar_campos()
            st.rerun()

# --- TABLA DE CAPTURA ACTUAL ---
df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)

if not df_hoy_captura.empty:
    df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
    st.subheader("📋 Revisión del conteo:")
    df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, use_container_width=True, hide_index=True, key="editor_conteo")

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Guardar cambios realizados arriba", use_container_width=True):
            c.execute("DELETE FROM captura_actual")
            for _, fila in df_editado.iterrows():
                if fila['nombre']:
                    c.execute("INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)", 
                             (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
            conn.commit()
            st.success("¡Conteo actualizado!")
            st.rerun()
    with col_cancel:
        if st.button("🗑️ Borrar lista de captura", use_container_width=True):
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.rerun()

# ------------------ SECCIÓN 2: CORTE Y COMPARACIÓN (PASO 2) ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

if st.button("REALIZAR CORTE Y CERRAR DÍA", type="primary", use_container_width=True):
    df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
    if not df_actualizado.empty:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        if not df_anterior.empty:
            ventas_detectadas = []
            ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                diferencia = fila_ant['cantidad'] - cant_hoy
                if diferencia > 0:
                    ventas_detectadas.append({"Producto": fila_ant['nombre'], "VENDIDOS": diferencia})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", (fila_ant['nombre'], fila_ant['fecha_cad'], diferencia, ts_mx))
            if ventas_detectadas:
                st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.success("✅ Corte realizado.")
        st.rerun()

if 'ultimo_corte' in st.session_state:
    st.balloons()
    st.table(st.session_state['ultimo_corte'])
    if st.button("Cerrar Resumen"):
        del st.session_state['ultimo_corte']
        st.rerun()

# ------------------ SECCIÓN 3: ESTADO ACTUAL ------------------
st.divider()
col_left, col_right = st.columns(2)
with col_left:
    st.header("⚠️ Alertas Caducidad")
    df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
    st.dataframe(df_cad, use_container_width=True, hide_index=True) if not df_cad.empty else st.success("✅ Todo bien hoy.")

with col_right:
    st.header("🏪 Stock Actual")
    df_estantes = pd.read_sql("SELECT nombre, cantidad FROM base_anterior", conn)
    st.dataframe(df_estantes, use_container_width=True, hide_index=True)

# ------------------ SECCIÓN 4: RESET TOTAL (HASTA ABAJO) ------------------
st.write("<br><br><br>", unsafe_allow_html=True) # Espaciado extra
st.divider()
st.header("🚨 Configuración Avanzada")
with st.expander("💣 ZONA DE PELIGRO - BORRAR TODO"):
    st.warning("Cuidado: Esta acción eliminará permanentemente TODO el inventario y el historial de ventas.")
    confirmar_todo = st.checkbox("Entiendo los riesgos, quiero borrar toda la base de datos.")
    if st.button("🔥 EJECUTAR RESET TOTAL DE LA BASE DE DATOS", type="secondary", use_container_width=True):
        if confirmar_todo:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.success("Base de datos reseteada.")
            st.rerun()
        else:
            st.error("Debes marcar la casilla de confirmación primero.")
