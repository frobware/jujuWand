#!/usr/bin/python

import subprocess
import yaml
from pprint import pprint
import time
from datetime import datetime


def wait_for_connection():
    while subprocess.call('timeout 5 juju status', shell=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT):
        time.sleep(5)


def status():
    wait_for_connection()
    return yaml.load(run('juju status', quiet=True))


def juju(cmd, quiet=False, write_to=None, fail_ok=False):
    print "juju cmd:", cmd
    offline_cmds = [
        'destroy-environment',
        'switch',
        'bootstrap',
    ]
    offline = False
    for c in offline_cmds:
        if cmd.startswith(c):
            offline = True
            break
    if not (offline or fail_ok):
        wait_for_connection()

    return run("juju " + cmd, quiet, write_to, fail_ok)


def run(cmd, quiet=False, write_to=None, fail_ok=False, empty_return=False):
    if not quiet:
        print cmd
    out = ""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, bufsize=1)
    lines_iterator = iter(p.stdout.readline, b"")

    for line in lines_iterator:
        now = datetime.utcnow().isoformat(' ')
        ts_line = now + '| ' + line
        if not quiet:
            print ts_line,
        if write_to is not None:
            write_to.write(ts_line)
        if not empty_return:
            out += line
    p.poll()

    if p.returncode:
        if not fail_ok:
            raise subprocess.CalledProcessError(p.returncode, cmd, out)
        else:
            print "Command returned", p.returncode

    return out


def watch(store, key, value):
    if store.get(key) != value:
        print datetime.now(), key + ":", value
        store[key] = value


def wait(forever=False):
    keep_trying = True
    watching = {}

    while keep_trying or forever:

        time.sleep(5)
        try:
            s = status()
        except subprocess.CalledProcessError:
            continue
        keep_trying = False

        try:
            for name, m in s['machines'].iteritems():
                agent_state = m.get('agent-state')
                watch(watching, name, agent_state)
                if agent_state != 'started':
                    keep_trying = True
                    continue

                ssms = m.get('state-server-member-status')
                if ssms and ssms != 'has-vote':
                    keep_trying = True
                    continue

            for service_name, service in s['services'].iteritems():
                if 'units' not in service:
                    continue
                for unit in service['units'].values():
                    name = unit['machine'] + ' ' + service_name
                    watch(watching, name, unit['agent-state'])

                    name += ' workload-status'
                    if unit['workload-status'].get('message'):
                        watch(watching, name, unit['workload-status']['message'])
                    else:
                        watch(watching, name, '')

                    if unit['agent-state'] != 'started':
                        keep_trying = True
                        continue
        except KeyError as e:
            print e
            print "continuing..."


if __name__ == '__main__':
    start_at = 0
    if start_at <= 1:
        run('go install  -v github.com/juju/juju/...')
        juju('destroy-environment --force amzeu', fail_ok=True)
        juju('switch amzeu')
        juju('bootstrap --upload-tools')
        # juju('set-env logging-config=juju.state.presence=TRACE')
        juju(r'set-env logging-config=\<root\>=TRACE')
        wait()

    if start_at <= 2:
        # I don't know why, but deploying a charm before doing ensure-availability
        # seems to help us not get stuck in the waiting for has-vote state.
        juju('deploy ubuntu')
        wait()

    if start_at <= 3:
        juju('ensure-availability -n 3')
        wait()

    if start_at <= 4:
        # Need to wait until the Mongo servers actually do their HA thing. This
        # is not the same as status showing everything as started. Bother.
        #time.sleep(30)
        # 30 seconds seems to be more than enough time to let things settle.
        while True:
            try:
                juju('ssh 0 "sudo halt -p"')
                break
            except subprocess.CalledProcessError:
                time.sleep(5)

        time.sleep(60)
        juju('ensure-availability -n 3')
