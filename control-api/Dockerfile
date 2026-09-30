FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY control-api/app.py ./app.py
RUN useradd --create-home --uid 10002 controlapi
USER controlapi

EXPOSE 8000
CMD ["python", "app.py"]
