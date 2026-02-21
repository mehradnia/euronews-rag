FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

# Copy dependency files first for layer caching
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
