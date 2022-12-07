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
# 3. Path to the shared volume
#
lang=$1
cmd=$2
path=$3

while true; do
    echo "Greetings from watch script"
    ls $path
    if [ -f $path/*.json ]; then
        for file in `ls $path/*.json`; do
            download_path=`grep -o '"downloadPath": "[^\"]*"' $file |tr -d '"' |tr -d ',' | awk '{print $2}' `
            output_file=`grep -o '"safeOutputFileName": "[^\"]*"' $file |tr -d '"' |tr -d ',' | awk '{print $2}' `
            completed_file=`grep -o 'completedFileName": "[^\"]*"' $file |tr -d '"' |tr -d ',' | awk '{print $2}' `
            output_format=`grep -o '"result-format": "[^\"]*"' $file |tr -d '"' |tr -d ',' | awk '{print $2}' `

            echo "Attempting $download_path -> $output_file -> $completed_file with $output_format format"
            $lang "$cmd" "$download_path" "$output_file" "$output_format" 2>&1 | tee $file.log

            if [ "${PIPESTATUS[0]}" == 0 ]; then
              echo "Success. skipping rest of input_files"
              mv "$output_file" "$completed_file"
              touch "$file".done
              rm "$file"
            else
              echo "Operation failed for $download_path"
              touch "$file".failed
              rm "$file"
            fi
          done;
    else
        sleep 1
    fi
done
