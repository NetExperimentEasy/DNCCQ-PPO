from tile import TileCoder
import numpy as np
import random

class Qlearning:
    def __init__(self, tile: TileCoder, w: list, action_num, alpha, beta, epsilon, tilings, wfile=None) -> None:
        # w 每个动作维护一个权重矩阵，w = [w1, w2, w3]
        self.tile = tile
        self.w = w
        self.action_num = action_num
        self.alpha = alpha # learning rate of bellman function  0.01
        self.beta = beta # 折扣因子 0.9
        self.epsilon = epsilon # 0.7
        self.gamma = 0.1 / tilings

        if wfile:
            print("load weights from", wfile)
            self.load_w(wfile)
    
    def getPredQ(self, states: np.ndarray, action_index: int):
        tiles = self.tile[states]
        return self.w[action_index][tiles].sum()
    
    def getMaxPredQ(self, states: np.ndarray):
        qlist = []
        for action_index in range(self.action_num):
            qlist.append(self.getPredQ(states, action_index))
        max_q = max(qlist)
        max_q_index = qlist.index(max_q)
        return max_q, max_q_index

    def explore_action(self, states: np.ndarray):
        # get action_index
        _, max_q_index = self.getMaxPredQ(states)
        random_value = random.random()
        if random_value > self.epsilon:
            random_action = random.sample(list(range(self.action_num)), 1)
            return random_action[0]
        else:
            return max_q_index

    def save_w(self, filename):
        np.save(filename, self.w)
    
    def load_w(self, filename):
        self.w = np.load(filename)

    def updateQ(self, reward, prev_states: np.ndarray, action_index: int, next_states: np.ndarray):
        predQ = self.getPredQ(prev_states, action_index)
        next_maxQ, _ = self.getMaxPredQ(next_states)
        newQ = predQ + self.alpha * (reward + self.beta * next_maxQ - predQ)
        tiles = self.tile[prev_states]
        self.w[action_index][tiles] += self.gamma * (newQ - predQ)
