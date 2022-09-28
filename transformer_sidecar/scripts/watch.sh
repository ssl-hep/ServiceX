lang=$1
cmd=$2
path=$3
while true; do
    if [ -f $path/*.json ]; then
        for file in `ls $path/*.json`; do
            downloadlink=`grep -o '"file-path":\s.*[Aa-zZ0-9]*' $file |tr -d '"' | tr -d "," | awk '{print $2}'`;
            rm $file;
            command=`$lang $cmd $downloadlink $path`;
            echo $command;
            $command;
            done;
    else
        sleep 1
    fi
done
