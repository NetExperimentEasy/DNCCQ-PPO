import subprocess
import time
import sys
import gzip
import bz2
import re
import os

from helper import CSV_PATH, PLOT_PATH
from helper import PCAP1, PCAP2
from helper import FLOW_FILE_EXTENSION, BUFFER_FILE_EXTENSION, COMPRESSION_EXTENSIONS, COMPRESSION_METHODS

colors = {
    'red': '[1;31;40m',
    'green': '[1;32;40m',
    'yellow': '[1;33;40m',
}


def print_error(line):
    print(colorize(line, 'red'))


def print_warning(line):
    print(colorize(line, 'yellow'))


def print_success(line):
    print(colorize(line, 'green'))


def colorize(string, color=None):
    if color not in colors.keys():
        return string
    return '\x1b{color}{string}\x1b[0m'.format(color=colors[color], string=string)


def get_git_revision_hash():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.PIPE).rstrip()
    except subprocess.CalledProcessError as e:
        print_error(e)
        return 'unknown'


def get_host_version():
    try:
        return subprocess.check_output(['uname', '-ovr'], stderr=subprocess.PIPE).rstrip()
    except subprocess.CalledProcessError as e:
        print_error(e)
        return 'unknown'


def get_available_algorithms():
    try:
        return subprocess.getoutput(['sysctl net.ipv4.tcp_available_congestion_control '
                                        '| sed -ne "s/[^=]* = \(.*\)/\\1/p"'])
    except subprocess.CalledProcessError as e:
        print_error('Cannot retrieve available congestion control algorithms.')
        print_error(e)
        return ''


def check_tools():
    missing_tools = []
    tools = {
        'tcpdump': 'tcpdump',
        'ethtool': 'ethtool',
        'netcat': 'netcat',
        'moreutils': 'ts'
    }

    for package, tool in tools.items():
        if not check_tool(tool):
            missing_tools.append(package)

    if len(missing_tools) > 0:
        print_error('Missing tools. Please run')
        print_error('  apt install ' + ' '.join(missing_tools))

    return len(missing_tools)


def check_tool(tool):
    try:
        process = subprocess.Popen(['which', tool], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = process.communicate()[0]
        if out == "":
            return False
    except (OSError, subprocess.CalledProcessError) as e:
        return False
    return True


def print_line(string, new_line=False):
    if new_line:
        string += '\n'
    else:
        string += '\r'
    sys.stdout.write(string)
    sys.stdout.flush()


def print_timer(complete, current):
    share = current * 100.0 / complete

    string = '  {:6.2f}%'.format(share)
    if complete == current:
        string = colorize(string, 'green')

    string += ' ['
    string += '=' * int(share / 10 * 3)
    string += ' ' * (30 - int(share / 10 * 3))
    string += '] {:6.1f}s remaining'.format(complete - current)

    print_line(string, new_line=complete == current)


def sleep_progress_bar(seconds, current_time, complete):
    print_timer(complete=complete, current=current_time)
    while seconds > 0:
        time.sleep(min(1, seconds))
        current_time = current_time + min(1, seconds)
        print_timer(complete=complete, current=current_time)
        seconds -= 1
    return current_time


def compress_file(uncompressed_file, method):
    try:
        subprocess.check_call([method, uncompressed_file])

    except Exception as e:
        print_error('Error on compressing {}.\n {}'.format(uncompressed_file, e))


def find_file(path):
    for method in COMPRESSION_METHODS:
        ext = COMPRESSION_EXTENSIONS[method]
        if os.path.isfile(path + ext):
            return path + ext
    return None


def open_compressed_file(path, write=False):
    file_extension = os.path.splitext(path)[1].replace('.', '')

    options = {
        'gz': {
            'f': gzip.open,
            'r': 'rb',
            'w': 'wt',
        },
        'bz2': {
            'f': bz2.BZ2File,
            'r': 'rb',
            'w': 'wt',
        },
        'csv': {
            'f': open,
            'r': 'r',
            'w': 'w',
        },
        'pcap': {
            'f': open,
            'r': 'rb',
            'w': 'wb',
        },
        FLOW_FILE_EXTENSION: {
            'f': open,
            'r': 'r',
            'w': 'w',
        },
        BUFFER_FILE_EXTENSION: {
            'f': open,
            'r': 'r',
            'w': 'w',
        },
    }

    try:
        func = options[file_extension]['f']
        params = options[file_extension]['w' if write else 'r']
        return func(path, params)
    except Exception:
        raise Exception(f'Unknown file extension: {path}')


def check_directory(dir, only_new=False):

    pcap1_exists = find_file(os.path.join(dir, PCAP1)) is not None
    pcap2_exists = find_file(os.path.join(dir, PCAP2)) is not None

    if not pcap1_exists & pcap2_exists:
        return False

    if only_new:
        csv_path = os.path.join(dir, CSV_PATH)
        pdf_path = os.path.join(dir, PLOT_PATH)
        if os.path.exists(csv_path) and os.path.exists(pdf_path):
            return False

    return True


def get_ip_from_filename(filename):
    ip = os.path.splitext(os.path.basename(filename))[0]
    ip = re.findall(r'[0-9]+(?:\.[0-9]+){3}', ip)[0]
    return ip


def get_interface_from_filename(filename):
    intf = os.path.splitext(os.path.basename(filename))[0]
    intf = re.findall(r'[^=]*-[^=]*-', intf)[0]
    return intf[:-1]


