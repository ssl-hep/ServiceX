FROM python:3.12

RUN useradd -ms /bin/bash servicex
RUN apt-get update && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /home/servicex
RUN mkdir ./servicex

ENV  POETRY_VERSION=1.5.1
RUN pip install poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

RUN pip install gunicorn

COPY boot.sh ./
COPY servicex/ ./servicex
RUN chmod +x boot.sh

USER servicex
# COPY app.conf .

ENV REPLICA_SVC_CONFIG_FILE "/home/servicex/app.conf"

EXPOSE 5000
# ENTRYPOINT ["./boot.sh"]

