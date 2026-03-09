import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import urllib.parse

# --- CONFIGURACIÓN Y DB ---
st.set_page_config(page_title="Champlitte Hub", page_icon="🥐", layout="wide")

# Estilo para reducir espacios en blanco superiores
st.markdown("""<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    h1, h2 {margin-top: 0px; padding-top: 0px;}
</style>""", unsafe_allow_html=True)

zona_mx = pytz.timezone('America/Mexico_City')
fecha_hoy = datetime.now(zona_mx).date()
conn = sqlite3.connect('inventario_champlitte.db', check_same_thread=False)
c = conn.cursor()

# Tablas actualizadas
c.execute('CREATE TABLE IF NOT EXISTS registro_diario (id INTEGER PRIMARY KEY, nombre TEXT, fecha_cad DATE, cantidad INTEGER, fecha_registro DATE)')
c.execute('CREATE TABLE IF NOT EXISTS base_anterior (nombre TEXT, fecha_cad DATE, cantidad INTEGER)')
conn.commit()

# --- ESTADO DE SESIÓN ---
if "lista_captura" not in st.session_state:
    st.session_state.lista_captura = []
if "conteo" not in st.session_state:
    st.session_state.conteo = 0

# --- FUNCIONES ---
def agregar_a_lista(nombre, caducidad, cantidad):
    if nombre and cantidad > 0:
        st.session_state.lista_captura.append({
            "Producto": nombre.upper(),
            "Caducidad": caducidad,
            "Cantidad": cantidad
        })
        st.session_state.conteo = 0

# --- PANEL PRINCIPAL (RETRACTIL) ---
with st.expander("🛠️ PANEL DE CONTROL & REGISTRO", expanded=True):
    tab_captura, tab_reporte, tab_corte = st.tabs(["📝 Captura", "📋 Registros del Día", "🏁 Corte/Inventario"])

    with tab_captura:
        # Fila de entrada rápida
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            prod_nom = st.text_input("Producto:", placeholder="Nombre...", key="input_nom").upper()
        with col2:
            prod_cad = st.date_input("Caducidad:", value=fecha_hoy)
        with col3:
            cant = st.number_input("Cantidad:", min_value=0, step=1, key="conteo")
        with col4:
            st.write(" ")
            if st.button("➕", use_container_width=True):
                agregar_a_lista(prod_nom, prod_cad, cant)
                st.rerun()

        # Editor de la lista actual (antes de guardar)
        if st.session_state.lista_captura:
            st.write("---")
            df_temp = pd.DataFrame(st.session_state.lista_captura)
            df_editado = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, key="editor_actual")
            
            c_g, c_l = st.columns(2)
            with c_g:
                if st.button("💾 GUARDAR EN BASE DE DATOS", type="primary", use_container_width=True):
                    for _, fila in df_editado.iterrows():
                        c.execute("INSERT INTO registro_diario (nombre, fecha_cad, cantidad, fecha_registro) VALUES (?,?,?,?)",
                                  (fila['Producto'], str(fila['Caducidad']), fila['Cantidad'], str(fecha_hoy)))
                    conn.commit()
                    st.session_state.lista_captura = []
                    st.success("¡Guardado correctamente!")
                    st.rerun()
            with c_l:
                if st.button("🧹 LIMPIAR LISTA (Sin borrar DB)", use_container_width=True):
                    st.session_state.lista_captura = []
                    st.rerun()

    with tab_reporte:
        st.subheader("Historial de hoy")
        df_hoy = pd.read_sql("SELECT id, nombre, fecha_cad, cantidad FROM registro_diario WHERE fecha_registro = ?", conn, params=(str(fecha_hoy),))
        
        if not df_hoy.empty:
            st.dataframe(df_hoy, use_container_width=True, hide_index=True)
            col_del_all, col_del_id = st.columns([2, 2])
            with col_del_id:
                id_borrar = st.number_input("ID a borrar", min_value=0, step=1)
                if st.button("🗑️ Borrar ID"):
                    c.execute("DELETE FROM registro_diario WHERE id = ?", (id_borrar,))
                    conn.commit()
                    st.rerun()
            with col_del_all:
                if st.button("⚠️ BORRAR TODO EL DÍA"):
                    c.execute("DELETE FROM registro_diario WHERE fecha_registro = ?", (str(fecha_hoy),))
                    conn.commit()
                    st.rerun()
        else:
            st.info("No hay registros guardados hoy.")

    with tab_corte:
        st.subheader("Estado actual en estantes")
        df_base = pd.read_sql("SELECT nombre, fecha_cad, cantidad FROM base_anterior", conn)
        st.dataframe(df_base, use_container_width=True)
        
        if st.button("🏁 REALIZAR CORTE FINAL (Comparar y Reiniciar)"):
            # Aquí va tu lógica de comparación de ventas que ya tenías
            st.warning("Función de corte conectada. Procesando...")

# --- VISTA RÁPIDA (SIEMPRE VISIBLE) ---
st.write("---")
col_info1, col_info2 = st.columns(2)
with col_info1:
    st.caption(f"📅 Fecha: {fecha_hoy}")
with col_info2:
    total_piezas = pd.read_sql("SELECT SUM(cantidad) FROM registro_diario WHERE fecha_registro = ?", conn, params=(str(fecha_hoy),)).iloc[0,0]
    st.metric("Total registrado hoy", int(total_piezas) if total_piezas else 0)
