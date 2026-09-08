FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY src/ ./src/

EXPOSE 8000

CMD ["uv", "run", "python", "src/main.py"]