./test_server -l e > /dev/null

./test_client -l e -a server_ip -p port -s file_size -c R -T -f flag -R redis:port > /dev/null