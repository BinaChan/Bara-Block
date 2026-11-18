FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    BARA_BIND=0.0.0.0 \
    BARA_PUBLIC_READ_ONLY=1 \
    BARA_CACHE_DIR=/app/data/runtime_cache
WORKDIR /app
COPY requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt
# Include bundled OSM, peat and foundation data in the image. Runtime cache is
# stored separately, so attaching a volume will not hide bundled seed files.
COPY . /app
RUN useradd --create-home --shell /usr/sbin/nologin bara \
    && mkdir -p /app/data/runtime_cache \
    && chown -R bara:bara /app/data/runtime_cache
USER bara
EXPOSE 8080
CMD ["python", "server.py"]
