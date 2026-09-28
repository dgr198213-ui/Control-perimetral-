FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY notifier/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY notifier/notifier.py ./notifier.py
COPY multisensor ./multisensor
RUN useradd --create-home --uid 10001 notifier
USER notifier

CMD ["python", "notifier.py"]
