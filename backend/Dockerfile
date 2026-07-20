FROM python:3.11-slim

# Stockfish is the project's source of truth for move quality — the model never evaluates a
# position itself — so the engine must be present in the image, not called as a service.
# curl is used by the container healthcheck below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependencies are installed before the rest of the source so that editing app.py or config/
# does not invalidate the slow dependency layer. src/ has to come first regardless: the project
# is a src-layout package, and an editable install fails with "egg_base 'src' does not exist"
# if the build backend cannot see it.
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv pip install --no-cache-dir --system -e .

COPY . .

# apt installs the engine at /usr/games/stockfish, while settings.py defaults to
# /usr/local/bin/stockfish and falls back to whatever `which stockfish` finds. The symlink
# makes the configured path correct outright rather than relying on that fallback.
# Fail the build here rather than at runtime if the engine is missing or unusable: a deployed
# image without a working engine cannot analyse anything, and the app would surface that as
# empty analysis rather than a clear error.
# apt installs the engine to /usr/games/stockfish, and /usr/games is NOT on PATH in this
# image. Both settings.py's default (/usr/local/bin/stockfish) and its shutil.which fallback
# would therefore fail to find it, giving an image with an engine it cannot reach. The symlink
# puts it exactly where the app already looks. The UCI handshake fails the build now rather
# than letting the service deploy and return empty analysis.
RUN ln -sf /usr/games/stockfish /usr/local/bin/stockfish \
    && printf 'uci\nquit\n' | /usr/local/bin/stockfish | grep -q "uciok" \
    && echo "stockfish verified: $(readlink -f /usr/local/bin/stockfish)"

# Run as a non-root user. The vector store is written at startup, so its directory has to be
# writable by that user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data/chroma \
    && chown -R appuser:appuser /app
USER appuser

ENV HOST=0.0.0.0 \
    PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Render overrides PORT, so the healthcheck reads it rather than assuming 8000.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
