FROM python:3.11-slim

WORKDIR /app

COPY src/ .

RUN pip install --no-cache-dir flask

EXPOSE 8080

CMD ["python", "main.py"]
