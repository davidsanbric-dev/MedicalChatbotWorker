# Use Python 3.12 slim image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    UV_PROJECT_ENVIRONMENT=system

# Set working directory
WORKDIR /app

# Install system dependencies
# RUN apt-get update && apt-get install -y \
#     gcc \
#     python3-dev \
#     && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv (the new universal manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

# Copy necessary files for package build
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY services/ ./services/
COPY repositories/ ./repositories/
COPY db/ ./db/

RUN uv sync --frozen

# Verify light-embed installation
RUN uv run python -c "import light_embed; print(f'light_embed version: {light_embed.__version__}')" || echo "Failed to import light_embed"

# Copy remaining application code
COPY . .

# Default command - use uv run to ensure proper environment
CMD ["uv", "run", "python", "main.py", "--help"]