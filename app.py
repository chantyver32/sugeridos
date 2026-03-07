import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE ZONA HORARIA (MÉXICO) ------------------
zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()

# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario y Corte de Ventas 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

# 1. captura_actual: Lo que anotas en pantalla ahorita
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
# 2. base_anterior: Lo que el sistema "sabe" que hay en estantes (memoria interna)
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
# 3. historial_ventas: Registro de todas las ventas pasadas
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ SECCIÓN 1: CAPTURA FÍSICA ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")
st.info("Instrucciones: Anota todos los productos que ves físicamente en los estantes en este momento.")

with st.container(border=True):
    # Sugerencias de nombres basadas en lo que ya existe
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev)
        if opcion == "-- Nuevo Producto --":
            nombre = st.text_input("Escribe el nombre del pan:").upper()
        else:
            nombre = opcion
    
    with col2:
        # Calendario ajustado a México (inicia en HOY)
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    
    with col3:
        cant = st.number_input("Cantidad física que ves:", min_value=1, value=1, step=1)

    if st.button("➕ Registrar Pan en el Conteo", use_container_width=True):
        if nombre and nombre.strip() != "":
            # Si ya existe en la captura de hoy, sumamos la cantidad
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre, f_cad)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre, f_cad, int(cant)))
            conn.commit()
            st.rerun()
        else:
            st.error("Por favor, escribe un nombre para el producto.")

# --- Tabla de Captura Actual (Lo que el usuario ve) ---
df_hoy = pd.read_sql("SELECT * FROM captura_actual", conn)
if not df_hoy.empty:
    st.subheader("📋 Tu conteo de este momento:")
    st.dataframe(df_hoy, use_container_width=True, hide_index=True)
    if st.button("🗑️ Limpiar esta lista y empezar de nuevo"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# ------------------ SECCIÓN 2: REALIZAR CORTE (COMPARACIÓN) ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar Revisión")
st.write("Al presionar este botón, compararemos tu conteo contra lo que había anteriormente.")

if st.button("REALIZAR CORTE Y CALCULAR VENTAS", type="primary", use_container_width=True):
    if df_hoy.empty:
        st.warning("No hay datos capturados para comparar.")
    else:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        
        if df_anterior.empty:
            # Primera vez: Lo de hoy se vuelve la base interna directamente
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.success("✅ Primer inventario guardado. Estos datos servirán de base para el próximo corte.")
            st.rerun()
        else:
            # Lógica de Comparación
            ventas_detectadas = []
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            
            # Comparamos lo que había antes contra lo que hay hoy
            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", 
                                   (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                
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

            # ACTUALIZACIÓN DE MEMORIA: 
            # Lo que contaste hoy pasa a ser la nueva "Base Anterior"
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()

            if ventas_detectadas:
                st.balloons()
                st.subheader("📊 Resumen de Ventas en este turno:")
                st.table(pd.DataFrame(ventas_detectadas))
            else:
                st.info("No se detectaron ventas. El inventario coincide perfectamente.")
            
            st.warning("🔄 La pantalla se ha limpiado. El sistema guardó los datos actuales para la próxima comparación.")

# ------------------ SECCIÓN 3: INVENTARIO ACTUAL (ESTANTES) ------------------
st.divider()
st.header("🏪 ¿Qué hay en mis estantes ahora?")
st.write("Esta es la existencia teórica basada en el último corte realizado.")

df_estantes = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Caducidad], cantidad as Cantidad FROM base_anterior", conn)

if not df_estantes.empty:
    st.metric("Total de piezas en exhibición", f"{int(df_estantes['Cantidad'].sum())} panes")
    st.dataframe(df_estantes, use_container_width=True, hide_index=True)
else:
    st.warning("Aún no hay inventario registrado en los estantes.")

# ------------------ SECCIÓN 4: HISTORIAL Y RESET ------------------
with st.expander("📖 Ver Historial de Ventas Acumuladas"):
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    if not df_hist.empty:
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.write("No hay ventas registradas todavía.")

if st.sidebar.button("⚠️ RESET TOTAL (Borrar todo el sistema)"):
    c.execute("DELETE FROM captura_actual")
    c.execute("DELETE FROM base_anterior")
    c.execute("DELETE FROM historial_ventas")
    conn.commit()
    st.rerun()
