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

## Cleaning up old Transformation Queues
It's easy to accumulate a bunch of transformation queues during testing. It 
would be quite tedious to try to delete them via the management console. You
can install the rabbitmqadmin cli and then with some tricky scripting batch
delete queues:
```bash
./d.sh $(python  rabbitmqadmin -V / --port=30182 -u user -p leftfoot1 list queues | grep ".*-.*" | awk '{print $2}')
```