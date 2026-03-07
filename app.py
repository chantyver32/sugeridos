import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ------------------ CONFIGURACIÓN ------------------
st.set_page_config(page_title="Inventario Pastelería", page_icon="🥐")
st.title("Comparador de Inventario Real-Time 🥐")

conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS existencias (nombre TEXT, fecha_cad DATE, revision_id INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, cantidad INTEGER, fecha_corte DATETIME)')
conn.commit()

# --- Obtener ID Actual ---
res_id = c.execute("SELECT MAX(revision_id) FROM existencias").fetchone()
rev_actual = res_id[0] if res_id[0] else 1

# ------------------ CAPTURA ------------------
st.header(f"📍 Paso 1: Conteo Físico (Revisión #{rev_actual})")
with st.container(border=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # Buscamos nombres existentes para sugerir
        nombres_sugeridos = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM existencias").fetchall()]
        nombre = st.selectbox("Producto:", ["-- Nuevo --"] + nombres_sugeridos)
        if nombre == "-- Nuevo --":
            nombre = st.text_input("Nombre del pan:").upper()
    with col2:
        f_cad = st.date_input("Caducidad:")
    with col3:
        cant = st.number_input("¿Cuántos ves?", min_value=1, value=1)

    if st.button("➕ Registrar Pan"):
        for _ in range(int(cant)):
            c.execute("INSERT INTO existencias VALUES (?, ?, ?)", (nombre, f_cad, rev_actual))
        conn.commit()
        st.rerun()

# --- Tabla de lo que hay hoy ---
df_hoy = pd.read_sql("SELECT nombre, fecha_cad, COUNT(*) as cantidad FROM existencias WHERE revision_id = ? GROUP BY nombre, fecha_cad", conn, params=(rev_actual,))
if not df_hoy.empty:
    st.subheader("Tu conteo de hoy:")
    st.dataframe(df_hoy, use_container_width=True)

# ------------------ COMPARACIÓN (EL CORTE) ------------------
st.divider()
st.header("🏁 Paso 2: Realizar Corte")

if st.button("CALCULAR VENTAS (Comparar con revisión anterior)", type="primary"):
    rev_anterior = rev_actual - 1
    
    if rev_anterior < 1:
        st.info("Esta es tu primera revisión. No hay nada contra qué comparar todavía. ¡Sigue capturando!")
        # Forzamos el salto a la siguiente revisión para que ya haya un "pasado"
        c.execute("UPDATE existencias SET revision_id = 2 WHERE revision_id = 1")
        conn.commit()
        st.rerun()
    else:
        # 1. Traer datos de ambos conteos
        df_ant = pd.read_sql("SELECT nombre, fecha_cad, COUNT(*) as cant FROM existencias WHERE revision_id = ? GROUP BY nombre, fecha_cad", conn, params=(rev_anterior,))
        
        # 2. Comparar en Python (para que sea visual e inmediato)
        comparativa = []
        for _, fila in df_ant.iterrows():
            # ¿Cuántos hay de este mismo pan y fecha en el conteo de HOY?
            ahora = len(c.execute("SELECT 1 FROM existencias WHERE nombre=? AND fecha_cad=? AND revision_id=?", 
                                 (fila['nombre'], fila['fecha_cad'], rev_actual)).fetchall())
            
            diferencia = fila['cant'] - ahora
            if diferencia > 0:
                comparativa.append({
                    "Producto": fila['nombre'],
                    "Caducidad": fila['fecha_cad'],
                    "Había": fila['cant'],
                    "Quedan": ahora,
                    "VENDIDOS": diferencia
                })
                # Guardar en historial
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", 
                         (fila['nombre'], fila['fecha_cad'], diferencia, datetime.now()))

        # 3. MOSTRAR RESULTADOS ANTES DE BORRAR
        if comparativa:
            st.success("¡Ventas detectadas!")
            st.table(pd.DataFrame(comparativa))
        else:
            st.warning("No se detectaron ventas. El inventario está igual.")

        # 4. LIMPIEZA DE BASE DE DATOS
        # Borramos el registro "viejo" (el que era el pasado)
        c.execute("DELETE FROM existencias WHERE revision_id = ?", (rev_anterior,))
        # El conteo de HOY se convierte en el nuevo PASADO (ID + 1)
        c.execute("UPDATE existencias SET revision_id = ? WHERE revision_id = ?", (rev_actual + 1, rev_actual))
        conn.commit()
        
        st.info(f"Corte completado. La base de datos se preparó para la Revisión #{rev_actual + 1}")

# --- HISTORIAL ---
with st.expander("Ver todas las ventas pasadas"):
    st.dataframe(pd.read_sql("SELECT * FROM historial_ventas", conn))

if st.sidebar.button("Reiniciar TODA la App (Borrar todo)"):
    c.execute("DELETE FROM existencias")
    c.execute("DELETE FROM historial_ventas")
    conn.commit()
    st.rerun()
