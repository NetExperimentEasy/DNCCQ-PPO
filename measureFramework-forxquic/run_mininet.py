from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.clean import cleanup

from helper.util import print_error, print_warning, print_success, colorize, print_line
from helper.util import get_git_revision_hash, get_host_version, get_available_algorithms, check_tools, check_tool
from helper.util import sleep_progress_bar
from helper.util import compress_file
from helper import BUFFER_FILE_EXTENSION, FLOW_FILE_EXTENSION, COMPRESSION_METHODS, TEXT_WIDTH

import os
import sys
import subprocess
import time
import argparse
import re
import glob

from mininet.node import Node


MAX_HOST_NUMBER = 256**2


class DumbbellTopo(Topo):
    "Three switchs connected to n senders and receivers."

    def build(self, n=2):
        switch1 = self.addSwitch('s1')
        switch2 = self.addSwitch('s2')
        switch3 = self.addSwitch('s3')

        self.addLink(switch1, switch2)
        self.addLink(switch2, switch3)

        for h in range(n):
            host = self.addHost('h%s' % h, cpu=.5 / n)
            self.addLink(host, switch1)
            # self.addLink(host, s123)
            receiver = self.addHost('r%s' % h, cpu=.5 / n)
            self.addLink(receiver, switch3)

            sri = self.addSwitch(f'sr{h}')
            self.addLink(host, sri)


def parseConfigFile(file):
    cc_algorithms = get_available_algorithms()
    print(cc_algorithms, type(cc_algorithms))
    cc_algorithms += ' xquic' # add xquic

    unknown_alorithms = []
    number_of_hosts = 0
    output = []
    f = open(file)
    for line in f:
        line = line.replace('\n', '').strip()

        if len(line) > 1:
            if line[0] == '#':
                continue

        split = line.split(',')
        if split[0] == '':
            continue
        command = split[0].strip()

        if command == 'host':
            if len(split) != 5:
                print_warning('Too few arguments to add host in line\n{}'.format(line))
                continue
            algorithm = split[1].strip()
            rtt = split[2].strip()
            start = float(split[3].strip())
            stop = float(split[4].strip())
            if algorithm not in cc_algorithms:
                if algorithm not in unknown_alorithms:
                    unknown_alorithms.append(algorithm)
                continue

            if number_of_hosts >= MAX_HOST_NUMBER:
                print_warning('Max host number reached. Skipping further hosts.')
                continue

            number_of_hosts += 1
            output.append({
                'command': command,
                'algorithm': algorithm,
                'rtt': rtt,
                'start': start,
                'stop': stop})

        elif command == 'link':
            if len(split) != 4:
                print_warning('Too few arguments to change link in line\n{}'.format(line))
                continue
            change = split[1].strip()
            if change != 'bw' and change != 'rtt' and change != 'loss':
                print_warning('Unknown link option "{} in line\n{}'.format(change, line))
                continue
            value = split[2].strip()
            start = float(split[3].strip())
            output.append({
                'command': command,
                'change': change,
                'value': value,
                'start': start
            })
        else:
            print_warning('Skip unknown command "{}" in line\n{}'.format(command, line))
            continue

    if len(unknown_alorithms) > 0:
        print_warning('Skipping uninstalled congestion control algorithm:\n  ' + ' '.join(unknown_alorithms))
        print_warning('Available algorithms:\n  ' + cc_algorithms.strip())
        print_warning('Start Test anyway in 10s. (Press ^C to interrupt)')
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            sys.exit(1)

    return output


def traffic_shaping(mode, interface, add, **kwargs):
    if mode == 'tbf':
        command = 'tc qdisc {} dev {} root handle 1: tbf rate {} buffer {} latency {}'.format('add' if add else ' change',
                                                                                    interface, kwargs['rate'],
                                                                                    kwargs['buffer'], kwargs['latency'])
    elif mode == 'netem':
        command = 'tc qdisc {} dev {} parent 1: handle 2: netem delay {} loss {}'.format('add' if add else ' change',
                                                                          interface, kwargs['delay'], kwargs['loss'])
    return command

def xquic_command(
    type,
    XQUIC_PATH="./xquic",
    server_ip='127.0.0.1',
    server_port=8443,
    file_size=304857600,
    redis_server='10.0.0.123', # redis connect to 
    redis_port=6379,
    rlcc_flag=4321,
):
    """
        type : 'client' 'server'
        50Mb/?B : 52428800
        10M : 10485760
    """
    if type == 'server':
        # return f"{XQUIC_PATH}/test_server -l e  > /dev/null"
        return f"{XQUIC_PATH}/test_server -l e > /dev/null"
    elif type == 'client':
        cmd = f"{XQUIC_PATH}/test_client -l e -a {server_ip}" \
            + f" -p {server_port} -s {file_size} -c b -T -f {rlcc_flag}" \
            + f" -R {redis_server}:{redis_port} > /dev/null"
        return cmd

import random
def generate_rand_rlcc_flag(already_set: set):
    flag = random.randint(1000,2000)
    if flag not in already_set:
        already_set.add(flag)
        return flag
    return generate_rand_rlcc_flag(already_set=already_set)

def run_test(commands, output_directory, name, bandwidth, initial_rtt, initial_loss,
             buffer_size, buffer_latency, poll_interval):

    duration = 0
    start_time = 0
    number_of_hosts = 0

    current_netem_delay = initial_rtt
    current_netem_loss = initial_loss

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    config = [
        'Test Name: {}'.format(name),
        'Date: {}'.format(time.strftime('%c')),
        'Kernel: {}'.format(get_host_version()),
        'Git Commit: {}'.format(get_git_revision_hash()),
        'Initial Bandwidth: {}'.format(bandwidth),
        'Burst Buffer: {}'.format(buffer_size),
        'Buffer Latency: {}'.format(buffer_latency),
        'Initial Link RTT: {}'.format(initial_rtt),
        'Initial Link Loss: {}'.format(initial_loss),
        'Commands: '
    ]
    for cmd in commands:
        start_time += cmd['start']

        config_line = '{}, '.format(cmd['command'])
        if cmd['command'] == 'link':
            config_line += '{}, {}, {}'.format(cmd['change'], cmd['value'], cmd['start'])
        elif cmd['command'] == 'host':
            number_of_hosts += 1
            config_line += '{}, {}, {}, {}'.format(cmd['algorithm'], cmd['rtt'], cmd['start'], cmd['stop'])
            if start_time + cmd['stop'] > duration:
                duration = start_time + cmd['stop']
        config.append(config_line)

    with open(os.path.join('{}'.format(output_directory), 'parameters.txt'), 'w') as f:
        f.write('\n'.join(config))

    print('-' * TEXT_WIDTH)
    print('Starting test: {}'.format(name))
    print('Total duration: {}s'.format(duration))

    try:
        topo = DumbbellTopo(number_of_hosts)
        net = Mininet(topo=topo, link=TCLink)
        
        # # 下下策：同时生成多个宿主网卡，每个网卡和发送端单独连接，单独ip，xquic指定redis的单独ip
        # # connect to Root
        # root_ip = '10.123.0.123'
        # root_routes=['10.123.0.0/16']
        
        # s123 = net['s123']
        # # Create a node in root namespace and link to switch
        # root = Node('root', inNamespace=False)
        # intf = net.addLink(root, s123).intf1
        # root.setIP(root_ip, intf=intf)
        # print(str(intf))
        # # Start network that now includes link to root namespace
        # net.start()
        # # Add routes from root ns to hosts
        # for route in root_routes:
        #     root.cmd('route add -net ' + route + ' dev ' + str(intf))
        
        host_counter = 0
        for cmd in commands:
            if cmd['command'] != 'host':
                continue
            cnt = host_counter % 100
            root_ip = f'10.{cnt+124}.0.1/24'  # 124.0.1 -> 124.0.2
            root = Node(f'root{cnt}', inNamespace=False)
            sri = net[f'sr{cnt}']
            print(host_counter, cnt, sri)
            intf = net.addLink(root, sri).intf1
            root.setIP(root_ip, intf=intf)
            host_counter += 1
        net.start()
        
    except Exception as e:
        print_error('Could not start Mininet:')
        print_error(e)
        sys.exit(1)

    # start tcp dump
    try:
        FNULL = open(os.devnull, 'w')
        # subprocess.Popen(['tcpdump', '-i', 's1-eth1', '-n', 'tcp', '-s', '88',
        #                   '-w', os.path.join(output_directory, 's1.pcap')], stderr=FNULL)
        subprocess.Popen(['tcpdump', '-i', 's1-eth1', '-n', '-s', '88',
                          '-w', os.path.join(output_directory, 's1.pcap')], stderr=FNULL)
        # subprocess.Popen(['tcpdump', '-i', 's3-eth1', '-n', 'tcp', '-s', '88',
        #                   '-w', os.path.join(output_directory, 's3.pcap')], stderr=FNULL)
        subprocess.Popen(['tcpdump', '-i', 's3-eth1', '-n', '-s', '88',
                          '-w', os.path.join(output_directory, 's3.pcap')], stderr=FNULL)
    except Exception as e:
        print_error('Error on starting tcpdump\n{}'.format(e))
        sys.exit(1)


    time.sleep(1)

    host_counter = 0
    for cmd in commands:
        if cmd['command'] != 'host':
            continue
        send = net.get('h{}'.format(host_counter))
        send.setIP('10.1.{}.{}/16'.format(host_counter // 256, host_counter % 256))
        # send.cmd(f"ip addr add 10.123.{host_counter // 256}.{host_counter % 256}/16 dev {send.intfs[1]}")
        send.cmd(f"ip addr add 10.{(host_counter % 100)+124}.0.2/24 dev {send.intfs[1]}")

        send.cmd(f"route add -net 10.2.0.0/16 dev {send.intfs[0]}")

        recv = net.get('r{}'.format(host_counter))
        recv.setIP('10.2.{}.{}/16'.format(host_counter // 256, host_counter % 256))
        recv.cmd(f"route add -net 10.1.0.0/16 dev {recv.intfs[0]}")
        host_counter += 1
        
        # test ping
        # send1 = net.get('h1')
        # send1.cmd("ifconfig >> test.log")
        # send1.cmd("ip route >> test.log")
        # send1.cmd(f"ping -i 1 -I {str(send.intfs[1])} 10.123.0.123 -t 3 > test.log")
        # if host_counter == 2:
        #     send.cmd(f"ping -i 1 10.123.0.123 -t 3 > test.log")

        # test xquic
        # send1 = net.get('h0')
        # recv1 = net.get('r0')
        # xquic_server = xquic_command(type="server")
        # recv1.cmd(f'{xquic_server} &')

        # xquic_client = xquic_command(type="client", server_ip=f"{recv.IP()}", rlcc_flag=1001)
        # send1.cmd(f'{xquic_client} &')

        # setup FQ, algorithm, netem, nc host
        send.cmd('tc qdisc add dev {}-eth0 root fq pacing'.format(send))
        if cmd['algorithm'][0:5] != "xquic":
            send.cmd('ip route change 10.0.0.0/16 dev {}-eth0 congctl {}'.format(send, cmd['algorithm']))
        else:
            send.cmd('ip route change 10.0.0.0/16 dev {}-eth0'.format(send))
        send.cmd('ethtool -K {}-eth0 tso off'.format(send))
        recv.cmd('tc qdisc add dev {}-eth0 root netem delay {}'.format(recv, cmd['rtt']))
        if cmd['algorithm'][0:5] != "xquic":
            # tcp
            recv.cmd('timeout {} nc -klp 9000 > /dev/null &'.format(duration))
        else:
            # xquic server
            xquic_server = xquic_command(type="server")
            print(xquic_server)
            recv.cmd(f'timeout {duration} {xquic_server} &')

        # test redis ping pong
        # send1 = net.get('h0')
        # send1.cmd(f"redis-cli -h 10.{(host_counter%100)+124}.0.1 -p {6379} ping > test.log")
        # send1 = net.get('h0')
        # send1.cmd(f"ping -i 1 10.123.0.123 > test.log")
        # # send1.cmd(f"ping -i 1 10.2.0.0 > test.log")
        
        # pull BBR values
        send.cmd('./ss_script.sh {} >> {}.{} &'.format(poll_interval, os.path.join(output_directory, send.IP()), FLOW_FILE_EXTENSION))

    s2, s3 = net.get('s2', 's3')
    s2.cmd(traffic_shaping('tbf', 's2-eth2', add=True, rate=bandwidth, buffer=buffer_size, latency=buffer_latency))

    netem_running = False
    if current_netem_delay != '0ms' or current_netem_loss != '0%':
        netem_running = True
        s2.cmd(traffic_shaping('netem', 's2-eth2', add=True, delay=current_netem_delay, loss=current_netem_loss))
    s2.cmd('./buffer_script.sh {0} {1} >> {2}.{3} &'.format(poll_interval, 's2-eth2',
                                                            os.path.join(output_directory, 's2-eth2-tbf'),
                                                            BUFFER_FILE_EXTENSION))

    complete = duration
    current_time = 0
    host_counter = 0

    rlcc_flag_set = set()
    try:
        for cmd in commands:
            start = cmd['start']
            current_time = sleep_progress_bar(start, current_time=current_time, complete=complete)

            if cmd['command'] == 'link':
                s2 = net.get('s2')

                if cmd['change'] == 'bw':
                    s2.cmd(traffic_shaping('tbf', 's2-eth2', add=False, rate=cmd['value'], buffer=buffer_size, latency=buffer_latency))
                    log_String = '  Change bandwidth to {}.'.format(cmd['value'])

                elif cmd['change'] == 'rtt' or cmd['change'] == 'loss':
                    current_netem_delay = cmd['value'] if cmd['change'] == 'rtt' else current_netem_delay
                    current_netem_loss = cmd['value'] if cmd['change'] == 'loss' else current_netem_loss

                    s2.cmd(traffic_shaping('netem', 's2-eth2', add=not netem_running, delay=current_netem_delay,
                                           loss=current_netem_loss))
                    netem_running = True
                    log_String = '  Change {} to {}.'.format(cmd['change'], cmd['value'])

            elif cmd['command'] == 'host':
                send = net.get('h{}'.format(host_counter))
                recv = net.get('r{}'.format(host_counter))
                timeout = cmd['stop']
                log_String = '  h{}: {} {}, {} -> {}'.format(host_counter, cmd['algorithm'], cmd['rtt'], send.IP(), recv.IP())
                # send.cmd('timeout {} nc {} 9000 < /dev/urandom > /dev/null &'.format(timeout, recv.IP()))
                if cmd['algorithm'][0:5] != "xquic":
                    # tcp
                    send.cmd('timeout {} nc {} 9000 < /dev/urandom > /dev/null &'.format(timeout, recv.IP()))
                else:
                    # xquic client
                    new_rand_flag = generate_rand_rlcc_flag(rlcc_flag_set)
                    xquic_client = xquic_command(type="client", server_ip=recv.IP(), rlcc_flag=new_rand_flag, redis_server=f'10.{(host_counter%100)+124}.0.1')
                    print(xquic_client)
                    send.cmd(f'timeout {timeout} {xquic_client} &')
                    # send.cmd(f"redis-cli -h 10.{(host_counter%100)+124}.0.1 -p {6379} ping >> test.log")
                    # send.cmd(f'ping 10.{(host_counter%100)+124}.0.1 -i 1 -I {send.intfs[1]} >> ping{send.IP()}.log 2>&1 &')
                    # send.cmd(f'ping 10.2.{host_counter // 256}.{host_counter % 256} -i 1 >> ping{send.IP()}.log 2>&1 &')
                    # send.cmd(f'ifconfig > ping{send.IP()}.log 2>&1 &')
                    
                    # 网络拓扑的问题: 同时指向一个switch的多个ip，只有后一个的网络会通，所以改为多个root网卡的形式，实现隔离

                host_counter += 1
            print(log_String + ' ' * (TEXT_WIDTH - len(log_String)))

        current_time = sleep_progress_bar((complete - current_time) % 1, current_time=current_time, complete=complete)
        current_time = sleep_progress_bar(complete - current_time, current_time=current_time, complete=complete)
    except (KeyboardInterrupt, Exception) as e:
        if isinstance(e, KeyboardInterrupt):
            print_warning('\nReceived keyboard interrupt. Stop Mininet.')
        else:
            print_error(e)
    finally:
        net.stop()
        cleanup()

    print('-' * TEXT_WIDTH)


def verify_arguments(args, commands):
    verified = True

    verified &= verify('rate', args.bandwidth)
    verified &= verify('time', args.rtt)
    verified &= verify('percent', args.loss)
    verified &= verify('size', args.buffer_size)
    verified &= verify('time', args.latency)

    for c in commands:
        if c['command'] == 'link':
            if c['change'] == 'bw':
                verified &= verify('rate', c['value'])
            elif c['change'] == 'rtt':
                verified &= verify('time', c['value'])
            elif c['change'] == 'loss':
                verified &= verify('percent', c['value'])
        elif c['command'] == 'host':
            verified &= verify('time', c['rtt'])

    return verified


def verify(type, value):
    if type == 'rate':
        allowed = ['bit', 'kbit', 'mbit', 'bps', 'kbps', 'mbps']
    elif type == 'time':
        allowed = ['s', 'ms', 'us']
    elif type == 'size':
        allowed = ['b', 'kbit', 'mbit', 'kb', 'k', 'mb', 'm']
    elif type == 'percent':
        allowed = ['%']
    else:
        allowed = []  # Unknown type

    si = re.sub('^([0-9]+\.)?[0-9]+', '', value).lower()

    if si not in allowed:
        print_error('Malformed {} unit: {} not in {}'.format(type, value, list(allowed)))
        return False
    return True


def compress_output(dir, method):

    all_files = glob.glob(os.path.join(dir, '*.{}'.format(FLOW_FILE_EXTENSION)))
    all_files += glob.glob(os.path.join(dir, '*.{}'.format(BUFFER_FILE_EXTENSION)))
    all_files += glob.glob(os.path.join(dir, '*.pcap'))

    print('Compressing files:')

    for f in all_files:
        compress_file(f, method)
        print('  * {}'.format(os.path.basename(f)))


if __name__ == '__main__':
    if check_tools() > 0:
        exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument('config', metavar='CONFIG',
                        help='Path to the config file.')
    parser.add_argument('-b', dest='bandwidth',
                        default='10Mbit', help='Initial bandwidth of the bottleneck link. (default: 10mbit)')
    parser.add_argument('-r', dest='rtt',
                        default='0ms', help='Initial rtt for all flows. (default 0ms)')
    parser.add_argument('--loss', dest='loss',
                        default='0%', help='Initial rtt for all flows. (default 0%)')
    parser.add_argument('-d', dest='directory',
                        default='test/', help='Path to the output directory. (default: test/)')
    parser.add_argument('-s', dest='buffer_size',
                        default='1600b', help='Burst size of the token bucket filter. (default: 1600b)')
    parser.add_argument('-l', dest='latency',
                        default='100ms', help='Maximum latency at the bottleneck buffer. (default: 100ms)')
    parser.add_argument('-n', dest='name',
                        help='Name of the output directory. (default: <config file name>)')
    parser.add_argument('--poll-interval', dest='poll_interval', type=float,
                        default=0.04, help='Interval to poll TCP values and buffer backlog in seconds. (default: 0.04)')
    parser.add_argument('-c --compression', dest='compression',
                        choices=COMPRESSION_METHODS, default=COMPRESSION_METHODS[1],
                        help='Compression method of the output files. Default: {}'.format(COMPRESSION_METHODS[1]))

    args = parser.parse_args()

    # Use config file name if no explicit name is specified
    args.name = args.name or os.path.splitext(os.path.basename(args.config))[0]

    if not os.path.isfile(args.config):
        print_error('Config file missing: {}'.format(args.config))
        sys.exit(128)

    commands = parseConfigFile(args.config)
    if len(commands) == 0:
        print_error('No valid commands found in config file.')
        sys.exit(128)

    if not verify_arguments(args, commands):
        print_error('Please fix malformed parameters.')
        sys.exit(128)

    output_directory = os.path.join(args.directory, '{}_{}'.format(time.strftime('%m%d_%H%M%S'), args.name))

    # setLogLevel('info')
    run_test(bandwidth=args.bandwidth,
             initial_rtt=args.rtt,
             initial_loss=args.loss,
             commands=commands,
             buffer_size=args.buffer_size,
             buffer_latency=args.latency,
             name=args.name,
             output_directory=output_directory,
             poll_interval=args.poll_interval)

    compression = args.compression

    if compression != COMPRESSION_METHODS[0]:
        if not check_tool(compression):
            print_warning('Compression with {} not possible. Continuing without compression.'.format(compression))
            compression = COMPRESSION_METHODS[0]

        compress_output(output_directory, compression)
        print('-' * TEXT_WIDTH)
