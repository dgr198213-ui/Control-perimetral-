FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY control-api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY control-api/app.py ./app.py
COPY control-api/db.py ./db.py
RUN useradd --create-home --uid 10002 controlapi
USER controlapi

EXPOSE 8000
CMD ["python", "app.py"]
