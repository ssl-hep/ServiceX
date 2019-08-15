# ServiceX REST Server

## Building Docker Image
```bash
docker build -t servicex_app .
```

## Running Docker 
```bash
docker run --name servicex-app --rm -p8000:5000 \
 --mount type=bind,source="$(pwd)"/sqlite,target=/sqlite \
 -e APP_CONFIG_FILE=/home/servicex/docker-dev.conf \
 servicex_app:latest
```
