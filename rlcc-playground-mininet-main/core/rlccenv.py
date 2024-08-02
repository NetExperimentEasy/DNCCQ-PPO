
import time
from .topo import multiTopo
from mininet.net import Mininet
from mininet.node import Node
from mininet.cli import CLI
import random
from redis.client import Redis
from .utils import cmd_at, traffic_shaping, xquic_command, generate_xquic_tls,\
    tcpdump_command, kill_pid_by_name
from mininet.util import info
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class PcapAt:
    host: str
    aim_hosts: list
    aim_ports: list


class RlccMininet:
    def __init__(self,
                 map_c_2_rlcc_flag: dict,
                 XQUIC_PATH: str,
                 Topo=multiTopo,
                 root_ip='10.0.0.123/32',
                 root_routes=['10.0.0.0/24'],
                 redis_ip='0.0.0.0',
                 redis_port=6379,
                 ) -> None:
        """
        map_c_2_rlcc_flag : dict 'clientname' : 'rlccflag'
        Topo : Train Topo
        root_ip : link to root interface
        root_route : route of root interface
        """
        self.map_c_2_rlcc_flag = map_c_2_rlcc_flag
        self.map_rlcc_flag_2_c = dict(
            zip(map_c_2_rlcc_flag.values(), map_c_2_rlcc_flag.keys()))
        self.timestamp = dict(zip(map_c_2_rlcc_flag.values(), [
                              time.time() for _ in map_c_2_rlcc_flag.keys()]))
        self.Xquic_path = XQUIC_PATH

        # init lock
        self.LOCK = None
        self.init_lock()

        self.root_ip = root_ip
        self.root_routes = root_routes

        # init Redis
        info("\n*** Init Redis \n")
        self.r = Redis(host=redis_ip, port=redis_port)
        self.rp = Redis(host=redis_ip, port=redis_port)
        self.pub = self.r.pubsub()
        self.pub.subscribe('redis')

        # init Topo
        info("\n*** Init Mininet Topo \n")
        topo = Topo(len(self.map_c_2_rlcc_flag.keys()))
        self.network = Mininet(topo, waitConnected=True)

        # connect to local interface
        info(f"\n*** Connect to local root note :{self.root_ip} \n")
        self.connect_to_rootNS()

        info("\n*** Hosts addresses:\n")
        for host in self.network.hosts[1:]:
            info(host.name, host.IP(), '\n')

        for item in self.network.switches:
            info(f"*** Init bottleneck property: {item.name}\n")
            self.set_fix_env(item, ifpublish=False)

        self.pool = ThreadPoolExecutor(max_workers=len(self.network.hosts))

    def init_lock(self):
        """
        lock 用来限制c上开的流的个数, 有些环境会重复启动
        """
        self.LOCK = dict(zip(self.map_c_2_rlcc_flag.values(), [
            0]*len(self.map_c_2_rlcc_flag.values())))

    def set_lock(self, rlcc_flag):
        self.LOCK[rlcc_flag] = 1

    def del_lock(self, rlcc_flag):
        self.LOCK[rlcc_flag] = 0

    def connect_to_rootNS(self):
        """Connect hosts to root namespace via switch. Starts network.
        network: Mininet() network object
        switch: switch to connect to root namespace
        ip: IP address for root namespace node
        routes: host networks to route to"""
        sw1 = self.network['sw1']
        # Create a node in root namespace and link to switch
        root = Node('root', inNamespace=False)
        intf = self.network.addLink(root, sw1).intf1
        root.setIP(self.root_ip, intf=intf)
        # Start network that now includes link to root namespace
        self.network.start()
        # Add routes from root ns to hosts
        for route in self.root_routes:
            root.cmd('route add -net ' + route + ' dev ' + str(intf))

    def set_random_env(self, switch, rlcc_flag=None, ifpublish=True):
        """
        set random env to link
        """
        e1 = random.randrange(0, 10)
        e2 = random.randrange(0, 10)
        rate = f'{random.randrange(5,100)}Mbit'
        buffer = f'{random.randrange(1400,2000)}b'
        # delay = f'{random.randrange(5,400)}ms' if e > 7 else \
        #     f'{random.randrange(5,100)}ms'
        # loss = f'{random.randrange(0,200)/10}%' if e > 7 else '0%'
        delay = f'{random.randrange(5,50)}ms'
        loss =  '0%'

        cmd_at(switch, traffic_shaping, ifbackend=False,
               mode='both',
               interface=switch.intfs[2].name,
               add=False,
               rate=rate,
               buffer=buffer,
               delay=delay,
               loss=loss)
        if ifpublish:
            assert rlcc_flag, "you need set valid rlccflag"
            self.rp.publish(
                'mininet', f"rlcc_flag:{rlcc_flag};bandwidth:{rate};"
                + f"rtt:{delay};loss:{loss}")

    def set_fix_env(self, switch, rlcc_flag=None, ifpublish=True,
                    rate='20Mbit',
                    buffer='1600b',
                    delay='200ms',
                    loss='0%'
                    ):
        cmd_at(switch, traffic_shaping, ifbackend=False,
               mode='both',
               interface=switch.intfs[2].name,
               add=False,
               rate=rate,
               buffer=buffer,
               delay=delay,
               loss=loss)
        if ifpublish:
            assert rlcc_flag, "you need set valid rlccflag"
            self.rp.publish(
                'mininet', f"rlcc_flag:{rlcc_flag};bandwidth:{rate};"
                + f"rtt:{delay};loss:{loss}")

    def cli(self):
        try:
            CLI(self.network)
        except:
            self.stop()

    def stop(self):
        self.network.stop()

    def run_client(self, host, ifdellock=True):
        start = time.time()
        id = int(host.name[1:])
        rlcc_flag = self.map_c_2_rlcc_flag[host.name]
        aim_server = self.network.get(f'ser{id}')
        cmd_at(host, xquic_command, ifprint=False,
               type="client",
               XQUIC_PATH=self.Xquic_path,
               server_ip=aim_server.IP(),
               rlcc_flag=rlcc_flag)
        end = time.time()
        if ifdellock:  # 测试环境中，不去🔓，只跑一次测试
            self.del_lock(rlcc_flag=rlcc_flag)
        running_time = end-start
        # 运行结束，这里返回给mininet done信息， redis给mininet返回重置该路实验的信号
        self.rp.publish(
            'mininet', f"rlcc_flag:{rlcc_flag};state:done;time:"
            + f"{running_time:.2f} sec")

    def run_train(self, mode):
        """
        mode : random : random env ,
                fix   :    fix env
        """
        info("\n ---RLCC experiment start---\n")

        info("Generate key\n")
        c1 = self.network.get("c1")
        cmd_at(c1, generate_xquic_tls)
        info("Generate ok\n")

        info("Start xquic server\n")
        for item in [s for s in self.network.hosts if
                     s.name.startswith('ser')]:
            cmd_at(item, xquic_command, ifbackend=True,
                   type='server',
                   XQUIC_PATH=self.Xquic_path)
        info("Start ok\n")

        msg_stream = self.pub.listen()

        try:
            for msg in msg_stream:
                if msg["type"] == "message":
                    # notice: 第一次订阅的时候，此处会收到 mininet频道订阅的回显消息
                    # 通过rlcc_flag交互
                    rlcc_flag = str(msg["data"], encoding="utf-8")
                    if rlcc_flag == "mininet":
                        # print("订阅channel : mininet") #
                        continue
                    if rlcc_flag.endswith("stop"): # 超时主动关闭流
                        rlcc_flag = rlcc_flag[:-4]
                        host_name = self.map_rlcc_flag_2_c[rlcc_flag]
                        host = self.network.get(host_name)
                        self.del_lock(rlcc_flag)
                        print(f"{rlcc_flag}:"
                            + "steps are too long, restart the flow")
                        kill_pid_by_name("test_client")
                        
                    if self.LOCK[rlcc_flag] == 0:      # 收到重复消息时，由于🔓，不会重启流引发错误
                        host_name = self.map_rlcc_flag_2_c[rlcc_flag]
                        host = self.network.get(host_name)
                        switch = self.network.get(f"sw{host_name[1:]}")
                        if mode == "random":
                            self.set_random_env(
                                switch, rlcc_flag=rlcc_flag)      # 随机重置环境
                        if mode == "fix":
                            # 固定环境测试
                            self.set_fix_env(switch, rlcc_flag=rlcc_flag)
                        print(
                            f"{rlcc_flag}:"
                            + f"{time.time()-self.timestamp[rlcc_flag]}")
                        self.timestamp[rlcc_flag] = time.time()

                        self.pool.submit(self.run_client, host,
                                         self.map_c_2_rlcc_flag)    # 开始流
                        self.set_lock(rlcc_flag=rlcc_flag)
                        print(
                            f"::start rlcc_flag: {rlcc_flag} on : {host_name}")

        except KeyboardInterrupt:
            self.rp.publish(
                'mininet', f"rlcc_flag:{self.map_c_2_rlcc_flag[host.name]};"
                + "state:stop_by_mininet")
            self.pool.shutdown()
            self.stop()

        self.stop()

    def run_exp(self, mode, pcaplist: list[PcapAt], filename=None):
        """
        mode : random : random env ,
                fix   :    fix env ,
        pcapat : list of client name

        """
        info("\n ---RLCC experiment start---\n")

        info("Generate key\n")
        c1 = self.network.get("c1")
        cmd_at(c1, generate_xquic_tls)
        info("Generate ok\n")

        info("Start xquic server\n")
        for item in [s for s in self.network.hosts if
                     s.name.startswith('ser')]:
            cmd_at(item, xquic_command, ifbackend=True,
                   type='server',
                   XQUIC_PATH=self.Xquic_path)
        info("Start ok\n")

        for clitem in pcaplist:
            host = self.network.get(clitem.host)
            aim_ips = [self.network.get(j).IP() for j in clitem.aim_hosts]
            cmd_at(host, tcpdump_command, ifbackend=True,
                   aim_ips=aim_ips,
                   ports=clitem.aim_ports)

        msg_stream = self.pub.listen()

        try:
            for msg in msg_stream:
                if msg["type"] == "message":
                    # notice: 第一次订阅的时候，此处会收到 mininet频道订阅的回显消息
                    # 通过rlcc_flag交互
                    rlcc_flag = str(msg["data"], encoding="utf-8")
                    if rlcc_flag == "mininet":
                        # print("订阅channel : mininet") #
                        continue
                    if rlcc_flag.endswith("stop"): # 超时主动关闭流
                        rlcc_flag = rlcc_flag[:-4]
                        host_name = self.map_rlcc_flag_2_c[rlcc_flag]
                        host = self.network.get(host_name)
                        self.del_lock(rlcc_flag)
                        print(f"{rlcc_flag}:"
                            + "steps are too long, restart the flow")
                        kill_pid_by_name("test_client")

                    if self.LOCK[rlcc_flag] == 0:      # 收到重复消息时，由于🔓，不会重启流引发错误
                        host_name = self.map_rlcc_flag_2_c[rlcc_flag]
                        host = self.network.get(host_name)
                        switch = self.network.get(f"sw{host_name[1:]}")
                        if mode == "random":
                            self.set_random_env(
                                switch, rlcc_flag=rlcc_flag)      # 随机重置环境
                        if mode == "fix":
                            # 固定环境测试
                            self.set_fix_env(switch, rlcc_flag=rlcc_flag)
                        print(
                            f"{rlcc_flag}:"
                            + f"{time.time()-self.timestamp[rlcc_flag]}")
                        self.timestamp[rlcc_flag] = time.time()

                        self.pool.submit(self.run_client, host,
                                         self.map_c_2_rlcc_flag,
                                         False)    # 开始流, 测试环境不去🔓，所以只会启动一次流
                        self.set_lock(rlcc_flag=rlcc_flag)
                        print(
                            f"::start rlcc_flag: {rlcc_flag} on : {host_name}")

        except KeyboardInterrupt:
            self.rp.publish(
                'mininet', f"rlcc_flag:{self.map_c_2_rlcc_flag[host.name]};"
                + "state:stop_by_mininet")
            self.pool.shutdown()
            # 退出pcap
            for clitem in pcaplist:
                host = self.network.get(clitem.host)
                kill_pid_by_name("tcpdump")
            self.stop()

        # 退出pcap
        for clitem in pcaplist:
            host = self.network.get(clitem.host)
            kill_pid_by_name("tcpdump")

        self.stop()
