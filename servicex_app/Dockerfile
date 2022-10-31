FROM python:3.10

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./servicex

ENV  POETRY_VERSION=1.2.2
RUN pip install poetry==$POETRY_VERSION

COPY README.rst README.rst
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

COPY *.py docker-dev.conf boot.sh ./
COPY servicex/ ./servicex
COPY migrations migrations

RUN chmod +x boot.sh

#ENV FLASK_APP servicex

USER servicex

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
