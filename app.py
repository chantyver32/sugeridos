# ------------------ PASO 1: CAPTURA FÍSICA ------------------
st.header(f"📝 Paso 1: Conteo en Estantes ({fecha_hoy_mx.strftime('%d/%m/%Y')})")

# 1. Inicializar estados necesarios
if "conteo_temp" not in st.session_state:
    st.session_state.conteo_temp = 0
if "buscar_prod" not in st.session_state:
    st.session_state.buscar_prod = ""

# 2. Función para limpiar buscador y selección
def limpiar_todo():
    st.session_state.buscar_prod = ""
    # Borramos la selección del selectbox para que no se quede pegado el último producto
    if "sel_prod" in st.session_state:
        del st.session_state["sel_prod"]

# 3. Obtener base de productos para el autofiltrado
nombres_prev = [r[0] for r in c.execute(
    "SELECT DISTINCT nombre FROM base_anterior UNION SELECT DISTINCT nombre FROM captura_actual"
).fetchall()]

# --- DISEÑO DE BÚSQUEDA ---
col_busq, col_limpiar = st.columns([3, 1])

with col_busq:
    # Este input captura lo que escribes en tiempo real
    texto_buscar = st.text_input("🔎 Escribe para filtrar o agregar nuevo:", key="buscar_prod").upper()

with col_limpiar:
    st.write("##") # Alineación visual
    st.button("🧹 Limpiar", on_click=limpiar_todo, use_container_width=True)

# 4. LÓGICA DE FILTRADO DINÁMICO
# Filtramos la lista de la base de datos según lo que el usuario escribe
sugerencias = [p for p in nombres_prev if texto_buscar in p] if texto_buscar else nombres_prev

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if sugerencias:
        # Si hay coincidencias, el selectbox las muestra. 
        # Si el usuario escribe algo que NO está, el selectbox no se muestra y usamos el texto directo.
        nombre_final = st.selectbox("Sugerencias (Base de Datos):", sugerencias, key="sel_prod")
    else:
        # Si no hay coincidencias, usamos el texto que el usuario escribió
        st.info("✨ Producto nuevo")
        nombre_final = texto_buscar

with col2:
    f_cad = st.date_input("Fecha de Caducidad:", value=fecha_hoy_mx, min_value=fecha_hoy_mx, key="date_cad")

with col3:
    st.write("Cantidad que ves")
    # Botones de suma (estos deben estar dentro del flujo para afectar a st.session_state.conteo_temp)

# --- BOTONES DE CONTEO ---
c1, c2, c3, c4 = st.columns(4)
with c1: st.button("+1", use_container_width=True, on_click=sumar, args=(1,))
with c2: st.button("+5", use_container_width=True, on_click=sumar, args=(5,))
with c3: st.button("+10", use_container_width=True, on_click=sumar, args=(10,))
with c4: st.button("Borrar Cantidad", use_container_width=True, on_click=resetear)

st.metric("Total contado", st.session_state.conteo_temp)
