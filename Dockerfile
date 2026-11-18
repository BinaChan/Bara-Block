FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 BARA_BIND=0.0.0.0 BARA_PUBLIC_READ_ONLY=1
WORKDIR /app
COPY requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt
COPY . /app
RUN useradd --create-home --shell /usr/sbin/nologin bara \
    && mkdir -p /app/data/tersimpan \
    && chown -R bara:bara /app/data
USER bara
EXPOSE 8080
CMD ["python", "server.py"]
