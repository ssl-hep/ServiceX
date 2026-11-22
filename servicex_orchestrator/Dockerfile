FROM python:3.11-slim

# Group 0 so the image also runs under OpenShift's arbitrary UIDs
RUN useradd -ms /bin/bash -g 0 servicex

WORKDIR /home/servicex

ENV POETRY_VERSION=2.1.1 \
    PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir poetry==$POETRY_VERSION && \
    poetry config virtualenvs.create false

# Dependencies first so code changes don't invalidate this layer
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-root --no-interaction --no-ansi --without test

COPY src ./src
RUN poetry install --only-root --no-interaction --no-ansi

USER servicex

ENTRYPOINT ["servicex-orchestrator"]
