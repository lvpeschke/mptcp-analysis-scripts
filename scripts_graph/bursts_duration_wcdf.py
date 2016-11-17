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

TINY = '<1s'
SMALL = '1-10s'
MEDIUM = '10-100s'
LARGE = '>=100s'

results_duration_bytes = {co.C2S: {TINY: [], SMALL: [], MEDIUM: [], LARGE: []}, co.S2C: {TINY: [], SMALL: [], MEDIUM: [], LARGE: []}}
results_pkts = {co.C2S: {TINY: [], SMALL: [], MEDIUM: [], LARGE: []}, co.S2C: {TINY: [], SMALL: [], MEDIUM: [], LARGE: []}}
min_duration = 0.001
for fname, conns in multiflow_connections.iteritems():
    for conn_id, conn in conns.iteritems():
        # Restrict to only 2SFs, but we can also see with more than 2
        if co.START in conn.attr and len(conn.flows) >= 2:
            # Rely here on MPTCP duration, maybe should be duration at TCP level?
            # Also rely on the start time of MPTCP; again, should it be the TCP one?
            conn_start_time = conn.attr[co.START].total_seconds()
            conn_start_time_int = long(conn_start_time)
            conn_start_time_dec = float('0.' + str(conn_start_time - conn_start_time_int).split('.')[1])
            conn_duration = float(conn.attr[co.DURATION])
            if conn_duration < min_duration:
                continue

            for direction in co.DIRECTIONS:
                tot_packs = 0
                to_add_pkts = []
                # First count all bytes sent (including retransmissions)
                tcp_conn_bytes = 0
                for flow_id, flow in conn.flows.iteritems():
                    tcp_conn_bytes += flow.attr[direction].get(co.BYTES_DATA, 0)

                # To cope with unseen TCP connections
                conn_bytes = max(conn.attr[direction][co.BYTES_MPTCPTRACE], tcp_conn_bytes)
                for flow_id, bytes, pkts, burst_duration, burst_start_time in conn.attr[direction][co.BURSTS]:
                    frac_bytes = (bytes + 0.0) / conn_bytes
                    if frac_bytes > 1.1:
                        print(frac_bytes, bytes, pkts, conn_bytes, direction, conn_id, flow_id)
                        continue
                    if frac_bytes < 0:
                        print(frac_bytes, bytes, pkts, conn_bytes, direction, conn_id, flow_id)
                        continue
                    burst_start_time_int = long(burst_start_time)
                    burst_start_time_dec = float('0.' + str(burst_start_time - burst_start_time_int).split('.')[1])
                    relative_time_int = burst_start_time_int - conn_start_time_int
                    relative_time_dec = burst_start_time_dec - conn_start_time_dec
                    relative_time = relative_time_int + relative_time_dec
                    frac_duration = relative_time / conn_duration
                    if frac_duration >= 0.0 and frac_duration <= 2.0:
                        if conn_duration < 2.0:
                            label = TINY
                        elif conn_duration < 10.0:
                            label = SMALL
                        elif conn_duration < 100.0:
                            label = MEDIUM
                        else:
                            label = LARGE
                        results_duration_bytes[direction][label].append((frac_duration, frac_bytes))
                        to_add_pkts.append(pkts)
                        tot_packs += pkts

                if conn_bytes < 1.0:
                    label = TINY
                elif conn_bytes < 10.0:
                    label = SMALL
                elif conn_bytes < 100.0:
                    label = MEDIUM
                else:
                    label = LARGE

                for p in to_add_pkts:
                    results_pkts[direction][label].append(p * 1.0 / tot_packs)


base_graph_name = 'bursts_'
color = {TINY: 'red', SMALL: 'blue', MEDIUM: 'green', LARGE: 'orange'}
ls = {TINY: ':', SMALL: '-.', MEDIUM: '--', LARGE: '-'}
for direction in co.DIRECTIONS:
    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    graph_fname = os.path.splitext(base_graph_name)[0] + "duration_wcdf_" + direction + ".pdf"
    graph_full_path = os.path.join(sums_dir_exp, graph_fname)

    for label in [TINY, SMALL, MEDIUM, LARGE]:
        x_val = [x[0] for x in results_duration_bytes[direction][label]]

        sample = np.array(sorted(x_val))
        sorted_array = np.sort(sample)
        tot = 0.0
        yvals = []
        for elem in sorted_array:
            tot += elem
            yvals.append(tot)

        if tot == 0:
            continue

        yvals = [x / tot for x in yvals]
        if len(sorted_array) > 0:
            # Add a last point
            sorted_array = np.append(sorted_array, sorted_array[-1])
            yvals = np.append(yvals, 1.0)
            ax.plot(sorted_array, yvals, color=color[label], linestyle=ls[label], linewidth=2, label=label)

            # Shrink current axis's height by 10% on the top
            # box = ax.get_position()
            # ax.set_position([box.x0, box.y0,
            #                  box.width, box.height * 0.9])

            # ax.set_xscale('log')

            # Put a legend above current axis
            # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)
    ax.legend(loc='best')
    plt.xlabel('Fraction of connection duration', fontsize=24)
    plt.ylabel("Weighted CDF", fontsize=24)
    plt.savefig(graph_full_path)
    plt.close('all')

    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    graph_fname = os.path.splitext(base_graph_name)[0] + "bytes_wcdf_" + direction + ".pdf"
    graph_full_path = os.path.join(sums_dir_exp, graph_fname)

    for label in [TINY, SMALL, MEDIUM, LARGE]:
        y_val = [x[1] for x in results_duration_bytes[direction][label]]

        sample = np.array(sorted(y_val))
        sorted_array = np.sort(sample)

        tot = 0.0
        yvals = []
        for elem in sorted_array:
            tot += elem
            yvals.append(tot)

        yvals = [x / tot for x in yvals]
        if len(sorted_array) > 0:
            # Add a last point
            sorted_array = np.append(sorted_array, sorted_array[-1])
            yvals = np.append(yvals, 1.0)
            ax.plot(sorted_array, yvals, color=color[label], linestyle=ls[label], linewidth=2, label=label)

            # Shrink current axis's height by 10% on the top
            # box = ax.get_position()
            # ax.set_position([box.x0, box.y0,
            #                  box.width, box.height * 0.9])

            # ax.set_xscale('log')

            # Put a legend above current axis
            # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)

    ax.legend(loc='best')
    plt.xlim(0.0, 1.0)
    plt.xlabel('Fraction of connection bytes', fontsize=24)
    plt.ylabel("Weighted CDF", fontsize=24)
    plt.savefig(graph_full_path)
    plt.close('all')


    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    graph_fname = os.path.splitext(base_graph_name)[0] + "pkts_wcdf_" + direction + ".pdf"
    graph_full_path = os.path.join(sums_dir_exp, graph_fname)

    for label in [TINY, SMALL, MEDIUM, LARGE]:
        sample = np.array(sorted(results_pkts[direction][label]))
        sorted_array = np.sort(sample)
        tot = 0.0
        yvals = []
        for elem in sorted_array:
            tot += elem
            yvals.append(tot)

        if tot == 0:
            continue

        yvals = [x / tot for x in yvals]
        print("PERCENTAGE 1 BLOCK", direction, label, len([x for x in sorted_array if x >= 0.99]) * 100. / tot)
        i = 0
        for elem in sorted_array:
            if elem >= 0.2:
                break
            else:
                i += 1

        print("PERCENTAGE 0.2 block conn", direction, label, yvals[i])
        if len(sorted_array) > 0:
            # Add a last point
            sorted_array = np.append(sorted_array, sorted_array[-1])
            yvals = np.append(yvals, 1.0)
            ax.plot(sorted_array, yvals, color=color[label], linestyle=ls[label], linewidth=2, label=label)

            # Shrink current axis's height by 10% on the top
            # box = ax.get_position()
            # ax.set_position([box.x0, box.y0,
            #                  box.width, box.height * 0.9])

            # ax.set_xscale('log')

            # Put a legend above current axis
            # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)

    ax.legend(loc='best')
    plt.xlim(0.0, 1.0)
    plt.xlabel('Fraction of connection packets', fontsize=24, labelpad=-1)
    plt.ylabel("Weighted CDF", fontsize=24)
    plt.savefig(graph_full_path)
    plt.close('all')
