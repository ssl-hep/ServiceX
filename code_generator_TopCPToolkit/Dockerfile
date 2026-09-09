FROM python:3.10

RUN useradd -ms /bin/bash -g 0 servicex && chmod 0750 /home/servicex
RUN apt-get update && apt-get install -y netcat-traditional && rm -rf /var/lib/apt/lists/*

WORKDIR /home/servicex
RUN mkdir ./servicex

ENV  POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

RUN pip install gunicorn

COPY boot.sh ./
RUN chmod 755 boot.sh

COPY transformer_capabilities.json ./
RUN chmod 644 transformer_capabilities.json

COPY servicex/ ./servicex
RUN chmod 777 -R servicex

COPY app.conf .
RUN chmod 755 app.conf

USER servicex

ENV CODEGEN_CONFIG_FILE="/home/servicex/app.conf"

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
