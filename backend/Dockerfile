FROM python:3.11-slim

# Install system dependencies, including Stockfish
RUN apt-get update && apt-get install -y \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable package installations
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install python packages using uv in system mode
RUN uv pip install --no-cache-dir --system -e .

# Copy backend source code
COPY . .

EXPOSE 8000

# Set production environment variables
ENV HOST=0.0.0.0
ENV PORT=8000

# Run uvicorn server
CMD uvicorn app:app --host $HOST --port $PORT
