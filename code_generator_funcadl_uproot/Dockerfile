FROM python:3.10

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./uproot_code_generator

ENV  POETRY_VERSION=1.2.2
RUN pip install poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

RUN pip install gunicorn

COPY boot.sh ./
COPY transformer_capabilities.json ./
COPY uproot_code_generator/ ./uproot_code_generator/
COPY scripts/from_ast_to_zip.py .
RUN chmod +x boot.sh

USER servicex
COPY app.conf .

ENV CODEGEN_CONFIG_FILE "/home/servicex/app.conf"

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]

