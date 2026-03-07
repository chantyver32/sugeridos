import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ------------------ CONEXIÓN A LA BASE DE DATOS ------------------
conn = sqlite3.connect('sucursal.db', check_same_thread=False)
c = conn.cursor()

# Tabla Maestro: Catálogo fijo
c.execute('CREATE TABLE IF NOT EXISTS maestro (codigo TEXT PRIMARY KEY, nombre TEXT)')
# Tabla Inventario: Lo que realmente hay en estante (incluye fecha_cad)
c.execute('''CREATE TABLE IF NOT EXISTS inventario 
             (codigo TEXT, nombre TEXT, fecha_cad DATE, ultima_revision DATE)''')
conn.commit()

st.title("Control de Inventario y Ventas 🥖")

menu = st.sidebar.selectbox("Selecciona:", ["Revisión Diaria", "Maestro de Productos", "Reporte de Ventas"])

# ------------------ MAESTRO DE PRODUCTOS ------------------
if menu == "Maestro de Productos":
    st.header("Catálogo de Productos")
    with st.form("nuevo_producto"):
        cod = st.text_input("Código de Barras")
        nom = st.text_input("Nombre del Producto")
        if st.form_submit_button("Guardar en Catálogo"):
            if cod and nom:
                c.execute("INSERT OR REPLACE INTO maestro VALUES (?,?)", (cod, nom))
                conn.commit()
                st.success(f"Registrado: {nom}")

# ------------------ REVISIÓN DIARIA (Lógica Principal) ------------------
elif menu == "Revisión Diaria":
    st.header("Escaneo de Existencias")
    hoy = datetime.now().date()
    
    # 1. Entrada de datos
    with st.expander("Registrar Producto en Estante", expanded=True):
        cod_escaneado = st.text_input("Código de Barras:")
        # Buscamos el nombre automáticamente si existe en el maestro
        res = c.execute("SELECT nombre FROM maestro WHERE codigo = ?", (cod_escaneado,)).fetchone()
        nombre_sugerido = res[0] if res else ""
        
        nom_prod = st.text_input("Producto:", value=nombre_sugerido)
        f_cad = st.date_input("Fecha de Caducidad:", value=hoy)
        
        if st.button("Confirmar en Estante ✅"):
            if cod_escaneado and nom_prod:
                # Insertamos el registro con la fecha de revisión de hoy
                c.execute("INSERT INTO inventario VALUES (?, ?, ?, ?)", 
                          (cod_escaneado, nom_prod, f_cad, hoy))
                conn.commit()
                st.toast(f"Confirmado: {nom_prod} (Cad: {f_cad})")

    # 2. Resumen de lo revisado hoy
    st.subheader("Productos detectados hoy")
    df_hoy = pd.read_sql("SELECT nombre, fecha_cad FROM inventario WHERE ultima_revision = ?", 
                         conn, params=(hoy,))
    st.table(df_hoy)

    # 3. CIERRE DE DÍA / CALCULAR VENTAS
    st.divider()
    if st.button("🧹 Finalizar Revisión (Calcular Ventas)"):
        # Buscamos lo que había antes de hoy que NO fue registrado hoy
        ventas = pd.read_sql("""SELECT nombre, fecha_cad FROM inventario 
                                WHERE ultima_revision < ?""", conn, params=(hoy,))
        
        if not ventas.empty:
            st.warning("🛍️ Productos vendidos (no encontrados en esta revisión):")
            st.dataframe(ventas)
            # Borramos lo viejo para dejar solo el inventario fresco
            c.execute("DELETE FROM inventario WHERE ultima_revision < ?", (hoy,))
            conn.commit()
            st.success("Inventario actualizado. Se eliminaron los productos vendidos.")
        else:
            st.info("No se detectaron bajas (ventas) o es la primera revisión del día.")

# ------------------ REPORTE DE VENTAS ------------------
elif menu == "Reporte de Ventas":
    st.header("Inventario Actual en Tienda")
    df_total = pd.read_sql("SELECT nombre, fecha_cad, ultima_revision FROM inventario", conn)
    if not df_total.empty:
        st.dataframe(df_total)
    else:
        st.write("El inventario está vacío. Realiza una revisión.")
