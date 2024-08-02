sudo python run_mininet.py test.conf

sudo python analyze.py -d test/02


/home/ubuntu/SATCCQFinal/measureFramewark/xquic/test_server -l d > /home/ubuntu/SATCCQFinal/measureFramewark/t_server.log

/home/ubuntu/SATCCQFinal/measureFramewark/xquic/test_client -l d -a 10.2.0.0 -p 8443 -s 304857600 -c R -T -f 1001 -R 10.123.0.123:6379 > /home/ubuntu/SATCCQFinal/measureFramewark/t_client.log

-l d -a 127.0.0.1 -p 8443 -s 304857600 -c R -T -f 1001 -R 127.0.0.1:6379

-l d -a 127.0.0.1 -p 8443 -s 304857600 -c R -T -f 1002 -R 127.0.0.1:6379