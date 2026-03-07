import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from PIL import Image

# ------------------ CONEXIÓN A LA BASE DE DATOS ------------------
conn = sqlite3.connect('sucursal.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS maestro (codigo TEXT PRIMARY KEY, nombre TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS caducidades (codigo TEXT, fecha_cad DATE, revision DATE)')
conn.commit()

st.title("Control de Sucursal 🥖")

# ------------------ MENÚ DE NAVEGACIÓN ------------------
menu = st.sidebar.selectbox("Selecciona:", ["Escanear/Revisar", "Maestro de Productos"])

# ------------------ MAESTRO DE PRODUCTOS ------------------
if menu == "Maestro de Productos":
    st.header("Registro de Productos Nuevos")
    cod = st.text_input("Código de Barras")
    nom = st.text_input("Nombre del Producto (Ej: Pastel Chocolate)")
    
    if st.button("Guardar en Catálogo"):
        if cod and nom:
            c.execute("INSERT OR REPLACE INTO maestro VALUES (?,?)", (cod, nom))
            conn.commit()
            st.success("Producto guardado en el catálogo.")
        else:
            st.error("Debes ingresar código y nombre del producto.")
    
    # Mostrar tabla de productos
    st.subheader("Catálogo Actual")
    df_maestro = pd.read_sql("SELECT * FROM maestro", conn)
    st.dataframe(df_maestro)

# ------------------ ESCANEAR / REVISAR ------------------
elif menu == "Escanear/Revisar":
    st.header("Revisión Diaria")
    foto = st.camera_input("Escanea el código")  # Foto opcional
    
    cod_escaneado = st.text_input("O escribe el código manualmente:")
    
    if st.button("Confirmar que está en estante"):
        if cod_escaneado:
            hoy = datetime.now().date()
            c.execute("INSERT INTO caducidades VALUES (?, ?, ?)", (cod_escaneado, hoy, hoy))
            conn.commit()
            st.success("Producto confirmado hoy.")
        else:
            st.error("Ingresa un código antes de confirmar.")
    
    # Mostrar productos revisados hoy
    st.subheader("Productos revisados hoy")
    hoy = datetime.now().date()
    df_hoy = pd.read_sql("SELECT * FROM caducidades WHERE revision = ?", conn, params=(hoy,))
    st.dataframe(df_hoy)
    
    # Botón para limpiar productos no revisados
    if st.button("🧹 Borrar productos no revisados hoy"):
        c.execute("DELETE FROM caducidades WHERE revision < ?", (hoy,))
        conn.commit()
        st.warning("Se borró todo lo que no fue revisado hoy.")