FROM python:3.12-slim
WORKDIR /app
COPY scripts/wifi_csi_gateway.py /app/wifi_csi_gateway.py
RUN useradd --system --uid 10001 gateway && mkdir -p /data && chown 10001:10001 /data
USER 10001
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/wifi_csi_gateway.py"]
