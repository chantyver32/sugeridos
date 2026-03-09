import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

# ------------------ CONFIGURACIÓN Y ESTILO ------------------
st.set_page_config(page_title="Champlitte LITE", page_icon="🥐", layout="centered")

# CSS para que la lista sea verdaderamente limpia y minimalista
st.markdown("""
    <style>
    /* Fondo y tipografía */
    .main { background-color: #ffffff; }
    
    /* Estilo de cada fila de la lista */
    .fila-producto {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 5px;
        border-bottom: 1px solid #f0f0f0;
    }
    .nombre-prod {
        font-size: 1.1rem;
        font-weight: 500;
        color: #333;
    }
    .info-secundaria {
        font-size: 0.85rem;
        color: #888;
    }
    .cant-badge {
        background-color: #f3f4f6;
        padding: 2px 10px;
        border-radius: 12px;
        font-weight: bold;
        color: #FF4B4B;
    }
    
    /* Ajuste de botones */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #ddd;
    }
    </style>
    """, unsafe_allow_html=True)

# ------------------ DB Y LÓGICA ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS captura_actual (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
conn.commit()

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy_mx = datetime.now(zona_mx).date()

if "conteo_temp" not in st.session_state: st.session_state.conteo_temp = 0

# ------------------ INTERFAZ DE ENTRADA ------------------
st.title("🥐 Champlitte")
st.subheader("Registro de Inventario")

# Área de entrada compacta
with st.container():
    buscar = st.text_input("Nombre del pan", placeholder="Ej. Croissant de mantequilla...").upper()
    col_f, col_n = st.columns([2, 1])
    with col_f:
        f_cad = st.date_input("Vencimiento", value=fecha_hoy_mx)
    with col_n:
        st.write(f"**Cantidad**")
        st.write(f"## {st.session_state.conteo_temp}")

    # Teclado numérico horizontal
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("+1"): st.session_state.conteo_temp += 1
    if c2.button("+5"): st.session_state.conteo_temp += 5
    if c3.button("+10"): st.session_state.conteo_temp += 10
    if c4.button("Reset"): st.session_state.conteo_temp = 0

    if st.button("➕ REGISTRAR PRODUCTO", type="primary"):
        if buscar and st.session_state.conteo_temp > 0:
            c.execute("INSERT INTO captura_actual VALUES (?, ?, ?)", (buscar, str(f_cad), st.session_state.conteo_temp))
            conn.commit()
            st.session_state.conteo_temp = 0
            st.rerun()
        else:
            st.error("Falta nombre o cantidad")

st.markdown("---")

# ------------------ LISTA LIMPIA (EL "PAPEL") ------------------
st.write("### 📋 Listado Actual")
productos = c.execute("SELECT rowid, nombre, cantidad, fecha_cad FROM captura_actual ORDER BY rowid DESC").fetchall()

if not productos:
    st.write("_No hay productos en la lista_")
else:
    for rowid, nombre, cant, fecha in productos:
        # Generamos la fila con HTML para control total del diseño
        st.markdown(f"""
            <div class="fila-producto">
                <div>
                    <div class="nombre-prod">{nombre}</div>
                    <div class="info-secundaria">📅 Caduca: {fecha}</div>
                </div>
                <div class="cant-badge">{cant} pzas</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Botón de borrar pequeño justo debajo (Streamlit no permite botones dentro de HTML inyectado)
        if st.button(f"Eliminar {nombre}", key=f"del_{rowid}"):
            c.execute("DELETE FROM captura_actual WHERE rowid=?", (rowid,))
            conn.commit()
            st.rerun()

    st.write("")
    if st.button("🗑️ VACIAR TODO"):
        c.execute("DELETE FROM captura_actual")
        conn.commit()
        st.rerun()

# ------------------ CORTE ------------------
st.markdown("---")
if st.button("🚀 REALIZAR CORTE FINAL", use_container_width=True):
    c.execute("DELETE FROM base_anterior")
    c.execute("INSERT INTO base_anterior SELECT * FROM captura_actual")
    c.execute("DELETE FROM captura_actual")
    conn.commit()
    st.success("Corte realizado correctamente.")
    st.balloons()
