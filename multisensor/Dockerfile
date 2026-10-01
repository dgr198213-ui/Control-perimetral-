FROM python:3.12-slim
WORKDIR /app
COPY multisensor/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY multisensor /app/multisensor
COPY scripts /app/scripts
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "multisensor.api.app"]
