import ray
import torch
import torch.nn as nn
import sys
import gym
import gym_rlcc
from gym_rlcc.envs.rlcc_world_rllib import RlccEnvR
from ray.rllib.algorithms import ppo
from ray.tune.logger import pretty_print
from ray.tune.registry import register_env

from ray.rllib.models.torch.recurrent_net import RecurrentNetwork as TorchRNN
from ray.rllib.examples.models.rnn_model import TorchRNNModel
from ray.rllib.models import ModelCatalog

ray.shutdown()
# ray.init(ignore_reinit_error=True, _temp_dir="/media/seclee/18928D55928D37F0/raysesson")
ray.init(ignore_reinit_error=True)

class MultiEnv(gym.Env):
    def __init__(self, env_config):
        # pick actual env based on worker and env indexes
        worker_index = env_config.worker_index
        vector_index = env_config.vector_index  # 0,1,2,3,4,5,6,7,8,9
        print(worker_index, vector_index)
        # self.env = gym.make("my_env", config={"rlcc_flag":1001, "reward_function":reward})
        # self.env = RlccEnv(config={"rlcc_flag":1003+vector_index})
        self.env = RlccEnvR(config={"rlcc_flag":1001, "plan": 3})
        self.action_space = self.env.action_space
        self.observation_space = self.env.observation_space
    def reset(self):
        return self.env.reset()
    def step(self, action):
        return self.env.step(action)

register_env("multienv", lambda config: MultiEnv(config))

def load_algo(path:str = "/home/ubuntu/xquic_mininet/rllib/single/qifashi/checkpoint_000087"):
    # https://zhuanlan.zhihu.com/p/363045859
    # https://zhuanlan.zhihu.com/p/80169381
    algo = ppo.PPO(env="multienv", config={
        "simple_optimizer":True,  # bug 
        "framework":"torch",
        "disable_env_checking":True,
        # "num_envs_per_worker":10,
        "num_envs_per_worker":1,
        "num_workers": 0,  # dan jiedian  buyao kai
        "num_gpus": 0,
        # "batch_mode": "truncate_episodes",    # 会采样卡顿
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
    })

    algo.restore(path)
    return algo

class SatccAction():
    def __init__(self) -> None:
        self.up_change_EMA = 0.1
        self.up_stay_EMA = 0.1
        self.down_change_EMA = 0.1
        self.down_stay_EMA = 0.1
        self._action_to_direction = {
                0: -1,
                1: 0,
                2: 1,
            }
        
    def EMA(new, old, rate): # rate 4, 8
        return (1/rate)*new + ((rate-1)/rate)*old

    def step(self, action):
        action = self._action_to_direction[action]
        action_choosed = action
        cwnd_change = 0
        if action_choosed == 0:
            self.up_stay_EMA = self.EMA(5, self.up_stay_EMA, 4)
            self.up_change_EMA = self.EMA(5, self.up_change_EMA, 4)
            self.down_stay_EMA = self.EMA(5, self.down_stay_EMA, 4)
            self.down_change_EMA = self.EMA(5, self.down_change_EMA, 4)
            # print(f"-----{action},{self.up_stay_EMA}{self.up_change_EMA}{self.down_stay_EMA}{self.down_change_EMA} --- {cwnd_change}")
        elif action_choosed == 1:
            self.up_change_EMA = self.EMA(10, self.up_change_EMA, 16) #16->4
            self.up_stay_EMA = self.EMA(0.2, self.up_stay_EMA, 16)#16->4
            self.down_change_EMA = self.EMA(5, self.down_change_EMA, 4)
            cwnd_change = (int)(self.up_change_EMA/self.up_stay_EMA)+1
            # if cwnd_change>=10:
            #     print(f"-----{action},{self.up_stay_EMA}{self.up_change_EMA}{self.down_stay_EMA}{self.down_change_EMA} --- {cwnd_change}")
        elif action_choosed == -1:
            self.down_stay_EMA = self.EMA(0.2, self.down_stay_EMA, 16)#16->4
            self.down_change_EMA = self.EMA(10, self.down_change_EMA, 16)#16->4
            self.up_change_EMA = self.EMA(5, self.up_change_EMA, 4)
            cwnd_change = -(int)(self.down_change_EMA/self.down_stay_EMA)-1
            # if cwnd_change<=-10:
            #     print(f"-----{action},{self.up_stay_EMA}{self.up_change_EMA}{self.down_stay_EMA}{self.down_change_EMA} --- {cwnd_change}")

        return [cwnd_change]

action_to_direction = {
                0: -1,
                1: 0,
                2: 1,
            }

def rllib_predict_action_sa(observation, sa: SatccAction, algo):
    action = algo.compute_single_action(observation)
    return sa.step(action)

def rllib_predict_action(observation, algo):
    action = algo.compute_single_action(observation)
    action = action_to_direction[action]
    return action