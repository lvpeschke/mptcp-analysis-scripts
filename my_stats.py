#!/usr/bin/env python
from __future__ import print_function

import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd

import common as co
import mptcp
import tcp

# import six

# pandas print options
pd.options.display.precision = 4
line = '--------------------------------------------------'


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
    # print(type(connections))
    # print(connections.keys())
    # for conn, second in connections.iteritems():
    #     print(type(conn), 'and', type(second))

    ret = [0] * nb_flows  # single flow if tcp
    if all(type(e) is tcp.TCPConnection for e in connections.values()):
        for idx, conn in connections.iteritems():
            if value in conn.flow.attr[direction]:
                ret[0] += conn.flow.attr[direction][value]
            else:
                print('>> "{}" not in TCP conn {} dir {}'.format(value, idx, direction))

    elif all(type(e) is mptcp.MPTCPConnection for e in connections.values()):
        if not all(len(conn.flows) == nb_flows for conn in connections.itervalues()):
            raise ValueError('all MPTCP connections do not have the required amount of flows')

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

    # print('ret is', ret)
    ret = [r * adjust for r in ret]
    return ret

# def get_sum_values_for_all_conns(connections, direction, value):
#     assert direction == co.S2C or direction == co.C2S
#
#     return sum(conn.attr[direction][value] for conn in connections)


def find_max_duration_connection(connections):
    maxi = -1
    idxi = -1
    for idx, conn in connections.iteritems():
        # print(conn.attr.keys())
        if type(conn) is mptcp.MPTCPConnection and conn.attr[co.DURATION] > maxi:
            maxi = conn.attr[co.DURATION]
            idxi = idx
            if maxi > (300 - 1):
                print('duration of MPTCP conn {} is {}'.format(idxi, maxi))
        elif type(conn) is tcp.TCPConnection and conn.flow.attr[co.DURATION] > maxi:
            maxi = conn.flow.attr[co.DURATION]
            idxi = idx
            if maxi > (300 - 1):
                print('duration of TCP conn {} is {}'.format(idxi, maxi))
    return idxi, maxi


def main(infile):
    with open(infile, 'r') as f:
        content = pickle.load(f)
        # print('infile is', infile)
        if type(content) is dict:
            # and (all(type(e) is mptcp.MPTCPConnection for e in content.values()) or
            #                               all(type(e) is tcp.TCPConnection for e in content.values())):
            # for e in content:
            #     print(type(e))
            n = len(content)
            if all(type(e) is mptcp.MPTCPConnection for e in content.values()):
                m = True
                nb_flows = 2
            elif all(type(e) is tcp.TCPConnection for e in content.values()):
                m = False
                nb_flows = 1
            else:
                raise TypeError('Not all TCPConnection, nor all MPTCPConnection.')

            if n == 2:  # MPD connection (idx 1) + video connection (idx 2)
                print('content has {} entries'.format(len(content)))
                # print(content)
                # print(content[n].attr.keys())
                # print(content[2].flows[0].attr[co.S2C].keys())
                data = pd.DataFrame(
                        {# 'file name': [os.path.basename(infile)] * nb_flows,
                            'conn nb': [n] * nb_flows,

                            # per flow
                            'S2C MB data':
                                values_per_flows(content[n], nb_flows, co.S2C, co.BYTES_DATA, 10 ** (-6)), # = total
                            'S2C MB unique':
                                values_per_flows(content[n], nb_flows, co.S2C, co.BYTES, 10 ** (-6)), # = unique
                            'S2C MB retrans':
                                values_per_flows(content[n], nb_flows, co.S2C, co.BYTES_RETRANS, 10 ** (-6)),
                            'S2C MB data/total %':
                                np.divide(values_per_flows(content[n], nb_flows, co.S2C, co.BYTES_DATA, 10 ** (-6)),
                                          float(content[n].attr[co.S2C][co.BYTES_MPTCPTRACE] * 10 ** (-6) / 100)) if m
                                else [100.0] * nb_flows,

                            # = flow total / connection total
                            'S2C pkts data':
                                values_per_flows(content[n], nb_flows, co.S2C, co.PACKS),
                            'S2C pkts retrans':
                                values_per_flows(content[n], nb_flows, co.S2C, co.PACKS_RETRANS),
                            'S2C pkts RTO':
                                values_per_flows(content[n], nb_flows, co.S2C, co.NB_RTX_RTO),
                            'S2C pkts RTO unn':
                                values_per_flows(content[n], nb_flows, co.S2C, co.NB_UNNECE_RTX_RTO),

                            # mptcp
                            'S2C MB reinj':
                                values_per_flows(content[n], nb_flows, co.S2C, co.REINJ_ORIG_BYTES, 10 ** (-6)) if m
                                else ['tcp'] * nb_flows,
                            'S2C pkts reinj':
                                values_per_flows(content[n], nb_flows, co.S2C, co.REINJ_ORIG_PACKS) if m
                                else ['tcp'] * nb_flows,

                            # whole connection
                            # 'S2C bytes mptcptrace': ([None] * n).append(content[2].attr[co.S2C][co.BYTES_MPTCPTRACE]),
                            # 'S2C retrans_dss': ([None] * n).append(content[2].attr[co.S2C][co.RETRANS_DSS]),
                            # 'S2C reinj_bytes': ([None] * n).append(content[2].attr[co.S2C][co.REINJ_BYTES]),
                            # 'S2C reinj_pc': ([None] * n).append(content[2].attr[co.S2C][co.REINJ_PC]),

                        }, index=[range(1, nb_flows + 1)])

                print('\n* Data from', os.path.basename(infile), ':\n', line, '\n', data, '\n', line, '\n')

            elif n > 2:  # MPD connection + many video connections
                print('content has {} entries'.format(len(content)))
                mpd_conn_idx = find_max_duration_connection(content)
                video_content = dict(content)  # copy the original
                del video_content[mpd_conn_idx[0]]  # delete mpd connection
                print('video_content has {} entries'.format(len(video_content)))
                # if m:
                #   total_bytes = float(sum(conn.attr[co.S2C][co.BYTES_MPTCPTRACE] for conn in video_content.values()))
                # else:
                #   total_bytes = float(sum(conn.flow.attr[co.S2C][co.BYTES_DATA] for conn in video_content.values()))

                data = pd.DataFrame(
                        {# 'file name': [os.path.basename(infile)] * nb_flows,
                            'conn nb': ['all video'] * nb_flows,
                            'conns': [len(video_content)] * nb_flows,
                            'conn mpd': [mpd_conn_idx] * nb_flows,

                            # sums per flow
                            'S2C MB data':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.BYTES_DATA, 10 ** (-6)), # = total
                            'S2C MB unique':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.BYTES, 10 ** (-6)), # = unique
                            'S2C MB retrans':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.BYTES_RETRANS, 10 ** (-6)),

                            'S2C MB data/total %':
                                np.divide(
                                    sum_values_per_flows(video_content, nb_flows, co.S2C, co.BYTES_DATA, 10 ** (-6)),
                                    float(sum(conn.attr[co.S2C][co.BYTES_MPTCPTRACE]
                                              for conn in video_content.values())) * 10 ** (-6) / 100) if m
                                else [100.0] * nb_flows,
                            # = flow total / connection total
                            'S2C packets':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.PACKS),
                            'S2C pkts retrans':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.PACKS_RETRANS),
                            'S2C RTO':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.NB_RTX_RTO),
                            'S2C RTO unn':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.NB_UNNECE_RTX_RTO),

                            # mptcp
                            'S2C MB reinj':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.REINJ_ORIG_BYTES, 10 ** (-6)) if m
                                else ['tcp'] * nb_flows,
                            'S2C pkts reinj':
                                sum_values_per_flows(video_content, nb_flows, co.S2C, co.REINJ_ORIG_PACKS) if m
                                else ['tcp'] * nb_flows,

                        }, index=[range(1, nb_flows + 1)])
                print('\n* Data from', os.path.basename(infile), ':\n', line, '\n', data, '\n', line, '\n')

            else:
                raise ValueError('{} connections'.format(n))

        else:
            raise TypeError('Not a dict.')


if __name__ == '__main__':
    print(__file__, 'is __main__')

    parser = argparse.ArgumentParser()
    parser.add_argument('infile',
                        type=str, # argparse.FileType('r'),
                        help='file name or path')
    parser.add_argument('-v', '--version',
                        action='version',
                        version=__file__ + ' version 29 December 2016')
    args = parser.parse_args()
    print(__file__, 'arguments are...', str(args))

    sys.exit(main(infile=args.infile))
