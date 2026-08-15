# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

# Instalar dependencias del sistema (Zbar y Tesseract en español)
RUN apt-get update && apt-get install -y \
    libzbar0 \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Configurar el directorio de trabajo en el contenedor
WORKDIR /app

# Copiar el archivo de requerimientos e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto que Render asigna por defecto
EXPOSE 10000

# Ejecutar Streamlit usando la variable de entorno PORT de Render
CMD streamlit run "app.py" --server.port=${PORT:-10000} --server.address=0.0.0.0
