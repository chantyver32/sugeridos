import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

# ------------------ CONFIGURACIÓN Y ESTILO ------------------
st.set_page_config(page_title="Inventario Champlitte MX", page_icon="🥐", layout="wide")

st.markdown("""
    <style>
    [data-testid="stHeader"] {display:none;}
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()
numero_whatsapp = "522283530069"

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

# Tabla de Inventario Real (Lo que hay en estante)
c.execute('''CREATE TABLE IF NOT EXISTS inventario 
             (nombre TEXT, fecha_cad DATE, cantidad INTEGER, PRIMARY KEY(nombre, fecha_cad))''')

# Historial para reportes
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas 
             (nombre TEXT, fecha_cad DATE, inicial INTEGER, final INTEGER, vendidos INTEGER, fecha_corte DATETIME)''')

conn.commit()

# ------------------ LÓGICA DE NEGOCIO ------------------
def registrar_en_inventario(nombre, fecha, cant):
    nombre = nombre.strip().upper()
    # Si ya existe el producto con esa fecha, sumamos. Si no, lo creamos.
    c.execute('''INSERT INTO inventario (nombre, fecha_cad, cantidad) 
                 VALUES (?, ?, ?) 
                 ON CONFLICT(nombre, fecha_cad) 
                 DO UPDATE SET cantidad = cantidad + excluded.cantidad''', (nombre, str(fecha), cant))
    conn.commit()

# ------------------ INTERFAZ (TABS) ------------------
tab1, tab2, tab3 = st.tabs(["📥 ENTRADA DE PAN", "⚖️ CORTE DE CAJA", "📊 HISTORIAL"])

# --- TAB 1: ENTRADA DE MERCANCÍA ---
with tab1:
    st.subheader("Registrar Entrada de Pan")
    
    if "conteo" not in st.session_state: st.session_state.conteo = 0

    col_busq, col_date, col_n = st.columns([2, 1, 1])
    
    # Obtener lista de productos previos para sugerencias
    productos_previos = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM inventario").fetchall()]
    
    with col_busq:
        nombre_prod = st.selectbox("Selecciona o escribe Producto", [""] + productos_previos, index=0)
        nuevo_prod = st.text_input("O escribe uno nuevo:").upper()
        nombre_final = nuevo_prod if nuevo_prod else nombre_prod

    with col_date:
        f_cad = st.date_input("Fecha de Caducidad", value=fecha_hoy_mx)

    with col_n:
        st.metric("Añadiendo", st.session_state.conteo)

    # Botones de conteo rápido
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("+1"): st.session_state.conteo += 1; st.rerun()
    if c2.button("+5"): st.session_state.conteo += 5; st.rerun()
    if c3.button("+10"): st.session_state.conteo += 10; st.rerun()
    if c4.button("Reset"): st.session_state.conteo = 0; st.rerun()

    if st.button("✅ GUARDAR EN INVENTARIO", use_container_width=True, type="primary"):
        if nombre_final and st.session_state.conteo > 0:
            registrar_en_inventario(nombre_final, f_cad, st.session_state.conteo)
            st.success(f"Agregado: {st.session_state.conteo} pzas de {nombre_final}")
            st.session_state.conteo = 0
            st.rerun()
        else:
            st.error("Falta nombre o cantidad")

# --- TAB 2: CORTE DE CAJA (COMPARACIÓN) ---
with tab2:
    st.subheader("Corte de Caja / Auditoría Física")
    st.info("Instrucciones: Escribe en la columna 'Cantidad Real' cuánto pan queda realmente en la charola.")

    df_inv = pd.read_sql("SELECT * FROM inventario WHERE cantidad > 0", conn)
    
    if not df_inv.empty:
        # Añadimos columna para que el usuario capture lo que ve
        df_inv['Cantidad Real'] = df_inv['cantidad'] 
        
        df_editado = st.data_editor(
            df_inv, 
            column_config={
                "nombre": "Producto",
                "fecha_cad": "Caducidad",
                "cantidad": "Sistema (Había)",
                "Cantidad Real": st.column_config.NumberColumn("Cantidad Real (Contada)", min_value=0)
            },
            disabled=["nombre", "fecha_cad", "cantidad"],
            use_container_width=True,
            hide_index=True
        )

        if st.button("🚀 REALIZAR CORTE Y GENERAR REPORTE", type="primary", use_container_width=True):
            reporte_msg = f"🥐 *CORTE CHAMPLITTE*\n📅 {fecha_hoy_mx}\n\n"
            ahora = datetime.now(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
            ventas_totales = []

            for _, fila in df_editado.iterrows():
                vendidos = fila['cantidad'] - fila['Cantidad Real']
                
                if vendidos >= 0:
                    # Registrar en historial
                    c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?, ?, ?)",
                              (fila['nombre'], fila['fecha_cad'], fila['cantidad'], fila['Cantidad Real'], vendidos, ahora))
                    
                    # Actualizar inventario con lo que quedó
                    if fila['Cantidad Real'] > 0:
                        c.execute("UPDATE inventario SET cantidad = ? WHERE nombre = ? AND fecha_cad = ?",
                                  (fila['Cantidad Real'], fila['nombre'], fila['fecha_cad']))
                    else:
                        c.execute("DELETE FROM inventario WHERE nombre = ? AND fecha_cad = ?", 
                                  (fila['nombre'], fila['fecha_cad']))
                    
                    if vendidos > 0:
                        reporte_msg += f"• *{fila['nombre']}*: {vendidos} vendid@s\n"
                        ventas_totales.append(fila)

            conn.commit()
            
            # Generar Link de WhatsApp
            link_wa = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(reporte_msg)}"
            st.success("Corte realizado con éxito.")
            st.link_button("📲 Enviar Reporte a WhatsApp", link_wa, use_container_width=True)
            st.balloons()
            
    else:
        st.warning("No hay productos en el inventario. Registra entradas primero.")

# --- TAB 3: ANÁLISIS ---
with tab3:
    st.subheader("Historial de Movimientos")
    df_hist = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    st.dataframe(df_hist, use_container_width=True)
    
    if st.button("⚠️ Vaciar Todo el Sistema"):
        c.execute("DELETE FROM inventario")
        c.execute("DELETE FROM historial_ventas")
        conn.commit()
        st.rerun()
