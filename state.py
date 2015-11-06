#!/usr/bin/python
import os
import re
import glob
from pprint import pprint, pformat

from datetime import datetime

import sys


def get_time(line):
    ts_len = len('2015-11-03 09:18:08')
    time_format = '%Y-%m-%d %H:%M:%S'
    n = line.find(': 2015-')
    if n != -1:
        n += 2
        t = line[n:n+ts_len]
    else:
        t = line[:ts_len]

    try:
        return datetime.strptime(t, time_format)
    except ValueError:
        return None


def multi_match(line, match_list):
    miss = False
    for p in match_list:
        if line.find(p) == -1:
            miss = True
            break
    return not miss


class LogChomper:
    def __init__(self):
        self.state = {}
        self.timeline = []
        self.addresses = {}

    def filter(self, f, fname, out):
        dirname, fname = os.path.split(fname)
        machine = os.path.basename(dirname)
        name = fname[:-4]
        #print machine, name
        sys.stdout.write(".")
        sys.stdout.flush()
        self.connection_state = [' ', ' ', ' ']

        disconnect = [
            ['connection is shut down'],
            [': i/o timeout'],
            ['connection reset by peer'],
            ['connection refused'],
            ['no route to host'],
            ['unable to connect to'],
            ['broken pipe'],
            ['connection timed out'],
        ]

        interesting = [
            ['INFO juju.api apiclient.go'],
        ]

        unhandled = [
            ['setting addresses for'],
            ['API addresses updated to'],
            ['making syslog connection for'],
            ['juju.apiserver admin.go', 'hostPorts'],
            ['juju.state address.go', 'setting API hostPorts'],
            ['juju.worker.peergrouper desired.go', 'members:'],
            ['State Server cerificate addresses updated to'],
            ['juju.apiserver apiserver.go', 'new certificate addresses'],
            ['juju.worker.peergrouper worker.go', 'successfully changed replica set to'],
            ['juju.worker.peergrouper worker.go', 'no change in desired peer group'],
            ['juju.worker.certupdater certupdater.go', 'existing cert addresses map'],
        ]

        ignore = unhandled + [
            ['downloading', 'from'],
            ['Monitor hosts are'],
            ['lxc-create template params'],
            ['not filtering address', 'for machine'],
            ['addresses after filtering'],
            ['dialled mongo successfully on address'],
            ['new machine addresses'],
            ['new addresses'],
            ['juju.worker.peergrouper worker.go', 'no change in desired peer group'],
            ['juju.worker.certupdater certupdater.go', 'existing cert addresses map'],
            ['juju.utils.ssh run.go'],
            ['juju.apiserver.client run.go'],
            ['-relation-changed '],
            ['worker.uniter.jujuc server.go:', 'running hook tool'],
            [' juju-log '],
            ['-relation-joined '],
            ['config-changed public_address:'],
            [' INFO config-changed '],
            ['DEBUG juju.worker.peergrouper worker.go:', 'desired peer group members'],
            ['INFO juju.apiserver apiserver.go', 'API connection from'],
        ]

        local_address = None
        self.restarted = True

        for line in f.readlines():
            if line.find('setting addresses for') != -1:
                r = re.search('local-cloud:(.*?)"', line)
                if local_address != r.group(1):
                    local_address = r.group(1)
                    self.addresses[machine] = local_address

            if line.find('juju.container.kvm kvm.go') != -1 and line.find('kvm-ok output') != -1:
                self.restarted = True

            # Look for lines that contain known IP addresses and make sure that
            # we handle them somehow.
            if line.find('10.10.197.') != -1:
                found = False
                for r in interesting + ignore + disconnect:
                    if multi_match(line, r):
                        found = True
                        break
                if not found:
                    # Now check for a timestamp. We don't want random
                    # multi-line stuff that we can't filter
                    if re.search('\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d', line):
                        print "interesting?"
                        print line,
                        print "-" * 80

            for r in disconnect:
                if not multi_match(line, r):
                    continue

                if line.find('rsyslog') != -1:
                    continue

                if line.find('10.10.197.27') != -1:
                    continue



                addr = re.search('(10\.10\.197\.\d+)', line)
                if addr:
                    print line,
                    address = addr.group(1)
                    event = 'disconnect'
                    detail = ' '.join(r)
                    self.update(name, address, event, line, machine, local_address, detail)

            for r in interesting:
                if not multi_match(line, r):
                    continue

                out.write(fname + ' ' + line)

                event = None
                addr = re.search('apiclient.go:\d+\s+(.*?)\s+"wss://(.*?)/', line)
                if addr:
                    event = addr.group(1)
                    address = addr.group(2)
                    address = address.split(':')[0]

                if event == 'dialing' or event is None:
                    continue

                self.update(name, address, event, line, machine, local_address, '')

    def update(self, name, address, event, line, machine, local_address, detail):

        if machine not in self.state:
            self.state[machine] = {}
        if name not in self.state[machine]:
            self.state[machine][name] = {}

        if address == 'localhost':
            address = local_address

        if address == 'controller03.maas':
            address = '10.10.197.27'

        if event == 'error dialing':
            event = 'disconnect'

        s = self.state[machine][name].get(address)
        if s is None:
            s = {
                'event': 'disconnect',
                'state': 'disconnect',
                'events': []
            }

        tag = ' '
        if self.restarted:
            self.restarted = False
            tag = 'r'
            # print "restarted", event
            # s['event'] = event
            #event = 'restarted'
            for a in self.state[machine][name]:
                self.state[machine][name][a]['event'] = ''

        if s['event'] != event:
            time = get_time(line)
            s['event'] = event

            translate = {
                '10.10.197.27': 0,
                '10.10.197.29': 1,
                '10.10.197.30': 2,
            }

            thingamy = {0: '0', 1: '4', 2: '5'}

            if event == 'connection established to':
                i = translate[address]
                if self.connection_state[i] != ' ':
                    return
                self.connection_state[i] = thingamy[i]
            elif event == 'disconnect':
                i = translate[address]
                if self.connection_state[i] == ' ':
                    return
                self.connection_state[translate[address]] = ' '
            else:
                print "Unknown event"
                print event
                exit(1)

            machine_names = {
                '10.10.197.25': 'machine1',
                '10.10.197.26': 'machine2',
                '10.10.197.27': 'machine0',
                '10.10.197.28': 'machine3',
                '10.10.197.29': 'machine4',
                '10.10.197.30': 'machine5',
            }

            # e = '{}| {} {} {} ({}/{}) {}'.format(
            #     tag,
            #     ''.join(self.connection_state),
            #     event, machine_names[address], machine, name, detail)

            if detail != '':
                detail = ': ' + detail
            e = '{}| {} -> {} | {} {}{}'.format(
                tag, name[-1],
                ''.join(self.connection_state),
                event, machine_names[address], detail)

            s['events'].append(e)
            self.timeline.append((time, e))

        self.state[machine][name][address] = s

    def result(self):
        print ""
        #pprint(self.state)
        #pprint(self.timeline)
        tl = sorted(self.timeline, key=lambda t: t[0])

        for e in tl:
            print e[0], e[1]

        pprint(self.addresses)


def main():
    #input_files = '/home/dooferlad/Downloads/Juju_HA_logs/*/*.log'
    input_files = '/home/dooferlad/Downloads/Juju_HA_logs/*/machine-?.log'
    #input_files = '/home/dooferlad/Downloads/Juju_HA_logs/machine3/machine-3.log'
    output_file = '/home/dooferlad/dbg/1510651/state.txt'

    lc = LogChomper()

    with open(output_file, 'w') as out:
        for fname in sorted(glob.glob(input_files)):
            with open(fname) as f:
                lc.filter(f, fname, out)

    lc.result()

if __name__ == '__main__':
    main()
