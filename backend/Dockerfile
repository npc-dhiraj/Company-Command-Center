FROM python:3.12-slim

# Create non-root group and user
RUN addgroup --system appgroup && adduser --system --group appuser

WORKDIR /app

# Copy dependency specifications
COPY requirements.txt requirements-dev.txt ./

# Install runtime and development dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Copy application files
COPY app/ ./app/
COPY tests/ ./tests/
COPY migrations/ ./migrations/
COPY alembic.ini pyproject.toml ./

# Adjust ownership to non-root user
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
