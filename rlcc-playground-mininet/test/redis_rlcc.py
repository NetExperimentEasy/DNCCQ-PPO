#
# 一对多环境
#

from redis.client import Redis
import time
import numpy as np

r = Redis(host='0.0.0.0', port=6379)
rp = Redis(host='0.0.0.0', port=6379)


def start_env(rlcc_path_flag):
    # 直接开始流
    # start_server()
    # start_client()
    pass


def start_mininet_env(rlcc_path_flag):
    # 运行mininet的bash脚本
    # start_server()
    # start_client()
    pass


def cacu_reward(state_dict):
    # return state_dict[0]/state_dict[1]
    return 10


def a3c(state_dict, reward):
    cwnd = 1.0
    pacing_rate = 1.5
    return cwnd, pacing_rate


def main(start_env, cacu_reward, agent, channels: list):
    pub = r.pubsub()
    pub.subscribe(channels)
    msg_stream = pub.listen()
    for msg in msg_stream:
        if msg["type"] == "message":
            data_list = msg["data"].decode("utf-8").split(';')
            current_channel = str(msg["channel"], encoding="utf-8")

            if len(data_list) == 0:
                continue

            # data_list = msg["data"].decode("utf-8").split(';')
            # len_of_list = len(data_list)
            # # data = [state_list[0]/, ]
            # # print(f"gym : {data_list}")
            # if len_of_list > 5:
            #     # a = np.array(data_list, dtype=np.float32)
            #     # print(a[0], a[1], type(a[0]), type(a[1]))
            #     data = np.array(data_list, dtype=np.float32)

            #     # print(np.divide(data, self.scale))
            #     return data
            # elif len_of_list == 3:
            #     return np.array([0], dtype=np.float32)
            # # 只处理大于5的列表
            # else:
            #     continue

            if current_channel == "mininet":
                print(data_list)   # 长度为4 是 miniet发回来的链路信息
                if len(data_list) == 3:  # 长度3 是 流执行完的统计信息
                    # rp.publish('redis', f"{state_dict['rlcc_flag']}")       # reset jizhi
                    continue
            else:
                current_channel_id = current_channel.split(
                    '_')[-1]   # 此处的channel来自rlcc.c
                # start = time.time()

                if len(data_list) == 1:
                    print(current_channel_id, ":", data_list[0])
                    continue

                data = np.array(data_list, dtype=np.float32)

                # end = time.time()
                # time_list.append(end-start)
                # print(f"avg time : {np.mean(time_list)}")

                reward = cacu_reward(data)
                cwnd, pacing_rate = agent(data_list, reward)
                print(
                    f"rtt:{int(data_list[2])/1024},lost_interval:{data_list[6]},lostpkg:{data_list[7]},reward:{reward},cwnd:{cwnd},pacing_rate:{pacing_rate}")
                rp.publish(f'rlccaction_{current_channel_id}', f"{0.0},{5.0}")

        elif msg["type"] == "subscribe":
            print(str(msg["channel"], encoding="utf-8"), '订阅成功')
            current_channel = str(msg["channel"], encoding="utf-8")
            current_channel_id = current_channel.split('_')[-1]  # rlcc_flag


if __name__ == "__main__":
    linknums = 1
    # rlcc channel 测试简单映射
    channels = [f'rlccstate_{1001+i}' for i in range(linknums)]
    channels.append('mininet')  # mininet channel
    channels.append('rlccstate_4321')
    try:
        main(start_mininet_env, cacu_reward, a3c, channels=channels)
    except KeyboardInterrupt:
        pass
