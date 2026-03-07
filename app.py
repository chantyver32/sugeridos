import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ------------------ CONFIGURACIÓN DE BASE DE DATOS ------------------
conn = sqlite3.connect('sucursal_pan.db', check_same_thread=False)
c = conn.cursor()

# Tabla de inventario actual: nombre del producto, su caducidad y cuándo se revisó por última vez
c.execute('''CREATE TABLE IF NOT EXISTS inventario 
             (nombre TEXT, fecha_cad DATE, ultima_revision DATE)''')
conn.commit()

st.set_page_config(page_title="Control de Panadería", page_icon="🥖")
st.title("Control de Existencias y Ventas 🥖")

# ------------------ LÓGICA DE SUGERENCIAS ------------------
# Obtenemos nombres únicos de productos que ya hemos registrado antes
productos_conocidos = [res[0] for res in c.execute("SELECT DISTINCT nombre FROM inventario").fetchall()]

# ------------------ REGISTRO DE PRODUCTOS ------------------
st.header("📝 Registro de Revisión")
col1, col2 = st.columns(2)

with col1:
    # El selectbox con 'index=None' y 'placeholder' permite escribir y buscar
    nombre_input = st.selectbox(
        "Nombre del Producto (Escribe para buscar):",
        options=productos_conocidos,
        index=None,
        placeholder="Ej: Concha Vainilla",
        help="Si el producto es nuevo, escríbelo y presiona Enter",
    )
    
    # Si el usuario quiere escribir uno nuevo que no está en la lista:
    nombre_nuevo = st.text_input("O registra uno nuevo aquí:")
    nombre_final = nombre_nuevo if nombre_nuevo else nombre_input

with col2:
    f_cad = st.date_input("Fecha de Caducidad:", value=datetime.now().date())
    cantidad = st.number_input("¿Cuántas piezas?", min_value=1, value=1)

if st.button("Confirmar en Estante ✅", use_container_width=True):
    if nombre_final:
        hoy = datetime.now().date()
        # Insertamos tantas filas como piezas haya (para manejo individual de ventas)
        for _ in range(cantidad):
            c.execute("INSERT INTO inventario VALUES (?, ?, ?)", (nombre_final, f_cad, hoy))
        conn.commit()
        st.success(f"Registrado: {cantidad}x {nombre_final} (Cad: {f_cad})")
        st.rerun() # Para limpiar campos y actualizar lista
    else:
        st.error("Por favor selecciona o escribe un nombre de producto.")

st.divider()

# ------------------ INVENTARIO ACTUAL Y CIERRE ------------------
st.header("📊 Inventario en Tienda")
hoy = datetime.now().date()

# Mostrar lo que se ha confirmado HOY
df_hoy = pd.read_sql("SELECT nombre, fecha_cad, COUNT(*) as cantidad FROM inventario WHERE ultima_revision = ? GROUP BY nombre, fecha_cad", conn, params=(hoy,))

if not df_hoy.empty:
    st.subheader("Productos revisados hoy:")
    st.dataframe(df_hoy, use_container_width=True)
else:
    st.info("Aún no has registrado productos hoy.")

# ------------------ BOTÓN MÁGICO: CALCULAR VENTAS ------------------
if st.button("🧹 Finalizar Día (Calcular Ventas)"):
    # 1. Identificar lo que había antes que NO se volvió a registrar hoy
    ventas = pd.read_sql("""SELECT nombre, fecha_cad, COUNT(*) as cantidad 
                            FROM inventario 
                            WHERE ultima_revision < ? 
                            GROUP BY nombre, fecha_cad""", conn, params=(hoy,))
    
    if not ventas.empty:
        st.warning("🚨 Se detectaron ventas (productos que ya no están en estante):")
        st.table(ventas)
        
        # 2. Borrar lo que no se revisó (lo vendido)
        c.execute("DELETE FROM inventario WHERE ultima_revision < ?", (hoy,))
        conn.commit()
        st.success("Inventario actualizado. Solo queda lo que registraste hoy.")
    else:
        st.info("No hay productos antiguos para eliminar. Todo está al día.")
