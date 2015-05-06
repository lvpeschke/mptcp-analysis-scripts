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

import argparse
import common as co
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mptcp
import numpy as np
import os
import os.path
import pickle
import sys
import tcp
import time

##################################################
##                  ARGUMENTS                   ##
##################################################

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument("-s",
                    "--stat", help="directory where the stat files of smartphone are stored", default=co.DEF_STAT_DIR+'_'+co.DEF_IFACE)
parser.add_argument("-t",
                    "--time", help="file of time of nostromo")
parser.add_argument("-b",
                    "--bytes", help="file of bytes of nostromo")
parser.add_argument("-j",
                    "--join", help="file of join time of nostromo")
parser.add_argument('-S',
                    "--sums", help="directory where the summary graphs will be stored", default=co.DEF_SUMS_DIR+'_'+co.DEF_IFACE)

args = parser.parse_args()

time_file_exp = os.path.abspath(os.path.expanduser(args.time))
bytes_file_exp = os.path.abspath(os.path.expanduser(args.bytes))
join_file_exp = os.path.abspath(os.path.expanduser(args.join))
stat_dir_exp = os.path.abspath(os.path.expanduser(args.stat))
sums_dir_exp = os.path.abspath(os.path.expanduser(args.sums))

co.check_directory_exists(sums_dir_exp)

def check_in_list(dirpath, dirs):
    """ Check if dirpath is one of the dir in dirs, True if dirs is empty """
    if not dirs:
        return True
    return os.path.basename(dirpath) in dirs


def fetch_data(dir_exp):
    co.check_directory_exists(dir_exp)
    dico = {}
    for dirpath, dirnames, filenames in os.walk(dir_exp):
        for fname in filenames:
            try:
                stat_file = open(os.path.join(dirpath, fname), 'r')
                dico[fname] = pickle.load(stat_file)
                stat_file.close()
            except IOError as e:
                print(str(e) + ': skip stat file ' + fname, file=sys.stderr)

    return dico


def nostromo_time(filepath):
    time_file = open(filepath)
    data = time_file.readlines()
    time_file.close()
    nostromo_time = []

    for line in data:
        try:
            nostromo_time.append(float(line))
        except Exception as e:
            print(str(e))
    return nostromo_time

def nostromo_bytes(filepath):
    bytes_file = open(filepath)
    data = bytes_file.readlines()
    bytes_file.close()
    nostromo_bytes = []

    for line in data:
        try:
            split_line = line.split()
            nostromo_bytes.append(int(split_line[1]))
        except Exception as e:
            print(str(e))
    return nostromo_bytes


def nostromo_join(filepath):
    join_file = open(filepath)
    data = join_file.readlines()
    join_file.close()
    nostromo_join = []

    for line in data:
        try:
            split_line = line.split()
            nostromo_join.append(float(split_line[1]))
        except Exception as e:
            print(str(e))
    return nostromo_join


SMART = "smartphone"
NOSTR = "server"
dataset = {SMART: {}, NOSTR: {}}

dataset[SMART] = fetch_data(stat_dir_exp)
dataset[NOSTR]["time"] = nostromo_time(time_file_exp)
dataset[NOSTR]["bytes"] = nostromo_bytes(bytes_file_exp)
dataset[NOSTR]["join"] = nostromo_join(join_file_exp)

def ensures_smartphone_to_proxy():
    for fname in dataset[SMART].keys():
        for conn_id in dataset[SMART][fname].keys():
            if isinstance(dataset[SMART][fname][conn_id], mptcp.MPTCPConnection):
                inside = True
                for flow_id, flow in dataset[SMART][fname][conn_id].flows.iteritems():
                    if not flow.attr[co.DADDR].startswith('172.17.') and not flow.attr[co.DADDR] == co.IP_PROXY:
                        dataset[SMART][fname].pop(conn_id, None)
                        inside = False
                        break
                if inside:
                    for direction in co.DIRECTIONS:
                        # This is a fix for wrapping seq num
                        if dataset[SMART][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE] < -1:
                            dataset[SMART][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE] = 2**32 + dataset[SMART][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE]


ensures_smartphone_to_proxy()

def plot_time():
    time_smartphone = []
    for fname, data in dataset[SMART].iteritems():
        for conn_id, conn in data.iteritems():
            if co.DURATION in conn.attr:
                time_smartphone.append(conn.attr[co.DURATION])
                if conn.attr[co.DURATION] < 0.001:
                    print(fname, conn_id, conn.attr[co.DURATION])
    co.plot_cdfs_natural({'all': {SMART: time_smartphone, NOSTR: dataset[NOSTR]["time"]}}, ['red', 'blue'], 'Seconds', os.path.join(sums_dir_exp, 'merge_time'), label_order=[NOSTR, SMART], xlog=True, xlim=1000000)


def plot_bytes():
    bytes_smartphone = []
    for fname, data in dataset[SMART].iteritems():
        for conn_id, conn in data.iteritems():
            tot_bytes = 0
            for direction in co.DIRECTIONS:
                if co.BYTES_MPTCPTRACE in conn.attr[direction]:
                    tot_bytes += conn.attr[direction][co.BYTES_MPTCPTRACE]
            bytes_smartphone.append(tot_bytes)
    co.plot_cdfs_natural({'all': {SMART: bytes_smartphone, NOSTR: dataset[NOSTR]["bytes"]}}, ['red', 'blue'], 'Data bytes', os.path.join(sums_dir_exp, 'merge_bytes'), label_order=[NOSTR, SMART], xlog=True)


def plot_join():
    join_smartphone = []
    for fname, data in dataset[SMART].iteritems():
        for conn_id, conn in data.iteritems():
            # First find initial subflow timestamp
            initial_sf_ts = float('inf')
            for flow_id, flow in conn.flows.iteritems():
                if co.START not in flow.attr:
                    continue
                if flow.attr[co.START] < initial_sf_ts:
                    initial_sf_ts = flow.attr[co.START]
            if initial_sf_ts == float('inf'):
                continue
            # Now store the delta and record connections with handover
            for flow_id, flow in conn.flows.iteritems():
                if co.START not in flow.attr:
                    continue
                delta = flow.attr[co.START] - initial_sf_ts
                if delta > 0.0:
                    join_smartphone.append(delta)

    co.plot_cdfs_natural({'all': {SMART: join_smartphone, NOSTR: dataset[NOSTR]["join"]}}, ['red', 'blue'], 'Seconds', os.path.join(sums_dir_exp, 'merge_join'), label_order=[NOSTR, SMART], xlog=True)
    for data in [join_smartphone, dataset[NOSTR]["join"]]:
        total = len(data)
        count_after_1 = 0
        count_after_2 = 0
        count_after_60 = 0
        count_after_3600 = 0
        for ts_join in data:
            if ts_join >= 1:
                count_after_1 += 1
                if ts_join >= 2:
                    count_after_2 += 1
                    if ts_join >= 60:
                        count_after_60 += 1
                        if ts_join >= 3600:
                            count_after_3600 += 1
        print("TOTAL", total, "After 1 sec", count_after_1, "After 2 sec", count_after_2, "Subflows after 60s", count_after_60, "Subflows after 3600s", count_after_3600)


plot_time()
plot_bytes()
plot_join()
