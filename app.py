import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE ZONA HORARIA (MÉXICO) ------------------
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ SECCIÓN 1: CAPTURA FÍSICA ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

with st.container(border=True):
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev)
        nombre_input = st.text_input("Nombre del pan:").upper() if opcion == "-- Nuevo Producto --" else opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    
    with col3:
        cant = st.number_input("Cantidad que ves AHORA:", min_value=1, value=1, step=1)

    if st.button("➕ Registrar en el Conteo", use_container_width=True):
        if nombre_input and nombre_input.strip() != "":
            nombre_final = nombre_input.strip().upper()
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
            conn.commit()
            st.rerun()

# --- Visualización de Captura Actual ---
df_hoy_captura = pd.read_sql("SELECT * FROM captura_actual", conn)
if not df_hoy_captura.empty:
    st.subheader("📋 Tu conteo de este momento:")
    st.dataframe(df_hoy_captura, use_container_width=True, hide_index=True)
    if st.button("🗑️ Limpiar este conteo"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# ------------------ SECCIÓN 2: CORTE Y COMPARACIÓN ------------------
st.divider()
st.header("🏁 Paso 2: Realizar Corte")

if st.button("CALCULAR VENTAS", type="primary", use_container_width=True):
    df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
    
    if df_anterior.empty:
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.success("✅ Base inicial establecida.")
        st.rerun()
    else:
        ventas_detectadas = []
        ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
        
        for _, fila_ant in df_anterior.iterrows():
            res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", 
                               (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
            
            # Si no se anotó hoy, es que hay 0 (se vendió todo lo que había)
            cant_hoy = res_hoy[0] if res_hoy else 0
            diferencia = fila_ant['cantidad'] - cant_hoy
            
            if diferencia > 0:
                ventas_detectadas.append({
                    "Producto": fila_ant['nombre'],
                    "Caducidad": fila_ant['fecha_cad'],
                    "Había": fila_ant['cantidad'],
                    "Hay Hoy": cant_hoy,
                    "VENDIDOS": diferencia
                })
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", 
                         (fila_ant['nombre'], fila_ant['fecha_cad'], diferencia, ts_mx))

        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()

        if ventas_detectadas:
            st.balloons()
            st.subheader("📊 Resumen de Ventas:")
            st.table(pd.DataFrame(ventas_detectadas))
        else:
            st.info("No se detectaron ventas.")
        st.rerun()

# ------------------ SECCIÓN 3: ALERTAS DE CADUCIDAD ------------------
st.divider()
st.header("⚠️ Alertas de Caducidad (HOY)")

# Buscamos en la base_anterior (lo que hay en estantes) los que caducan hoy
# Convertimos la fecha de hoy a string para la comparación en SQL
fecha_str = fecha_hoy_mx.strftime('%Y-%m-%d')
df_caducan_hoy = pd.read_sql("SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad = ?", 
                             conn, params=(fecha_str,))

if not df_caducan_hoy.empty:
    st.error(f"¡Atención! Tienes {int(df_caducan_hoy['Cantidad'].sum())} piezas que caducan hoy {fecha_hoy_mx.strftime('%d/%m/%Y')}:")
    st.dataframe(df_caducan_hoy, use_container_width=True, hide_index=True)
else:
    st.success("✅ No hay productos que caduquen el día de hoy.")

# ------------------ SECCIÓN 4: INVENTARIO TOTAL EN ESTANTES ------------------
st.header("🏪 Inventario Total en Exhibición")
df_estantes = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Caducidad], cantidad as Cantidad FROM base_anterior", conn)

if not df_estantes.empty:
    st.metric("Total piezas en estantes", f"{int(df_estantes['Cantidad'].sum())} panes")
    st.dataframe(df_estantes, use_container_width=True, hide_index=True)
else:
    st.warning("No hay productos registrados en los estantes.")

# ------------------ SECCIÓN 5: HISTORIAL ------------------
with st.expander("📖 Ver Historial de Ventas"):
    st.dataframe(pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn), use_container_width=True)

if st.sidebar.button("⚠️ RESET TOTAL"):
    c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
    conn.commit()
    st.rerun()
