import ray
import torch
import torch.nn as nn
import sys
import gym
import gym_rlcc
from gym_rlcc.envs import RlccEnvMultiR
from ray.rllib.algorithms import ppo
from ray.tune.logger import pretty_print
from ray.tune.registry import register_env

from ray.rllib.models.torch.recurrent_net import RecurrentNetwork as TorchRNN
from ray.rllib.examples.models.rnn_model import TorchRNNModel
from ray.rllib.models import ModelCatalog

ray.init(ignore_reinit_error=True)


def reward(state):
    # print(state, state[0] , type(state[0]))
    # tuhroughput/(rtt/10000 * loss)
    # rtt,srtt max 8*10^8  throughput
    try:
        rewardvalue = state[0] / ((state[1]) * (state[5] + 1))
    except:
        print(f"state error : {state}")
        rewardvalue = state[0]
    return rewardvalue


# test = gym.make("gym_rlcc/rlcc-v0", config={"rlcc_flag":1001, "reward_function":reward})
# print(test)


class MultiEnv(gym.Env):
    def __init__(self, env_config):
        # pick actual env based on worker and env indexes
        worker_index = env_config.worker_index
        vector_index = env_config.vector_index  # 0,1,2,3,4,5,6,7,8,9
        # print(worker_index, vector_index)
        # self.env = gym.make("my_env", config={"rlcc_flag":1001, "reward_function":reward})
        self.env = RlccEnvMultiR(
            config={"rlcc_flag": 1001 + worker_index, "reward_function": reward}
        )
        self.action_space = self.env.action_space
        self.observation_space = self.env.observation_space

    def reset(self):
        return self.env.reset()

    def step(self, action):
        return self.env.step(action)


register_env("multienv", lambda config: MultiEnv(config))

# https://zhuanlan.zhihu.com/p/363045859
# https://zhuanlan.zhihu.com/p/80169381
algo = ppo.PPO(
    env="multienv",
    config={
        "framework": "torch",
        "disable_env_checking": True,
        # "num_envs_per_worker":20,
        "num_envs_per_worker": 1,
        "num_workers": 0,
        "batch_mode": "complete_episodes",
        "sample_async": True,
        "gamma": 0.99,
        "lr": 5e-5,
        "model": {
            "fcnet_hiddens": [512, 256],
            # "use_lstm": True,
            # "max_seq_len": 30,      # 训练的序列最长30步
            # "lstm_cell_size": 256,
            # "lstm_use_prev_action": True,   # 把上一步的动作也送进模型
            # "lstm_use_prev_reward": False,
        },
    },
)


# total 266万8千  667
# 125论 对应 50万步
algo.restore("/home/seclee/coding/rllibtest/rllib/ns6_200_checkpoint/checkpoint_000470")


import numpy as np

# testobs = torch.Tensor(np.array([400000,30000,30000, 1365,0,0,0])).unsqueeze(0)
# action = algo.compute_single_action(testobs)
# print(action)


## run game
rlcc_flag = 1001


def reward(state):
    # print(state, state[0] , type(state[0]))
    # tuhroughput/(rtt/10000 * loss)
    # rtt,srtt max 8*10^8  throughput
    try:
        rewardvalue = state[0] / ((state[1]) * (state[5] + 1))
    except:
        print(f"state error : {state}")
        rewardvalue = state[0]
    return rewardvalue


config = {
    "rlcc_flag": rlcc_flag,
    # "reward_function" : reward
}

env = gym.make("gym_rlcc/rlcc-v0", config=config)

for episode in range(1):
    done = False
    observation = env.reset()  # 初始化环境每次迭代
    print(f"start episode {episode}")
    while not done:
        action = algo.compute_single_action(observation)
        observation, reward, done, info = env.step(action)
        print(observation, reward, done)

env.close()
