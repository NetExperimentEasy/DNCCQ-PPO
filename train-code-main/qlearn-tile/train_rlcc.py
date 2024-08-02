import gymnasium as gym
import gym_rlcc
from gym_rlcc.envs import RlccEnvQ
from qlearning import Qlearning
from tile import TileCoder
import numpy as np

# number of tile spanning each dimension
tiles_per_dim = [16, 16]
# value limits of each dimension
# state1 state2 action
lims = [(0, 2048), (0, 500)]   # 104857600
# number of tilings
tilings = 32

# owl
action_num = 7
# # 反比例
# action_num = 3

tile = TileCoder(tiles_per_dim, lims, tilings)
w = []
for i in range(action_num):
    w.append(np.zeros(tile.n_tiles))

wfile = "rlcc.npy"
# , wfile=wfile
agent = Qlearning(tile=tile, w=w, action_num=action_num, alpha=0.05, beta=0.9, epsilon=0.8, tilings=tilings)


rlcc_flag = 1001
# owl
# config = {
#     "rlcc_flag" : rlcc_flag,
#     "plan" :2,
#     "maxsteps":1800,
# }
# 反比例
config = {
    "rlcc_flag" : rlcc_flag,
    "plan" :2,
    "maxsteps":900,
}

# env = gym.make("gym_rlcc/rlcc-v0-q", config=config)
env = RlccEnvQ(config=config)

big_th = 0
big_delay = 0

try:
    for i in range(500):
        print("train: episode:", i)
        obs, info = env.reset()
        done = False
        record_reward = []
        # env.render()
        delay = (obs[2]-obs[3])
        th = obs[-2]/128
        if delay > 500:
            delay = 500
        if th > 2048:
            th = 2048
        states = np.array([th, delay])
        while not done:
            # print(states)
            action_index = agent.explore_action(states=states)
            action = action_index
            # print(action)
            if delay>big_delay:
                big_delay = delay
                print("---big---", big_th, big_delay)
            if th>big_th:
                big_th = th
                print("---big---", big_th, big_delay)
            print("now :", th, delay, end='\r')

            newobs, reward, terminated, truncated, info = env.step(np.array(action))
            delay = (newobs[2]-newobs[3])
            th = newobs[-2]/128
            if delay > 500:
                delay = 500
            if th > 2048:
                th = 2048
            next_states = np.array([th, delay])
            agent.updateQ(reward=reward, prev_states=states, action_index=action_index, next_states=next_states)
            record_reward.append(reward)
            states = next_states
            if terminated or truncated:
                print("avg reward:", np.mean(record_reward))
                done = True
except KeyboardInterrupt:
    print("---big---", big_th, big_delay)
    agent.save_w(wfile)

print("---big---", big_th, big_delay)
agent.save_w(wfile)
env.close()