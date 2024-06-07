FROM python:3.11 AS builder

COPY scripts/*.py  resources/start.sh requirements.txt ./
RUN mkdir servicex_storage
COPY servicex_storage/* ./servicex_storage/

RUN python3 -m pip install -r requirements.txt

RUN chmod +x start.sh

ENTRYPOINT ["./start.sh"]
