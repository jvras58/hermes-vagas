FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system jobhunter \
    && useradd --system --gid jobhunter --create-home jobhunter

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN python -m pip install --no-cache-dir .

RUN mkdir -p /app/workspace/inputs /app/workspace/outputs /app/workspace/state \
    && chown -R jobhunter:jobhunter /app

USER jobhunter

EXPOSE 8000

CMD ["python", "-m", "job_hunter.mcp_server"]

