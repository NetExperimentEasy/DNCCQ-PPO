# DNCCQ-PPO:A Dynamic Network Congestion Control Algorithm Based on Deep Reinforcement
## Introduction 

The diversity of network forms and services poses challenges for TCP protocol from obtaining good performance,and the current XQUIC implementation of the QUIC protocol still adopts the heuristic mechanism in TCP in its congestion control approach, resulting in limited performance improvement. In recent years, congestion control based on reinforcement learning has become an effective alternative to traditional congestion control strategies, but the current algorithms are not optimized for dynamic network characteristics. In this paper, we propose a deep reinforcement learning-based dynamic network congestion control algorithm (Dynamic network congestion control for QUIC protocol based on PPO, DNCCQ-PPO) for this purpose. To cope with the challenge of the heterogeneity of the dynamic network training environment, we introduce a new sampling interaction mechanism, action space and reward function, and propose an asynchronous distributed parallel training scheme. In addition, a generalized reinforcement learning-based congestion control algorithm development framework supporting the XQUIC protocol is developed, and the performance of the DNCCQ-PPO algorithm is verified under the framework.

## Directory Introduction

> **node:** Every time you modify the sampling mechanism and action space, you need to recompile XQUIC. You can use static compilation or dynamic compilation.For static compilation, see static-build-xquic；For dynamic compilation, see xquic_forrlcc.

The rlcc-playground-mininet directory is used to start the training environment, which includes the network simulation module, Open Gym module, and visualization module. When developing and training congestion control algorithms, you can easily use this environment and use the implemented OpenAI Gym module to interact with the environment for training.

The train-code directory is the training module. You can use the rllib library or the Sample Factory library for training.

The xquic_forrlcc directory is the executor, namely XQUIC congestion control, which is implemented in the form of a patch in the C language implementation of the XQUIC protocol library.

The deploy directory  is a deployment module that can be used to test the effect of the trained model.

The measureFramework-forxquic directory is the measureframework modified by XQUIC, which starts  XQUIC flow.

The static-build-xquic directory is for statically compiling the xquic client.

## Environment Configuration

All use python3

### mininet

`git clone https://gitee.com/derekwin/mininet.git`

`./mininet/util/install.sh -a`

### streamlit

`pip install streamlit`

### redis-py & redis

`sudo apt install redis`

`pip install redis`

### gym & gym-rlcc

`pip install gym`

### Install the gym environment of this project in modify mode

`cd gym-rlcc`

`pip install -e .`

### install Sample Factory 

`pip install sample-factory`

### install rllib

`pip install ray==2.1.0`

`pip install -U "ray[rllib]"`

# QuickStart

1. How to start the training environment

```
cd rlcc-playground-mininet
sudo python train_env.py
```

2. How to train
   (use rllib)
```
cd train-code/rllib/singe
python train.py
```

   or use Sample Factory

```
cd train-code/rlcc-sf
python train_rlcc.py --env=rlcc --experiment=testexp --device=cpu
```

3. How to visualize in real-time

```
cd rlcc-playground-mininet
cd webui
streamlit run app.py
```
The visual interface is as follows:
![image](https://github.com/NetExperimentEasy/DNCCQ-PPO/blob/main/web.png)

4. How to deploy

```
cd deploy 
python deploy.py
```

