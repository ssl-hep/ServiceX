# ServiceX-DID-finder

For a given RUCIO DID and client site finds optimal access paths.

Docker image is autobuilt here: 

output consist of:
* file in /data/request_name/did-finder/status.log
* if request successful paths to files will be listed in /data/request_name/did-finder/paths.json

To run it:

``` 
docker run \
-v /tmp/rucio.cfg:/opt/rucio/etc/rucio.cfg \
-it -d --name=rucio-client rucio/rucio-clients
```

After the container is started you can attach to it and start using the rucio commands:

```
docker exec -it rucio-clients /bin/bash rucio ping
```

An example command to run:
```
docker exec -it rucio-clients /bin/bash ./run.sh request_name mc15_13TeV:xAOD.root
```
