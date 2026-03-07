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
st.title("Sistema de Inventario y Corte de Ventas 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# --- Función para limpiar los campos del Paso 1 ---
def limpiar_formulario():
    st.session_state["prod_input"] = "-- Nuevo Producto --"
    st.session_state["txt_nombre"] = ""
    st.session_state["fecha_input"] = fecha_hoy_mx
    st.session_state["cant_input"] = 1

# ------------------ SECCIÓN 1: CAPTURA FÍSICA (PASO 1) ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

with st.container(border=True):
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key="prod_input")
        if opcion == "-- Nuevo Producto --":
            nombre_final = st.text_input("Nombre del pan:", key="txt_nombre").upper()
        else:
            nombre_final = opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key="fecha_input")
    
    with col3:
        cant = st.number_input("Cantidad que ves AHORA:", min_value=1, value=1, step=1, key="cant_input")

    if st.button("➕ Registrar en el Conteo", use_container_width=True):
        if nombre_final and nombre_final.strip() != "":
            nombre_limpio = nombre_final.strip().upper()
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_limpio, f_cad)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_limpio, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_limpio, f_cad, int(cant)))
            conn.commit()
            if opcion == "-- Nuevo Producto --":
                st.session_state["txt_nombre"] = ""
            st.rerun()

# --- TABLA DE CAPTURA CON OPCIÓN DE ELIMINAR INDIVIDUAL ---
df_hoy = pd.read_sql("SELECT * FROM captura_actual", conn)
if not df_hoy.empty:
    st.subheader("📋 Tu conteo actual:")
    st.dataframe(df_hoy, use_container_width=True, hide_index=True)
    
    # --- NUEVA FUNCIÓN: ELIMINAR REGISTRO ESPECÍFICO ---
    with st.expander("🛠️ Editar o Eliminar un registro de la lista"):
        # Creamos una lista de textos descriptivos para el selectbox
        opciones_borrar = [f"{row['nombre']} ({row['fecha_cad']})" for _, row in df_hoy.iterrows()]
        seleccion_borrar = st.selectbox("Selecciona el pan que quieres quitar:", opciones_borrar)
        
        if st.button("🗑️ Eliminar este pan de la lista", type="secondary"):
            # Extraemos el nombre y la fecha para el DELETE
            # (El formato es "NOMBRE (FECHA)")
            nombre_borrar = seleccion_borrar.split(" (")[0]
            fecha_borrar = seleccion_borrar.split(" (")[1].replace(")", "")
            
            c.execute("DELETE FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_borrar, fecha_borrar))
            conn.commit()
            st.success(f"Eliminado: {nombre_borrar}")
            st.rerun()

    if st.button("⚠️ Borrar toda la lista", type="secondary"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# ------------------ SECCIÓN 2: CORTE Y LIMPIEZA TOTAL (PASO 2) ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar Revisión")

if st.button("REALIZAR CORTE Y LIMPIAR TODO", type="primary", use_container_width=True):
    if df_hoy.empty:
        st.warning("No hay datos para comparar.")
    else:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
        
        if not df_anterior.empty:
            ventas_detectadas = []
            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                diff = fila_ant['cantidad'] - cant_hoy
                if diff > 0:
                    ventas_detectadas.append({"Producto": fila_ant['nombre'], "VENDIDOS": diff})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", (fila_ant['nombre'], fila_ant['fecha_cad'], diff, ts_mx))
            
            if ventas_detectadas:
                st.session_state["ultimo_corte"] = pd.DataFrame(ventas_detectadas)

        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        
        limpiar_formulario()
        st.success("✅ Corte realizado. El formulario se ha reiniciado.")
        st.rerun()

# Mostrar resultados flotantes
if "ultimo_corte" in st.session_state:
    st.balloons()
    st.subheader("📊 Ventas del último turno:")
    st.table(st.session_state["ultimo_corte"])
    if st.button("Cerrar resultados"):
        del st.session_state["ultimo_corte"]
        st.rerun()

# ------------------ SECCIÓN 3: ESTADO DE ESTANTES Y CADUCIDADES ------------------
st.divider()
col_a, col_b = st.columns(2)

with col_a:
    st.header("⚠️ Caducan Hoy")
    df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(fecha_hoy_mx.strftime('%Y-%m-%d'),))
    if not df_cad.empty:
        st.error(f"Retirar {int(df_cad['cantidad'].sum())} piezas.")
        st.table(df_cad)
    else:
        st.success("Nada caduca hoy.")

with col_b:
    st.header("🏪 En Estantes")
    df_est = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM base_anterior", conn)
    if not df_est.empty:
        st.dataframe(df_est, use_container_width=True, hide_index=True)
    else:
        st.write("Estantes vacíos.")

# ------------------ HISTORIAL ------------------
with st.expander("📖 Historial de Ventas"):
    st.dataframe(pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn), use_container_width=True)

if st.sidebar.button("⚠️ RESET TOTAL"):
    c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
    conn.commit()
    limpiar_formulario()
    st.rerun()
