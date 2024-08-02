TEXT_WIDTH = 60


BUFFER_FILE_EXTENSION = 'buffer'
FLOW_FILE_EXTENSION = 'bbr'


PCAP1 = 's1.pcap'
PCAP2 = 's3.pcap'


PLOT_PATH = 'pdf_plots'
PLOT_TYPES = [
    'sending_rate',
    'throughput',
    'fairness',
    'retransmission',
    'avg_rtt',
    'rtt',
    'inflight',
    'cwnd',
    'buffer_backlog',
    'bdp',
    'btl_bw',
    'rt_prop',
    'window_gain',
    'pacing_gain',
]


COMPRESSION_METHODS = ['none', 'gzip', 'bzip2']
COMPRESSION_EXTENSIONS = {
    'none': '',
    'gzip': '.gz',
    'bzip2': '.bz2',
}


CSV_PATH = 'csv_data'
CSV_FILE_NAMES = {
    'rtt': 'rtt.csv',
    'throughput': 'throughput.csv',
    'fairness': 'fairness.csv',
    'inflight': 'inflight.csv',
    'avg_rtt': 'avg_rtt.csv',
    'sending_rate': 'sending_rate.csv',
    'bbr_values': 'bbr_values.csv',
    'bbr_total_values': 'bbr_total_values.csv',
    'cwnd_values': 'cwnd_values.csv',
    'retransmissions': 'retransmissions.csv',
    'retransmissions_interval': 'retransmissions_interval.csv',
    'buffer_backlog': 'buffer_backlog.csv'
}

INFORMATION_FILE = 'values.info'

