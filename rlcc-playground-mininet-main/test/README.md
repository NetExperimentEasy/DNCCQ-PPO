redis_rlcc.py

用于伪装智能体，测试与test_client的交互性。

python redis_rlcc.py 

test_server -l e
test_client -l e -a 127.0.0.1 -p 8443 -s 1024000 -c R -T -f 4321 -R 127.0.0.1:6379


test_gym.ipynb

用于测试gym环境的可用性