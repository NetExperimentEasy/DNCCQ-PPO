from subprocess import check_output
import subprocess


def traffic_shaping(mode, interface, add, **kwargs):
    """
        mode : bw, loss, rtt; both
        if bw:
            rate :  bandwidth of the link
            buffer : Burst size of the token bucket filter
            latency : Maximum latency at the buffer

        if rtt loss:
            delay : rtt of the link
            loss : loss of the link

    tc qdisc replace dev s1-s2 root netem rate 50Mbps delay 200ms
    """

    if mode == 'bw':
        command = f"tc qdisc {'add' if add else 'change'} dev {interface}" \
            + f" root handle 1: tbf rate {kwargs['rate']} buffer" \
            + f" {kwargs['buffer']} latency {kwargs['latency']}"
    elif mode == 'loss' or mode == "rtt":
        command = f"tc qdisc {'add' if add else 'change'} dev {interface}" \
            + f" parent 1: handle 2: netem delay {kwargs['delay']} loss" \
            + f" {kwargs['loss']}"
    elif mode == 'both':
        command = f"tc qdisc replace dev {interface} root netem rate" \
            + f" {kwargs['rate']} delay {kwargs['delay']} loss" \
            + f" {kwargs['loss']}"
    return command


def xquic_command(
    type,
    XQUIC_PATH,
    server_ip='127.0.0.1',
    server_port=8443,
    file_size=304857600,
    redis_server='10.0.0.123',
    redis_port=6379,
    rlcc_flag=4321,
):
    """
        type : 'client' 'server'
        50Mb/?B : 52428800
        10M : 10485760
    """
    if type == 'server':
        return f"{XQUIC_PATH}/test_server -l e  > /dev/null"
    elif type == 'client':
        cmd = f"{XQUIC_PATH}/test_client -l e -a {server_ip}" \
            + f" -p {server_port} -s {file_size} -c R -T -f {rlcc_flag}" \
            + f" -R {redis_server}:{redis_port} > /dev/null"
        return cmd


def generate_xquic_tls():
    cmd = 'keyfile=server.key '
    cmd += '&& certfile=server.crt '
    cmd += "&& openssl req -newkey rsa:2048 -x509" \
        + ' -nodes -keyout "$keyfile" -new -out "$certfile" -subj' \
        + " /CN=test.xquic.com"
    return cmd


def tcpdump_command(aim_ips: list, ports: list, filename=None):
    """
    aim_ips : list of str : one ip or many ips
    ports   : list of int : one port or many ports
    """
    cmd = "tcpdump -i any "

    if aim_ips:
        cmd += f"host {aim_ips[0]} "
        for i in aim_ips[1:]:
            cmd += f"or {i} "
        if ports:
            cmd += "and "

    if ports:
        cmd += f"port {ports[0]} "
        for i in ports[1:]:
            cmd += f"or {i} "

    if filename:
        cmd += f"-w {filename}"
    else:
        cmd += f"-w ./{aim_ips[0]}.pcap"
    return cmd


def cmd_at(host, func, ifbackend=False, ifprint=True, **kwargs):
    """
    host : cmd at
    func : command func
    ifbackend : bool default is False
    **kwargs : params for func
    """
    command = func(**kwargs)
    if ifbackend:
        command = f'{command} &'
    if ifprint:
        print(f"## {host.name} : '{command}'")
    host.cmd(command)


def kill_pid_by_name(name: str):
    try:
        pid = int(check_output(["pidof", "-s", f"{name}"]))
        subprocess.call(["kill %d" % pid], shell=True)
    except subprocess.CalledProcessError:
        return