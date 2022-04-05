FROM python:3.9

ARG APP_CONFIG_FILE="app.atlas.xaod.conf"

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./servicex

COPY requirements.txt requirements.txt

RUN pip install safety==1.9.0
RUN safety check -r requirements.txt
RUN pip install -r requirements.txt
RUN pip install gunicorn
RUN pip list

COPY boot.sh ./
COPY servicex/ ./servicex
COPY scripts/from_ast_to_zip.py .
RUN chmod +x boot.sh

USER servicex
COPY ${APP_CONFIG_FILE} app.conf
ENV APP_CONFIG_FILE /home/servicex/app.conf

EXPOSE 5000
ENTRYPOINT ["/home/servicex/boot.sh"]
