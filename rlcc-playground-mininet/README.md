# 说明
- mininet生成训练或者实验环境
- redis pub/sub作为中间消息通道
- streamlit订阅通道实现前端显示

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

## 以修改模式安装本项目的gym环境
cd gym-rlcc

pip install -e .

# usage
启动训练环境:

cd tmp

sudo python ../train.py


> 注意：tmp中需要xquic运行所需的密钥文件，github仓库未提供，可以按照xquic的说明使用openssl生成

启动web监控界面

cd webui

streamlit run app.py


> 注意上述操作只是启动了训练环境，训练需要运行使用gym环境的对应实现的训练代码