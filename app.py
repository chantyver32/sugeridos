import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE PÁGINA (ESTILO LIMPIO) ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# CSS para ocultar menús de Streamlit y "fork"
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stTable { background-color: #f9f9f9; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

# ------------------ CONFIGURACIÓN DE ZONA HORARIA (MÉXICO) ------------------
zona_mx = pytz.timezone('America/Mexico_City')
ahora_mx = datetime.now(zona_mx)
fecha_hoy_mx = ahora_mx.date()

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS historial_ventas (nombre TEXT, fecha_cad DATE, vendidos INTEGER, fecha_corte DATETIME)')
conn.commit()

# ------------------ LÓGICA DE RESET DE FORMULARIO ------------------
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

def reset_formulario():
    st.session_state.reset_key += 1

# ------------------ SECCIÓN 1: CAPTURA FÍSICA (PASO 1) ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

with st.container(border=True):
    rk = st.session_state.reset_key
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key=f"sel_prod_{rk}")
        if opcion == "-- Nuevo Producto --":
            nombre_input = st.text_input("Nombre del pan:", key=f"txt_prod_{rk}").upper()
        else:
            nombre_input = opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key=f"date_cad_{rk}")
    
    with col3:
        cant = st.number_input("Cantidad física actual:", min_value=1, value=1, step=1, key=f"num_cant_{rk}")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Registrar en el Conteo", use_container_width=True, type="primary"):
            if nombre_input and nombre_input.strip() != "":
                nombre_final = nombre_input.strip().upper()
                existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad)).fetchone()
                if existe:
                    c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad))
                else:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad, int(cant)))
                conn.commit()
                reset_formulario()
                st.rerun()
    
    with col_btn2:
        if st.button("🧹 Limpiar Formulario", use_container_width=True):
            reset_formulario()
            st.rerun()

# --- REVISIÓN DE CAPTURA ---
df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
if not df_hoy_captura.empty:
    df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
    st.subheader("📋 Lista de Captura Actual:")
    df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, use_container_width=True, hide_index=True, key="editor_conteo")

    if st.button("💾 Guardar cambios de tabla", use_container_width=True):
        c.execute("DELETE FROM captura_actual")
        for _, fila in df_editado.iterrows():
            if fila['nombre']:
                c.execute("INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)", 
                         (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
        conn.commit()
        st.rerun()

# ------------------ SECCIÓN 2: CORTE Y ANIMACIÓN ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

if st.button("🚀 REALIZAR CORTE FINAL", type="primary", use_container_width=True):
    df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
    
    if df_actualizado.empty:
        st.warning("No hay productos en la captura actual para realizar el corte.")
    else:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        ventas_resumen = []
        ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
        
        if not df_anterior.empty:
            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", 
                                   (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                diferencia = fila_ant['cantidad'] - cant_hoy
                
                if diferencia > 0:
                    ventas_resumen.append({"Producto": fila_ant['nombre'], "Cantidad Vendida": diferencia})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", 
                             (fila_ant['nombre'], fila_ant['fecha_cad'], diferencia, ts_mx))
        
        # Guardar en estado para mostrar después del rerun
        st.session_state['resumen_corte'] = pd.DataFrame(ventas_resumen) if ventas_resumen else "Sin ventas detectadas"
        st.session_state['mostrar_globos'] = True
        
        # Mover captura a base anterior y limpiar
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# Lógica para mostrar globos y resumen tras el corte
if 'mostrar_globos' in st.session_state:
    st.balloons()
    st.success("✅ ¡Corte realizado con éxito!")
    if isinstance(st.session_state['resumen_corte'], pd.DataFrame):
        st.subheader("📊 Resumen de Ventas del Corte:")
        st.table(st.session_state['resumen_corte'])
    else:
        st.info(st.session_state['resumen_corte'])
    
    if st.button("Cerrar Resumen"):
        del st.session_state['mostrar_globos']
        del st.session_state['resumen_corte']
        st.rerun()

# ------------------ SECCIÓN 3: ESTADO ACTUAL ------------------
st.divider()
col_a, col_b = st.columns(2)
with col_a:
    st.header("⚠️ Vencimientos Hoy")
    df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
    st.dataframe(df_cad, use_container_width=True, hide_index=True) if not df_cad.empty else st.success("✅ No hay mermas hoy.")

with col_b:
    st.header("🏪 Stock en Tienda")
    df_stock = pd.read_sql("SELECT nombre, cantidad FROM base_anterior", conn)
    st.metric("Total Piezas", f"{int(df_stock['cantidad'].sum())}") if not df_stock.empty else st.write("Inventario vacío")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

# ------------------ SECCIÓN 4: RESET TOTAL (HASTA ABAJO) ------------------
st.write("<br><br><br>", unsafe_allow_html=True)
st.divider()
with st.expander("⚙️ Configuración Avanzada / Reset"):
    st.warning("Esta zona borra TODA la base de datos de forma permanente.")
    confirmar = st.checkbox("Confirmar borrado total")
    if st.button("🔥 EJECUTAR RESET TOTAL", type="secondary", use_container_width=True):
        if confirmar:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.success("Base de datos reiniciada.")
            st.rerun()
        else:
            st.error("Marca la casilla para confirmar.")
