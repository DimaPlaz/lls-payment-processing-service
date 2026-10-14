FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Сначала ставим только зависимости (по заглушке пакета), чтобы слой кешировался
# и не пересобирался при каждом изменении кода
COPY pyproject.toml ./
RUN mkdir -p src/payments && touch src/payments/__init__.py \
    && pip install . \
    && pip uninstall -y llc_mkk_basis_test \
    && rm -rf src build

COPY src ./src
RUN pip install --no-deps . && rm -rf build

COPY alembic.ini ./
COPY alembic ./alembic

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000

CMD ["uvicorn", "payments.presentation.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
