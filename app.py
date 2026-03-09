import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

st.markdown("""
    <style>
    [data-testid="stHeader"] {display:none;}
    .block-container {padding-top: 1rem;}
    </style>
    """, unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT, fecha_cad DATE, habia INTEGER, quedan INTEGER, vendidos INTEGER, fecha_corte DATETIME
)''')
conn.commit()

# ------------------ FUNCIONES DE ESTADO ------------------
def limpiar_buscador():
    st.session_state.busqueda_input = ""

def sumar_cantidad(valor):
    st.session_state.conteo_temp += valor

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 AÑADIR PRODUCTOS", "📦 INVENTARIO Y CORTE", "📊 ANÁLISIS"])

with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    col_busq, col_limpiar = st.columns([4, 1])
    with col_busq:
        # Usamos el key 'busqueda_input' para controlar el widget
        buscar = st.text_input("Buscador", placeholder="🔎 BUSCAR O ESCRIBIR PRODUCTO...", key="busqueda_input").upper()
    with col_limpiar:
        # El botón ahora usa un callback para limpiar sin errores de API
        st.button("🧹 Limpiar", on_click=limpiar_buscador, use_container_width=True)

    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        nombre_input = st.selectbox("Producto:", sugerencias, key="sel_prod") if sugerencias else buscar
    with col2:
        f_cad = st.date_input("Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    with col3:
        st.metric("A añadir", st.session_state.conteo_temp)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar_cantidad, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar_cantidad, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar_cantidad, args=(10,))
    with c4: 
        if st.button("Borrar Cantidad", use_container_width=True):
            st.session_state.conteo_temp = 0

    if st.button("➕ REGISTRAR EN LISTA TEMPORAL", use_container_width=True, type="primary"):
        if nombre_input and str(nombre_input).strip() != "":
            nombre_final = str(nombre_input).strip().upper()
            cant = st.session_state.conteo_temp
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, str(f_cad))).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, str(f_cad)))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(cant)))
            conn.commit()
            st.session_state.conteo_temp = 0
            st.rerun()

    st.divider()
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM captura_actual", conn)
    
    if not df_hoy_captura.empty:
        st.subheader("📋 Lista de hoy (acumulativa)")
        df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        col_s, col_v = st.columns(2)
        with col_s:
            if st.button("💾 Guardar cambios en lista", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['Producto']:
                        c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (fila['Producto'].strip().upper(), str(fila['Fecha Cad']), int(fila['Cantidad'])))
                conn.commit()
                st.rerun()
        with col_v:
            if st.button("🗑️ Vaciar lista sin borrar DB", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

with tab2:
    # --- AQUÍ ESTÁ EL BOTÓN DE BORRADO TOTAL ---
    st.subheader("⚙️ Configuración y Mantenimiento")
    with st.expander("🚨 ZONA DE PELIGRO: BORRADO COMPLETO"):
        st.write("Esta acción eliminará el inventario actual y todo el historial de ventas permanentemente.")
        confirmar_todo = st.checkbox("Confirmo que quiero borrar TODA la base de datos")
        if st.button("⚠️ EJECUTAR BORRADO TOTAL", type="secondary", use_container_width=True):
            if confirmar_todo:
                c.execute("DELETE FROM captura_actual")
                c.execute("DELETE FROM base_anterior")
                c.execute("DELETE FROM historial_ventas")
                conn.commit()
                st.success("Sistema reiniciado.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Debes marcar la casilla de confirmación.")
    
    st.divider()
    
    if st.button("🚀 FINALIZAR CAPTURA Y REALIZAR CORTE", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actualizado.empty:
            st.warning("⚠️ No hay productos en la lista para comparar.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_detectadas = []

            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                diferencia = fila_ant['cantidad'] - cant_hoy
                
                if diferencia > 0:
                    ventas_detectadas.append({"Producto": fila_ant['nombre'], "Vendidos": diferencia})
                
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", 
                         (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']), int(cant_hoy), int(max(0, diferencia)), ts_mx))

            st.session_state['resumen_corte'] = pd.DataFrame(ventas_detectadas)
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.balloons()
            st.rerun()

    if 'resumen_corte' in st.session_state:
        st.success("✅ Corte realizado con éxito")
        st.table(st.session_state['resumen_corte'])
        if st.button("Cerrar Resumen"):
            del st.session_state['resumen_corte']
            st.rerun()

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("#### ⚠️ Caducan Hoy")
        df_cad = pd.read_sql("SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        if not df_cad.empty:
            st.error(f"⚠️ Retirar {int(df_cad['Cantidad'].sum())} piezas")
            st.dataframe(df_cad, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Nada caduca hoy")

    with col_b:
        st.write("#### 📦 Inventario Actual")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM base_anterior", conn)
        st.dataframe(df_inv, use_container_width=True, hide_index=True)

with tab3:
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    if not df_hist.empty:
        st.subheader("📊 Historial General")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos todavía.")
