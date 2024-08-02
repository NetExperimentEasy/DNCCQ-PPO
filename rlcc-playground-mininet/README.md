# introduce

- mininet generates training or experimental environment
- redis as a message middleware
- Streamlit subscribes to the channel to achieve front-end display

# dependency

### mininet安装
https://zhuanlan.zhihu.com/p/576832894

### streamlit
pip install streamlit

> if protobuf got err
<!-- pip install --upgrade protobuf -->
pip install protobuf==3.20.1


### redis-py & redis
sudo apt install redis

pip install redis

### gym & gym-rlcc
pip install gym

## Install the gym environment of this project in modify mode
cd gym-rlcc

pip install -e .

# usage
Start the training environment:

sudo python train_env.py

Start the web monitoring interface

cd webui

streamlit run app.py


> Note that the above operation only starts the training environment. Training requires running the corresponding training code implemented using the gym environment.

