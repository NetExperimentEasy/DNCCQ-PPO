import streamlit as st
from redis.client import Redis
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import time
from collections import namedtuple

Data = namedtuple('Data', ['throughput', 'delivered_rate', 'rtt', 'loss'])


class DataSource:
    def __init__(self, channels: list, redis_ip='0.0.0.0', redis_port=6379):
        self.redis_ip = redis_ip
        self.redis_port = redis_port

        self.channels = channels
        self.datas = dict(zip(channels, [Data([], [], [], [])
                          for _ in range(len(channels))]))
        self.states = dict(zip(channels, [{} for _ in range(len(channels))]))

        self.pool = ThreadPoolExecutor(max_workers=len(channels))

    def parser_redis_data(self, channel: list):
        r = Redis(host=self.redis_ip, port=self.redis_port)
        pub = r.pubsub()
        channel.append('mininet')
        pub.subscribe(channel)
        msg_stream = pub.listen()
        for msg in msg_stream:
            if msg["type"] == "message":
                data_list = msg["data"].decode("utf-8").split(';')
                current_channel = str(msg["channel"], encoding="utf-8")

                if len(data_list) == 0:
                    continue
                # print(data_list)
                if current_channel == "mininet":
                    if len(data_list) == 4:  # 长度为4 是 miniet发回来的链路信息, 流启动
                        if f"rlccstate_{data_list[0].split(':')[-1]}" == channel[0]:
                            self.states[channel[0]] = {
                                "bandwidth": data_list[1].split(':')[-1],
                                "rtt": data_list[2].split(':')[-1],
                                "loss": data_list[3].split(':')[-1]
                            }

                    if len(data_list) == 3:  # 长度3 是 流执行完的统计信息，流结束
                        continue
                else:
                    # np.finfo(np.float32).max,  # cwnd
                    # np.finfo(np.float32).max,  # pacing_rate
                    # np.finfo(np.float32).max,  # rtt
                    # np.finfo(np.float32).max,  # min_rtt
                    # np.finfo(np.float32).max,  # srtt
                    # np.finfo(np.float32).max,  # inflight
                    # np.finfo(np.float32).max,  # lost_interval 采样周期内的丢包数
                    # np.finfo(np.float32).max,  # lost_pkts sampler周期内约rtt的丢包
                    # np.finfo(np.float32).max,  # is_app_limited
                    # np.finfo(np.float32).max,  # delivery_rate
                    # np.finfo(np.float32).max,  # throughput | sending rate
                    # np.finfo(np.float32).max,  # sended_interval
                    if len(data_list) == 1:
                        # init 启动确认相关的信息, 重置数据
                        if current_channel == channel[0]:
                            self.datas[channel[0]] = Data([], [], [], [])

                    if len(data_list) > 5:
                        # self.datas['rlccstate_1001'] = \
                        # self.datas['rlccstate_1001'].append(
                        # pd.DataFrame({
                        #     # 'time': [time.time()],
                        #     'throughput': [np.float32(data_list[-2])/1024/1024],
                        #     'rtt': [np.float32(data_list[4])/1024/1024],
                        #     'loss': [np.float32(data_list[-5])]
                        # }, dtype=np.float32), ignore_index=True)
                        if current_channel == channel[0]:  # 每个线程[目标channel，mininet]
                            self.datas[channel[0]].throughput.append(
                                np.float32(data_list[-2])*8/1024/1024),
                            self.datas[channel[0]].delivered_rate.append(
                                np.float32(data_list[-3])*8/1024/1024),
                            self.datas[channel[0]].rtt.append(
                                np.float32(data_list[2])/1024),
                            self.datas[channel[0]].loss.append(
                                np.float32(data_list[-6])),

            elif msg["type"] == "subscribe":
                # print(str(msg["channel"], decode="utf-8"), '订阅成功')
                current_channel = str(msg["channel"], encoding="utf-8")

    def run_collector(self):
        for channel in self.channels:
            self.pool.submit(self.parser_redis_data, [channel])


if __name__ == "__main__":
    channels_list = [
        # "rlccstate_1001",
        "rlccstate_1002",
        # "rlccstate_1003",
        # "rlccstate_1004",
        # "rlccstate_1005",
        # "rlccstate_1006",
        # "rlccstate_1007",
        # "rlccstate_1008",
        # "rlccstate_1009",
        # "rlccstate_1010",
    ]
    datasource = DataSource(channels=channels_list, redis_ip="127.0.0.1", redis_port=6379)
    datasource.run_collector()
    showarea = {}
    st.set_page_config(layout="wide")
    for channel in channels_list:
        title = st.title(channel)
        col1, col2 = st.columns(2)
        with col1:
            em1 = st.empty()
            txt1 = st.text('')
        with col2:
            em2 = st.empty()
            txt2 = st.text('')
        col3, col4 = st.columns(2)
        with col3:
            em3 = st.empty()
            txt3 = st.text('')
        with col4:
            em4 = st.empty()
            txt4 = st.text('')
        showarea[channel] = [title, st.empty().text(''), em1, txt1, em2, txt2, em3, txt3, em4, txt4]
    while True:
        # print(len(datasource.datas['rlccstate_1001'].throughput))
        for channel in channels_list:
            # showarea[channel][0].text(channel)
            state = datasource.states[channel]
            if len(state) > 0:
                showarea[channel][1].text(
                    f"{state['bandwidth']}, {state['rtt']}, {state['loss']}")
            # Throughput
            showarea[channel][2].line_chart(
                datasource.datas[channel].throughput)
            showarea[channel][3].text(
                f"Throughput:{datasource.datas[channel].throughput[-1] if len(datasource.datas[channel].throughput) > 1 else ''}Mbps")
            # delivered_rate
            showarea[channel][4].line_chart(
                datasource.datas[channel].delivered_rate)
            showarea[channel][5].text(
                f"Delivered_rate:{datasource.datas[channel].delivered_rate[-1] if len(datasource.datas[channel].delivered_rate) > 1 else ''}Mbps")
            # RTT
            showarea[channel][6].line_chart(
                datasource.datas[channel].rtt[10:])
            showarea[channel][7].text(
                f"RTT:{datasource.datas[channel].rtt[-1] if len(datasource.datas[channel].rtt) > 1 else ''}ms")
            # loss in this sample interval
            showarea[channel][8].line_chart(
                datasource.datas[channel].loss)
            showarea[channel][9].text(
                f"Loss:{datasource.datas[channel].loss[-1] if len(datasource.datas[channel].loss) > 1 else ''}")

        time.sleep(1)
