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
    # Sugerencias dinámicas
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        opcion = st.selectbox("Producto:", ["-- Nuevo Producto --"] + nombres_prev, key="sel_prod")
        if opcion == "-- Nuevo Producto --":
            nombre_input = st.text_input("Nombre del pan:", key="txt_prod").upper()
        else:
            nombre_input = opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key="date_cad")
    
    with col3:
        cant = st.number_input("Cantidad que ves AHORA:", min_value=1, value=1, step=1, key="num_cant")

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

# --- TABLA EDITABLE DE CAPTURA ACTUAL ---
df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)

if not df_hoy_captura.empty:
    st.subheader("📋 Revisión de Captura (Edita o elimina aquí)")
    st.info("💡 Haz doble clic en una celda para editar. Selecciona una fila y presiona 'Suprimir' para borrar.")
    
    # Editor interactivo
    df_editado = st.data_editor(
        df_hoy_captura,
        column_config={
            "rowid": None, # Oculto para el usuario
            "nombre": st.column_config.TextColumn("Producto"),
            "fecha_cad": st.column_config.DateColumn("Caducidad"),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0)
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="editor_captura"
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 Guardar Cambios Realizados", use_container_width=True, type="secondary"):
            c.execute("DELETE FROM captura_actual")
            for _, row in df_editado.iterrows():
                if row['cantidad'] > 0:
                    c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", 
                             (row['nombre'].upper(), row['fecha_cad'], int(row['cantidad'])))
            conn.commit()
            st.success("¡Cambios guardados!")
            st.rerun()
            
    with col_btn2:
        if st.button("🗑️ Limpiar Toda la Pantalla", use_container_width=True):
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.rerun()

# ------------------ SECCIÓN 2: CORTE Y COMPARACIÓN (PASO 2) ------------------
st.divider()
st.header("🏁 Paso 2: Finalizar y Calcular Ventas")

if st.button("REALIZAR CORTE FINAL", type="primary", use_container_width=True):
    # Volvemos a leer para asegurar que tenemos lo último guardado
    df_final_captura = pd.read_sql("SELECT * FROM captura_actual", conn)
    
    if df_final_captura.empty:
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
        
        # EL RELEVO
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.success("✅ Corte realizado. Inventario actualizado.")
        st.rerun()

# Mostrar resultados del último corte
if 'ultimo_corte' in st.session_state:
    st.balloons()
    st.subheader("📊 Resultados del Último Corte:")
    st.table(st.session_state['ultimo_corte'])
    if st.button("Cerrar Tabla de Resultados"):
        del st.session_state['ultimo_corte']
        st.rerun()

# ------------------ SECCIÓN 3: ALERTAS Y ESTADO ACTUAL ------------------
st.divider()
st.header("⚠️ Alertas de Caducidad (HOY)")
fecha_str = fecha_hoy_mx.strftime('%Y-%m-%d')
df_caducan_hoy = pd.read_sql("SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad = ?", 
                             conn, params=(fecha_str,))

if not df_caducan_hoy.empty:
    st.error(f"¡Atención! Retirar {int(df_caducan_hoy['Cantidad'].sum())} piezas que caducan hoy.")
    st.dataframe(df_caducan_hoy, use_container_width=True, hide_index=True)
else:
    st.success("✅ No hay caducidades para hoy.")

st.header("🏪 Inventario Actual en Estantes")
df_estantes = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Caducidad], cantidad as Cantidad FROM base_anterior", conn)
if not df_estantes.empty:
    st.metric("Total piezas en exhibición", f"{int(df_estantes['Cantidad'].sum())} panes")
    st.dataframe(df_estantes, use_container_width=True, hide_index=True)

# ------------------ HISTORIAL ------------------
with st.expander("📖 Ver Historial de Ventas Acumulado"):
    st.dataframe(pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn), use_container_width=True)

if st.sidebar.button("⚠️ RESET TOTAL (Borrar todo)"):
    c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
    conn.commit()
    st.rerun()
