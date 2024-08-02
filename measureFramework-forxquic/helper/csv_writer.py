import os
import errno
import numpy as np


from helper.pcap_data import PcapData

from helper import CSV_PATH, CSV_FILE_NAMES, INFORMATION_FILE
from helper import COMPRESSION_EXTENSIONS
from helper.util import open_compressed_file, find_file


def write_to_csv(path, pcap_data, compression):
    path = os.path.join(path, CSV_PATH)

    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

    write_info_file(path, pcap_data)
    value_dict = pcap_data.values_as_dict()

    for value in value_dict:
        write_csv(os.path.join(path, CSV_FILE_NAMES[value]), value_dict[value], compression=compression)


def write_csv(path, data, compression):
    f = open_compressed_file('{}{}'.format(path, COMPRESSION_EXTENSIONS[compression]), write=True)
    connections = []
    max_length = 0
    columns = 1
    for d in data:
        connections.append(data[d])
        columns = len(data[d])

        max_length = max(max_length, len(data[d][0]))

        for col in range(0, columns):
            f.write('{};'.format(d))
    f.write('\n')

    for i in range(max_length):
        for j in connections:
            if i < len(j[0]):
                for col in range(0, columns):
                    f.write('{};'.format(j[col][i]))
            else:
                for col in range(0, columns):
                    f.write(';')
        f.write('\n')
    f.close()


def read_from_csv(path):
    path = os.path.join(path, CSV_PATH)

    data_files = {
        'throughput_file': os.path.join(path, CSV_FILE_NAMES['throughput']),
        'avg_rtt_file': os.path.join(path, CSV_FILE_NAMES['avg_rtt']),
        'fairness_file': os.path.join(path, CSV_FILE_NAMES['fairness']),
        'rtt_file': os.path.join(path, CSV_FILE_NAMES['rtt']),
        'inflight_file': os.path.join(path, CSV_FILE_NAMES['inflight']),
        'sending_rate_file': os.path.join(path, CSV_FILE_NAMES['sending_rate']),
        'bbr_values_file': os.path.join(path, CSV_FILE_NAMES['bbr_values']),
        'bbr_total_values_file': os.path.join(path, CSV_FILE_NAMES['bbr_total_values']),
        'cwnd_values_file': os.path.join(path, CSV_FILE_NAMES['cwnd_values']),
        'retransmissions_file': os.path.join(path, CSV_FILE_NAMES['retransmissions']),
        'retransmissions_interval_file': os.path.join(path, CSV_FILE_NAMES['retransmissions_interval']),
        'buffer_backlog_file': os.path.join(path, CSV_FILE_NAMES['buffer_backlog'])
    }

    throughput = read_csv(data_files['throughput_file'], 2)
    avg_rtt = read_csv(data_files['avg_rtt_file'])
    fairness = read_csv(data_files['fairness_file'], 2)
    rtt = read_csv(data_files['rtt_file'])
    inflight = read_csv(data_files['inflight_file'])
    sending_rate = read_csv(data_files['sending_rate_file'])
    bbr_values = read_csv(data_files['bbr_values_file'], 6)
    bbr_total_values = read_csv(data_files['bbr_total_values_file'])
    cwnd_values = read_csv(data_files['cwnd_values_file'], 3)
    retransmissions = read_csv(data_files['retransmissions_file'], 1)
    retransmissions_interval = read_csv(data_files['retransmissions_interval_file'], 3)
    buffer_backlog = read_csv(data_files['buffer_backlog_file'])

    return PcapData(throughput=throughput,
                    rtt=rtt,
                    fairness=fairness,
                    inflight=inflight,
                    avg_rtt=avg_rtt,
                    sending_rate=sending_rate,
                    bbr_values=bbr_values,
                    bbr_total_values=bbr_total_values,
                    cwnd_values=cwnd_values,
                    retransmissions=retransmissions,
                    retransmissions_interval=retransmissions_interval,
                    buffer_backlog=buffer_backlog)


def read_csv(path, columns_per_connection=2):
    output = {}
    file_path = find_file(path)

    if file_path is None:
        raise IOError('File not found {}'.format(path))

    f = open_compressed_file(file_path)

    first_line = f.readline().split(';')[:-1]
    for line in f:
        split = line.split(';')
        for i in range(0, len(first_line), columns_per_connection):
            if split[i] == '':
                continue

            try:
                index = int(first_line[i])
            except ValueError:
                index = first_line[i]

            if index not in output:
                output[index] = tuple([[] for _ in range(0, columns_per_connection)])
            for column in range(0, columns_per_connection):
                output[index][column].append(float(split[i + column]))
    f.close()
    return output


def write_info_file(path, pcap_data):

    data_values = [
        ('Sending Rate', pcap_data.sending_rate, 1, False),
        ('Throughput', pcap_data.throughput, 1, False),
        ('Fairness', pcap_data.fairness, 1, False),
        ('Avg Rtt', pcap_data.avg_rtt, 1, False),
        ('Inflight', pcap_data.inflight, 1, False),
        ('BDP', pcap_data.bbr_values, 5, False),
        ('Buffer Backlog', pcap_data.buffer_backlog, 1, False)
    ]

    path = os.path.join(path, INFORMATION_FILE)
    f = open(path, 'w')

    f.write('Synchronized at:\n {}\n'.format(pcap_data.data_info.sync_phases))
    f.write('with durations:\n {}\n'.format(pcap_data.data_info.sync_duration))
    sync_duration = pcap_data.data_info.sync_duration
    if len(sync_duration) > 0:
        f.write('Avg:\n {}\n'.format(sum(sync_duration) / len(sync_duration)))
    else:
        f.write('Avg:\n 0\n')

    percentages = [1, 0.3]

    for percentage in percentages:
        f.write('\n{:-<58}\n\nValues used: last {}%\n'.format('', percentage * 100))

        for d in data_values:
            total = 0
            f.write('\n{}:\n'.format(d[0]))
            f.write('{:13}  {:>13}  {:>13}  {:>13}  {:>13}  {:>13}\n'.format('Connection',
                                                                             'Median', 'Mean',
                                                                             'Std Dev', 'Min',
                                                                             'Max'))
            for c, data in d[1].items():
                value_range = int(len(data[d[2]]) * percentage)
                if value_range < 1:
                    continue
                median = np.median(data[d[2]][-value_range:])
                mean = np.mean(data[d[2]][-value_range:])
                std = np.std(data[d[2]][-value_range:])
                min_value = np.min(data[d[2]][-value_range:])
                max_value = np.max(data[d[2]][-value_range:])
                f.write('{:13}  {:>13.3f}  {:>13.3f}  {:>13.3f} {:>13.3f} {:>13.3f}\n'.format(
                    str(c), median, mean, std, min_value, max_value))

    f.close()
