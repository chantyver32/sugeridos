import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE PÁGINA (APP LIMPIA) ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# CSS para ocultar menú de hamburguesa, marca de agua y header de Streamlit
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp { margin-top: -50px; }
    </style>
    """, unsafe_allow_html=True)

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

# ------------------ LÓGICA DE REINICIO DE CAMPOS ------------------
# Usamos un contador en session_state para las llaves (keys) de los inputs
if "contador_limpieza" not in st.session_state:
    st.session_state.contador_limpieza = 0

def limpiar_campos():
    st.session_state.contador_limpieza += 1

# ------------------ SIDEBAR: CONFIGURACIÓN ------------------
st.sidebar.header("⚙️ Configuración")

with st.sidebar.expander("🚨 Zona de Peligro"):
    st.write("Borrar historial e inventario.")
    confirmar_reset = st.checkbox("Confirmar borrado", key="check_reset")
    if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.rerun()

# ------------------ SECCIÓN 1: CAPTURA FÍSICA (PASO 1) ------------------
st.title("Sistema de Inventario Champlitte 🥐")
st.header(f"📝 Paso 1: Conteo en Estantes")

with st.container(border=True):
    # Generamos una llave dinámica única para este ciclo
    llave_ciclo = st.session_state.contador_limpieza
    
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Al cambiar la llave con 'llave_ciclo', el widget vuelve a su estado inicial
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key=f"sel_{llave_ciclo}")
        if opcion == "-- Nuevo Producto --":
            nombre_input = st.text_input("Nombre del pan:", key=f"txt_{llave_ciclo}").upper()
        else:
            nombre_input = opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key=f"date_{llave_ciclo}")
    
    with col3:
        cant = st.number_input("Cantidad física:", min_value=1, value=1, step=1, key=f"num_{llave_ciclo}")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Registrar en el Conteo", type="primary", use_container_width=True):
            if nombre_input and nombre_input.strip() != "":
                nombre_final = nombre_input.strip().upper()
                existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad)).fetchone()
                if existe:
                    c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad))
                else:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
                conn.commit()
                limpiar_campos() # Limpiamos para el siguiente registro
                st.rerun()
    
    with col_btn2:
        # ESTE ES EL BOTÓN QUE BUSCABAS: Limpia todo con un clic
        if st.button("🧹 Limpiar Campos", use_container_width=True):
            limpiar_campos()
            st.rerun()

# --- TABLA DE CAPTURA ACTUAL ---
df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)

if not df_hoy_captura.empty:
    df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
    st.subheader("📋 Revisión del conteo:")
    df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, use_container_width=True, hide_index=True, key="editor_conteo")

    if st.button("💾 Guardar cambios de la tabla", use_container_width=True):
        c.execute("DELETE FROM captura_actual")
        for _, fila in df_editado.iterrows():
            if fila['nombre']:
                c.execute("INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)", 
                         (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
        conn.commit()
        st.rerun()

# ------------------ SECCIÓN 2: CORTE ------------------
st.divider()
if st.button("🏁 REALIZAR CORTE Y FINALIZAR DÍA", type="primary", use_container_width=True):
    df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
    if not df_actualizado.empty:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
        for _, fila_ant in df_anterior.iterrows():
            res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
            cant_hoy = res_hoy[0] if res_hoy else 0
            dif = fila_ant['cantidad'] - cant_hoy
            if dif > 0:
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", (fila_ant['nombre'], fila_ant['fecha_cad'], dif, ts_mx))
        c.execute("DELETE FROM base_anterior"); c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual"); c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.success("✅ Corte realizado."); st.rerun()

# ------------------ SECCIÓN 3: ESTADO ACTUAL ------------------
st.divider()
col_l, col_r = st.columns(2)
with col_l:
    st.header("⚠️ Caducidades Hoy")
    df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
    st.dataframe(df_cad, use_container_width=True, hide_index=True) if not df_cad.empty else st.success("Todo ok")

with col_r:
    st.header("🏪 Stock Actual")
    df_stock = pd.read_sql("SELECT nombre, cantidad FROM base_anterior", conn)
    st.dataframe(df_stock, use_container_width=True, hide_index=True)
