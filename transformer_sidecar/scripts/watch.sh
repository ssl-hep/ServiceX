#!/usr/bin/env bash
# This script is used in the science container to watch for new transform
# requests in the form of JSON files. From this file, it extracts the source
# input file URI, a scratch output filename and a final file path to write
# the transformed file upon completion.
# Signal to the sidecar that we are done by writing a file with the extension
# .done to the directory. Also write the log files to the shared volume.
# Finally, if there is an error then write a .failure file to signal to the
# sidecar.
#
# Arguments:
# 1. A "language" used to execute the transform script. Usually bash or python
# 2. The script to execute
#
lang=$1
cmd=$2
path=$3

echo "connecting..."

coproc nc { nc localhost 8081; }

while [[ $nc_PID ]] ; do
  
    start=$(date +%s%N | cut -b1-13)
    echo "start: $start"
    # ask for a file to be processed
    printf >&${nc[1]} '%s\n' "GeT"
    read -r -u${nc[0]} line
    printf >&2 '%s\n' "Received request:" "$line"
    if [[ -z "$line" ]]; then
      echo "received an empty line"
      break
    fi
    download_path=$(echo $line | jq -r '.downloadPath')
    output_file=$(echo $line | jq -r '.safeOutputFileName')
    output_format=$(echo $line | jq -r '."result-format"')

    echo "Attempting $download_path -> $output_file with $output_format format"
    $lang "$cmd" "$download_path" "$output_file" "$output_format" 2>&1 | tee $path/abc.log

    # sending status back
    if [ "${PIPESTATUS[0]}" == 0 ]; then
      echo "Success. skipping rest of input_files"
      printf >&${nc[1]} '%s\n' "success."
    else
      echo "Operation failed for $download_path"
      printf >&${nc[1]} '%s\n' "failure."
    fi
    
    # get confirmation.
    read -r -u${nc[0]} line
    printf >&2 '%s\n' "Reply:" "$line"
    
    end=$(date +%s%N | cut -b1-13)
    echo "Elapsed Time: $(($end-$start)) ms"
done


# {
#   "request-id": "decfc25d-4b19-47c9-a742-6259450142c7", 
#   "file-id": null, 
#   "columns": null, 
#   "paths": "root://lcg-lrz-rootd.grid.lrz.de:1094/pnfs/lrz-muenchen.de/data/atlas/dq2/atlaslocalgroupdisk/rucio/user/ivukotic/53/26/00284890-DCDB-E511-9F9D-02163E012FCA.root,root://eosatlas.cern.ch:1094//eos/atlas/atlasscratchdisk/rucio/user/ivukotic/53/26/00284890-DCDB-E511-9F9D-02163E012FCA.root", 
#   "tree-name": null, 
#   "service-endpoint": "http://servicex-release-testing-2-servicex-app:8000/servicex/internal/transformation/decfc25d-4b19-47c9-a742-6259450142c7", 
#   "chunk-size": "1000", 
#   "result-destination": "object-store", 
#   "result-format": "parquet", 
#   "downloadPath": "root://xcache.af.uchicago.edu:1094//root://lcg-lrz-rootd.grid.lrz.de:1094/pnfs/lrz-muenchen.de/data/atlas/dq2/atlaslocalgroupdisk/rucio/user/ivukotic/53/26/00284890-DCDB-E511-9F9D-02163E012FCA.root", 
#   "safeOutputFileName": "/servicex/output/decfc25d-4b19-47c9-a742-6259450142c7/scratch/root:::xcache.af.uchicago.edu:1094::root:::lcg-lrz-rootd.grid.lrz.de:1094:pnfs:lrz-muenchen.de:data:atlas:dq2:atlaslocalgroupdisk:rucio:user:ivukotic:53:26:00284890-DCDB-E511-9F9D-02163E012FCA.root.parquet", 
#   "completedFileName": "/servicex/output/decfc25d-4b19-47c9-a742-6259450142c7/root:::xcache.af.uchicago.edu:1094::root:::lcg-lrz-rootd.grid.lrz.de:1094:pnfs:lrz-muenchen.de:data:atlas:dq2:atlaslocalgroupdisk:rucio:user:ivukotic:53:26:00284890-DCDB-E511-9F9D-02163E012FCA.root.parquet"
# }
