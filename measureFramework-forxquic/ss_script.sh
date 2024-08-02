while true;
do
    ss -tin | sed -n -e 's/.* cwnd:\([0-9]*\).* bbr:(\([^)]*\)).*/\1;;\2/p' -e 's/.* cwnd:\([0-9]*\).* ssthresh:\([0-9]*\).*/\1;\2;/p';
    sleep $1;
done | ts '%.s;'
