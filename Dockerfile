FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY aleph /app/aleph

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[mcp]"

ENTRYPOINT ["aleph"]
