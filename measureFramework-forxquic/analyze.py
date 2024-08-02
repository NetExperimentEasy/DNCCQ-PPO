import argparse
import dpkt
import socket
import os
import sys
import glob
import gzip

from helper.csv_writer import write_to_csv, read_from_csv
from helper.pcap_data import PcapData, DataInfo
from helper.create_plots import plot_all
from helper.util import check_directory, print_line, open_compressed_file, colorize, get_ip_from_filename, get_interface_from_filename

from helper import PCAP1, PCAP2, PLOT_PATH, CSV_PATH, PLOT_TYPES
from helper import BUFFER_FILE_EXTENSION, FLOW_FILE_EXTENSION
from helper import COMPRESSION_METHODS, COMPRESSION_EXTENSIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d --directory', dest='directory',
                        default='.', help='Path to the working directory (default: .)')
    parser.add_argument('-s', dest='source',
                        choices=['pcap', 'csv'],
                        default='pcap', help='Create plots from csv or pcap')
    parser.add_argument('-o', dest='output',
                        choices=['pdf+csv', 'pdf', 'csv'],
                        default='pdf+csv', help='Output Format (default: pdf+csv)')
    parser.add_argument('-t', dest='delta_t',
                        default='0.2', help='Interval in seconds for computing average throughput,... '
                                            '(default: 0.2)')
    parser.add_argument('-r', dest='recursive', action='store_true',
                        help='Process all sub-directories recursively.')
    parser.add_argument('-n', dest='new', action='store_true',
                        help='Only process new (unprocessed) directories.')
    parser.add_argument('--hide-total', dest='hide_total', action='store_true',
                        help='Hide total values in plots for sending rate, throughput, ...')
    parser.add_argument('-a --add-plot', action='append', choices=PLOT_TYPES, dest='added_plots',
                        help='Add a plot to the final PDF output. This is overwritten by the -i option if both are given.')
    parser.add_argument('-i --ignore-plot', action='append', choices=PLOT_TYPES, dest='ignored_plots',
                        help='Remove a plot from the PDF output. This overwrites the -a option.')
    parser.add_argument('-c --compression', dest='compression',
                        choices=COMPRESSION_METHODS, default=COMPRESSION_METHODS[1],
                        help='Compression method of the output files. Default: {}'.format(COMPRESSION_METHODS[1]))
    parser.add_argument('--all-plots', dest='all_plots', action='store_true',
                        help='Additionally store each plot in an individual PDF file.')

    args = parser.parse_args()

    directory = args.directory

    paths = []
    plots = PLOT_TYPES

    if args.added_plots is not None:
        plots = args.added_plots

    if args.ignored_plots is not None:
        plots = [p for p in PLOT_TYPES if p not in args.ignored_plots]

    if args.recursive:
        for subdirs, _, _ in os.walk(directory):
            if check_directory(subdirs, only_new=args.new):
                paths.append(subdirs)
    else:
        if check_directory(directory, only_new=args.new):
            paths = [directory]
    print('Found {} valid sub directories.'.format(len(paths)))

    paths = sorted(paths)

    for i, directory in enumerate(paths):
        print('{}/{} Processing {}'.format(i + 1, len(paths), directory))
        if args.source == 'pcap':

            pcap_data = parse_pcap(path=directory, delta_t=float(args.delta_t))

            if 'csv' in args.output:
                string = 'Writing to CSV'
                if args.compression != COMPRESSION_METHODS[0]:
                    string += ' and compressing with {}'.format(args.compression)
                print(string)
                write_to_csv(directory, pcap_data, compression=args.compression)
        else:
            pcap_data = read_from_csv(directory)
            if pcap_data == -1:
                continue

        if 'pdf' in args.output:
            if args.all_plots:
                print('Creating {} plots'.format(len(plots) + 1))
            else:
                print('Creating Complete plot')
            plot_all(directory, pcap_data, plot_only=plots, hide_total=args.hide_total, all_plots=args.all_plots)


def parse_pcap(path, delta_t):
    # Find correct .pcap files
    pcap1 = glob.glob(os.path.join(path, PCAP1 + '*'))[0]
    pcap2 = glob.glob(os.path.join(path, PCAP2 + '*'))[0]

    total_packets = len(list(dpkt.pcap.Reader(open_compressed_file(pcap1)))) + \
                    len(list(dpkt.pcap.Reader(open_compressed_file(pcap1))))
    print('  Found {} frames.'.format(colorize(total_packets, 'green')))
    processed_packets = 0

    f = open_compressed_file(pcap1)

    pcap = dpkt.pcap.Reader(f)

    connections = []
    active_connections = []

    round_trips = {}
    inflight = {}
    sending_rate = {}
    avg_rtt = {}

    inflight_seq = {}
    inflight_ack = {}

    sending_rate_data_size = {}

    inflight_avg = {}

    avg_rtt_samples = {}

    total_throughput = ([], [])
    total_sending_rate = ([], [])

    retransmissions = {}
    retransmission_counter = {}
    packet_counter = {}
    retransmissions_interval = {}
    total_retransmisions = ([], [], [])

    start_seq = {}

    t = 0

    ts_vals = {}
    seqs = {}

    start_ts = -1

    print('Connections:')
    for ts, buf in pcap:
        if start_ts < 0:
            start_ts = ts
            t = start_ts + delta_t

        processed_packets += 1
        if processed_packets % 500 == 0:
            print_progress(processed_packets, total_packets)

        eth = dpkt.ethernet.Ethernet(buf)
        ip = eth.data
        tcp = ip.data

        src_ip = socket.inet_ntoa(ip.src)
        dst_ip = socket.inet_ntoa(ip.dst)
        src_port = tcp.sport
        dst_port = tcp.dport

        # identify a connection always as (client port, server port)
        if src_port > dst_port:
            tcp_tuple = (src_ip, src_port, dst_ip, dst_port)
        else:
            tcp_tuple = (dst_ip, dst_port, src_ip, src_port)

        while ts >= t:

            total_sending_rate[0].append(t)
            total_sending_rate[1].append(0)

            total_retransmisions[0].append(t)
            total_retransmisions[1].append(0)
            total_retransmisions[2].append(0)

            for key in connections:

                if key not in active_connections:
                    continue

                tp = float(sending_rate_data_size[key]) / delta_t
                sending_rate[key][0].append(t)
                sending_rate[key][1].append(tp)
                sending_rate_data_size[key] = 0

                total_sending_rate[1][-1] += tp

                retransmissions_interval[key][0].append(t)
                retransmissions_interval[key][1].append(retransmission_counter[key])
                retransmissions_interval[key][2].append(packet_counter[key])
                total_retransmisions[1][-1] += retransmission_counter[key]
                total_retransmisions[2][-1] += packet_counter[key]
                retransmission_counter[key] = 0
                packet_counter[key] = 0

                inflight[key][0].append(t)
                if len(inflight_avg[key]) > 0:
                    inflight[key][1].append(sum(inflight_avg[key]) / len(inflight_avg[key]))
                else:
                    inflight[key][1].append(0)
                inflight_avg[key] = []

                if len(avg_rtt_samples[key]) > 0:
                    avg_rt = sum(avg_rtt_samples[key]) / len(avg_rtt_samples[key])
                    avg_rtt[key][0].append(t)
                    avg_rtt[key][1].append(avg_rt)
                avg_rtt_samples[key] = []

            t += delta_t

        if tcp.flags & 0x02 and tcp_tuple not in connections:
            connections.append(tcp_tuple)
            active_connections.append(tcp_tuple)
            connection_index = tcp_tuple

            start_seq[connection_index] = tcp.seq

            round_trips[connection_index] = ([], [])
            inflight[connection_index] = ([], [])
            avg_rtt[connection_index] = ([], [])
            sending_rate[connection_index] = ([], [])

            ts_vals[connection_index] = ([], [])
            seqs[connection_index] = []

            inflight_seq[connection_index] = 0
            inflight_ack[connection_index] = 0

            inflight_avg[connection_index] = []

            sending_rate_data_size[connection_index] = 0

            avg_rtt_samples[connection_index] = []

            retransmissions[connection_index] = ([],)
            retransmission_counter[connection_index] = 0
            packet_counter[connection_index] = 0
            retransmissions_interval[connection_index] = ([], [], [])

            print('  [SYN] {}:{} -> {}:{}'.format(tcp_tuple[0], tcp_tuple[1],
                                                  tcp_tuple[2], tcp_tuple[3]))

        if tcp.flags & 0x01:
            if tcp_tuple in active_connections:
                active_connections.remove(tcp_tuple)
                print('  [FIN] {}:{} -> {}:{}'.format(tcp_tuple[0], tcp_tuple[1],
                                                      tcp_tuple[2], tcp_tuple[3]))
            continue

        connection_index = tcp_tuple

        ts_val = None
        ts_ecr = None

        options = dpkt.tcp.parse_opts(tcp.opts)
        for opt in options:
            if opt[0] == dpkt.tcp.TCP_OPT_TIMESTAMP:
                ts_val = int.from_bytes(opt[1][:4], 'big')
                ts_ecr = int.from_bytes(opt[1][4:], 'big')

        if src_port > dst_port:
            # client -> server
            tcp_seq = tcp.seq - start_seq[connection_index]
            if tcp_seq < 0:
                tcp_seq += 2 ** 32

            packet_counter[connection_index] += 1

            inflight_seq[connection_index] = max(tcp_seq, inflight_seq[connection_index])
            sending_rate_data_size[connection_index] += ip.len * 8

            if tcp_seq in seqs[connection_index]:
                retransmissions[connection_index][0].append(ts)
                retransmission_counter[connection_index] += 1

            else:
                seqs[connection_index].append(tcp_seq)
                if ts_val is not None:
                    ts_vals[connection_index][0].append(ts)
                    ts_vals[connection_index][1].append(ts_val)

        else:
            # server -> client
            tcp_ack = tcp.ack - start_seq[connection_index]
            if tcp_ack < 0:
                tcp_ack += 2 ** 32

            inflight_ack[connection_index] = max(tcp_ack, inflight_ack[connection_index])

            seqs[connection_index] = [x for x in seqs[connection_index] if x >= tcp_ack]

            if ts_ecr in ts_vals[connection_index][1]:
                index = ts_vals[connection_index][1].index(ts_ecr)
                rtt = (ts - ts_vals[connection_index][0][index]) * 1000

                ts_vals[connection_index][0].pop(index)
                ts_vals[connection_index][1].pop(index)

                avg_rtt_samples[connection_index].append(rtt)

                round_trips[connection_index][0].append(ts)
                round_trips[connection_index][1].append(rtt)

        inflight_data = max(0, inflight_seq[connection_index] - inflight_ack[connection_index])
        inflight_avg[connection_index].append(inflight_data * 8)

    f.close()

    # Compute throughput after the bottleneck
    f = open_compressed_file(pcap2)

    pcap = dpkt.pcap.Reader(f)

    connections = []
    active_connections = []
    throughput = {}

    throughput_data_size = {}

    t = start_ts + delta_t

    for ts, buf in pcap:

        processed_packets += 1
        if processed_packets % 500 == 0:
            print_progress(processed_packets, total_packets)

        eth = dpkt.ethernet.Ethernet(buf)
        ip = eth.data
        tcp = ip.data

        src_ip = socket.inet_ntoa(ip.src)
        dst_ip = socket.inet_ntoa(ip.dst)
        src_port = tcp.sport
        dst_port = tcp.dport

        # identify a connection always as (client port, server port)
        if src_port > dst_port:
            tcp_tuple = (src_ip, src_port, dst_ip, dst_port)
        else:
            tcp_tuple = (dst_ip, dst_port, src_ip, src_port)

        while ts >= t:
            total_throughput[0].append(t)
            total_throughput[1].append(0)

            for key in connections:
                if key not in active_connections:
                    continue
                tp = float(throughput_data_size[key]) / delta_t
                throughput[key][0].append(t)
                throughput[key][1].append(tp)
                total_throughput[1][-1] += tp
                throughput_data_size[key] = 0
            t += delta_t

        if tcp.flags & 0x02 and tcp_tuple not in connections:
            connections.append(tcp_tuple)
            active_connections.append(tcp_tuple)
            connection_index = tcp_tuple

            throughput[connection_index] = ([], [])
            throughput_data_size[connection_index] = 0

        if tcp.flags & 0x01:
            if tcp_tuple in active_connections:
                active_connections.remove(tcp_tuple)
            continue

        connection_index = tcp_tuple

        if src_port > dst_port:
            # client -> server
            throughput_data_size[connection_index] += ip.len * 8

    print('  100.00%')

    fairness_troughput = compute_fairness(throughput, delta_t)
    fairness_sending_rate = compute_fairness(sending_rate, delta_t)
    fairness = {
        'Throughput': fairness_troughput,
        'Sending Rate': fairness_sending_rate
    }

    bbr_values, cwnd_values = parse_bbr_and_cwnd_values(path)
    bbr_total_values, sync_phases, sync_duration = compute_total_values(bbr_values)
    buffer_backlog = parse_buffer_backlog(path)

    data_info = DataInfo(sync_duration=sync_duration,
                         sync_phases=sync_phases)

    throughput['total'] = total_throughput
    sending_rate['total'] = total_sending_rate
    retransmissions_interval['total'] = total_retransmisions

    return PcapData(rtt=round_trips,
                    inflight=inflight,
                    throughput=throughput,
                    fairness=fairness,
                    avg_rtt=avg_rtt,
                    sending_rate=sending_rate,
                    bbr_values=bbr_values,
                    bbr_total_values=bbr_total_values,
                    cwnd_values=cwnd_values,
                    retransmissions=retransmissions,
                    retransmissions_interval=retransmissions_interval,
                    buffer_backlog=buffer_backlog,
                    data_info=data_info)


def print_progress(current, total):
    print_line('  {:7.3}%          '.format(100 * current / float(total)))


def parse_buffer_backlog(path):
    output = {}
    paths = glob.glob(os.path.join(path, '*.{}*'.format(BUFFER_FILE_EXTENSION)))

    for file_path in paths:
        intf = get_interface_from_filename(file_path)
        output[intf] = ([], [])
        f = open_compressed_file(file_path)
        for line in f:
            if type(line) == bytes:
                line = line.decode('utf8').replace('\n', '')
            split = line.split(';')
            timestamp = parse_timestamp(split[0])
            size = split[1].replace('b', '')
            if 'K' in size:
                size = float(size.replace('K', '')) * 1000
            elif 'M' in size:
                size = float(size.replace('M', '')) * 1000000
            elif 'G' in size:
                size = float(size.replace('G', '')) * 1000000000
            output[intf][0].append(timestamp)
            output[intf][1].append(float(size) * 8)
        f.close()
    return output


def parse_bbr_and_cwnd_values(path):
    bbr_values = {}
    cwnd_values = {}

    paths = glob.glob(os.path.join(path, '*.{}*'.format(FLOW_FILE_EXTENSION)))

    all_files = sorted(paths)

    for file_path in all_files:

        ip = get_ip_from_filename(file_path)

        bbr_values[ip] = ([], [], [], [], [], [])
        cwnd_values[ip] = ([], [], [])

        f = open_compressed_file(file_path)

        for line in f:
            if type(line) == bytes:
                line = line.decode('utf8').replace('\n', '')
            split = line.split(';')

            timestamp = parse_timestamp(split[0])
            cwnd, ssthresh = 0, 0

            if split[1] != '':
                cwnd = int(split[1])
            if split[2] != '':
                ssthresh = int(split[2])

            cwnd_values[ip][0].append(timestamp)
            cwnd_values[ip][1].append(cwnd)
            cwnd_values[ip][2].append(ssthresh)

            if split[3] != '':
                bbr = split[3].replace('bw:', '')\
                    .replace('mrtt:','')\
                    .replace('pacing_gain:', '')\
                    .replace('cwnd_gain:', '')
                bbr = bbr.split(',')

                if len(bbr) < 4:
                    pacing_gain = 0
                    cwnd_gain = 0
                else:
                    pacing_gain = float(bbr[2])
                    cwnd_gain = float(bbr[3])

                if 'Mbps' in bbr[0]:
                    bw = float(bbr[0].replace('Mbps', '')) * 1000000
                elif 'Kbps' in bbr[0]:
                    bw = float(bbr[0].replace('Kbps', '')) * 1000
                elif 'bps' in bbr[0]:
                    bw = float(bbr[0].replace('bps', ''))
                else:
                    bw = 0

                rtt = float(bbr[1])

                bbr_values[ip][0].append(timestamp)
                bbr_values[ip][1].append(bw)
                bbr_values[ip][2].append(rtt)
                bbr_values[ip][3].append(pacing_gain)
                bbr_values[ip][4].append(cwnd_gain)
                bbr_values[ip][5].append(bw * rtt / 1000)

        f.close()
    return bbr_values, cwnd_values


def parse_timestamp(string):
    return float(string)


def compute_total_values(bbr):
    connection_first_index = {f: 0 for f in bbr}
    current_bw = {f: 0 for f in bbr}
    current_window = {f: 0 for f in bbr}
    current_gain = {f: 0 for f in bbr}

    total_bw = ([], [])
    total_window = ([], [])
    total_gain = ([], [])

    sync_window_start = -1
    sync_window_phases = []
    sync_window_durations = []

    while True:
        active_connections = 0
        current_timestamps = {}

        for c in bbr:
            if connection_first_index[c] < len(bbr[c][0]):
                current_timestamps[c] = bbr[c][0][connection_first_index[c]]
                active_connections += 1
            else:
                current_window[c] = 0
                current_bw[c] = 0
                current_gain[c] = 0

        if active_connections < 1:
            break

        c, ts = min(current_timestamps.items(), key=lambda x: x[1])
        current_bw[c] = bbr[c][1][connection_first_index[c]]
        current_window[c] = float(bbr[c][4][connection_first_index[c]])
        current_gain[c] = float(bbr[c][3][connection_first_index[c]])
        connection_first_index[c] += 1

        total_bw[0].append(ts)
        total_bw[1].append(sum(current_bw.values()))

        total_window[0].append(ts)
        total_window[1].append(sum(current_window.values()))

        total_gain[0].append(ts)
        total_gain[1].append(sum(current_gain.values()))

        min_window = 0
        for i in connection_first_index.values():
            if i > 0:
                min_window += 1

        if sum(current_window.values()) == min_window:
            if sync_window_start < 0:
                sync_window_start = ts
                sync_window_phases.append(sync_window_start)
        elif sync_window_start > 0:
            duration = (ts - sync_window_start) * 1000
            sync_window_start = -1
            sync_window_durations.append(duration)

    return {0: total_bw, 1: total_window, 2: total_gain}, sync_window_phases, sync_window_durations


def compute_fairness(data, interval):
    output = ([], [])
    connections = {k: 0 for k in data.keys()}

    max_ts = 0
    min_ts = float('inf')
    for c in data:
        max_ts = max(max_ts, max(data[c][0]))
        min_ts = min(min_ts, min(data[c][0]))

    ts = min_ts
    while True:
        if ts > max_ts:
            break

        shares = []
        for i in data.keys():
            if len(data[i][0]) <= connections[i]:
                continue
            if data[i][0][connections[i]] == ts:
                shares.append(data[i][1][connections[i]])
                connections[i] += 1

        output[0].append(ts)
        output[1].append(compute_jain_index(*shares))
        ts += interval
    return output


def compute_jain_index(*args):

    sum_normal = 0
    sum_square = 0

    for arg in args:
        sum_normal += arg
        sum_square += arg**2

    if len(args) == 0 or sum_square == 0:
        return 1

    return sum_normal ** 2 / (len(args) * sum_square)


if __name__ == "__main__":
    main()
