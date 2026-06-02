FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY app.py .

# Открываем порт для Flask (keep-alive)
EXPOSE 8080

CMD ["python", "app.py"]
