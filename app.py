import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE PÁGINA Y ESTILO ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Ocultar menús de Streamlit
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()

# ------------------ LÓGICA DE LIMPIEZA CORREGIDA ------------------
# Usamos un "form_id" en la session_state para forzar el reseteo de los widgets
if "form_iteration" not in st.session_state:
    st.session_state.form_iteration = 0

def reiniciar_formulario():
    st.session_state.form_iteration += 1  # Al cambiar la key de los widgets, se vacían

# ------------------ SECCIÓN 1: CAPTURA ------------------
st.title("Sistema de Inventario Champlitte 🥐")
st.header("📝 Paso 1: Conteo en Estantes")

with st.container(border=True):
    # Generamos llaves dinámicas basadas en form_iteration para poder limpiar
    iter = st.session_state.form_iteration
    
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key=f"sel_{iter}")
        nombre_final = ""
        if opcion == "-- Nuevo Producto --":
            nombre_final = st.text_input("Nombre del pan:", key=f"txt_{iter}").upper()
        else:
            nombre_final = opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key=f"date_{iter}")
    
    with col3:
        cant = st.number_input("Cantidad física:", min_value=1, value=1, step=1, key=f"num_{iter}")

    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        if st.button("➕ Registrar en el Conteo", type="primary", use_container_width=True):
            if nombre_final and nombre_final.strip() != "":
                nombre_db = nombre_final.strip().upper()
                existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_db, f_cad)).fetchone()
                if existe:
                    c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_db, f_cad))
                else:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_db, f_cad, int(cant)))
                conn.commit()
                reiniciar_formulario() # Limpia después de guardar
                st.rerun()
            else:
                st.error("Por favor, introduce un nombre.")

    with btn_col2:
        if st.button("🧹 Limpiar Campos", use_container_width=True):
            reiniciar_formulario() # Limpia sin guardar
            st.rerun()

# ------------------ REVISIÓN Y TABLAS (RESTO DEL CÓDIGO) ------------------
df_hoy = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
if not df_hoy.empty:
    st.subheader("📋 Revisión de Captura:")
    # (El resto de tu lógica de data_editor se mantiene igual...)
    st.dataframe(df_hoy, use_container_width=True, hide_index=True)
    if st.button("🗑️ Borrar toda la captura"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# --- BOTÓN DE CORTE FINAL ---
st.divider()
if st.button("🏁 REALIZAR CORTE FINAL", type="primary", use_container_width=True):
    # Lógica de comparación y guardado en historial...
    st.success("Corte realizado correctamente.")
