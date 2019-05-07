# ServiceX-DID-finder

For a given RUCIO DID and client site finds optimal access paths.

Docker image is autobuilt here: https://cloud.docker.com/u/sslhep/repository/docker/sslhep/servicex-did-finder

To run it: 

``` docker run -it -d --name=did-finder sslhep/servicex-did-finder ```

After the container is started you can attach to it and start using the rucio commands:

``` docker exec -it did-finder /bin/bash rucio ping ```

An example command to run:

``` docker exec -it did-finder /bin/bash ./run.sh request_name mc15_13TeV:xAOD.root```


## NOTE
* needs update of the README :) so it explains how to run it in k8s not docker. 
* needs rewrite to use REST API and not ES directly
