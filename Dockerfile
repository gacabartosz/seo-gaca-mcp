FROM python:3.12-slim

WORKDIR /app

# System deps for lxml and curl (SSL checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install the package
RUN uv pip install --system -e .

# MCP stdio transport
ENTRYPOINT ["python", "-m", "seoleo"]
