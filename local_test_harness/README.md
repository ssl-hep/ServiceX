Local Test Harness for running the codegen and science image for the root file

### Step1. Configure the config.yml file
```yaml
    TestName: local test
    codegen: 
    port: 8005 
    query: '[{"treename": {"nominal": "modified"}, "filter_name": ["lbn"]}]' #provide the query as string

    science:
    rootfile: root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/user/mgeyik/e7/ee/user.mgeyik.30182995._000093.out.root
    outputfile: /generated/out.parquet
    outputformat: root-file
```

### Step2. Configure the .env for the compose file
```yaml
BASH_ENV='/servicex/.bashrc'
LOG_LEVEL=DEBUG
SCIENCE=sslhep/servicex_func_adl_uproot_transformer:uproot5 #science image
CODEGEN=sslhep/servicex_code_gen_raw_uproot:develop #codegen image
LOCAL_FOLDER=./temp1 #local folder where you want output files
PORT=8005 # port number for your codegen
```

### Step3. Setup the proxy and run
```shell
python test.py --proxy_image <name of proxy_image>
```

OR if you already have the proxy setup in your `/tmp`

```shell
python test.py
```
The default proxy image: `sslhep/x509-secrets:develop`