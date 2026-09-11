FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[postgres]"

RUN useradd --create-home --uid 10001 promptlab
USER promptlab
EXPOSE 8000
CMD ["uvicorn", "prompt_laboratory.api:app", "--host", "0.0.0.0", "--port", "8000"]
