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

results_duration_bytes = {co.C2S: [], co.S2C: []}
min_duration = 0.001
for fname, conns in multiflow_connections.iteritems():
    for conn_id, conn in conns.iteritems():
        # Restrict to only 2SFs, but we can also see with more than 2
        if co.START in conn.attr and len(conn.flows) == 2:
            # Rely here on MPTCP duration, maybe should be duration at TCP level?
            # Also rely on the start time of MPTCP; again, should it be the TCP one?
            conn_start_time = conn.attr[co.START].total_seconds()
            conn_start_time_int = long(conn_start_time)
            conn_start_time_dec = float('0.' + str(conn_start_time - conn_start_time_int).split('.')[1])
            conn_duration = float(conn.attr[co.DURATION])
            if conn_duration < min_duration:
                continue
            for direction in co.DIRECTIONS:
                conn_bytes = conn.attr[direction][co.BYTES_MPTCPTRACE]
                for flow_id, bytes, burst_duration, burst_start_time in conn.attr[direction][co.BURSTS]:
                    frac_bytes = (bytes + 0.0) / conn_bytes
                    if frac_bytes > 1:
                        print(frac_bytes, bytes, conn_bytes, direction, conn_id, flow_id)
                        continue
                    if frac_bytes < 0:
                        print(frac_bytes, bytes, conn_bytes, direction, conn_id, flow_id)
                        continue
                    burst_start_time_int = long(burst_start_time)
                    burst_start_time_dec = float('0.' + str(burst_start_time - burst_start_time_int).split('.')[1])
                    relative_time_int = burst_start_time_int - conn_start_time_int
                    relative_time_dec = burst_start_time_dec - conn_start_time_dec
                    relative_time = relative_time_int + relative_time_dec
                    frac_duration = relative_time / conn_duration
                    if frac_duration >= 0.0:
                        results_duration_bytes[direction].append((frac_duration, frac_bytes))

base_graph_name = 'bursts_duration_bytes'
for direction in co.DIRECTIONS:
    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()

    x_val = [x[0] for x in results_duration_bytes[direction]]
    y_val = [x[1] for x in results_duration_bytes[direction]]

    ax.scatter(x_val, y_val, label='Bursts', color='blue', alpha=1.)

    # Put a legend to the right of the current axis
    ax.legend(loc='best', fontsize='large', scatterpoints=1)
    plt.xlabel('Fraction of connection duration', fontsize=24)
    plt.ylabel('Fraction of connection bytes', fontsize=24)
    plt.grid()

    # plt.annotate('1', xy=(0.57, 0.96),  xycoords="axes fraction",
    #         xytext=(0.85, 0.85), textcoords='axes fraction',
    #         arrowprops=dict(facecolor='black', shrink=0.05),
    #         horizontalalignment='right', verticalalignment='bottom', size='large'
    #         )
    #
    # plt.annotate('2', xy=(0.38, 0.04),  xycoords="axes fraction",
    #         xytext=(0.125, 0.2), textcoords='axes fraction',
    #         arrowprops=dict(facecolor='black', shrink=0.05),
    #         horizontalalignment='left', verticalalignment='top', size='large'
    #         )

    graph_fname = base_graph_name + "_" + direction + ".pdf"
    graph_full_path = os.path.join(sums_dir_exp, graph_fname)

    plt.savefig(graph_full_path)

    plt.clf()
    plt.close('all')
