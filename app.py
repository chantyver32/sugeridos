import streamlit as st
import pd
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN DE PÁGINA (ESTILO LIMPIO) ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# CSS para ocultar menús de Streamlit y "fork" para una app más limpia
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
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
    # Clave dinámica para resetear widgets
    rk = st.session_state.reset_key
    
    # Sugerencias dinámicas
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
        cant = st.number_input("Cantidad que ves AHORA:", min_value=1, value=1, step=1, key=f"num_cant_{rk}")

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

# --- TABLA DE CAPTURA ACTUAL (EDITABLE) ---
df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)

if not df_hoy_captura.empty:
    df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date
    st.subheader("📋 Revisión del conteo (Edita o elimina filas aquí):")
    
    df_editado = st.data_editor(
        df_hoy_captura,
        column_config={
            "rowid": None,
            "nombre": st.column_config.TextColumn("Producto"),
            "fecha_cad": st.column_config.DateColumn("Fecha Caducidad"),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0)
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_conteo"
    )

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Guardar cambios realizados arriba", use_container_width=True):
            c.execute("DELETE FROM captura_actual")
            for _, fila in df_editado.iterrows():
                if fila['nombre']:
                    c.execute("INSERT INTO captura_actual (nombre, fecha_cad, cantidad) VALUES (?, ?, ?)", 
                             (fila['nombre'].strip().upper(), str(fila['fecha_cad']), int(fila['cantidad'])))
            conn.commit()
            st.success("¡Conteo actualizado!")
            st.rerun()
            
    with col_cancel:
        if st.button("🗑️ Borrar TODO el conteo actual", use_container_width=True):
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.rerun()

# ------------------ SECCIÓN 2: CORTE Y COMPARACIÓN (PASO 2) ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

if st.button("REALIZAR CORTE Y REINICIAR FORMULARIO", type="primary", use_container_width=True):
    df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
    
    if df_actualizado.empty:
        st.warning("No hay nada que comparar. La lista de captura está vacía.")
    else:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        
        if not df_anterior.empty:
            ventas_detectadas = []
            ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
            
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
                        "Quedan": cant_hoy,
                        "VENDIDOS": diferencia
                    })
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", 
                             (fila_ant['nombre'], fila_ant['fecha_cad'], diferencia, ts_mx))
            
            if ventas_detectadas:
                st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)
        
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.success("✅ Corte realizado con éxito.")
        st.rerun()

if 'ultimo_corte' in st.session_state:
    st.balloons()
    st.subheader("📊 Resumen de ventas detectadas:")
    st.table(st.session_state['ultimo_corte'])
    if st.button("Cerrar Resumen"):
        del st.session_state['ultimo_corte']
        st.rerun()

# ------------------ SECCIÓN 3: ALERTAS Y ESTADO ACTUAL ------------------
st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.header("⚠️ Alertas de Caducidad")
    fecha_str = fecha_hoy_mx.strftime('%Y-%m-%d')
    df_caducan_hoy = pd.read_sql("SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad = ?", 
                                 conn, params=(fecha_str,))

    if not df_caducan_hoy.empty:
        st.error(f"¡Atención! Retirar {int(df_caducan_hoy['Cantidad'].sum())} piezas.")
        st.dataframe(df_caducan_hoy, use_container_width=True, hide_index=True)
    else:
        st.success("✅ Todo bien hoy.")

with col_right:
    st.header("🏪 Inventario Actual")
    df_estantes = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Caducidad], cantidad as Cantidad FROM base_anterior", conn)
    if not df_estantes.empty:
        st.metric("Piezas totales", f"{int(df_estantes['Cantidad'].sum())}")
        st.dataframe(df_estantes, use_container_width=True, hide_index=True)
    else:
        st.info("Sin inventario.")

st.divider()
with st.expander("📖 Historial General"):
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    st.dataframe(df_hist, use_container_width=True)
    if not df_hist.empty:
        csv = df_hist.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", data=csv, file_name=f"ventas_{fecha_hoy_mx}.csv")

# ------------------ SECCIÓN 4: BOTÓN DE RESET TOTAL (HASTA ABAJO) ------------------
st.write("<br><br><br>", unsafe_allow_html=True)
st.divider()
st.subheader("⚙️ Configuración del Sistema")
with st.expander("🚨 Zona de Peligro (Reset de Base de Datos)"):
    st.write("Esta acción borrará todo el historial y el inventario actual de forma permanente.")
    confirmar_reset = st.checkbox("Confirmar que deseo borrar toda la base de datos", key="final_reset_check")
    
    if st.button("⚠️ EJECUTAR RESET TOTAL", type="secondary", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.success("Base de datos limpiada con éxito.")
            st.rerun()
        else:
            st.error("Primero debes marcar la casilla de confirmación.")
