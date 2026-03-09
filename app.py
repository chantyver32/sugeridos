import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

# ------------------ CONFIGURACIÓN Y ESTILO LIMPIO ------------------
st.set_page_config(page_title="Champlitte LITE", page_icon="🥐", layout="centered")

# CSS para eliminar el aspecto de "tabla" y dejar una lista pura
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    /* Contenedor de la lista */
    .lista-limpia {
        border-radius: 10px;
        padding: 10px;
    }
    /* Cada fila de producto */
    .item-pan {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 5px;
        border-bottom: 1px solid #eee;
    }
    .nombre-pan {
        font-size: 18px;
        font-weight: 600;
        color: #333;
        text-transform: uppercase;
    }
    .meta-pan {
        font-size: 13px;
        color: #888;
    }
    .cantidad-pan {
        font-size: 20px;
        font-weight: bold;
        color: #FF4B4B;
        background: #fff5f5;
        padding: 5px 12px;
        border-radius: 8px;
    }
    /* Botones de eliminar pequeños */
    .stButton>button {
        border-radius: 8px;
        padding: 2px 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# ------------------ DB ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
conn.commit()

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()

if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0

# ------------------ INTERFAZ DE ENTRADA ------------------
st.title("🥐 Registro de Pan")

with st.container():
    nombre = st.text_input("PRODUCTO", placeholder="Nombre del pan...", label_visibility="collapsed").upper()
    col_f, col_n = st.columns([2, 1])
    with col_f:
        f_cad = st.date_input("Caducidad", value=fecha_hoy_mx)
    with col_n:
        st.markdown(f"<div style='text-align:center;'><b>Contando:</b><br><span style='font-size:28px; color:#FF4B4B;'>{st.session_state.n if 'n' in st.session_state else 0}</span></div>", unsafe_allow_html=True)

    # Teclado rápido
    if "n" not in st.session_state: st.session_state.n = 0
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("+1"): st.session_state.n += 1
    if c2.button("+5"): st.session_state.n += 5
    if c3.button("+10"): st.session_state.n += 10
    if c4.button("0"): st.session_state.n = 0

    if st.button("➕ REGISTRAR EN LISTA", type="primary", use_container_width=True):
        if nombre and st.session_state.n > 0:
            c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (nombre, str(f_cad), st.session_state.n))
            conn.commit()
            st.session_state.n = 0
            st.rerun()

st.write("---")

# ------------------ LA LISTA ILIMITADA (SIN TÍTULOS DE TABLA) ------------------
st.subheader("📋 Lista de hoy")

# Obtenemos los datos de la base de datos
productos_hoy = c.execute("SELECT rowid, nombre, cantidad, fecha_cad FROM captura_actual ORDER BY rowid DESC").fetchall()

if not productos_hoy:
    st.write("_La lista está vacía..._")
else:
    for rowid, nom, cant, fec in productos_hoy:
        # Aquí generamos el diseño de lista limpia (Sin títulos de columna)
        col_info, col_del = st.columns([0.85, 0.15])
        
        with col_info:
            st.markdown(f"""
                <div class="item-pan">
                    <div>
                        <div class="nombre-pan">{nom}</div>
                        <div class="meta-pan">📅 {fec}</div>
                    </div>
                    <div class="cantidad-pan">{cant}</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col_del:
            # Botón discreto para eliminar solo ese producto
            st.write("") # Espaciador
            if st.button("❌", key=f"del_{rowid}"):
                c.execute("DELETE FROM captura_actual WHERE rowid=?", (rowid,))
                conn.commit()
                st.rerun()

    st.write("---")
    if st.button("🗑️ VACIAR TODA LA LISTA"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# ------------------ BOTÓN DE CORTE ------------------
st.markdown("---")
if st.button("🚀 REALIZAR CORTE (CALCULAR VENTAS)", type="secondary", use_container_width=True):
    # Lógica de traspaso a base_anterior
    c.execute("DELETE FROM base_anterior")
    c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
    c.execute("DELETE FROM captura_actual")
    conn.commit()
    st.success("¡Corte exitoso!")
    st.balloons()
