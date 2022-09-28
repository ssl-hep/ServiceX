FROM python:3.7

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./servicex

COPY requirements.txt requirements.txt

RUN pip install safety==1.9.0
RUN safety check -r requirements.txt
RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY boot.sh ./
COPY servicex/ ./servicex
COPY scripts/from_text_to_zip.py .
RUN chmod +x boot.sh

USER servicex

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]

