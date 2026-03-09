import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse
import time

# ------------------ CONFIGURACIÓN ------------------
st.set_page_config(page_title="Champlitte LITE", page_icon="🥐", layout="wide")

# CSS para que la lista se vea limpia y sin bordes de tabla
st.markdown("""
    <style>
    .producto-fila {
        display: flex;
        justify-content: space-between;
        padding: 8px 0px;
        border-bottom: 1px solid #eee;
        font-size: 18px;
    }
    .stButton>button { border-radius: 20px; }
    </style>
    """, unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()

conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
conn.commit()

# ------------------ LÓGICA DE REGISTRO ------------------
if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0

st.title("📝 Registro Rápido")

# Buscador y Teclado en una sola línea
col_input, col_num = st.columns([2, 1])

with col_input:
    buscar = st.text_input("PRODUCTO", placeholder="Escribe aquí...", label_visibility="collapsed").upper()
    f_cad = st.date_input("CADUCIDAD", value=fecha_hoy_mx, label_visibility="collapsed")

with col_num:
    st.write(f"### Cantidad: {st.session_state.conteo_temp}")
    c1, c2, c3 = st.columns(3)
    if c1.button("+1"): st.session_state.conteo_temp += 1
    if c2.button("+5"): st.session_state.conteo_temp += 5
    if c3.button("0"): st.session_state.conteo_temp = 0

if st.button("➕ AGREGAR A LA LISTA", use_container_width=True, type="primary"):
    if buscar:
        c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (buscar, str(f_cad), st.session_state.conteo_temp))
        conn.commit()
        st.session_state.conteo_temp = 0
        st.rerun()

st.write("---")

# ------------------ LA LISTA ILIMITADA (SIN TÍTULOS) ------------------
# Aquí es donde ocurre la magia: leemos los datos y los mostramos como texto, no como tabla.
st.subheader("Lista de hoy")
productos_hoy = c.execute("SELECT rowid, nombre, cantidad, fecha_cad FROM captura_actual ORDER BY rowid DESC").fetchall()

if not productos_hoy:
    st.info("La lista está vacía")
else:
    for rowid, nombre, cant, fecha in productos_hoy:
        col_txt, col_btn = st.columns([0.85, 0.15])
        with col_txt:
            # Mostramos el producto de forma sencilla: NOMBRE - CANTIDAD
            st.markdown(f"**{nombre}** ({cant} pzas) - <small>{fecha}</small>", unsafe_allow_html=True)
        with col_btn:
            if st.button("❌", key=f"del_{rowid}"):
                c.execute("DELETE FROM captura_actual WHERE rowid=?", (rowid,))
                conn.commit()
                st.rerun()

    st.write("---")
    if st.button("🗑️ BORRAR TODA LA LISTA", use_container_width=True):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# ------------------ BOTÓN DE CORTE (PASO 2) ------------------
st.write("## 🏁 Finalizar día")
if st.button("🚀 REALIZAR CORTE (CALCULAR VENTAS)", type="secondary", use_container_width=True):
    # Lógica de comparación simplificada
    df_actual = pd.read_sql("SELECT * FROM captura_actual", conn)
    if not df_actual.empty:
        # Aquí guardas en base_anterior y limpias captura_actual
        c.execute("DELETE FROM base_anterior")
        c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.success("Corte guardado. ¡Buen trabajo!")
        time.sleep(1)
        st.rerun()
