#!/usr/bin/python

import re
import glob
from pprint import pprint, pformat
from datetime import datetime


def main():
    #input_files = '/home/dooferlad/dbg/1510651/*.log'
    input_files = '/home/dooferlad/Downloads/Juju_HA_logs/machine4/unit-rabbitmq-1.log'
    #input_files = '*.log'

    has_local_timestamp = False

    ts_len = len('2015-11-03 09:18:08')
    ts2_len = len('2015-11-04 15:19:14.944920| ')
    time_format = '%Y-%m-%d %H:%M:%S'
    initial_time = datetime.strptime('2014-11-03 09:18:08', time_format)

    for fname in sorted(glob.glob(input_files)):

        print fname

        max_time_diff = None
        old_time = {}
        line_number = 0
        last_line = ""

        with open(fname) as f:
            for line in f.readlines():
                if has_local_timestamp:
                    # Grab the local timestamp
                    ts2 = line[:ts2_len]
                    line = line[ts2_len:]

                line_number += 1
                n = line.find(': 2015-')
                if n != -1:
                    n += 2
                    t = line[n:n+ts_len]
                    key = line[:n]
                else:
                    t = line[:ts_len]
                    key = fname

                if key not in old_time:
                    old_time[key] = initial_time

                try:
                    new_time = datetime.strptime(t, time_format)
                    diff = old_time[key] - new_time

                    if old_time[key] > new_time and diff.seconds > 600:
                        print "-" * 80
                        print key
                        print old_time
                        print old_time[key], new_time
                        print fname + " +" + str(line_number), diff, diff.seconds
                        print " ", last_line,
                        print " ", line,
                        if max_time_diff is None:
                            max_time_diff = diff
                        else:
                            max_time_diff = max(max_time_diff, diff)
                    old_time[key] = new_time

                except ValueError:
                    print t
                    print line,
                    pass

                last_line = line

        print "Max time travel", max_time_diff

if __name__ == '__main__':
    main()
