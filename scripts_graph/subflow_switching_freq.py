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


def plot(connections, multiflow_connections, sums_dir_exp):
    log_file = sys.stdout
    bursts_sec = {co.C2S: [], co.S2C: []}
    color = 'red'
    graph_fname_sec = "merge_bursts_sec_log"
    base_graph_path_sec = os.path.join(sums_dir_exp, graph_fname_sec)
    min_bytes = 1000000
    min_duration = 0.1

    for fname, conns in multiflow_connections.iteritems():
        for conn_id, conn in conns.iteritems():
            # We never know, still check
            if isinstance(conn, mptcp.MPTCPConnection):
                count_established = 0
                for flow_id, flow in conn.flows.iteritems():
                    if flow.attr.get(co.DURATION, 0.0) > 0.0:
                        count_established += 1
                if count_established < 2:
                    continue

                for direction in co.DIRECTIONS:
                    if conn.attr[direction].get(co.BYTES_MPTCPTRACE, 0) < min_bytes or float(conn.attr.get(co.DURATION, '0.0')) <= min_duration:
                        continue
                    if co.BURSTS in conn.attr[direction] and len(conn.attr[direction][co.BURSTS]) > 0:
                        bursts_sec[direction].append((len(conn.attr[direction][co.BURSTS]) - 1.0) / float(conn.attr[co.DURATION]))

    # Plot
    for direction in co.DIRECTIONS:
        sample = np.array(sorted(bursts_sec[direction]))
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
            ax.plot(sorted_array, yvals, color=color, linewidth=2, label="Burstiness")

            # Shrink current axis's height by 10% on the top
            # box = ax.get_position()
            # ax.set_position([box.x0, box.y0,
            #                  box.width, box.height * 0.9])
            ax.set_xscale('log')

            # Put a legend above current axis
            # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)
            ax.legend(loc='lower right')

            plt.xlabel('# switches / second', fontsize=24)
            plt.ylabel("CDF", fontsize=24)
            plt.savefig(base_graph_path_sec + "_" + direction + "_log.pdf")
            plt.close('all')

plot(connections, multiflow_connections, sums_dir_exp)
