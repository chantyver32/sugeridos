import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

# Estilo para ocultar headers y ajustar márgenes superiores
st.markdown("""
    <style>
    [data-testid="stHeader"] {display:none;}
    .block-container {padding-top: 1rem;}
    </style>
    """, unsafe_allow_html=True)

# Animación de carga inicial (del código antiguo)
with st.spinner('Iniciando sistema Champlitte... 🥐'):
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

# ------------------ FUNCIONES ------------------
def sonido_click():
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def sumar_cantidad(valor):
    st.session_state.conteo_temp += valor
    sonido_click()

def limpiar_buscador():
    st.session_state.busqueda_input = ""

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 AÑADIR PRODUCTOS", "📦 INVENTARIO Y CORTE", "📊 ANÁLISIS DE VENTAS"])

with tab1:
    if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0
    
    # Buscador optimizado con botón limpiar (Callback)
    col_busq, col_limpiar = st.columns([4, 1])
    with col_busq:
        buscar = st.text_input("Buscador", placeholder="🔎 BUSCAR O ESCRIBIR PRODUCTO...", key="busqueda_input").upper()
    with col_limpiar:
        st.button("🧹 Limpiar", on_click=limpiar_buscador, use_container_width=True)

    # Sugerencias dinámicas
    nombres_prev = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual").fetchall()]
    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if sugerencias:
            nombre_input = st.selectbox("Sugerencias:", sugerencias, key="sel_prod")
        else:
            st.info("✨ Producto nuevo")
            nombre_input = buscar

    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)

    with col3:
        st.metric("Total a añadir", st.session_state.conteo_temp)

    # Botones de conteo rápido
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar_cantidad, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar_cantidad, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar_cantidad, args=(10,))
    with c4: 
        if st.button("Borrar Cantidad", use_container_width=True):
            st.session_state.conteo_temp = 0
            sonido_click()

    if st.button("➕ REGISTRAR EN LISTA TEMPORAL", use_container_width=True, type="primary"):
        if nombre_input and str(nombre_input).strip() != "":
            nombre_final = str(nombre_input).strip().upper()
            cant = st.session_state.conteo_temp
            # Lógica acumulativa e ilimitada
            existe = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (nombre_final, str(f_cad))).fetchone()
            if existe:
                c.execute("UPDATE captura_actual SET cantidad = cantidad + ? WHERE nombre=? AND fecha_cad=?", (int(cant), nombre_final, str(f_cad)))
            else:
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(cant)))
            conn.commit()
            sonido_click()
            st.toast(f"✅ {nombre_final} en lista", icon="🍞")
            st.session_state.conteo_temp = 0
            st.rerun()

    st.divider()
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre as Producto, fecha_cad as [Fecha Cad], cantidad as Cantidad FROM captura_actual", conn)
    
    if not df_hoy_captura.empty:
        st.write("### 📋 Conteo en proceso")
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
            if st.button("🗑️ Vaciar lista (sin borrar DB)", use_container_width=True):
                c.execute("DELETE FROM captura_actual")
                conn.commit()
                st.rerun()

with tab2:
    # --- ZONA DE PELIGRO (Mantenimiento) ---
    with st.expander("🚨 ZONA DE PELIGRO: MANTENIMIENTO"):
        st.write("Esta acción borrará todo el historial y el inventario actual.")
        confirmar_reset = st.checkbox("Confirmar que deseo borrar TODO")
        if st.button("⚠️ EJECUTAR RESET TOTAL", type="secondary", use_container_width=True):
            if confirmar_reset:
                c.execute("DELETE FROM captura_actual"); c.execute("DELETE FROM base_anterior"); c.execute("DELETE FROM historial_ventas")
                conn.commit()
                st.success("Base de datos limpiada.")
                time.sleep(1); st.rerun()
    
    st.divider()

    if st.button("🚀 FINALIZAR CAPTURA Y REALIZAR CORTE", type="primary", use_container_width=True):
        df_actualizado = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actualizado.empty:
            st.warning("⚠️ No hay productos en la lista para realizar el corte.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_detectadas = []

            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                diferencia = fila_ant['cantidad'] - cant_hoy
                
                if diferencia > 0:
                    ventas_detectadas.append({
                        "Producto": fila_ant['nombre'], "Caducidad": fila_ant['fecha_cad'],
                        "Había": fila_ant['cantidad'], "Quedan": cant_hoy, "VENDIDOS": diferencia
                    })
                
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", 
                         (fila_ant['nombre'], fila_ant['fecha_cad'], int(fila_ant['cantidad']), int(cant_hoy), int(max(0, diferencia)), ts_mx))

            st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            st.balloons()
            st.rerun()

    # Resumen con Botón de WhatsApp
    if 'ultimo_corte' in st.session_state:
        with st.container(border=True):
            st.write("### 📊 Resumen de ventas detectadas")
            df_ventas = st.session_state['ultimo_corte']
            st.table(df_ventas)

            mensaje = "📊 *CORTE DE VENTAS CHAMPLITTE*\n"
            mensaje += f"📅 Fecha: {fecha_hoy_mx.strftime('%d/%m/%Y')}\n---------------------------------\n\n"
            for _, row in df_ventas.iterrows():
                mensaje += (f"🍞 *{row['Producto']}*\n📅 Cad: {row['Caducidad']}\n📥 Había: {row['Había']} | 📤 Quedan: {row['Quedan']}\n💰 *VENDIDOS: {row['VENDIDOS']}*\n---------------------------------\n")

            link = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"
            col_wa, col_close = st.columns(2)
            with col_wa:
                st.link_button("📲 Enviar reporte por WhatsApp", link, use_container_width=True)
            with col_close:
                if st.button("❌ CERRAR RESUMEN", type="primary", use_container_width=True):
                    del st.session_state['ultimo_corte']
                    st.rerun()

    st.divider()
    col_left, col_right = st.columns(2)
    with col_left:
        st.write("#### ⚠️ Alertas de Caducidad")
        df_cad = pd.read_sql("SELECT nombre as Producto, cantidad as Cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        if not df_cad.empty:
            st.error(f"¡Atención! Retirar {int(df_cad['Cantidad'].sum())} piezas.")
            st.dataframe(df_cad, use_container_width=True, hide_index=True)
            
            # Botón WhatsApp para caducidades
            mensaje_alerta = "⚠️ PRODUCTOS QUE CADUCAN HOY\n\n"
            for _, row in df_cad.iterrows():
                mensaje_alerta += f"Producto: {row['Producto']}\nCantidad: {row['Cantidad']}\n-----------------\n"
            st.link_button("⚠️ Enviar caducidad por WhatsApp", "https://wa.me/" + numero_whatsapp + "?text=" + urllib.parse.quote(mensaje_alerta))
        else:
            st.success("✅ Todo bien hoy.")

    with col_right:
        st.write("#### 🏪 Inventario Actual")
        df_inv = pd.read_sql("SELECT nombre as Producto, fecha_cad as [Fecha Caducidad], cantidad as Cantidad FROM base_anterior", conn)
        if not df_inv.empty:
            st.metric("Piezas totales", f"{int(df_inv['Cantidad'].sum())}")
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
        else:
            st.info("Sin inventario.")

with tab3:
    with st.spinner('Cargando análisis...'):
        df_hist = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, habia as Habia, quedan as Quedan, vendidos as Vendidos, fecha_corte as Fecha_Hora FROM historial_ventas", conn)

    if df_hist.empty:
        st.info("No hay historial de ventas todavía.")
    else:
        df_hist['Fecha_Hora'] = pd.to_datetime(df_hist['Fecha_Hora'])
        df_hist['Fecha'] = df_hist['Fecha_Hora'].dt.date

        # Buscador en historial
        buscar_h = st.text_input("🔍 Buscar en historial", key="buscar_hist").upper()
        df_filtrado = df_hist[df_hist["Producto"].str.contains(buscar_h, case=False)] if buscar_h else df_hist
        st.dataframe(df_filtrado.sort_values(by="Fecha_Hora", ascending=False), use_container_width=True, hide_index=True)

        st.divider()
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.write("📈 **Ventas por fecha**")
            st.line_chart(df_hist.groupby("Fecha")["Vendidos"].sum())
        with col_graf2:
            st.write("🥐 **Top Productos**")
            top_productos = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_productos)
