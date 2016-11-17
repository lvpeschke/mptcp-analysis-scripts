#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#  Copyright 2015 Quentin De Coninck
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#  To install on this machine: matplotlib, numpy

from __future__ import print_function

import argparse
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

# Add root directory in Python path and be at the root
ROOT_DIR = os.path.abspath(os.path.join(".", os.pardir))
os.chdir(ROOT_DIR)
sys.path.append(ROOT_DIR)

import common as co
import common_graph as cog
import mptcp
import tcp

##################################################
##                  ARGUMENTS                   ##
##################################################

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument("-s",
                    "--stat", help="directory where the stat files are stored", default=co.DEF_STAT_DIR + '_' + co.DEF_IFACE)
parser.add_argument('-S',
                    "--sums", help="directory where the summary graphs will be stored", default=co.DEF_SUMS_DIR + '_' + co.DEF_IFACE)
parser.add_argument("-d",
                    "--dirs", help="list of directories to aggregate", nargs="+")

args = parser.parse_args()
stat_dir_exp = os.path.abspath(os.path.join(ROOT_DIR, args.stat))
sums_dir_exp = os.path.abspath(os.path.join(ROOT_DIR, args.sums))
co.check_directory_exists(sums_dir_exp)
print('-s dir is', args.stat, 'and -S dir is', args.sums)

##################################################
##                 GET THE DATA                 ##
##################################################

connections = cog.fetch_valid_data(stat_dir_exp, args)
multiflow_connections, singleflow_connections = cog.get_multiflow_connections(connections)

##################################################
##               PLOTTING RESULTS               ##
##################################################


def has_two_opened_sfs(ts_delta, ts_delta_first_sent, idle_time, connection, direction):
    """ Return true if two SFs were available at ts_delta

        C                                     S
        ______________
                      \_SYN________________
                                           \->
                            __________________
           _________SYN/ACK/
        <-/
        ______________
                      \ACK_________________
                                           \->
                           ___________________ OK FOR SERVER TO START SENDING
                          /
           ____________ACK
        <-/
    OK FOR CLIENT TO START SENDING
    """
    count = 0
    for flow_id, flow in conn.flows.iteritems():
        if direction == co.C2S:
            # TODO should have one more attribute here...
            if co.START in flow.attr and ((ts_delta_first_sent - flow.attr[co.START]).total_seconds() >= 0.0
                                          and (ts_delta_first_sent - flow.attr[co.START]).total_seconds() <= flow.attr[co.DURATION]):
                count += 1
        else:
            if co.START in flow.attr and (((ts_delta_first_sent - idle_time - flow.attr[co.START]).total_seconds() - flow.attr[co.S2C][co.TIME_FIRST_ACK] >= 0.0
                                          and (ts_delta_first_sent - flow.attr[co.START]).total_seconds() <= flow.attr[co.DURATION])
                                          or (co.TIME_LAST_ACK_TCP in flow.attr
                                          and (flow.attr[co.TIME_LAST_ACK_TCP] - ts_delta).total_seconds() > 0.0)):
                count += 1

    return count >= 2


retransmissions_since_first = []
retransmissions_since_last = []
retransmissions_since_last_active = []
count_retrans_dss = []
for fname, conns in multiflow_connections.iteritems():
    for conn_id, conn in conns.iteritems():
        retrans_dss = {}
        for ts_delta, flow_id, dss, idle_time, retrans_since_first, retrans_since_last, retrans_since_last_all in conn.attr[co.S2C][co.RETRANS_DSS]:
            if conn.attr[co.S2C][co.RTT_SAMPLES] > 1 and has_two_opened_sfs(ts_delta, ts_delta - retrans_since_first, idle_time, conn, co.S2C):
                retransmissions_since_first.append(retrans_since_first.total_seconds() * 1000.0 / conn.attr[co.S2C][co.RTT_AVG])
                retransmissions_since_last.append(retrans_since_last.total_seconds() * 1000.0 / conn.attr[co.S2C][co.RTT_AVG])
                retransmissions_since_last_active.append(retrans_since_last_all.total_seconds() * 1000.0 / conn.attr[co.S2C][co.RTT_AVG])
                if dss not in retrans_dss:
                    retrans_dss[dss] = 0
                retrans_dss[dss] += 1

        for dss in retrans_dss.keys():
            if retrans_dss[dss] > 100000:
                print(fname, conn_id, dss, retrans_dss[dss])
            count_retrans_dss.append(retrans_dss[dss])

sample = np.array(sorted(retransmissions_since_first))
sorted_array = np.sort(sample)
yvals = np.arange(len(sorted_array)) / float(len(sorted_array))
if len(sorted_array) > 0:
    # Add a last point
    sorted_array = np.append(sorted_array, sorted_array[-1])
    yvals = np.append(yvals, 1.0)

    # Log plot
    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    ax.plot(sorted_array, yvals, color='red', linewidth=2, label="Retrans / RTT")

    # Shrink current axis's height by 10% on the top
    # box = ax.get_position()
    # ax.set_position([box.x0, box.y0,
    #                  box.width, box.height * 0.9])
    ax.set_xscale('log')

    # Put a legend above current axis
    # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)
    ax.legend(loc='lower right')

    plt.xlim(xmin=0.001)

    plt.xlabel('Retrans DSS Time / Avg RTT', fontsize=24, labelpad=-1)
    plt.ylabel("CDF", fontsize=24)
    plt.savefig(os.path.join(sums_dir_exp, 'retrans_dss.pdf'))
    plt.close('all')

sample = np.array(sorted(retransmissions_since_last))
sorted_array = np.sort(sample)
yvals = np.arange(len(sorted_array)) / float(len(sorted_array))
if len(sorted_array) > 0:
    # Add a last point
    sorted_array = np.append(sorted_array, sorted_array[-1])
    yvals = np.append(yvals, 1.0)

    # Log plot
    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    ax.plot(sorted_array, yvals, color='red', linewidth=2, label="Retrans / RTT")

    # Shrink current axis's height by 10% on the top
    # box = ax.get_position()
    # ax.set_position([box.x0, box.y0,
    #                  box.width, box.height * 0.9])
    ax.set_xscale('log')

    # Put a legend above current axis
    # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)
    ax.legend(loc='lower right')

    plt.xlabel('Retrans DSS Time / Avg RTT', fontsize=24, labelpad=-1)
    plt.ylabel("CDF", fontsize=24)
    plt.savefig(os.path.join(sums_dir_exp, 'retrans_dss_last.pdf'))
    plt.close('all')

sample = np.array(sorted(retransmissions_since_last_active))
sorted_array = np.sort(sample)
yvals = np.arange(len(sorted_array)) / float(len(sorted_array))
if len(sorted_array) > 0:
    # Add a last point
    sorted_array = np.append(sorted_array, sorted_array[-1])
    yvals = np.append(yvals, 1.0)

    # Log plot
    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    ax.plot(sorted_array, yvals, color='red', linewidth=2, label="Retrans / RTT")

    # Shrink current axis's height by 10% on the top
    # box = ax.get_position()
    # ax.set_position([box.x0, box.y0,
    #                  box.width, box.height * 0.9])
    ax.set_xscale('log')

    # Put a legend above current axis
    # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)
    ax.legend(loc='lower right')

    plt.xlabel('Retrans DSS Time / Avg RTT', fontsize=24, labelpad=-1)
    plt.ylabel("CDF", fontsize=24)
    plt.savefig(os.path.join(sums_dir_exp, 'retrans_dss_all.pdf'))
    plt.close('all')

sample = np.array(sorted(count_retrans_dss))
sorted_array = np.sort(sample)
yvals = np.arange(len(sorted_array)) / float(len(sorted_array))
if len(sorted_array) > 0:
    # Add a last point
    sorted_array = np.append(sorted_array, sorted_array[-1])
    yvals = np.append(yvals, 1.0)

    # Log plot
    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    ax.plot(sorted_array, yvals, color='red', linewidth=2, label="# of retrans per DSS")

    # Shrink current axis's height by 10% on the top
    # box = ax.get_position()
    # ax.set_position([box.x0, box.y0,
    #                  box.width, box.height * 0.9])
    ax.set_xscale('log')

    # Put a legend above current axis
    # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)
    ax.legend(loc='lower right')

    plt.xlabel('# of retransmissions per DSS', fontsize=24, labelpad=-1)
    plt.ylabel("CDF", fontsize=24)
    plt.savefig(os.path.join(sums_dir_exp, 'count_retrans_dss.pdf'))
    plt.close('all')
