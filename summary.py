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
stat_dir = DEF_STAT_DIR
app_name = ''

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument(
    "-stat", help="directory where the stat files are stored")
parser.add_argument(
    "-app", help="application results to summarize")
args = parser.parse_args()

if args.stat:
    stat_dir = args.stat

if args.app:
    app_name = args.app

stat_dir_exp = os.path.expanduser(stat_dir)

##################################################
##                 GET THE DATA                 ##
##################################################

check_directory_exists(stat_dir_exp)
connections = {}
for dirpath, dirnames, filenames in os.walk(os.path.join(os.getcwd(), stat_dir_exp)):
    for fname in filenames:
        if app_name in fname:
            try:
                stat_file = open(os.path.join(dirpath, fname), 'r')
                connections[fname] = pickle.load(stat_file)
                stat_file.close()
            except IOError as e:
                print(str(e) + ': skip stat file ' + fname)

##################################################
##               PLOTTING RESULTS               ##
##################################################


def count_interesting_connections(data):
    """ Return the number of interesting connections in data """
    count = 0
    for k, v in data.iteritems():
        if isinstance(v, dict):
            # Check for the dict v
            count += count_interesting_connections(v)
        else:
            # Check the key k
            if k == IF:
                count += 1
    return count


N = len(connections)
ind = np.arange(N)
counts = []
int_counts = []
labels = []
width = 0.35       # the width of the bars
fig, ax = plt.subplots()

# So far, simply count the number of connections
for fname, data in connections.iteritems():
    labels.append(fname)
    counts.append(len(data))
    int_counts.append(count_interesting_connections(data))

tot_count = ax.bar(ind, counts, width, color='b')
int_count = ax.bar(ind+width, int_counts, width, color='g')

# add some text for labels, title and axes ticks
ax.set_ylabel('Counts')
ax.set_title('Counts of total and interesting connections')
ax.set_xticks(ind+width)
ax.set_xticklabels(labels)

ax.legend((tot_count[0], int_count[0]),('Total', 'Interesting'))

def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/2., 1.05*height, '%d'%int(height),
                ha='center', va='bottom')

autolabel(tot_count)
autolabel(int_count)

plt.show()

print("End of summary")
