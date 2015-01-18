#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#  Copyright 2015 Matthieu Baerts & Quentin De Coninck
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

##################################################
##                   IMPORTS                    ##
##################################################

from common import *

import argparse
import Gnuplot
import matplotlib.pyplot as plt
import numpy as np
import os
import os.path
import pickle

##################################################
##                  CONSTANTS                   ##
##################################################

# The default stat directory
DEF_STAT_DIR = 'stats'

##################################################
##                  ARGUMENTS                   ##
##################################################

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument("-s",
                    "--stat", help="directory where the stat files are stored", default=DEF_STAT_DIR)
parser.add_argument("-a",
                    "--app", help="application results to summarize", default="")
parser.add_argument(
    "time", help="aggregate data in specified time, in format START,STOP")

args = parser.parse_args()

split_agg = args.time.split(',')

if not len(split_agg) == 2 or not is_number(split_agg[0]) or not is_number(split_agg[1]):
    print("The aggregation argument is not well formatted", file=sys.stderr)
    parser.print_help()
    exit(1)

start_time = split_agg[0]
stop_time = split_agg[1]

if int(start_time) > int(stop_time):
    print("The start time is posterior to the stop time", file=sys.stderr)
    parser.print_help()
    exit(2)

stat_dir_exp = os.path.abspath(os.path.expanduser(args.stat))

##################################################
##                 GET THE DATA                 ##
##################################################

check_directory_exists(stat_dir_exp)
connections = {}
for dirpath, dirnames, filenames in os.walk(stat_dir_exp):
    for fname in filenames:
        if args.app in fname:
            try:
                stat_file = open(os.path.join(dirpath, fname), 'r')
                connections[fname] = pickle.load(stat_file)
                stat_file.close()
            except IOError as e:
                print(str(e) + ': skip stat file ' + fname, file=sys.stderr)

##################################################
##               PLOTTING RESULTS               ##
##################################################


def get_experiment_condition(fname):
    """ Return a string of the format protocol_condition (e.g. tcp_both4TCD100m) """
    app_index = fname.index(args.app)
    dash_index = fname.index("-")
    end_index = fname[:dash_index].rindex("_")
    return fname[:app_index] + fname[app_index + len(args.app) + 1:end_index]


def count_interesting_connections(data):
    """ Return the number of interesting connections in data """
    count = 0
    tot = 0
    for k, v in data.iteritems():
        if isinstance(v, dict):
            # Check for the dict v
            int_tot, int_count = count_interesting_connections(v)
            tot += int_tot
            count += int_count
        else:
            # Check the key k
            # An interesting flow has an IF field
            if k == IF:
                count += 1
            # All flows have a DADDR field
            if k == DADDR:
                tot += 1
    return tot, count


aggl_res = {}
tot_lbl = 'Total Connections'
tot_flw_lbl = 'Total Flows'
tot_int_lbl = 'Interesting Flows'

# Need to agglomerate same tests
for fname, data in connections.iteritems():
    condition = get_experiment_condition(fname)
    tot_flow, tot_int = count_interesting_connections(data)
    if condition in aggl_res:
        aggl_res[condition][tot_lbl] += [len(data)]
        aggl_res[condition][tot_flw_lbl] += [tot_flow]
        aggl_res[condition][tot_int_lbl] += [tot_int]
    else:
        aggl_res[condition] = {
            tot_lbl: [len(data)], tot_flw_lbl: [tot_flow], tot_int_lbl: [tot_int]}

# At the end, convert Python arrays to numpy arrays (easier for mean and std)
for cond, elements in aggl_res.iteritems():
    for label, array in elements.iteritems():
        elements[label] = np.array(array)

print(aggl_res)


N = len(aggl_res)
ind = np.arange(N)
labels = []
conn_mean = []
conn_std = []
flow_mean = []
flow_std = []
int_mean = []
int_std = []
width = 0.30       # the width of the bars
fig, ax = plt.subplots()

# So far, simply count the number of connections
for cond, elements in aggl_res.iteritems():
    labels.append(cond)
    conn_mean.append(elements[tot_lbl].mean())
    conn_std.append(elements[tot_lbl].std())
    flow_mean.append(elements[tot_flw_lbl].mean())
    flow_std.append(elements[tot_flw_lbl].std())
    int_mean.append(elements[tot_int_lbl].mean())
    int_std.append(elements[tot_int_lbl].std())

tot_count = ax.bar(ind, conn_mean, width, color='b', yerr=conn_std, ecolor='g')
flo_count = ax.bar(ind + width, flow_mean, width, color='g', yerr=flow_std, ecolor='r')
int_count = ax.bar(ind + 2 * width, int_mean, width, color='r', yerr=int_std, ecolor='b')

# add some text for labels, title and axes ticks
ax.set_ylabel('Counts')
ax.set_title('Counts of total and interesting connections of ' + args.app)
ax.set_xticks(ind + width)
ax.set_xticklabels(labels)

ax.legend((tot_count[0], flo_count[0], int_count[0]),
          (tot_lbl, tot_flw_lbl, tot_int_lbl))


def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x() + rect.get_width() / 2., 1.05 * height, '%d' % int(height),
                ha='center', va='bottom')

autolabel(tot_count)
autolabel(flo_count)
autolabel(int_count)

plt.savefig("count_" + args.app + "_" + start_time + "_" + stop_time + '.pdf')


#TODO I will create a subroutine to avoid code duplication
aggl_res = {}
tot_lbl = 'Bytes s2d'
tot_flw_lbl = 'Bytes d2s'
tot_int_lbl = 'Duration'

# Need to agglomerate same tests
for fname, data in connections.iteritems():
    condition = get_experiment_condition(fname)
    if condition.startswith("mptcp"):
        data = data[data.keys()[0]]
    here = [i for i in data.keys() if i in [BYTES_S2D, BYTES_D2S, DURATION]]
    if not len(here) == 3:
        continue
    if condition in aggl_res:
        aggl_res[condition][tot_lbl] += [data[BYTES_S2D]]
        aggl_res[condition][tot_flw_lbl] += [data[BYTES_D2S]]
        aggl_res[condition][tot_int_lbl] += [data[DURATION]]
    else:
        aggl_res[condition] = {
            tot_lbl: [data[BYTES_S2D]], tot_flw_lbl: [data[BYTES_D2S]], tot_int_lbl: [data[DURATION]]}

# At the end, convert Python arrays to numpy arrays (easier for mean and std)
for cond, elements in aggl_res.iteritems():
    for label, array in elements.iteritems():
        elements[label] = np.array(array)

print(aggl_res)


N = len(aggl_res)
ind = np.arange(N)
labels = []
conn_mean = []
conn_std = []
flow_mean = []
flow_std = []
int_mean = []
int_std = []
width = 0.30       # the width of the bars
fig, ax = plt.subplots()

# So far, simply count the number of connections
for cond, elements in aggl_res.iteritems():
    labels.append(cond)
    conn_mean.append(elements[tot_lbl].mean())
    conn_std.append(elements[tot_lbl].std())
    flow_mean.append(elements[tot_flw_lbl].mean())
    flow_std.append(elements[tot_flw_lbl].std())
    int_mean.append(elements[tot_int_lbl].mean())
    int_std.append(elements[tot_int_lbl].std())

tot_count = ax.bar(ind, conn_mean, width, color='b', yerr=conn_std, ecolor='g')
flo_count = ax.bar(ind + width, flow_mean, width, color='g', yerr=flow_std, ecolor='r')
int_count = ax.bar(ind + 2 * width, int_mean, width, color='r', yerr=int_std, ecolor='b')

# add some text for labels, title and axes ticks
ax.set_ylabel('Values (bytes & seconds)')
ax.set_title('Counts of total and interesting connections of ' + args.app)
ax.set_xticks(ind + width)
ax.set_xticklabels(labels)

ax.legend((tot_count[0], flo_count[0], int_count[0]),
          (tot_lbl, tot_flw_lbl, tot_int_lbl))


def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x() + rect.get_width() / 2., 1.05 * height, '%d' % int(height),
                ha='center', va='bottom')

autolabel(tot_count)
autolabel(flo_count)
autolabel(int_count)

plt.savefig("bytes_" + args.app + "_" + start_time + "_" + stop_time + '.pdf')

print("End of summary")
