# syntax=docker/dockerfile:1

FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

RUN playwright install --with-deps chromium

COPY src ./src
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV PYTHONPATH=/app/src

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-u", "-m", "crawler.worker"]