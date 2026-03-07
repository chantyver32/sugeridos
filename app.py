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

# ------------------ SECCIÓN 1: CAPTURA FÍSICA (PASO 1) ------------------
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
        cant = st.number_input("Cantidad que ves AHORA:", min_value=1, value=1, step=1, key="num_cant")

    if st.button("➕ Registrar en el Conteo", use_container_width=True):
        if nombre_input and nombre_input.strip() != "":
            nombre_final = nombre_input.strip().upper()
            # Convertimos la fecha a string para SQLite
            f_cad_str = f_cad.strftime('%Y-%m-%d')
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, f_cad_str)).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, f_cad_str))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, f_cad_str, int(cant)))
            conn.commit()
            st.rerun()

# --- TABLA EDITABLE DE CAPTURA ACTUAL ---
# Cargamos los datos asegurando que la fecha sea reconocida como objeto fecha para el editor
df_hoy_captura = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM captura_actual", conn)
if not df_hoy_captura.empty:
    df_hoy_captura['fecha_cad'] = pd.to_datetime(df_hoy_captura['fecha_cad']).dt.date

if not df_hoy_captura.empty:
    st.subheader("📋 Revisión de Captura (Edita o elimina aquí)")
    st.info("💡 Haz doble clic para editar. Para borrar: selecciona la fila y presiona 'Suprimir' (Delete).")
    
    # Usamos el editor sin 'key' conflictiva o con una lógica de guardado más limpia
    df_editado = st.data_editor(
        df_hoy_captura,
        column_config={
            "nombre": st.column_config.TextColumn("Producto", required=True),
            "fecha_cad": st.column_config.DateColumn("Caducidad", required=True),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, required=True)
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic"
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 Guardar Cambios Realizados", use_container_width=True, type="primary"):
            c.execute("DELETE FROM captura_actual")
            for _, row in df_editado.iterrows():
                # Validar que no haya nulos y cantidad > 0
                if pd.notnull(row['nombre']) and row['cantidad'] > 0:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", 
                             (str(row['nombre']).upper(), str(row['fecha_cad']), int(row['cantidad'])))
            conn.commit()
            st.success("¡Captura actualizada!")
            st.rerun()
            
    with col_btn2:
        if st.button("🗑️ Borrar toda la lista", use_container_width=True):
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.rerun()

# ------------------ SECCIÓN 2: CORTE Y COMPARACIÓN (PASO 2) ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

if st.button("REALIZAR CORTE FINAL (Cerrar caja)", use_container_width=True):
    df_actual = pd.read_sql("SELECT * FROM captura_actual", conn)
    
    if df_actual.empty:
        st.warning("Agrega productos primero.")
    else:
        df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
        if not df_anterior.empty:
            ts_mx = ahora_mx.strftime("%Y-%m-%d %H:%M:%S")
            ventas_list = []
            
            for _, ant in df_anterior.iterrows():
                # Buscamos el mismo producto y fecha en la captura de hoy
                hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", 
                               (ant['nombre'], ant['fecha_cad'])).fetchone()
                
                cant_hoy = hoy[0] if hoy else 0
                dif = ant['cantidad'] - cant_hoy
                
                if dif > 0:
                    ventas_list.append({"Producto": ant['nombre'], "Caducidad": ant['fecha_cad'], "Vendidos": dif})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", (ant['nombre'], ant['fecha_cad'], dif, ts_mx))
            
            if ventas_list:
                st.session_state['res_corte'] = pd.DataFrame(ventas_list)

        # Relevo de inventario
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

if 'res_corte' in st.session_state:
    st.success("✅ Corte finalizado con éxito.")
    st.table(st.session_state['res_corte'])
    if st.button("Entendido"):
        del st.session_state['res_corte']
        st.rerun()

# ------------------ SECCIÓN 3: ESTADO ------------------
st.divider()
st.subheader("🏪 Inventario Actual en Piso")
df_piso = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM base_anterior", conn)
if not df_piso.empty:
    st.dataframe(df_piso, use_container_width=True, hide_index=True)
else:
    st.write("El estante está vacío.")

with st.expander("📖 Historial de Ventas"):
    st.dataframe(pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn), use_container_width=True)

if st.sidebar.button("⚠️ RESET TOTAL"):
    c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
    conn.commit()
    st.rerun()
