from redis.client import Redis
import numpy as np
import logging
import sys
import json
import time
import argparse
import random

from rllib import rllib_predict_action, load_algo

# logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)

REDIS_HOST = '0.0.0.0'
REDIS_PORT = 6379
STATE_SCALE = np.array([1, 1, 512, 512, 512, 16384, 1, 1, 1, 1024, 1024, 1], dtype=np.float32) # 缩放状态
STATE_SLICE_FROM = 0  # 状态切片
STATE_SLICE_TO = 9


def test_predict_action(state):
    cwnd_rate = 2*random.random()+0.5
    pacing_rate = 2*random.random()+0.5
    return np.array([0, pacing_rate])

def rllib_predict_handler(algo):
    r = Redis(host=REDIS_HOST, port=REDIS_PORT)
    r2 = Redis(host=REDIS_HOST, port=REDIS_PORT)
    pub = r.pubsub()
    pub.psubscribe("rlccstate_*")  # 匹配订阅所有state_通道
    # pub.psubscribe()
    msg_stream = pub.listen()
    for msg in msg_stream:
        # print(f"msg {msg}")
        if msg["type"] == "pmessage":
            logging.debug(f"main_process: get msg {msg}")
            channel = str(msg["channel"], encoding="utf-8")
            logging.debug(f"get data from {channel}")
            if channel.startswith("rlccstate_"):
                # print(channel)
                cid = channel.replace("rlccstate_", "", 1) # 删除前缀，获取cid
                state_str = msg["data"].decode("utf-8").split(';')
                # print(f"----------{state_str}---------------")
                if len(state_str) < 7:
                    logging.debug(f"scid {cid} : {state_str}")
                    continue # 小于7的是其他消息，不是状态信息
                data_64 = np.array(state_str, dtype=np.float64)
                data =np.divide(data_64, STATE_SCALE, dtype=np.float32)
                input_state = data[STATE_SLICE_FROM:STATE_SLICE_TO] # 传回的状态中，有些状态不用于训练，用于计算奖励，切除多余状态
                
                logging.debug(f"go state {input_state}")
                
                # action = predict_action(input_state)
                
                # action =test_predict_action(input_state)
                # action_str = f"{action[0]},{action[1]}"
                
                action = rllib_predict_action(input_state, algo)
                action_str = f"{action}" # cwnd
                # action_str = f"0,{action[0]}" # pacing
                
                # rlcc需要的动作形式 "%f,%f"
                r2.publish(f"rlccaction_{cid}", action_str)
                
                logging.debug(f"worker action_{cid} : predict action {action}")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', dest='directory',
                        help='Path to the output directory.')
    args = parser.parse_args()
    
    if args.directory:
        algo = load_algo(args.directory)
    else:
        algo = load_algo()
    rllib_predict_handler(algo)