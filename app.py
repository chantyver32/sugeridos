import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz  # Necesaria para la zona horaria de México

# ------------------ CONFIGURACIÓN DE ZONA HORARIA ------------------
# Definimos la zona horaria de Ciudad de México
zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()

# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Control Pastelería MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario y Corte de Ventas 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

# 1. Captura Actual (Lo que el usuario anota hoy)
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
# 2. Base Anterior (Memoria interna del último corte)
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
# 3. Historial de Ventas (Resultados de las comparaciones)
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ SECCIÓN 1: CAPTURA FÍSICA (PASO 1) ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")
st.info("Anota todo lo que ves físicamente en este momento.")

with st.container(border=True):
    # Sugerencias de nombres para no escribir siempre
    nombres_con = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo --"] + nombres_con)
        nombre = st.text_input("Nombre del pan:").upper() if opcion == "-- Nuevo --" else opcion
    
    with col2:
        # CALENDARIO INICIANDO EN HOY (ZONA MX)
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    
    with col3:
        cant = st.number_input("Cantidad detectada:", min_value=1, value=1, step=1)

    if st.button("➕ Registrar en Conteo de Hoy", use_container_width=True):
        if nombre:
            # Sumar si ya existe en la captura de hoy
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre, f_cad)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre, f_cad, int(cant)))
            conn.commit()
            st.rerun()

# --- Tabla Visual de Captura ---
df_hoy = pd.read_sql("SELECT * FROM captura_actual", conn)
if not df_hoy.empty:
    st.subheader("📋 Tu conteo actual (Lo que estás anotando):")
    st.dataframe(df_hoy, use_container_width=True, hide_index=True)
    if st.button("🗑️ Limpiar pantalla (Borrar conteo de hoy)"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# ------------------ SECCIÓN 2: REALIZAR CORTE (PASO 2) ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar y Comparar")

if st.button("REALIZAR CORTE Y CALCULAR VENTAS", type="primary", use_container_width=True):
    if df_hoy.empty:
        st.warning("Primero debes anotar qué hay en los estantes hoy.")
    else:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        
        if df_anterior.empty:
            # Es la primera vez, solo guardamos como base
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.success("✅ Primer inventario guardado como base. ¡Listo para comparar en el siguiente turno!")
            st.rerun()
        else:
            # COMPARACIÓN
            ventas = []
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            
            for _, ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (ant['nombre'], ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                
                diff = ant['cantidad'] - cant_hoy
                if diff > 0:
                    ventas.append({"Producto": ant['nombre'], "Caducidad": ant['fecha_cad'], "Había": ant['cantidad'], "Hay": cant_hoy, "VENDIDOS": diff})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", (ant['nombre'], ant['fecha_cad'], diff, ts_mx))

            # RELEVO DE DATOS: Lo de hoy pasa a ser la base de mañana
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()

            if ventas:
                st.balloons()
                st.subheader("📊 Resultados del Corte (Ventas detectadas):")
                st.table(pd.DataFrame(ventas))
            else:
                st.info("No hubo ventas. El inventario coincide con el anterior.")
            st.warning("La pantalla se ha limpiado. El sistema guardó internamente lo que hay en estantes para la siguiente revisión.")

# ------------------ SECCIÓN 3: INVENTARIO REAL AHORA ------------------
st.divider()
st.header("🏪 ¿Qué hay en mis estantes ahora?")
df_real = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Caducidad], cantidad as Cantidad FROM base_anterior", conn)

if not df_
