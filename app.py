import streamlit as st
import urllib.parse
from datetime import datetime
import pytz
import sqlite3
import pandas as pd
import time
import io

# ------------------ CONFIGURACIÓN ------------------

st.set_page_config(page_title="Corte Champlitte", layout="centered", page_icon="🥐")

zona_mx = pytz.timezone("America/Mexico_City")

# ------------------ BASE DE DATOS ------------------

conn = sqlite3.connect("corte_champlitte.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS ventas (
id INTEGER PRIMARY KEY AUTOINCREMENT,
categoria TEXT,
monto REAL,
hora TEXT)
""")
conn.commit()

# ------------------ CSS ------------------

st.markdown("""
<style>
header {visibility:hidden;}
footer {visibility:hidden;}
.stApp{ background:#121212; color:white; }
input{
    background:#000!important; color:#90ee90!important;
    font-size:2rem!important; text-align:center!important;
    border-radius:12px!important; border:2px solid #444!important;
}
.stButton>button{
    width:100%; border-radius:10px; padding:16px;
    background:#1e1e1e!important; color:white!important;
    font-size:0.9rem!important; border:1px solid #333!important;
}
.stButton>button:hover{ border-color:#90ee90!important; background:#262626!important; }
.confirm{
    background:#1e1e1e; padding:15px; border-radius:10px;
    border-left:5px solid #90ee90; margin-top:15px;
}
.total-card{
    background:#1b1b1b; padding:20px; border-radius:14px;
    border-left:5px solid #90ee90; margin-bottom:20px; text-align:center;
}
.total-card h1{ font-size:2.5rem; margin:0; color:#90ee90; }
</style>
""", unsafe_allow_html=True)

# ------------------ ORDEN Y CATEGORÍAS ------------------

ORDEN_CATEGORIAS = [
    "Tarjeta Débito", 
    "Tarjeta Crédito", 
    "Uber", 
    "Didi", 
    "Rappi", 
    "Transferencia Liga"
]

labels_botones = [
    ("💳 T. Débito", "Tarjeta Débito"),
    ("💳 T. Crédito", "Tarjeta Crédito"),
    ("🚗 Uber", "Uber"),
    ("🛵 Didi", "Didi"),
    ("📦 Rappi", "Rappi"),
    ("🔗 Transf. Liga", "Transferencia Liga")
]

# ------------------ LÓGICA DE VARIABLES ------------------

if "calc_historial" not in st.session_state: st.session_state.calc_historial = []

def op_calc(tipo, accion):
    monto = st.session_state.monto_calculadora
    if monto and monto > 0:
        tipo_str = "Crédito" if tipo == "cre" else "Débito"
        accion_str = "Suma a Base" if accion == "base" else "Resta"
        
        st.session_state.calc_historial.append({
            "Tarjeta": tipo_str,
            "Operación": accion_str,
            "Monto": float(monto)
        })
        st.session_state.monto_calculadora = None

def limpiar_calc():
    st.session_state.calc_historial = [] 

def registrar_pago(cat):
    monto = st.session_state.monto_actual
    if monto and monto > 0:
        hora = datetime.now(zona_mx).strftime("%H:%M:%S")
        c.execute("INSERT INTO ventas (categoria,monto,hora) VALUES (?,?,?)", (cat,monto,hora))
        conn.commit()
        st.session_state.confirmacion = f"""
        <div class="confirm">
        ✅ <b>{cat}:</b> ${monto:.2f} | 🕒 {hora}
        </div>
        """
        st.session_state.monto_actual = None

# Función para convertir dataframe a CSV
@st.cache_data
def convertir_df_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# ------------------ SIDEBAR (MENÚ LATERAL) ------------------

st.sidebar.header("⚙️ Configuración")

# Lista desplegable para números de WhatsApp
opciones_wa = {
    "Contacto Principal": "522283530069",
    "Contacto Secundario": "522299359597",
    "Contacto 3": "520987654321" 
}
seleccion_wa = st.sidebar.selectbox("📱 Selecciona el WhatsApp destino", list(opciones_wa.keys()))
numero_whatsapp = opciones_wa[seleccion_wa]

st.sidebar.divider()

# Espacio para adjuntar CSV y restaurar datos
st.sidebar.subheader("💾 Respaldo de Base de Datos")
st.sidebar.info("Sube tu archivo CSV para restaurar los movimientos de ventas (puedes descargarlo desde la pestaña RESUMEN).")
archivo_csv = st.sidebar.file_uploader("⬆️ Subir Respaldo CSV", type=["csv"])

if archivo_csv is not None:
    if st.sidebar.button("🔄 Cargar y Restaurar Ventas", use_container_width=True):
        try:
            df_restaurar = pd.read_csv(archivo_csv)
            c.execute("DELETE FROM ventas")
            for _, fila in df_restaurar.iterrows():
                c.execute("INSERT INTO ventas (categoria, monto, hora) VALUES (?, ?, ?)", 
                          (str(fila['categoria']), float(fila['monto']), str(fila['hora'])))
            conn.commit()
            st.sidebar.success("✅ Base de datos restaurada correctamente")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"⚠️ Error al restaurar: {e}")

st.sidebar.divider()

with st.sidebar.expander("🚨 Zona de Peligro"):
    confirmar_reset = st.checkbox("Confirmar que deseo borrar todo", key="check_reset")
    if st.button("⚠️ EJECUTAR RESET TOTAL", use_container_width=True):
        if confirmar_reset:
            c.execute("DELETE FROM ventas")
            conn.commit()
            st.session_state.calc_historial = []
            st.sidebar.success("✅ Base de datos limpiada por completo")
            time.sleep(1)
            st.rerun()
        else:
            st.sidebar.error("Debes confirmar primero")


# ------------------ INTERFAZ (TABS) ------------------

tab1, tab2, tab3 = st.tabs(["📝 REGISTRO", "📊 RESUMEN", "🧮 CALCULADORA"])

# --- TAB 1: REGISTRO ---
with tab1:
    st.number_input("Monto", min_value=0.0, step=0.01, value=None, format="%.2f", key="monto_actual", placeholder="0.00")
    
    for i in range(0, len(labels_botones), 2):
        col1, col2 = st.columns(2)
        with col1:
            label, key = labels_botones[i]
            st.button(label, on_click=registrar_pago, args=(key,), key=f"btn_{i}")
        with col2:
            if i+1 < len(labels_botones):
                label, key = labels_botones[i+1]
                st.button(label, on_click=registrar_pago, args=(key,), key=f"btn_{i+1}")

    if "confirmacion" in st.session_state:
        st.markdown(st.session_state.confirmacion, unsafe_allow_html=True)

    st.divider()
    st.write("### 📋 Últimos Registros (Editable)")
    datos_recientes = c.execute("SELECT categoria, monto, hora FROM ventas ORDER BY id DESC LIMIT 10").fetchall()
    if datos_recientes:
        df_recientes = pd.DataFrame(datos_recientes, columns=["categoria", "monto", "hora"])
        edited_df_recientes = st.data_editor(df_recientes, use_container_width=True, hide_index=True, key="editor_tab1")
        
        # Opcional: WhatsApp sólo de los últimos movimientos
        mensaje_t1 = f"📝 *REGISTROS RECIENTES* ({datetime.now(zona_mx).strftime('%d/%m/%Y')})\n\n"
        for _, row in df_recientes.iterrows():
            mensaje_t1 += f"• {row['categoria']}: ${row['monto']:.2f} ({row['hora']})\n"
        
        url_wa_t1 = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje_t1)}"
        st.link_button("📲 ENVIAR ESTOS REGISTROS AL WA", url_wa_t1, use_container_width=True)
    else:
        st.info("Sin registros recientes.")


# --- TAB 2: RESUMEN ---
with tab2:
    datos = c.execute("SELECT categoria, monto, hora FROM ventas").fetchall()
    
    if not datos:
        st.info("Sin registros")
    else:
        df = pd.DataFrame(datos, columns=["categoria", "monto", "hora"])
        
        st.write("### 📂 Todos los Movimientos (Editable)")
        edited_df = st.data_editor(df, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_tab2")

        c1, c2, c3 = st.columns(3)
        if c1.button("💾 Guardar Cambios", use_container_width=True):
            c.execute("DELETE FROM ventas")
            for _, row in edited_df.iterrows():
                if pd.notna(row["categoria"]): # Evita guardar filas vacías
                    c.execute("INSERT INTO ventas (categoria, monto, hora) VALUES (?,?,?)", 
                             (row["categoria"], row["monto"], row["hora"]))
            conn.commit()
            st.success("Cambios guardados.")
            time.sleep(1)
            st.rerun()
            
        csv = convertir_df_csv(df)
        c2.download_button(label="📥 Descargar CSV", data=csv, file_name='ventas_respaldo.csv', mime='text/csv', use_container_width=True)
        
        if c3.button("🗑️ Borrar Todo", use_container_width=True):
            c.execute("DELETE FROM ventas")
            conn.commit()
            st.rerun()

        st.divider()

        st.write("### Totales por Categoría")
        
        mensaje = f"💰 *CORTE CHAMPLITTE* ({datetime.now(zona_mx).strftime('%d/%m/%Y')})\n\n"
        total_general = 0

        for cat in ORDEN_CATEGORIAS:
            monto_cat = edited_df[edited_df["categoria"] == cat]["monto"].sum()
            if monto_cat > 0:
                st.write(f"**{cat}:** ${monto_cat:.2f}")
                mensaje += f"• *{cat}:* ${monto_cat:.2f}\n"
                total_general += monto_cat
        
        t_deb = edited_df[edited_df["categoria"] == "Tarjeta Débito"]["monto"].sum()
        t_cre = edited_df[edited_df["categoria"] == "Tarjeta Crédito"]["monto"].sum()
        
        st.markdown(f"""
        <div class="total-card">
        <p>💳 TOTAL TARJETAS</p>
        <h1>${(t_deb + t_cre):.2f}</h1>
        </div>
        """, unsafe_allow_html=True)

        url_wa = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje)}"
        st.link_button("📲 ENVIAR REPORTE AL WA", url_wa, use_container_width=True)

# --- TAB 3: CALCULADORA ---
with tab3:
    st.write("### Calculadora de Tarjetas")
    st.number_input("Monto a ingresar", min_value=0.0, step=0.01, value=None, format="%.2f", key="monto_calculadora", placeholder="0.00")
    
    st.write("**1. Sumar Monto Base**")
    c1, c2 = st.columns(2)
    c1.button("➕ Base T. Crédito", on_click=op_calc, args=("cre", "base"), key="btn_base_cre")
    c2.button("➕ Base T. Débito", on_click=op_calc, args=("deb", "base"), key="btn_base_deb")

    st.write("**2. Restar Cantidades**")
    c3, c4 = st.columns(2)
    c3.button("➖ Restar a T. Crédito", on_click=op_calc, args=("cre", "resta"), key="btn_resta_cre")
    c4.button("➖ Restar a T. Débito", on_click=op_calc, args=("deb", "resta"), key="btn_resta_deb")

    st.divider()
    
    # --- TABLA DE DETALLES EDITABLE ---
    st.write("### 🧮 Detalle de Movimientos (Editable)")
    
    df_calc = pd.DataFrame(columns=["Tarjeta", "Operación", "Monto"]) # Default vacío
    if st.session_state.calc_historial:
        df_calc = pd.DataFrame(st.session_state.calc_historial)
        
    edited_calc = st.data_editor(df_calc, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_calc")
    
    if st.button("💾 Guardar Cambios en Calculadora", use_container_width=True):
        st.session_state.calc_historial = edited_calc.to_dict('records')
        st.success("Cálculos actualizados.")
        time.sleep(1)
        st.rerun()
        
    st.divider()
    
    # Recalculamos basándonos en la tabla editada
    base_cre = edited_calc[(edited_calc["Tarjeta"] == "Crédito") & (edited_calc["Operación"] == "Suma a Base")]["Monto"].sum()
    resta_cre = edited_calc[(edited_calc["Tarjeta"] == "Crédito") & (edited_calc["Operación"] == "Resta")]["Monto"].sum()
    
    base_deb = edited_calc[(edited_calc["Tarjeta"] == "Débito") & (edited_calc["Operación"] == "Suma a Base")]["Monto"].sum()
    resta_deb = edited_calc[(edited_calc["Tarjeta"] == "Débito") & (edited_calc["Operación"] == "Resta")]["Monto"].sum()

    res_cre = base_cre - resta_cre
    res_deb = base_deb - resta_deb
    
    st.write("### Resultados Finales")
    st.markdown(f"""
    <div class="confirm" style="border-left:5px solid #ffcc00;">
        <p style="margin:0; font-size:14px; color:#aaa;">💳 T. CRÉDITO (Base: ${base_cre:.2f} | Restado: ${resta_cre:.2f})</p>
        <h2 style="margin:0; color:#ffcc00;">${res_cre:.2f}</h2>
    </div>
    <div class="confirm" style="border-left:5px solid #00ccff;">
        <p style="margin:0; font-size:14px; color:#aaa;">💳 T. DÉBITO (Base: ${base_deb:.2f} | Restado: ${resta_deb:.2f})</p>
        <h2 style="margin:0; color:#00ccff;">${res_deb:.2f}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    
    col_calc_1, col_calc_2 = st.columns(2)
    with col_calc_1:
        st.button("🧹 Limpiar Calculadora", on_click=limpiar_calc, use_container_width=True)
    
    with col_calc_2:
        mensaje_calc = f"🧮 *CALCULADORA CHAMPLITTE* ({datetime.now(zona_mx).strftime('%d/%m/%Y')})\n\n"
        mensaje_calc += f"💳 *T. CRÉDITO:*\nBase: ${base_cre:.2f}\nRestado: ${resta_cre:.2f}\n*RESULTADO: ${res_cre:.2f}*\n\n"
        mensaje_calc += f"💳 *T. DÉBITO:*\nBase: ${base_deb:.2f}\nRestado: ${resta_deb:.2f}\n*RESULTADO: ${res_deb:.2f}*"
        
        url_wa_calc = f"https://wa.me/{numero_whatsapp}?text={urllib.parse.quote(mensaje_calc)}"
        st.link_button("📲 ENVIAR RESULTADOS AL WA", url_wa_calc, use_container_width=True)

