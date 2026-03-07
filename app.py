import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ------------------ CONFIGURACIÓN DE PÁGINA ------------------
st.set_page_config(page_title="Control de Inventario Pan", page_icon="🥐")
st.title("Corte de Inventario por Revisión 🥐")

# ------------------ BASE DE DATOS ------------------
conn = sqlite3.connect('inventario_pan.db', check_same_thread=False)
c = conn.cursor()

# Tabla de Existencias: Almacena el conteo físico de cada revisión
c.execute('''CREATE TABLE IF NOT EXISTS existencias 
             (nombre TEXT, fecha_cad DATE, revision_id INTEGER)''')

# Tabla de Historial: Registro permanente de lo que se determinó como "Vendido"
c.execute('''CREATE TABLE IF NOT EXISTS historial_ventas 
             (nombre TEXT, fecha_cad DATE, cantidad INTEGER, fecha_corte DATETIME)''')
conn.commit()

# --- Lógica de IDs de Revisión ---
# Buscamos cuál es el ID más alto registrado actualmente
res_id = c.execute("SELECT MAX(revision_id) FROM existencias").fetchone()
rev_actual = (res_id[0] if res_id[0] else 1)

# ------------------ SECCIÓN 1: CAPTURA DE PRODUCTOS ------------------
st.header(f"📝 Capturando: Revisión #{rev_actual}")

with st.container(border=True):
    # Obtenemos nombres previos para el autocompletado
    query_nombres = "SELECT DISTINCT nombre FROM existencias UNION SELECT DISTINCT nombre FROM historial_ventas"
    nombres_previos = [r[0] for r in c.execute(query_nombres).fetchall()]
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Corregido: eliminamos str_value_allowed que causaba el error
        opcion = st.selectbox(
            "Selecciona Producto:", 
            options=["-- Escribir Nuevo --"] + nombres_previos,
            index=0
        )
        
        if opcion == "-- Escribir Nuevo --":
            nombre_final = st.text_input("Nombre del producto nuevo:", key="nuevo_prod")
        else:
            nombre_final = opcion
    
    with col2:
        f_cad = st.date_input("Fecha de Caducidad:", value=datetime.now().date())
        cant = st.number_input("Cantidad física detectada:", min_value=1, value=1, step=1)

    if st.button("➕ Agregar al conteo actual", use_container_width=True):
        if nombre_final and nombre_final.strip() != "":
            for _ in range(int(cant)):
                c.execute("INSERT INTO existencias (nombre, fecha_cad, revision_id) VALUES (?, ?, ?)", 
                         (nombre_final.strip(), f_cad, rev_actual))
            conn.commit()
            st.success(f"Registrado: {cant} unidades de '{nombre_final}'")
            st.rerun()
        else:
            st.error("Por favor, ingresa un nombre de producto válido.")

# ------------------ SECCIÓN 2: VISTA PREVIA DEL CONTEO ------------------
df_conteo = pd.read_sql("""SELECT nombre, fecha_cad, COUNT(*) as cantidad 
                           FROM existencias WHERE revision_id = ? 
                           GROUP BY nombre, fecha_cad""", conn, params=(rev_actual,))

if not df_conteo.empty:
    st.subheader("Lista actual de esta revisión:")
    st.dataframe(df_conteo, use_container_width=True)
else:
    st.info("Aún no hay capturas para la revisión actual.")

# ------------------ SECCIÓN 3: BOTÓN DE CORTE (FINALIZAR) ------------------
st.divider()
if st.button("🏁 FINALIZAR REVISIÓN Y CALCULAR VENTAS", type="primary", use_container_width=True):
    if df_conteo.empty:
        st.warning("No puedes finalizar una revisión sin datos capturados.")
    else:
        # 1. Identificar la revisión anterior para comparar
        rev_anterior = rev_actual - 1
        
        # 2. Traer lo que quedó en la revisión anterior
        df_anterior = pd.read_sql("""SELECT nombre, fecha_cad, COUNT(*) as cant 
                                     FROM existencias WHERE revision_id = ? 
                                     GROUP BY nombre, fecha_cad""", conn, params=(rev_anterior,))

        ventas_detectadas = []
        ahora_fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. Lógica de comparación: Anterior vs Actual
        for _, fila in df_anterior.iterrows():
            # Contar cuántos hay AHORA del mismo nombre y caducidad
            res_ahora = c.execute("""SELECT COUNT(*) FROM existencias 
                                     WHERE nombre=? AND fecha_cad=? AND revision_id=?""", 
                                  (fila['nombre'], fila['fecha_cad'], rev_actual)).fetchone()
            cant_ahora = res_ahora[0]
            
            diferencia = fila['cant'] - cant_ahora
            
            if diferencia > 0:
                ventas_detectadas.append({
                    "Producto": fila['nombre'], 
                    "Caducidad": fila['fecha_cad'], 
                    "Vendidos": diferencia
                })
                # Guardar en el historial permanente
                c.execute("INSERT INTO historial_ventas (nombre, fecha_cad, cantidad, fecha_corte) VALUES (?, ?, ?, ?)", 
                         (fila['nombre'], fila['fecha_cad'], diferencia, ahora_fecha))

        # 4. Limpieza: Borramos la revisión "vieja" (ID anterior)
        c.execute("DELETE FROM existencias WHERE revision_id = ?", (rev_anterior,))
        
        # 5. Preparamos para el siguiente turno: Incrementamos el ID de lo capturado hoy
        proxima_rev = rev_actual + 1
        c.execute("UPDATE existencias SET revision_id = ? WHERE revision_id = ?", (proxima_rev, rev_actual))
        
        conn.commit()

        # 6. Resultados
        st.balloons()
        st.success(f"✅ Revisión #{rev_actual} cerrada.")
        
        if ventas_detectadas:
            st.subheader("🛍️ Resumen de Ventas detectadas:")
            st.table(pd.DataFrame(ventas_detectadas))
        else:
            st.info("No se detectaron ventas (el inventario coincide con el turno anterior).")
        
        st.info(f"El sistema está listo para la **Revisión #{proxima_rev}**")
        
        if st.button("Comenzar nueva revisión"):
            st.rerun()

# ------------------ SECCIÓN 4: HISTÓRICO ------------------
with st.expander("📖 Ver Historial General de Ventas Acumuladas"):
    df_ventas = pd.read_sql("SELECT * FROM historial_ventas ORDER BY fecha_corte DESC", conn)
    if not df_ventas.empty:
        st.dataframe(df_ventas, use_container_width=True)
    else:
        st.write("No hay ventas registradas en el historial todavía.")
