# 1. Imagem base otimizada e leve (FinOps/Performance)
FROM python:3.11-slim

# 2. Define o diretório de trabalho lá dentro
WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# 3. Instala dependências do sistema operacional necessárias para compilar bibliotecas
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia APENAS o arquivo de requisitos primeiro (Tática de Cache de Camada)
COPY requirements.txt .

# 5. Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Agora sim, copia todo o nosso código fonte para dentro do contêiner
COPY . .

# 7. Expõe a porta padrão do Streamlit
EXPOSE 8501

# 8. Comando de inicialização do servidor web
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]