FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY docker-entrypoint.sh /usr/local/bin/sakhicare-entrypoint
ENTRYPOINT ["sh", "/usr/local/bin/sakhicare-entrypoint"]
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0"]
