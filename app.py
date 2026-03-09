import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
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

# ------------------ FUNCIONES CALLBACK (UN SOLO CLIC) ------------------
def sumar_cantidad(valor):
    st.session_state.conteo_temp += valor
    # sonido_click() # Opcional: añade la función si la requieres

def resetear_cantidad():
    st.session_state.conteo_temp = 0
    st.toast("Contador reiniciado 🔄")

def limpiar_buscador():
    st.session_state.busqueda_input = ""
    st.toast("Buscador limpio 🧹")

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 AÑADIR PRODUCTOS", "📦 INVENTARIO Y CORTE", "📊 ANÁLISIS DE VENTAS"])

with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    col_busq, col_limpiar = st.columns([4, 1])
    with col_busq:
        buscar = st.text_input("Buscador", placeholder="🔎 BUSCAR O ESCRIBIR PRODUCTO...", key="busqueda_input").upper()
    with col_limpiar:
        st.button("🧹 Limpiar", on_click=limpiar_buscador, use_container_width=True)

    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        nombre_input = st.selectbox("Producto:", sugerencias, key="sel_prod") if sugerencias else buscar
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)
    with col3:
        st.metric("Total a añadir", st.session_state.conteo_temp)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar_cantidad, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar_cantidad, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar_cantidad, args=(10,))
    with c4: st.button("Borrar Cantidad", use_container_width=True, on_click=resetear_cantidad)

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
            st.success(f"✅ {nombre_final} registrado correctamente.") 
            st.session_state.conteo_temp = 0
            time.sleep(0.5)
            st.rerun()

    st.divider()
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM captura_actual", conn)
    
    if not df_hoy_captura.empty:
        df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        col_s, col_v = st.columns(2)
        with col_s:
            if st.button("💾 Guardar cambios en lista", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                for _, fila in df_editado.iterrows():
                    if fila['Producto']:
                        c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (fila['Producto'].strip().upper(), str(fila['Fecha Cad']), int(fila['Cantidad'])))
                conn.commit()
                st.success("💾 Cambios guardados correctamente.")
                time.sleep(0.5)
                st.rerun()
        with col_v:
            if st.button("🗑️ Vaciar lista (sin borrar DB)", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.success("🗑️ Lista temporal vaciada.")
                time.sleep(0.5)
                st.rerun()

with tab2:
    with st.expander("🚨 ZONA DE PELIGRO: MANTENIMIENTO"):
        confirmar_reset = st.checkbox("Confirmar borrar TODO (Historial e Inventario)")
        if st.button("⚠️ EJECUTAR RESET TOTAL", type="secondary", use_container_width=True):
            if confirmar_reset:
                c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
                conn.commit()
                st.success("💥 Base de datos eliminada por completo.")
                time.sleep(1)
                st.rerun()

    st.divider()

    if st.button("🚀 FINALIZAR CAPTURA Y REALIZAR CORTE", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actualizado.empty:
            st.warning("⚠️ La lista está vacía.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_detectadas = []

            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                diferencia = fila_ant['cantidad'] - cant_hoy
                if diferencia > 0:
                    ventas_detectadas.append({"Producto": fila_ant['nombre'], "VENDIDOS": diferencia})
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']), int(cant_hoy), int(max(0, diferencia)), ts_mx))

            st.session_state['resumen_corte'] = pd.DataFrame(ventas_detectadas)
            c.execute("DELETE FROM base_anterior"); c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual"); c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.success("🏁 Corte finalizado con éxito.")
            st.balloons()
            st.rerun()

    if 'resumen_corte' in st.session_state:
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
            st.success("✅ Nada caduca hoy.")

    with col_b:
        st.write("#### 📦 Stock en Estantes")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM base_anterior", conn)
        st.dataframe(df_inv, use_container_width=True, hide_index=True)

with tab3:
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    if not df_hist.empty:
        st.success("📊 Historial de ventas cargado.")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("Sin registros.")
