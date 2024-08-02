import numpy as np
import os
import errno
import math

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from helper.pcap_data import PcapData
from helper import PLOT_PATH, PLOT_TYPES
from helper.util import print_line
from helper import TEXT_WIDTH

PLOT_TOTAL = True


class Plot:
    def __init__(self, data, plot_function, file_name, plot_name, unit, number):
        self.data = data
        self.plot_function = plot_function
        self.file_name = file_name
        self.plot_name = plot_name
        self.unit = unit
        self.number = number


def plot_all(path, pcap_data, plot_only, hide_total=False, all_plots=False):

    global PLOT_TOTAL
    PLOT_TOTAL = not hide_total

    path = os.path.join(path, PLOT_PATH)

    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

    pcap_data = shift_timestamps(pcap_data)

    throughput = pcap_data.throughput
    fairness = pcap_data.fairness
    rtt = pcap_data.rtt
    inflight = pcap_data.inflight
    avg_rtt = pcap_data.avg_rtt
    sending_rate = pcap_data.sending_rate
    bbr_values = pcap_data.bbr_values
    bbr_total_values = pcap_data.bbr_total_values
    cwnd_values = pcap_data.cwnd_values
    retransmissions = pcap_data.retransmissions
    retransmissions_interval = pcap_data.retransmissions_interval
    buffer_backlog = pcap_data.buffer_backlog

    t_max = pcap_data.get_max_ts()
    t_min = pcap_data.get_min_ts()
    plots = []

    if 'sending_rate' in plot_only:
        plots += [
            Plot((sending_rate, retransmissions), plot_sending_rate, 'plot_sending_rate.pdf', 'Sending Rate', 'bit/s', len(sending_rate))
        ]

    if 'throughput' in plot_only:
        plots += [
            Plot((throughput, retransmissions), plot_throughput, 'plot_throughput.pdf', 'Throughput', 'bit/s', len(throughput))
        ]

    if 'fairness' in plot_only and len(sending_rate.keys()) > 2:
        plots += [
            Plot(fairness, plot_fairness, 'plot_fairness.pdf', 'Fairness', "Jain's Index", len(fairness))
        ]

    if 'retransmission' in plot_only:
        plots += [
            Plot(retransmissions_interval, plot_retransmissions, 'plot_retransmissions.pdf', 'Retransmissions', '#', len(retransmissions_interval)),
            Plot(retransmissions_interval, plot_retransmission_rate, 'plot_retransmission_rate.pdf', 'Retransmission Rate', '%', 1),
        ]

    if 'avg_rtt' in plot_only:
        plots += [
            Plot(avg_rtt, plot_avg_rtt, 'plot_avg_rtt.pdf', 'Avg RTT', 'ms', len(avg_rtt))
        ]

    if 'rtt' in plot_only:
        plots += [
            Plot(rtt, plot_rtt, 'plot_rtt.pdf', 'RTT', 'ms', len(rtt))
        ]

    if 'inflight' in plot_only:
        plots += [
            Plot(inflight, plot_inflight, 'plot_inflight.pdf', 'Inflight', 'bit', len(inflight))
        ]

    if 'cwnd' in plot_only:
        plots += [
            Plot(cwnd_values, plot_cwnd, 'plot_cwnd.pdf', 'CWnd', 'MSS', 2)
        ]

    if 'buffer_backlog' in plot_only and len(buffer_backlog) > 0:
        plots += [
            Plot((buffer_backlog, retransmissions), plot_buffer_backlog, 'plot_buffer_backlog.pdf', 'Buffer Backlog', 'bit', len(buffer_backlog))
        ]

    has_bbr = False
    for i in bbr_values:
        if len(bbr_values[i][0]) > 0:
            has_bbr = True
            break

    if 'bdp' in plot_only and has_bbr:
        plots += [
            Plot(bbr_values, plot_bbr_bdp, 'plot_bbr_bdp.pdf', 'BDP', 'bit', len(bbr_values)),
            # Plot((inflight, bbr_values), plot_diff_inflight_bdp, 'plot_inflight_div_bdp.pdf', 'Inflight/BDP', ''),
        ]

    if 'btl_bw' in plot_only and has_bbr:
        plots += [
            Plot((bbr_values, bbr_total_values), plot_bbr_bw, 'plot_bbr_bw.pdf', 'BtlBw', 'bit/s', len(bbr_values)),
        ]

    if 'rt_prop' in plot_only and has_bbr:
        plots += [
            Plot(bbr_values, plot_bbr_rtt, 'plot_bbr_rtt.pdf', 'RTprop', 'ms', len(bbr_values)),
        ]

    if 'window_gain' in plot_only and has_bbr:
        plots += [
            Plot((bbr_values, bbr_total_values), plot_bbr_window, 'plot_bbr_window.pdf', 'Window Gain', '', len(bbr_values)),
        ]

    if 'pacing_gain' in plot_only and has_bbr:
        plots += [
            Plot((bbr_values, bbr_total_values), plot_bbr_pacing, 'plot_bbr_pacing.pdf', 'Pacing Gain', '', len(bbr_values))
        ]

    if all_plots:
        for plot in plots:
            print_line('  *  {} ...'.format(plot.plot_name), new_line=False)
            f, ax = plt.subplots(1)
            f.set_size_inches(20, 10)

            label = plot.plot_name
            if plot.unit != '':
                label += ' in {}'.format(plot.unit)

            setup_ax(ax=ax, title=plot.plot_name, label=label, xmin=t_min, xmax=t_max)
            plot.plot_function(plot.data, ax)

            legend = ax.legend(loc='upper left', bbox_to_anchor=(0, -0.04, 1, 0), mode='expand', borderaxespad=0.1, ncol=20,
                               shadow=True, fancybox=True)

            f.savefig(os.path.join(path, plot.file_name), bbox_extra_artists=(legend, ), bbox_inches='tight')
            plt.close()
            print('  *  {} created'.format(plot.plot_name))

    f, axarr = plt.subplots(len(plots), sharex=True)

    if len(plots) == 1:
        axarr = [axarr]

    pdf_height = 60.0 * float(len(plots)) / len(PLOT_TYPES)
    f.set_size_inches(20, pdf_height)
    max_legend_rows = 1

    for i, plot in enumerate(plots):
        print_line('     -  Complete plot: {} ...'.format(plot.plot_name).ljust(TEXT_WIDTH))
        label = plot.plot_name
        if plot.unit != '':
            label += ' in {}'.format(plot.unit)

        title = '{}. {}'.format(i + 1, plot.plot_name)
        setup_ax(ax=axarr[i], title=title, label=label, xmin=t_min, xmax=t_max)
        plot.plot_function(plot.data, axarr[i])

        legend_offset = -0.04
        if i == len(plots) - 1:
            legend_offset = -0.08
        legend = axarr[i].legend(loc='upper left', bbox_to_anchor=(0, legend_offset, 1, 0),
                                 borderaxespad=0, ncol=20,shadow=True, fancybox=True, mode='expand')

        max_legend_rows = max(max_legend_rows, math.ceil(plot.number / 20.0))

    print_line('  *  Complete plot ...'.ljust(TEXT_WIDTH))
    plt.tight_layout(h_pad=1 + 1.5 * max_legend_rows)
    plt.savefig(os.path.join(path, 'plot_complete.pdf'), bbox_extra_artists=(legend, ), bbox_inches='tight')

    plt.close()
    print('  *  Complete plot created'.ljust(TEXT_WIDTH))


def setup_ax(ax, title , label, xmin, xmax):
    grid_tick_maior_interval = 10
    grid_tick_minor_interval = 2

    ax.set_xticks(np.arange(xmin, xmax, grid_tick_maior_interval))
    ax.set_xticks(np.arange(xmin, xmax, grid_tick_minor_interval), minor=True)
    ax.grid(which='both', color='black', linestyle='dashed', alpha=0.4)

    ax.set_ylabel(label)
    ax.set_title(title)
    ax.set_xlim(left=xmin, right=xmax)


def plot_throughput(data, p_plt):
    throughput = data[0]
    retransmissions = data[1]
    total = len(throughput) - 1

    if total > 1 and PLOT_TOTAL:
        data = throughput['total']
        data = filter_smooth(data, 5, 2)
        p_plt.plot(data[0], data[1], label='Total', color='#444444')

    for c in throughput:
        data = throughput[c]
        data = filter_smooth(data, 5, 2)

        if c != 'total':
            p_plt.plot(data[0], data[1], label='{}'.format(c))

    for c in retransmissions:
        data = retransmissions[c]
        p_plt.plot(data, np.zeros_like(data), '.', color='red')


def plot_sending_rate(data, p_plt):
    sending_rate = data[0]
    retransmissions = data[1]
    total = len(sending_rate) - 1

    if total > 1 and PLOT_TOTAL:
        data = sending_rate['total']
        data = filter_smooth(data, 5, 2)
        p_plt.plot(data[0], data[1], label='Total', color='#444444')

    for c in sending_rate:
        data = sending_rate[c]
        data = filter_smooth(data, 5, 2)

        if c != 'total':
            p_plt.plot(data[0], data[1], label='{}'.format(c))

    for c in retransmissions:
        data = retransmissions[c]
        p_plt.plot(data, np.zeros_like(data), '.', color='red')


def plot_fairness(fairness, p_plt):
    for c in fairness:
        data = filter_smooth((fairness[c][0], fairness[c][1]), 10, 2)
        p_plt.plot(data[0], data[1], label=c)

    p_plt.set_ylim(bottom=0, top=1.1)


def plot_rtt(rtt, p_plt):
    for c in rtt:
        data = rtt[c]
        p_plt.plot(data[0], data[1], label='{}'.format(c))
    p_plt.set_ylim(bottom=0)


def plot_avg_rtt(avg_rtt, p_plt):
    for c in avg_rtt:
        data = avg_rtt[c]
        data = filter_smooth(data, 3, 2)
        p_plt.plot(data[0], data[1], label='{}'.format(c))
    p_plt.set_ylim(bottom=0)


def plot_inflight(inflight, p_plt):
    for c in inflight:
        data = inflight[c]
        data = filter_smooth(data, 5, 1)
        p_plt.plot(data[0], data[1], label='{}'.format(c))


def plot_buffer_backlog(data, p_plt):
    buffer_backlog = data[0]
    retransmissions = data[1]
    for c in buffer_backlog:
        data = buffer_backlog[c]

        if len(data[0]) < 1:
            continue
        data = filter_smooth(data, 5, 2)
        p_plt.plot(data[0], data[1], label='Buffer Backlog {}'.format(c))

    for c in retransmissions:
        data = retransmissions[c]
        p_plt.plot(data, np.zeros_like(data), '.', color='red')


def plot_bbr_bw(data, p_plt):
    bbr = data[0]
    bbr_bw_total = data[1]

    num_flows = 0
    for c in bbr:
        data = bbr[c]
        p_plt.plot(data[0], data[1], label='{}'.format(c))
        if len(data[0]) > 0:
            num_flows += 1

    if len(bbr) > 2 and num_flows > 1 and PLOT_TOTAL:
        p_plt.plot(bbr_bw_total[0][0], bbr_bw_total[0][1], label='Total', color='#444444')


def plot_bbr_rtt(bbr, p_plt):
    for c in bbr:
        data = bbr[c]
        p_plt.plot(data[0], data[2], label='{}'.format(c))


def plot_bbr_pacing(data, p_plt):
    bbr, total = data
    for c in bbr:
        data = bbr[c]
        p_plt.plot(data[0], data[3], label='{}'.format(c))
    #if len(bbr) > 1:
    #    p_plt.plot(total[2][0], total[2][1], label='Total', color='#444444')


def plot_bbr_window(data, p_plt):
    bbr, total = data
    num_flows = 0
    for c in bbr:
        data = bbr[c]
        p_plt.plot(data[0], data[4], label='{}'.format(c))
        if len(data[0]) > 0:
            num_flows += 1
    if len(bbr) > 2 and num_flows > 1 and PLOT_TOTAL:
        p_plt.plot(total[1][0], total[1][1], label='Total', color='#444444')


def plot_bbr_bdp(bbr, p_plt):
    for c in bbr:
        data = bbr[c]
        p_plt.plot(data[0], data[5], label='{}'.format(c))


def plot_cwnd(cwnd, p_plt):
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

    p_plt.plot([], [], label='CWND', color='black')
    p_plt.plot([], [], ':', label='SSTHRES', color='black')
    p_plt.legend()

    for i, c in enumerate(cwnd):
        data = cwnd[c]
        p_plt.plot(data[0], data[1], color=colors[i % len(colors)])
        p_plt.plot(data[0], data[2], ':', color=colors[i % len(colors)])


def plot_retransmissions(ret_interval, p_plt):
    plot_sum = (ret_interval['total'][0][:],
                ret_interval['total'][1][:])
    total_sum = 0
    for c in ret_interval:

        if c == 'total':
            continue

        data = ret_interval[c]
        total_loss = int(sum(data[1]))
        total_sum += total_loss
        p_plt.bar(plot_sum[0], plot_sum[1], plot_sum[0][1], label=total_loss)
        for i, value in enumerate(data[0]):
            if value in plot_sum[0]:
                plot_sum[1][plot_sum[0].index(value)] -= data[1][i]

    p_plt.bar(plot_sum[0], plot_sum[1], plot_sum[0][1], label='Total {}'.format(total_sum), color='black')


def plot_retransmission_rate(ret_interval, p_plt):

    for c in ret_interval:

        data = ret_interval[c]

        rate = []
        ts = data[0]

        for i,_ in enumerate(data[1]):
            if data[2][i] == 0:
                rate.append(0)
            else:
                rate.append(float(data[1][i]) / float(data[2][i]) * 100)

        if c == 'total':
            p_plt.plot(ts, rate, label='Total Retransmission Rate', color='black')
        else:
            p_plt.plot(ts, rate, label='{}'.format(c), alpha=0.3)

    p_plt.set_ylim(bottom=0)


def plot_diff_inflight_bdp(data, p_plt):
    inflight = data[0]
    bbr = data[1]
    for c in inflight:

        if c not in bbr:
            continue

        ts = []
        diff = []

        bbr_ts = bbr[c][0]
        bdp = bbr[c][5]

        for i, t1 in enumerate(inflight[c][0]):
            for j, t2 in enumerate(bbr_ts):
                if t1 > t2:
                    ts.append(t2)
                    if bdp[j] == 0:
                        diff.append(0)
                    else:
                        diff.append((inflight[c][1][i]) / bdp[j])
                else:
                    bbr_ts = bbr_ts[j:]
                    bdp = bdp[j:]
                    break
        ts, diff = filter_smooth((ts, diff), 10, 5)
        p_plt.plot(ts, diff, label='{}'.format(c))


def filter_smooth(data, size, repeat=1):
    x = data[0]
    y = data[1]

    if repeat == 0:
        return x, y

    size = int(math.ceil(size / 2.0))
    for _ in range(1, repeat):
        y_smooth = []
        for i in range(0, len(y)):
            avg = 0
            avg_counter = 0
            for j in range(max(0, i - size), min(i + size, len(y) - 1)):
                avg += y[j]
                avg_counter += 1
            if avg_counter > 0:
                y_smooth.append(avg / avg_counter)
            else:
                y_smooth.append(0)
        y = y_smooth
    return x, y


def filter_percentile(data, percentile_min=0.0, percentile_max=0.0):
    min_size = int(math.floor(percentile_min * len(data[0])))
    max_size = int(math.floor(percentile_max * len(data[0])))

    y, x = zip(*sorted(zip(data[1], data[0])))
    if max_size > 0:
        x = x[min_size:-max_size]
        y = y[min_size:-max_size]
    else:
        x = x[min_size:]
        y = y[min_size:]

    x, y = zip(*sorted(zip(x, y)))

    return x, y


def shift_timestamps(data):
    t_min = data.get_min_ts()
    data = data.values_as_dict()

    for v in data:
        for c in data[v]:
            data[v][c][0][:] = [x - t_min for x in data[v][c][0]]

    return PcapData.from_dict(data)