FROM python:3.10

ARG APP_CONFIG_FILE="app.atlas.xaod.conf"

ENV  POETRY_VERSION=1.2.2
RUN pip install poetry==$POETRY_VERSION

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./xaod_code_generator

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi
RUN pip install gunicorn
RUN pip list

COPY boot.sh ./
COPY transformer_capabilities.json ./
COPY xaod_code_generator/ ./xaod_code_generator
COPY scripts/from_ast_to_zip.py .
RUN chmod +x boot.sh

USER servicex
COPY ${APP_CONFIG_FILE} app.conf
ENV CODEGEN_CONFIG_FILE /home/servicex/app.conf

EXPOSE 5000
ENTRYPOINT ["/home/servicex/boot.sh"]
