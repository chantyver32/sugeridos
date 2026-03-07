import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN GENERAL ------------------
zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")
st.title("Sistema de Inventario: Control de Ventas y Caducidades 🥐")

# Contenedor para mensajes de éxito temporales
mensaje_global = st.empty()

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas (
    nombre TEXT,
    fecha_cad DATE,
    habia INTEGER,
    quedan INTEGER,
    vendidos INTEGER,
    fecha_corte DATETIME
)''')
conn.commit()

# ------------------ FUNCIONES ------------------

# ------------------ FUNCIONES PARA WHATSAPP ------------------
def enviar_whatsapp(texto):
    """Genera un enlace de WhatsApp con el mensaje dado y lo abre en el navegador"""
    import webbrowser
    mensaje = urllib.parse.quote(texto)
    url = f"https://api.whatsapp.com/send?phone={numero_whatsapp}&text={mensaje}"
    webbrowser.open(url)

def reporte_conteo_para_whatsapp():
    """Genera un mensaje amigable del conteo actual"""
    df = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if df.empty:
        return "⚠️ No hay productos registrados en el conteo actual."
    
    mensaje = "📝 *Reporte de Conteo Actual* 🥐\n\n"
    for _, fila in df.iterrows():
        mensaje += f"- {fila['nombre']} | Cad: {fila['fecha_cad']} | Cantidad: {fila['cantidad']}\n"
    mensaje += f"\nFecha: {fecha_hoy_mx.strftime('%d/%m/%Y')}"
    return mensaje

def reporte_corte_para_whatsapp():
    """Genera un mensaje amigable del último corte realizado"""
    if not st.session_state.get('ultimo_corte'):
        return "⚠️ No se ha realizado ningún corte."
    
    df = st.session_state['ultimo_corte']
    mensaje = "🏁 *Reporte de Corte de Ventas* 🥐\n\n"
    for _, fila in df.iterrows():
        mensaje += f"- {fila['Producto']} | Cad: {fila['Caducidad']} | Había: {fila['Había']} | Quedan: {fila['Quedan']} | Vendidos: {fila['VENDIDOS']}\n"
    mensaje += f"\nFecha Corte: {datetime.now(zona_mx).strftime('%d/%m/%Y %H:%M')}"
    return mensaje

def reporte_historial_para_whatsapp():
    """Genera un mensaje amigable del historial completo"""
    df = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, habia as Habia, quedan as Quedan, vendidos as Vendidos, fecha_corte as Fecha_Hora FROM historial_ventas", conn)
    if df.empty:
        return "⚠️ No hay historial de ventas todavía."
    
    mensaje = "📊 *Historial de Ventas* 🥐\n\n"
    resumen = df.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False)
    for producto, vendidos in resumen.items():
        mensaje += f"- {producto}: {int(vendidos)} vendidos\n"
    mensaje += f"\nTotal histórico: {int(df['Vendidos'].sum())} piezas"
    return mensaje

def enviar_whatsapp(titulo, df):
    """Genera un enlace de WhatsApp con el contenido del DataFrame"""
    if df.empty:
        return
    
    texto = f"📊 *{titulo}* 🥐\n\n"
    for _, fila in df.iterrows():
        detalles = " | ".join([f"{k}: {v}" for k, v in fila.to_dict().items()])
        texto += f"• {detalles}\n"
    
    texto_encoded = urllib.parse.quote(texto)
    url = f"https://wa.me/{numero_whatsapp}?text={texto_encoded}"
    
    st.markdown(f'''
        <a href="{url}" target="_blank">
            <button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; cursor:pointer; font-weight:bold;">
                Ver en WhatsApp ✅
            </button>
        </a>
    ''', unsafe_allow_html=True)
    
def sonido_click():
    st.markdown(
        """<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mpeg"></audio>""",
        unsafe_allow_html=True
    )

def sumar(valor):
    st.session_state.conteo_temp += valor
    sonido_click()

def resetear():
    st.session_state.conteo_temp = 0
    sonido_click()

def mostrar_exito(mensaje, duracion=2):
    mensaje_global.success(mensaje)
    time.sleep(duracion)
    mensaje_global.empty()

# ------------------ SIDEBAR ------------------
st.sidebar.header("⚙️ Configuración")
with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar borrar todo", key="check_reset")
    if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM captura_actual")
            c.execute("DELETE FROM base_anterior")
            c.execute("DELETE FROM historial_ventas")
            conn.commit()
            st.sidebar.success("Base de datos limpiada.")
            st.rerun()

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📝 Añadir productos", "📦 Inventario", "📊 Análisis de Ventas"])

with tab1:
    st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

    if "conteo_temp" not in st.session_state:
        st.session_state.conteo_temp = 0
    
    # Buscador
    buscar = st.text_input("🔎 Buscar o escribir producto", key="buscar_prod_input").upper()

    nombres_prev = [r[0] for r in c.execute(
        "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
    ).fetchall()]

    sugerencias = [p for p in nombres_prev if buscar in p] if buscar else nombres_prev

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        nombre_input = st.selectbox("Sugerencias:", sugerencias) if sugerencias else buscar

    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx)

    with col3:
        st.metric("Total contado", st.session_state.conteo_temp)

    # Botones de suma
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
    with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
    with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
    with c4: st.button("Borrar", use_container_width=True, on_click=resetear)

    if st.button("➕ Registrar en el Conteo", use_container_width=True, type="primary"):
        if nombre_input:
            nombre_final = nombre_input.strip().upper()
            cant = st.session_state.conteo_temp
            c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre_final, str(f_cad), int(cant)))
            conn.commit()
            st.session_state.conteo_temp = 0
            mostrar_exito("✅ Producto agregado")
            st.rerun()

    # Tabla editable
    df_hoy_captura = pd.read_sql("SELECT rowid, nombre, fecha_cad, cantidad FROM captura_actual", conn)
    if not df_hoy_captura.empty:
        st.write("---")
        df_editado = st.data_editor(df_hoy_captura, column_config={"rowid": None}, use_container_width=True, hide_index=True)
        
        if st.button("💾 Guardar cambios en tabla"):
            c.execute("DELETE FROM captura_actual")
            for _, fila in df_editado.iterrows():
                c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (fila['nombre'], str(fila['fecha_cad']), fila['cantidad']))
            conn.commit()
            st.rerun()

    if st.button("📤 Enviar reporte de conteo por WhatsApp"):
        texto = reporte_conteo_para_whatsapp()
        enviar_whatsapp(texto)

with tab2:
    st.header("🏁 Paso 2: Finalizar y Calcular Ventas")
    if st.button("REALIZAR CORTE", type="primary", use_container_width=True):
        df_actual = pd.read_sql("SELECT * FROM captura_actual", conn)
        if df_actual.empty:
            st.warning("No hay nada en el conteo.")
        else:
            df_anterior = pd.read_sql("SELECT * FROM base_anterior", conn)
            ventas_detectadas = []
            ts_mx = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            
            # Comparar anterior con actual para sacar ventas
            for _, fila_ant in df_anterior.iterrows():
                res_hoy = c.execute("SELECT cantidad FROM captura_actual WHERE nombre=? AND fecha_cad=?", 
                                  (fila_ant['nombre'], fila_ant['fecha_cad'])).fetchone()
                cant_hoy = res_hoy[0] if res_hoy else 0
                vendidos = fila_ant['cantidad'] - cant_hoy
                if vendidos > 0:
                    ventas_detectadas.append({"Producto": fila_ant['nombre'], "VENDIDOS": vendidos})
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)", 
                             (fila_ant['nombre'], fila_ant['fecha_cad'], fila_ant['cantidad'], cant_hoy, vendidos, ts_mx))
            
            c.execute("DELETE FROM base_anterior")
            c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
            c.execute("DELETE FROM captura_actual")
            conn.commit()
            
            if ventas_detectadas:
                st.session_state['ultimo_corte'] = pd.DataFrame(ventas_detectadas)
                st.session_state['mostrar_resumen'] = True
            st.rerun()

    if st.session_state.get('mostrar_resumen'):
        st.balloons()
        st.subheader("Resumen de Ventas Recientes")
        st.table(st.session_state['ultimo_corte'])
        enviar_whatsapp("Resumen de Corte", st.session_state['ultimo_corte'])
        if st.button("Cerrar Resumen"):
            st.session_state['mostrar_resumen'] = False
            st.rerun()

    st.divider()
    col_l, col_r = st.columns(2)
    with col_l:
        st.header("⚠️ Caducidades")
        df_cad = pd.read_sql("SELECT nombre, cantidad FROM base_anterior WHERE fecha_cad = ?", conn, params=(str(fecha_hoy_mx),))
        if not df_cad.empty:
            st.error(f"Retirar {int(df_cad['cantidad'].sum())} piezas hoy.")
            st.dataframe(df_cad, use_container_width=True)
            enviar_whatsapp("⚠️ Caducan Hoy", df_cad)
        else:
            st.success("✅ Todo fresco por hoy.")
    
    with col_r:
        st.header("🏪 Stock")
        df_inv = pd.read_sql("SELECT nombre, cantidad FROM base_anterior", conn)
        st.dataframe(df_inv, use_container_width=True)

    if st.session_state.get('mostrar_resumen'):
        if st.button("📤 Enviar corte por WhatsApp"):
            texto = reporte_corte_para_whatsapp()
            enviar_whatsapp(texto)

with tab3:
    st.header("📊 Análisis de Ventas")
    df_hist = pd.read_sql("SELECT nombre as Producto, fecha_cad as Caducidad, vendidos as Vendidos, fecha_corte as Fecha FROM historial_ventas", conn)
    
    if df_hist.empty:
        st.info("No hay datos históricos.")
    else:
        bus_h = st.text_input("Filtrar producto en historial:").upper()
        df_f = df_hist[df_hist["Producto"].str.contains(bus_h)] if bus_h else df_hist
        st.dataframe(df_f, use_container_width=True)
        enviar_whatsapp("Historial de Ventas", df_f)
        
        st.subheader("📈 Top Ventas")
        top = df_hist.groupby("Producto")["Vendidos"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top)

   if st.button("📤 Enviar historial por WhatsApp"):
        texto = reporte_historial_para_whatsapp()
        enviar_whatsapp(texto)
