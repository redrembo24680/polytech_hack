FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY booking_mcp ./booking_mcp
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8002
CMD ["python", "-m", "booking_mcp"]
