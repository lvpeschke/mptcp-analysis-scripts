#!/usr/bin/env python
from __future__ import print_function

import argparse
import pickle
import sys

import numpy as np
import pandas as pd

import common as co
import mptcp
import tcp

# pandas print options
pd.options.display.precision = 2
line = '--------------------------------------------------'

H_LINK = 'link'
H_RATIO = 'ratio'
H_MBPS = '(Mbps)'
H_MS = '(ms)'

H_TRAFFIC_MB = 'traffic (MB)'
H_UNIQUE_TRAFFIC_MB = 'unique traffic (MB)'
H_RETRANS_MB = 'retransmissions (MB)'
H_REINJ_MB = 'reinjections (MB)'
H_TRAFFIC_PERC = 'traffic (% of total)'
H_TRAFFIC_PKTS = 'traffic (pkts)' # extra
H_RETRANS_PKTS = 'retransmissions (pkts)'
H_REINJ_PKTS = 'reinjections (pkts)'
H_RTO_PKTS = 'RTO (pkts)'
H_UNNEC_RTO_PKTS = 'unnecessary RTO (pkts)'

H_SEG_PERF = 'segment performance (s/s)'


def values_per_flows(connection, nb_flows, direction, value, adjust=1):
    assert direction == co.S2C or direction == co.C2S

    if type(connection) is tcp.TCPConnection:
        ret = [connection.flow.attr[direction][value] * adjust if value in connection.flow.attr[direction] else None]

    elif type(connection) is mptcp.MPTCPConnection:
        if not len(connection.flows) == nb_flows:
            raise ValueError('MPTCP connection does not have the required amount of flows')

        ret = [connection.flows[i].attr[direction][value] * adjust
               if value in connection.flows[i].attr[direction]
               else None
               for i in range(nb_flows)]

    else:
        raise TypeError('Not a TCPConnection, nor a MPTCPConnection.')

    return ret


def sum_values_per_flows(connections, nb_flows, direction, value, adjust=1):
    assert direction == co.S2C or direction == co.C2S

    ret = [0] * nb_flows  # single flow if tcp
    if all(type(e) is tcp.TCPConnection for e in connections.values()):
        for idx, conn in connections.iteritems():
            if value in conn.flow.attr[direction]:
                ret[0] += conn.flow.attr[direction][value]
            else:
                print('>> "{}" not in TCP conn {} dir {}'.format(value, idx, direction))

    elif all(type(e) is mptcp.MPTCPConnection for e in connections.values()):
        if not all(len(conn.flows) == nb_flows for conn in connections.itervalues()):
            less_flow = []
            for idx, conn in connections.iteritems():
                if len(conn.flows) < nb_flows:
                    less_flow.append((idx, len(conn.flows)))
            print('Careful!', len(less_flow), 'conns with less subflows (val =', value, '):', str(less_flow))

        for idx, conn in connections.iteritems():
            # print('conn idx is:', idx)
            for flow_idx in conn.flows.keys():
                # print('flow idx is:', flow_idx)
                if value in conn.flows[flow_idx].attr[direction]:
                    ret[flow_idx] += conn.flows[flow_idx].attr[direction][value]
                else:
                    print('>> "{}" not in MPTCP conn {} flow {} dir {}'.format(value, idx, flow_idx, direction))
    else:
        raise TypeError('Not all TCPConnection, nor all MPTCPConnection.')

    ret = [r * adjust for r in ret]
    return ret


def find_max_attr_connection(connections, attr=co.DURATION):
    maxi = -1
    idxi = -1
    for idx, conn in connections.iteritems():
        # print(conn.attr.keys())
        if type(conn) is mptcp.MPTCPConnection and conn.attr[attr] > maxi:
            maxi = conn.attr[attr]
            idxi = idx
            if maxi > (300 - 1):
                print('{} of MPTCP conn {} is {}'.format(attr, idxi, maxi))
        elif type(conn) is tcp.TCPConnection and conn.flow.attr[attr] > maxi:
            maxi = conn.flow.attr[attr]
            idxi = idx
            if maxi > (300 - 1):
                print('{} of TCP conn {} is {}'.format(attr, idxi, maxi))
    return idxi, maxi


def main(infile, total_bandwidth, ratio, delays):
    with open(infile, 'r') as f:
        content = pickle.load(f)
        if type(content) is dict:
            n = len(content)  # number of connections
            total_MB = None  # total video traffic (MB)
            print('content has {} entries'.format(n))

            if n == 2:  # MPD connection (less bytes) + video connection (more bytes)
                if all(type(e) is tcp.TCPConnection for e in content.values()):
                    if content[2].flow.attr[co.S2C][co.BYTES] > content[1].flow.attr[co.S2C][co.BYTES]:
                        mpd_conn = (1, '?')
                        video_content = content[2]
                    else:
                        mpd_conn = (2, '?')
                        video_content = content[1]
                elif all(type(e) is mptcp.MPTCPConnection for e in content.values()):
                    if content[2].attr[co.S2C][co.BYTES_MPTCPTRACE] > content[1].attr[co.S2C][co.BYTES_MPTCPTRACE]:
                        mpd_conn = (1, '?')
                        video_content = content[2]
                    else:
                        mpd_conn = (2, '?')
                        video_content = content[1]
                else:
                    raise ValueError('{} connections'.format(n))
                get_values = values_per_flows
            elif n > 2:  # MPD connection (idx to be found) + many video connections (all other idxs)
                mpd_conn = find_max_attr_connection(content)
                video_content = dict(content)  # copy the original
                del video_content[mpd_conn[0]]  # delete mpd connection
                print('video_content has {} entries'.format(len(video_content)))
                get_values = sum_values_per_flows
            else:
                raise ValueError('{} connections'.format(n))

            if all(type(e) is mptcp.MPTCPConnection for e in content.values()):  # pure MPTCP
                m = True
                nb_flows = 2
                if n == 2:
                    total_MB = float(content[n].attr[co.S2C][co.BYTES_MPTCPTRACE] * 10 ** (-6))
                else:
                    total_MB = float(sum(conn.attr[co.S2C][co.BYTES_MPTCPTRACE]
                                         for conn in video_content.values()) * 10 ** (-6))
            elif all(type(e) is tcp.TCPConnection for e in content.values()):  # pure TCP
                m = False
                nb_flows = 1
            else:
                raise TypeError('Not all TCPConnection, nor all MPTCPConnection.')

            data = pd.DataFrame(
                    {
                        'conns': [n - 1] * nb_flows,
                        'conn mpd': [mpd_conn] * nb_flows,

                        # per flow
                        H_TRAFFIC_MB:
                            get_values(video_content, nb_flows, co.S2C, co.BYTES_DATA, 10 ** (-6)), # = total
                        H_UNIQUE_TRAFFIC_MB:
                            get_values(video_content, nb_flows, co.S2C, co.BYTES, 10 ** (-6)), # = unique
                        H_RETRANS_MB:
                            get_values(video_content, nb_flows, co.S2C, co.BYTES_RETRANS, 10 ** (-6)),
                        H_TRAFFIC_PERC:
                            np.divide(get_values(video_content, nb_flows, co.S2C, co.BYTES_DATA, 10 ** (-6)),
                                      total_MB / 100) if m and total_MB is not None
                            else [100.0] * nb_flows,

                        # = flow total / connection total
                        H_TRAFFIC_PKTS:
                            get_values(video_content, nb_flows, co.S2C, co.PACKS),
                        H_RETRANS_PKTS:
                            get_values(video_content, nb_flows, co.S2C, co.PACKS_RETRANS),
                        H_RTO_PKTS:
                            get_values(video_content, nb_flows, co.S2C, co.NB_RTX_RTO),
                        H_UNNEC_RTO_PKTS:
                            get_values(video_content, nb_flows, co.S2C, co.NB_UNNECE_RTX_RTO),

                        # mptcp
                        H_REINJ_MB:
                            get_values(video_content, nb_flows, co.S2C, co.REINJ_ORIG_BYTES, 10 ** (-6)) if m
                            else [''] * nb_flows,
                        H_REINJ_PKTS:
                            get_values(video_content, nb_flows, co.S2C, co.REINJ_ORIG_PACKS) if m
                            else [''] * nb_flows,

                        # for LaTeX
                        H_LINK: ['link 1', 'link 2'] if m else ['link 1'],
                        H_RATIO: [ratio, 1.0 - ratio] if m else [1],
                        H_MBPS: [ratio * total_bandwidth, (1 - ratio) * total_bandwidth] if m else [total_bandwidth],
                        H_MS: delays,
                        H_SEG_PERF: [''] * nb_flows,

                    }, index=[range(1, nb_flows + 1)])

            # columns = [H_LINK, H_RATIO, H_MBPS, H_MS,
            #            H_TRAFFIC_MB, H_UNIQUE_TRAFFIC_MB, H_RETRANS_MB, H_REINJ_MB, H_TRAFFIC_PERC,
            #            H_RETRANS_PKTS, H_REINJ_PKTS, H_RTO_PKTS, H_UNNEC_RTO_PKTS, H_SEG_PERF]
            columns = [H_LINK, H_RATIO, H_MBPS, H_MS,
                       H_TRAFFIC_PERC, H_RETRANS_PKTS, H_RTO_PKTS, H_UNNEC_RTO_PKTS, H_REINJ_PKTS]
            column_format = 'lSSSSSSSS'
            assert len(columns) == len(column_format)
            latex = data.to_latex(columns=columns, column_format=column_format, col_space=None,
                                  header=True, index=False, index_names=False, bold_rows=False,
                                  formatters=None, float_format=None, sparsify=None,
                                  longtable=None, escape=True, encoding='utf-8',
                                  na_rep='NaN', decimal='.')

            # LaTeX to console
            print(line)
            print(latex)
            print(line)

            return data

        else:
            raise TypeError('Not a dict.')


if __name__ == '__main__':
    print(__file__, 'is __main__')

    parser = argparse.ArgumentParser()
    parser.add_argument('infile',
                        type=str, # argparse.FileType('r'),
                        help='file name or path')
    parser.add_argument('bandwidth',
                        type=float,
                        help='total configured bandwidth')
    parser.add_argument('ratio',
                        type=float,
                        help='ratio')
    parser.add_argument('delays',
                        type=int,
                        nargs='+',
                        help='delay(s)')
    parser.add_argument('-v', '--version',
                        action='version',
                        version=__file__ + ' version 29 December 2016')
    args = parser.parse_args()
    print(__file__, 'arguments are...', str(args))

    assert args.bandwidth > 0
    assert 0 < args.ratio <= 1
    assert all(d > 0 for d in args.delays)

    sys.exit(main(infile=args.infile, total_bandwidth=args.bandwidth, ratio=args.ratio, delays=args.delays))
