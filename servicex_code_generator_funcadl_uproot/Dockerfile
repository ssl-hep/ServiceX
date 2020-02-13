FROM python:3.7

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./servicex

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY boot.sh ./
COPY servicex/ ./servicex
COPY scripts/from_ast_to_zip.py .
RUN chmod +x boot.sh

USER servicex
COPY app.conf .

ENV APP_CONFIG_FILE "/home/servicex/app.conf"

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]

