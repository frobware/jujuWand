#!/usr/bin/python
import os
import subprocess
import threading
import time
from glob import glob

import wand

connections = {}


def connect(thing_name, thing_type, address):
    cmd = 'ssh -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null ubuntu@{} sudo tail -n 10000 -f /var/log/juju/machine-{}.log'.format(
        address, thing_name)
    file_name = '{}-{}.log'.format(thing_type, thing_name)
    connections[name] = {
        'file': open(file_name, 'a'),
    }
    connections[name]['thread'] = threading.Thread(
        target=wand.run,
        args=(cmd,),
        kwargs={
            'quiet': True,
            'write_to': connections[name]['file'],
            'empty_return': True,
    })
    print cmd, 'to', file_name
    connections[name]['thread'].start()


logs = glob('*.log')
for l in logs:
    os.remove(l)

while True:
    try:
        s = wand.status()

        for name, m in s['machines'].iteritems():
            if name not in connections and 'dns-name' in m:
                connect(name, 'machine', m['dns-name'])

    except subprocess.CalledProcessError:
        pass

    # Clean up dead connections.
    dead = []
    for name, info in connections.iteritems():
        if not info['thread'].isAlive():
            print name, 'is dead'
            dead.append(name)

    for name in dead:
        connections.pop(name)
    time.sleep(30)
