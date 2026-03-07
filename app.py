import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

# Tabla de Existencias: Lo que está físicamente en tienda ahora
c.execute('''CREATE TABLE IF NOT EXISTS existencias 
             (nombre TEXT, fecha_cad DATE, revision_id INTEGER)''')
# Tabla de Historial: Para guardar qué se vendió y cuándo
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas 
             (nombre TEXT, fecha_cad DATE, cantidad INTEGER, fecha_corte DATETIME)''')
conn.commit()

st.set_page_config(page_title="Control de Turnos", page_icon="🥐")
st.title("Corte de Inventario por Revisión 🥐")

# --- Lógica de IDs de Revisión ---
# Obtenemos el ID de la revisión actual (la que estamos capturando)
res_id = c.execute("SELECT MAX(revision_id) FROM existencias").fetchone()
rev_actual = (res_id[0] if res_id[0] else 1)

# ------------------ SECCIÓN 1: CAPTURA DE PRODUCTOS ------------------
st.header(f"📝 Capturando: Revisión #{rev_actual}")

with st.container(border=True):
    # Sugerencias de nombres
    nombres_previos = [r[0] for r in c.execute("SELECT DISTINCT nombre FROM existencias UNION SELECT DISTINCT nombre FROM historial_ventas").fetchall()]
    
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.selectbox("Producto:", options=nombres_previos, index=None, placeholder="Busca o escribe...", str_value_allowed=True)
        if not nombre: # Si no elige del select, permite escribir manual
            nombre = st.text_input("¿Producto nuevo? Escríbelo:")
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=datetime.now().date())
        cant = st.number_input("Cantidad física que ves:", min_value=1, value=1)

    if st.button("➕ Agregar al conteo actual", use_container_width=True):
        if nombre:
            for _ in range(cant):
                c.execute("INSERT INTO existencias (nombre, fecha_cad, revision_id) VALUES (?, ?, ?)", 
                          (nombre, f_cad, rev_actual))
            conn.commit()
            st.success(f"Registrado: {cant} {nombre}")
        else:
            st.error("Escribe el nombre del pan.")

# ------------------ SECCIÓN 2: VISTA PREVIA DEL CONTEO ------------------
df_conteo = pd.read_sql("""SELECT nombre, fecha_cad, COUNT(*) as cantidad 
                           FROM existencias WHERE revision_id = ? 
                           GROUP BY nombre, fecha_cad""", conn, params=(rev_actual,))

if not df_conteo.empty:
    st.subheader("Lista de lo que has capturado:")
    st.dataframe(df_conteo, use_container_width=True)
else:
    st.info("Aún no has capturado nada en esta revisión.")

# ------------------ SECCIÓN 3: BOTÓN DE CORTE (FINALIZAR) ------------------
st.divider()
if st.button("🏁 FINALIZAR REVISIÓN Y HACER CORTE", type="primary", use_container_width=True):
    if df_conteo.empty:
        st.warning("No puedes finalizar una revisión vacía.")
    else:
        # 1. Buscar lo que había en la revisión anterior (ID - 1)
        rev_anterior = rev_actual - 1
        df_anterior = pd.read_sql("""SELECT nombre, fecha_cad, COUNT(*) as cant 
                                     FROM existencias WHERE revision_id = ? 
                                     GROUP BY nombre, fecha_cad""", conn, params=(rev_anterior,))

        # 2. Comparar para hallar ventas
        ventas_detectadas = []
        for _, fila in df_anterior.iterrows():
            # Cuántos registramos AHORA de este producto/caducidad
            ahora = len(c.execute("SELECT 1 FROM existencias WHERE nombre=? AND fecha_cad=? AND revision_id=?", 
                                (fila['nombre'], fila['fecha_cad'], rev_actual)).fetchall())
            
            diferencia = fila['cant'] - ahora
            if diferencia > 0:
                ventas_detectadas.append({
                    "Producto": fila['nombre'], 
                    "Caducidad": fila['fecha_cad'], 
                    "Vendidos": diferencia
                })
                # Guardar en el historial de ventas permanente
                c.execute("INSERT INTO historial_ventas VALUES (?, ?, ?, ?)", 
                          (fila['nombre'], fila['fecha_cad'], diferencia, datetime.now()))

        # 3. Limpiar lo viejo y preparar para la siguiente revisión
        # Borramos los registros de la revisión anterior
        c.execute("DELETE FROM existencias WHERE revision_id < ?", (rev_actual,))
        # El ID de revisión para la PRÓXIMA vez será el actual + 1
        proxima_rev = rev_actual + 1
        c.execute("UPDATE existencias SET revision_id = ?", (proxima_rev,))
        conn.commit()

        # 4. Mostrar Resultados
        st.balloons()
        st.success(f"✅ Revisión #{rev_actual} cerrada exitosamente.")
        
        if ventas_detectadas:
            st.subheader("🛍️ Resumen de Ventas en este turno:")
            st.table(pd.DataFrame(ventas_detectadas))
        else:
            st.info("No hubo ventas: El inventario coincide con la revisión anterior.")
        
        st.info(f"La siguiente captura será la Revisión #{proxima_rev}")
        st.rerun()

# ------------------ SECCIÓN 4: HISTÓRICO ------------------
with st.expander("📖 Ver Historial General de Ventas"):
    df_ventas = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    if not df_ventas.empty:
        st.dataframe(df_ventas)
    else:
        st.write("Aún no hay ventas registradas.")
