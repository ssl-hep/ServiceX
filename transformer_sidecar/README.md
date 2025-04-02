# ServiceX Sidecar Transformer

The ServiceX sidecar transformer runs alongside a science image to execute generated transformer 
code to read and transform data. The sidecar communicates with the science image through a shared
volume and a simple tcp/ip protocol.

The sidecar is implemented as a celery application that serves up the transform_file method. For
transformer development, this method can be called directly.

## The Watch Script
The science image has very dependencies so that in most cases we can use experiment provided
images with no modification. The only requirement is that the image can run bash and has the 
netcat (`nc`) command available. 

## Purpose
This script is used in the science container to watch for new transform requests in the form of 
JSON documents coming over the socket on port 8081. From the JSON document, it extracts the source 
input file URI, an output filename, and a file path to write the transformed file upon completion. 
It then signals to the sidecar that the transformation is done and writes the log files to the 
shared volume.

## Communication Steps
1. The script sends "GeT" over the socket to ask for a JSON document.
2. The script reads the JSON document and extracts the necessary information (download path, output file name, and output format).
3. The script executes the transformation script (specified as an argument) with the extracted information.
4. If the transformation is successful, the script sends "success." over the socket, otherwise it sends "failure."
5. The script listens for a confirmation message over the socket.

## Arguments
1. `$1`: The "language" used to execute the transform script. Usually "bash" or "python".
2. `$2`: The script to execute.
3. `$3`: The path to write the output files.

## Error Handling
The script handles errors by checking the exit status of the transformation script execution. If 
the exit status is not 0 (indicating a successful execution), the script sends "failure." over 
the socket.

## Logging
The script writes the log output of the transformation script execution to the file specified by 
the `$3` argument (usually `$path/abc.log`).


### Sidecar Container
The sidecar container is a celery application that serves up the transform_file method. 



# Testing
This service is designed for a couple of different testing and development scenarios. In both 
cases you need to manually launch the science image in your docker environment.

*Note:* - the science image won't start unless the sidecar is already running. The sidecar script
waits til it handshakes with the sidecar before it starts any processing.

```shell
docker run --rm -it -v ${PWD}/test_posix_vol:/servicex/output  \
            -v ${PWD}/test_posix_vol/generated_code:/generated --net=host  \
            sslhep/servicex_func_adl_uproot_transformer:uproot5 \
            /servicex/output/scripts/watch.sh python /generated/transform_single_file.py /servicex/output/ 
```

There is a new, final argument to the watch.sh script that is hostname to use to connect to the sidecar.
Inside the Kubernetes environment, this is just plain ol' `localhost` since the two containers are 
running inside the same pod. In the docker environment we have to get a little fancy. For Docker Desktop
on Mac, the hostname is `host.docker.internal`. I'm not sure what this is on windows @ketan96-m can you 
verify?


This mounts the test_posix_vol directory into the science image along with the generated_code 
directory. It launches the watch script with the python command and the local paths.

There is a stub version of this directory in this repo with some `.gitignore` settings to keep
it generic.


### 1. Testing the Celery application in the sidecar container.
There is a script in the [tests/sandbox](tests/sandbox/transform_file.py) that connects to the
celery application and sends a request to transform a file. This can be used to test the sidecar.

### 2. Testing the sidecar from the Command Line
You can run the transfomer.py script with the following arguments to transoform a single file:
```shell
python transformer_sidecar/transform.py --result-destination output-dir \\
      --output-dir /servicex/output \ 
      --path /servicex/output/sample_files/ggH125_ZZ4lep.4lep.root
```
Where the `--path` argument is the path to the file on your local drive you want to transform.