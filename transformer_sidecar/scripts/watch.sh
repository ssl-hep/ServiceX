#!/usr/bin/env bash
lang=$1
cmd=$2
path=$3

while true; do
    echo "Greetings from watch script"
    ls $path
    if [ -f $path/*.json ]; then
        for file in `ls $path/*.json`; do
            download_path=`grep -o '"downloadPath":\s.*[Aa-zZ0-9]*' $file |tr -d '"' |tr -d ',' | awk '{print $2}' `
            output_file=`grep -o '"safeOutputFileName":\s.*[Aa-zZ0-9]*' $file |tr -d '"' |tr -d ',' | awk '{print $2}' `

            echo "Attempting $download_path -> $output_file"
            transform_result=$($lang "$cmd" "$download_path" "$output_file" 2>&1 | tee $file.log )
            if [ $? == 0 ]; then
              echo "Success. skipping rest of input_files"
              touch $file.done
              rm $file
              break
            else
              echo "Hmm, got $?"
              touch $file.failed
              rm $file
            fi
          done;
    else
        sleep 1
    fi
done
