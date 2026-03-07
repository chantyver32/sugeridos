import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Inventario Pastelería", page_icon="🥐", layout="wide")
st.title("Sistema de Revisión y Comparativa de Ventas 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

# existencias: guarda el conteo físico de cada revisión
c.execute('''CREATE TABLE IF NOT EXISTS existencias 
             (nombre TEXT, fecha_cad DATE, revision_id INTEGER)''')

# historial_ventas: guarda el resultado de las comparaciones
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas 
             (nombre TEXT, fecha_cad DATE, cantidad INTEGER, fecha_corte DATETIME, rev_origen INTEGER)''')
conn.commit()

# --- Lógica de IDs ---
# Buscamos el ID más alto para saber en qué revisión estamos trabajando
res_id = c.execute("SELECT MAX(revision_id) FROM existencias").fetchone()
rev_actual = (res_id[0] if res_id[0] else 1)

# ------------------ SECCIÓN 1: CAPTURA DE PRODUCTOS ------------------
st.header(f"📋 Captura Física: Revisión #{rev_actual}")
st.info("Anota todo lo que ves en los estantes en este momento.")

with st.container(border=True):
    query_nombres = "SELECT DISTINCT nombre FROM existencias UNION SELECT DISTINCT nombre FROM historial_ventas"
    nombres_previos = [r[0] for r in c.execute(query_nombres).fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        opcion = st.selectbox("Producto:", options=["-- Nuevo --"] + nombres_previos, index=0)
        nombre_final = st.text_input("Escribe el nombre:") if opcion == "-- Nuevo --" else opcion
    
    with col2:
        f_cad = st.date_input("Caducidad:", value=datetime.now().date())
    
    with col3:
        cant = st.number_input("Cantidad física:", min_value=1, value=1)

    if st.button("➕ Registrar en Revisión Actual", use_container_width=True):
        if nombre_final:
            for _ in range(int(cant)):
                c.execute("INSERT INTO existencias (nombre, fecha_cad, revision_id) VALUES (?, ?, ?)", 
                         (nombre_final.strip().upper(), f_cad, rev_actual))
            conn.commit()
            st.rerun()

# ------------------ SECCIÓN 2: VISTA PREVIA ------------------
df_conteo = pd.read_sql("SELECT nombre, fecha_cad, COUNT(*) as cantidad FROM existencias WHERE revision_id = ? GROUP BY nombre, fecha_cad", 
                       conn, params=(rev_actual,))

if not df_conteo.empty:
    st.subheader(f"Inventario actual en estantes (Rev #{rev_actual}):")
    st.dataframe(df_conteo, use_container_width=True)

# ------------------ SECCIÓN 3: PROCESAR CORTE (COMPARATIVA) ------------------
st.divider()
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("🏁 FINALIZAR Y COMPARAR CON ANTERIOR", type="primary", use_container_width=True):
        rev_anterior = rev_actual - 1
        
        # Obtenemos lo que había en la revisión pasada
        df_anterior = pd.read_sql("SELECT nombre, fecha_cad, COUNT(*) as cant FROM existencias WHERE revision_id = ? GROUP BY nombre, fecha_cad", 
                                 conn, params=(rev_anterior,))
        
        if rev_actual == 1:
            st.warning("Esta es la Revisión #1. No hay una anterior para comparar. Se guardará como base inicial.")
            # Solo saltamos a la siguiente revisión
            c.execute("UPDATE existencias SET revision_id = ? WHERE revision_id = ?", (rev_actual + 1, rev_actual))
            conn.commit()
            st.rerun()
        else:
            analisis = []
            ahora_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Comparamos lo que había antes contra lo que hay ahora
            for _, fila in df_anterior.iterrows():
                res_ahora = c.execute("SELECT COUNT(*) FROM existencias WHERE nombre=? AND fecha_cad=? AND revision_id=?", 
                                     (fila['nombre'], fila['fecha_cad'], rev_actual)).fetchone()
                cant_ahora = res_ahora[0]
                
                vendidos = fila['cant'] - cant_ahora
                
                if vendidos > 0:
                    analisis.append({"Producto": fila['nombre'], "Caducidad": fila['fecha_cad'], "Antes": fila['cant'], "Ahora": cant_ahora, "Vendidos": vendidos})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?)", 
                             (fila['nombre'], fila['fecha_cad'], vendidos, ahora_timestamp, rev_actual))

            # Borramos la revisión anterior para no saturar la base de datos
            c.execute("DELETE FROM existencias WHERE revision_id = ?", (rev_anterior,))
            
            # Preparamos la siguiente revisión
            c.execute("UPDATE existencias SET revision_id = ? WHERE revision_id = ?", (rev_actual + 1, rev_actual))
            conn.commit()
            
            st.balloons()
            if analisis:
                st.write("### 📊 Resultado del Análisis de Ventas:")
                st.table(pd.DataFrame(analisis))
            else:
                st.info("No hay cambios: El inventario es idéntico al anterior.")
            
            if st.button("Empezar Nueva Captura"):
                st.rerun()

with col_btn2:
    if st.expander("⚠️ Opciones de Peligro"):
        if st.button("Borrar TODA la Base de Datos"):
            c.execute("DELETE FROM existencias")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.rerun()

# ------------------ SECCIÓN 4: HISTORIAL ------------------
st.divider()
with st.expander("📖 Historial Acumulado de Ventas"):
    df_hist = pd.read_sql("SELECT nombre, fecha_cad, cantidad as vendidos, fecha_corte FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    st.dataframe(df_hist, use_container_width=True)
