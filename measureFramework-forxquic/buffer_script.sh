while true;
do
    tc -s -d qdisc show dev $2 | sed -n 's/.*backlog \([^ ]*\).*/\1/p';
    if [ ${PIPESTATUS[0]} -ne "0" ];
    then
            break
    fi
    sleep $1;
done | ts '%.s;'
