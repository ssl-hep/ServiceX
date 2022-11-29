FROM python:3.11 AS builder

RUN useradd -ms /bin/bash cleanup

COPY pyproject.toml poetry.lock /home/cleanup/
WORKDIR /home/cleanup

FROM builder as poetry
ENV POETRY_HOME=/home/cleanup
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN python -c 'from urllib.request import urlopen; print(urlopen("https://install.python-poetry.org").read().decode())' | python -
COPY resources ./
RUN poetry install --no-interaction --no-ansi -vvv

FROM builder AS runtime

COPY --from=poetry /home/cleanup /home/cleanup
WORKDIR /home/cleanup
RUN mkdir ./cleanup
COPY scripts/*.py  resources/start.sh ./

RUN chmod +x start.sh

USER cleanup

ENTRYPOINT ["./start.sh"]