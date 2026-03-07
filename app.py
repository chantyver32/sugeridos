import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE ZONA HORARIA ------------------
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

# ------------------ PÁGINA ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ LÓGICA DE LIMPIEZA AUTOMÁTICA ------------------
# Esta función asegura que los campos queden en blanco sin causar errores de API
def reset_campos():
    st.session_state["sel_prod"] = "-- Nuevo Producto --"
    st.session_state["num_cant"] = 1
    st.session_state["date_cad"] = fecha_hoy_mx
    if "txt_prod" in st.session_state:
        st.session_state["txt_prod"] = ""

# ------------------ SIDEBAR ------------------
st.sidebar.header("⚙️ Configuración")
with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar borrar todo")
    if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            reset_campos()
            st.rerun()

# ------------------ PASO 1: CAPTURA ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

with st.container(border=True):
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key="sel_prod")
        nombre_input = st.text_input("Nombre del pan:", key="txt_prod").upper() if opcion == "-- Nuevo Producto --" else opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key="date_cad")
    
    with col3:
        cant = st.number_input("Cantidad actual:", min_value=1, value=1, key="num_cant")

    if st.button("➕ Registrar en el Conteo", use_container_width=True):
        if nombre_input and str(nombre_input).strip() != "":
            nombre_final = str(nombre_input).strip().upper()
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
            conn.commit()
            reset_campos() # <--- Limpia todo después de agregar
            st.rerun()

# ------------------ TABLA EDITABLE ------------------
df_hoy = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)

if not df_hoy.empty:
    # IMPORTANTE: Esto arregla el error de "type_compatibilities" de la foto
    df_hoy['fecha_cad'] = pd.to_datetime(df_hoy['fecha_cad']).dt.date
    
    st.subheader("📋 Revisión (Edita o borra si es necesario):")
    df_editado = st.data_editor(
        df_hoy,
        column_config={
            "rowid": None,
            "nombre": "Producto",
            "fecha_cad": st.column_config.DateColumn("Caducidad"),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0)
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_conteo"
    )

    if st.button("💾 Guardar cambios en la lista", use_container_width=True):
        c.execute("DELETE FROM captura_actual")
        for _, fila in df_editado.iterrows():
            if fila['nombre']:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (fila['nombre'], str(fila['fecha_cad']), int(fila['cantidad'])))
        conn.commit()
        st.success("Cambios guardados.")
        st.rerun()

# ------------------ PASO 2: CORTE ------------------
st.divider()
st.header("🏁 Paso 2: Realizar Corte")

if st.button("REALIZAR CORTE Y LIMPIAR TODO", type="primary", use_container_width=True):
    df_hoy_check = pd.read_sql("SELECT * FROM captura_actual", conn)
    if df_hoy_check.empty:
        st.warning("No hay datos para procesar.")
    else:
        df_ant = pd.read_sql("SELECT * FROM base_anterior", conn)
        if not df_ant.empty:
            ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
            for _, f_ant in df_ant.iterrows():
                h = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (f_ant['nombre'], f_ant['fecha_cad'])).fetchone()
                cant_h = h[0] if h else 0
                dif = f_ant['cantidad'] - cant_h
                if dif > 0:
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", (f_ant['nombre'], f_ant['fecha_cad'], dif, ts_mx))
        
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        reset_campos() # <--- Limpia todo después del corte
        st.success("✅ Corte finalizado. Pantalla limpia.")
        st.rerun()

# ------------------ ESTADO ACTUAL ------------------
st.divider()
c1, c2 = st.columns(2)
with c1:
    st.subheader("⚠️ Caducan Hoy")
    cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(fecha_today_mx,))
    if not cad.empty: st.error(f"Retirar {int(cad['cantidad'].sum())} piezas."); st.table(cad)
    else: st.success("Sin caducidades.")
with c2:
    st.subheader("🏪 En Estantes")
    inv = pd.read_sql("SELECT nombre, cantidad FROM base_anterior", conn)
    if not inv.empty: st.metric("Total Panes", int(inv['cantidad'].sum())); st.dataframe(inv, hide_index=True)
