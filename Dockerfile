FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости (если нужны, например, для aiohttp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY app.py .

# Открываем порт для Flask (keep-alive)
EXPOSE 8080

# Запускаем бота
CMD ["python", "app.py"]
