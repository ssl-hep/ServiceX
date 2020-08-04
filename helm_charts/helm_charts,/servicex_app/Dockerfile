FROM python:3.6

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./servicex

COPY setup.py setup.py
COPY setup.cfg setup.cfg
COPY README.rst README.rst
RUN pip install -e .
RUN pip install gunicorn
RUN pip install safety && \
    pip freeze | safety check


COPY *.py docker-dev.conf boot.sh ./
COPY servicex/ ./servicex
COPY migrations migrations

RUN chmod +x boot.sh

#ENV FLASK_APP servicex

USER servicex

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
