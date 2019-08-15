FROM python:3.6

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY *.py docker-dev.conf boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP run.py

USER servicex

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
