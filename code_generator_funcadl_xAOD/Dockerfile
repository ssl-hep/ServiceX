FROM python:3.7

RUN useradd -ms /bin/bash servicex

WORKDIR /home/servicex
RUN mkdir ./servicex

COPY setup.py setup.py
COPY setup.cfg setup.cfg
COPY README.rst README.rst
RUN pip install -e .
RUN pip install gunicorn
RUN pip install git+https://github.com/iris-hep/ast-language.git@e6470deb68529e1885a4bc46f781e2fe43a6f4c8


COPY boot.sh ./
COPY app.conf ./
COPY servicex/ ./servicex
RUN chmod +x boot.sh

USER servicex
ENV APP_CONFIG_FILE "/home/servicex/app.conf"

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
