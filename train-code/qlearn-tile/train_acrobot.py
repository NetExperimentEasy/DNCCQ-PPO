import gymnasium as gym
from qlearning import Qlearning
from tile import TileCoder
import numpy as np

# number of tile spanning each dimension
tiles_per_dim = [10, 10, 10, 10, 10, 10]
# value limits of each dimension
# state1 state2 action
lims = [(-1, 1), (-1, 1), (-1, 1), (-1, 1), (-13, 13), (-29, 29)]
# number of tilings
tilings = 8

action_num = 3

tile = TileCoder(tiles_per_dim, lims, tilings)
w = []
for i in range(action_num):
    w.append(np.zeros(tile.n_tiles))

wfile = "acrobot.npy"

agent = Qlearning(tile=tile, w=w, action_num=action_num, alpha=0.05, beta=0.9, epsilon=0.8, tilings=tilings, wfile=wfile)

# env = gym.make("Acrobot-v1")
env = gym.make("Acrobot-v1", render_mode="human")

try:
    for i in range(1):
        print("train: episode:", i)
        obs, info = env.reset()
        done = False
        record_reward = []
        # env.render()
        while not done:
            action_index = agent.explore_action(states=obs)
            action = action_index
            newobs, reward, terminated, truncated, info = env.step(np.array(action))
            agent.updateQ(reward=reward, prev_states=obs, action_index=action_index, next_states=newobs)
            record_reward.append(reward)
            obs = newobs
            if terminated or truncated:
                print("avg reward:", np.mean(record_reward))
                done = True
except KeyboardInterrupt:
    agent.save_w(wfile)

agent.save_w(wfile)
env.close()