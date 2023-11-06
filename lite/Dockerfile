FROM python:3.11 AS builder

RUN useradd -ms /bin/bash sxlite

COPY pyproject.toml poetry.lock /home/sxlite/
WORKDIR /home/sxlite

FROM builder as poetry
ENV POETRY_HOME=/home/sxlite
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN python -c 'from urllib.request import urlopen; print(urlopen("https://install.python-poetry.org").read().decode())' | python -
COPY resources ./
RUN poetry install --no-interaction --no-ansi -vvv

FROM builder AS runtime

COPY --from=poetry /home/sxlite /home/sxlite
WORKDIR /home/sxlite
RUN mkdir ./sxlite
COPY scripts/*.py  resources/start.sh ./

RUN chmod +x start.sh

USER sxlite

ENTRYPOINT ["./start.sh"]
