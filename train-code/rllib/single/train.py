import ray
import torch
import torch.nn as nn
import sys
import gym
import gym_rlcc
from gym_rlcc.envs import RlccEnvR
from ray.rllib.algorithms import ppo
from ray.tune.logger import pretty_print
from ray.tune.registry import register_env

from ray.rllib.models.torch.recurrent_net import RecurrentNetwork as TorchRNN
from ray.rllib.examples.models.rnn_model import TorchRNNModel
from ray.rllib.models import ModelCatalog

ray.init(ignore_reinit_error=True)

# test = gym.make("gym_rlcc/rlcc-v0", config={"rlcc_flag":1001, "reward_function":reward})
# print(test)


class MultiEnv(gym.Env):
    def __init__(self, env_config):
        # pick actual env based on worker and env indexes
        worker_index = env_config.worker_index
        vector_index = env_config.vector_index  # 0,1,2,3,4,5,6,7,8,9
        print(worker_index, vector_index)
        # self.env = gym.make("my_env", config={"rlcc_flag":1001, "reward_function":reward})
        self.env = RlccEnvR(config={"rlcc_flag": 1001 + worker_index, "plan": 1, "maxsteps":1800})
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
        # "num_envs_per_worker":10,
        "num_envs_per_worker": 1,
        "num_workers": 0,
        "num_gpus": 0,
        # "batch_mode": "truncate_episodes",    # 会采样卡顿
        "batch_mode": "complete_episodes",
        # "sample_async": True,
        "sample_async": False,  # 线性动作开始训练会很慢，一次长度>600s，导致async超时
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

algo.restore("/home/seclee/coding/train-rlcc/rllib/single/checkpoint_ppo_1/checkpoint_000050")

stop_iter = 1000

iter = 0
while iter < stop_iter:
    try:
        if iter % 10 == 0:
            print(f"\n save at {iter} \n")
            algo.save("./checkpoint_ppo_2")
        print(algo.train())
        iter += 1
        # result = algo.train()
        # print(pretty_print(result))
        # if (
        #         result["timesteps_total"] >= stop_timesteps
        #     ):
        #         break
    except KeyboardInterrupt:
        algo.stop()
        algo.save("./checkpoint_ppo_3")
        sys.exit(1)

algo.stop()
