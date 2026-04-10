FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install uv

# Copy the full monorepo (needed for workspace packages)
COPY . .

# Install all workspace packages
RUN uv sync --all-packages --no-dev

# Install extras that uv sync misses
RUN uv pip install pytest-asyncio iniconfig python-jose pypdf --python .venv/bin/python 2>/dev/null || true

EXPOSE 8000

CMD [".venv/bin/python", "-m", "uvicorn", "astra_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api"]
