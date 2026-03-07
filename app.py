import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ------------------ CONFIGURACIÓN ------------------
st.set_page_config(page_title="Control Pastelería", page_icon="🥐")
st.title("Sistema de Captura y Comparación 🥐")

conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

# 1. Tabla de CAPTURA ACTUAL (Lo que el usuario ve y anota ahora)
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
# 2. Tabla de BASE ANTERIOR (Lo que se anotó en la revisión pasada, para comparar)
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
# 3. Historial de Ventas
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ PASO 1: CAPTURA FÍSICA ------------------
st.header("🛒 Nueva Revisión: Captura de Estantes")
st.write("Anota los productos que hay **físicamente** en este momento.")

with st.container(border=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # Sugerencias basadas en lo que ya conocemos
        nombres_conocidos = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
        nombre = st.selectbox("Producto:", ["-- Nuevo --"] + nombres_conocidos)
        if nombre == "-- Nuevo --":
            nombre = st.text_input("Escribe el nombre:").upper()
    with col2:
        f_cad = st.date_input("Caducidad:", value=datetime.now().date())
    with col3:
        cant = st.number_input("Cantidad:", min_value=1, value=1)

    if st.button("➕ Agregar al Conteo", use_container_width=True):
        if nombre:
            # Buscamos si ya existe ese pan con esa fecha para SUMAR en lugar de crear fila nueva
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre, f_cad)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (cant, nombre, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre, f_cad, int(cant)))
            conn.commit()
            st.rerun()

# --- Mostrar lo que se está capturando AHORA ---
df_hoy = pd.read_sql("SELECT * FROM captura_actual", conn)
if not df_hoy.empty:
    st.subheader("📋 Tu conteo actual (lo que ves ahora):")
    st.dataframe(df_hoy, use_container_width=True)
    
    if st.button("🗑️ Borrar todo el conteo actual (Limpiar pantalla)"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()
else:
    st.info("La pantalla está limpia. Empieza a anotar los productos.")

# ------------------ PASO 2: CORTE Y COMPARACIÓN ------------------
st.divider()
st.header("🏁 Finalizar y Comparar")
st.write("Al presionar este botón, compararemos lo que acabas de anotar contra lo que había en la revisión pasada.")

if st.button("REALIZAR CORTE DE VENTAS", type="primary", use_container_width=True):
    if df_hoy.empty:
        st.warning("No puedes hacer un corte si no has anotado nada hoy.")
    else:
        # 1. Traer la Base Anterior (lo que se quedó guardado internamente la vez pasada)
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        
        if df_anterior.empty:
            st.success("✅ Primer registro guardado con éxito.")
            st.info("Como es la primera vez, no hay con qué comparar. Estos datos ahora son tu 'Base Interna'.")
            # Movemos lo de hoy a la base anterior y limpiamos pantalla
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.rerun()
        else:
            # 2. COMPARACIÓN LÓGICA
            analisis_ventas = []
            ahora_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for _, fila_ant in df_anterior.iterrows():
                # Buscamos el mismo pan en el conteo de hoy
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", 
                                   (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                
                cant_hoy = res_hoy[0] if res_hoy else 0
                vendidos = fila_ant['cantidad'] - cant_hoy
                
                if vendidos > 0:
                    analisis_ventas.append({
                        "Producto": fila_ant['nombre'],
                        "Caducidad": fila_ant['fecha_cad'],
                        "Había": fila_ant['cantidad'],
                        "Hay ahora": cant_hoy,
                        "VENDIDOS": vendidos
                    })
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", 
                             (fila_ant['nombre'], fila_ant['fecha_cad'], vendidos, ahora_timestamp))

            # 3. ACTUALIZAR BASE INTERNA
            # Borramos la base vieja y la reemplazamos por lo que contamos HOY
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            # Limpiamos la pantalla (captura actual)
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            
            # 4. MOSTRAR RESULTADOS
            if analisis_ventas:
                st.balloons()
                st.subheader("📊 Resultados del Corte:")
                st.table(pd.DataFrame(analisis_ventas))
            else:
                st.info("El inventario coincide perfectamente. No se registraron ventas.")
            
            st.warning("⚠️ La pantalla de captura se ha limpiado. Lo que anotaste ahora es la base para la siguiente revisión.")

# ------------------ HISTORIAL ------------------
with st.expander("📖 Ver todas las ventas acumuladas"):
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    st.dataframe(df_hist, use_container_width=True)

if st.sidebar.button("RESETEAR TODO (Borrar memoria interna)"):
    c.execute("DELETE FROM captura_actual")
    c.execute("DELETE FROM base_anterior")
    c.execute("DELETE FROM historial_ventas")
    conn.commit()
    st.rerun()
