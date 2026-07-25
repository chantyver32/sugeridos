# Usamos una imagen ligera de Python
FROM python:3.9-slim

# Establecemos el directorio de trabajo
WORKDIR /app

# Copiamos primero el requirements para aprovechar el caché de Docker
COPY requirements.txt ./requirements.txt

# Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de tu desmadre al contenedor
COPY . .

# Exponemos el puerto que usa Streamlit por defecto
EXPOSE 8501

# Comando para ejecutar la aplicación (CAMBIA 'app.py' POR EL NOMBRE DE TU ARCHIVO PRINCIPAL)
CMD mkdir -p .streamlit && echo "[connections.supabase]" > .streamlit/secrets.toml && echo "url = \"$SUPABASE_URL\"" >> .streamlit/secrets.toml && streamlit run app.py --server.port=8501 --server.address=0.0.0.0
