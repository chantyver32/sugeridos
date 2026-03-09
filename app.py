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
# Nueva tabla para registrar movimientos (Logs)
c.execute('CREATE TABLE IF NOT EXISTS registro_actividad (evento TEXT, detalle TEXT, fecha_hora DATETIME)')
conn.commit()

# ------------------ FUNCIONES CALLBACK (UN SOLO CLIC) ------------------
def registrar_log(evento, detalle):
    ahora = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO registro_actividad VALUES (?, ?, ?)", (evento, detalle, ahora))
    conn.commit()

def sumar_cantidad(valor):
    st.session_state.conteo_temp += valor

def resetear_cantidad():
    st.session_state.conteo_temp = 0
    st.toast("Contador reiniciado 🔄")

def limpiar_buscador():
    st.session_state.busqueda_input = ""
    st.toast("Buscador limpio 🧹")

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 AÑADIR PRODUCTOS", "📦 INVENTARIO Y CORTE", "📊 ANÁLISIS Y LOGS"])

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
            c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(cant)))
            registrar_log("AÑADIDO", f"Se añadieron {cant} pzas de {nombre_final}")
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
                registrar_log("ACTUALIZACIÓN", "Se modificó manualmente la lista temporal")
                conn.commit()
                st.success("💾 Cambios guardados correctamente.")
                st.rerun()
        with col_v:
            if st.button("🗑️ Vaciar lista", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                registrar_log("BORRADO", "Se vació la lista temporal de captura")
                conn.commit()
                st.success("🗑️ Lista temporal vaciada.")
                st.rerun()

with tab2:
    with st.expander("🚨 ZONA DE PELIGRO"):
        confirmar_reset = st.checkbox("Confirmar borrar TODO")
        if st.button("⚠️ EJECUTAR RESET TOTAL", type="secondary", use_container_width=True):
            if confirmar_reset:
                c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
                registrar_log("RESET TOTAL", "Se eliminó toda la base de datos")
                conn.commit()
                st.success("💥 Base de datos eliminada.")
                st.rerun()

    if st.button("🚀 REALIZAR CORTE FINAL", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if not df_actualizado.empty:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_detectadas = []
            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT SUM(cantidad) FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy[0] else 0
                diferencia = fila_ant['cantidad'] - cant_hoy
                if diferencia > 0:
                    ventas_detectadas.append({"Producto": fila_ant['nombre'], "Había": fila_ant['cantidad'], "Quedan": cant_hoy, "VENDIDOS": diferencia})
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']), int(cant_hoy), int(max(0, diferencia)), ts_mx))
            
            st.session_state['resumen_ventas'] = pd.DataFrame(ventas_detectadas)
            c.execute("DELETE FROM base_anterior"); c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual"); c.execute("DELETE FROM captura_actual")
            registrar_log("CORTE", f"Corte de caja realizado por el usuario")
            conn.commit()
            st.balloons()
            st.rerun()

    if 'resumen_ventas' in st.session_state:
        st.success("📊 Resumen de Ventas Generado")
        df_res = st.session_state['resumen_ventas']
        st.table(df_res)
        
        # --- ENVÍO WHATSAPP ---
        msg = f"🥐 *REPORTE DE VENTAS CHAMPLITTE*\n📅 {fecha_hoy_mx}\n\n"
        for _, r in df_res.iterrows():
            msg += f"🍞 *{r['Producto']}*\nHabía: {r['Había']} | Quedan: {r['Quedan']}\n💰 *VENDIDOS: {r['VENDIDOS']}*\n---\n"
        
        link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(msg)}"
        col_wa, col_ce = st.columns(2)
        with col_wa: st.link_button("📲 Enviar por WhatsApp", link, use_container_width=True)
        with col_ce:
            if st.button("Cerrar Resumen", use_container_width=True):
                del st.session_state['resumen_ventas']
                st.rerun()

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("#### ⚠️ Caducan Hoy")
        df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        st.dataframe(df_cad, use_container_width=True, hide_index=True) if not df_cad.empty else st.success("Todo al día ✅")
    with col_b:
        st.write("#### 📦 Inventario")
        df_inv = pd.read_sql("SELECT nombre, cantidad FROM base_anterior", conn)
        st.dataframe(df_inv, use_container_width=True, hide_index=True)

with tab3:
    col_h, col_l = st.columns(2)
    with col_h:
        st.write("### 📈 Historial de Ventas")
        st.dataframe(pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn), hide_index=True)
    with col_l:
        st.write("### 📑 Registro de Actividad (Logs)")
        st.dataframe(pd.read_sql("SELECT * FROM registro_actividad ORDER BY fecha_hora DESC", conn), hide_index=True)
