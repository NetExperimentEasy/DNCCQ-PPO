from redis.client import Redis
import numpy as np
import logging
import sys
import json
import time
import random
from multiprocessing import Queue, Process

from rllib import rllib_predict_action_sa, SatccAction, load_algo

logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig(level=logging.INFO)

REDIS_HOST = '0.0.0.0'
REDIS_PORT = 6379
STATE_SCALE = np.array([1, 1, 512, 512, 512, 16384, 1, 1, 1, 1024, 1024, 1], dtype=np.float32) # 缩放状态
STATE_SLICE_FROM = 0  # 状态切片
STATE_SLICE_TO = 9


def random_load_balance_process_handler(in_queue: Queue, out_queue_list: list):
    logging.info("start random_load_balance process")
    while True:
        msg = in_queue.get(True)
        random_id = random.randint(0, len(out_queue_list)-1)
        logging.debug(f"load_blance_process: send msg {msg} to worker {random_id}")
        out_queue_list[random_id].put(msg) # 随机分配消息


def main_process_handler(in_queue: Queue):
    logging.info("start main process")
    # get cid from redis channel: flag
    r = Redis(host=REDIS_HOST, port=REDIS_PORT)
    pub = r.pubsub()
    pub.psubscribe("rlccstate_*")  # 匹配订阅所有state_通道
    # pub.psubscribe()
    msg_stream = pub.listen()
    for msg in msg_stream:
        if msg["type"] == "pmessage":
            logging.debug(f"main_process: get msg {msg}")
            in_queue.put(msg)  # 所有信息交给负载去处理


def test_predict_action(state):
    cwnd_rate = 2*random.random()+0.5
    pacing_rate = 2*random.random()+0.5
    return np.array([0, pacing_rate])

def worker_process_handler(worker_queue: Queue, worker_id: int, algo):
    r = Redis(host=REDIS_HOST, port=REDIS_PORT)
    logging.info(f"start worker {worker_id} process")
    while True:
        msg = worker_queue.get(True)
        channel = str(msg["channel"], encoding="utf-8")
        logging.debug(f"worker process {worker_id}: get data from {channel}")
        if channel.startswith("rlccstate_"):
            print(channel)
            cid = channel.replace("rlccstate_", "", 1) # 删除前缀，获取cid
            state_str = msg["data"].decode("utf-8").split(';')
            if len(state_str) < 7:
                logging.debug(f"worker {worker_id}, scid {cid} : {state_str}")
                continue # 小于7的是其他消息，不是状态信息
            data_64 = np.array(state_str, dtype=np.float64)
            data =np.divide(data_64, STATE_SCALE, dtype=np.float32)
            input_state = data[STATE_SLICE_FROM:STATE_SLICE_TO] # 传回的状态中，有些状态不用于训练，用于计算奖励，切除多余状态
            
            logging.debug(f"worker {worker_id} : go state {input_state}")
            
            # action = predict_action(input_state)
            
            # action =test_predict_action(input_state)
            # action_str = f"{action[0]},{action[1]}"
            
            print(f"current cid: {cid}, {SAset[cid]}")
            action = rllib_predict_action_sa(input_state, SAset[cid], algo)  # [pacing]
            action_str = f"{action[0]}" # cwnd
            # action_str = f"0,{action[0]}" # pacing
            
            # rlcc需要的动作形式 "%f,%f"
            r.publish(f"rlccaction_{cid}", action_str)
            
            logging.debug(f"worker {worker_id} action_{cid} : predict action {action}")
    

if __name__ == "__main__":

    map_c_2_rlcc_flag = {
        'c1': "1001",
        'c2': "1002",
        'c3': "1003",
        # 'c4': "1004",
        # 'c5': "1005",
        # 'c6': "1006",
        # 'c7': "1007",
        # 'c8': "1008",
        # 'c9': "1009",
        # 'c10': "1010",
    }
    
    SAset = {
        "1001" : SatccAction(),
        "1002" : SatccAction(),
        "1003" : SatccAction()
    }

    #####
    workers_num = 3
    
    process_list = []
    
    algo = load_algo()
    
    in_flag_queue = Queue()
    
    manager_process = Process(target=main_process_handler, args=(in_flag_queue,)) 
    process_list.append(manager_process)
    
    workers_queue_list = []
    
    for i in range(workers_num):
        worker_queue = Queue()
        worker_process = Process(target=worker_process_handler, args=(worker_queue, i, algo))
        workers_queue_list.append(worker_queue)
        process_list.append(worker_process)

    load_balance_prcess = Process(target=random_load_balance_process_handler, args=(in_flag_queue, workers_queue_list))
    process_list.append(load_balance_prcess)
    
    try:
        for p in process_list:
            p.start()
        for p in process_list:
            p.join()
    except KeyboardInterrupt:
        sys.exit(1)