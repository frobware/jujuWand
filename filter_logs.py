#!/usr/bin/python

import re
import glob
from pprint import pprint, pformat


def parse_structure(a):
    a = a.lstrip().rstrip().lstrip(':').lstrip()
    is_map = re.search('map\[.*?\].*?{(.*)}', a)
    sort_before_return = False
    if is_map:
        sort_before_return = True
        a = is_map.group(1)

    parsed = []
    inside = []
    index_stack = []
    pairs = [('"', '"'), ('{', '}'), ('[', ']'), ('(', ')')]
    thing = ""
    key, value = '', ''
    max_index = len(a)-1

    for index in range(len(a)):
        for p in pairs:
            if a[index] == p[1]:
                if p[0] != p[1]:
                    # Should be a simple balanced bracket or similar
                    assert inside[-1] == p[0]
                    inside.pop(-1)
                    start = index_stack.pop(-1)
                    if len(index_stack) == 0:
                        thing += a[start:index+1]
                else:
                    # Something like a quote both starts and ends a string...
                    if len(inside) and inside[-1] == p[1]:
                        inside.pop(-1)
                        start = index_stack.pop(-1)
                        if len(index_stack) == 0:
                            thing += a[start:index+1]
                    else:
                        inside.append(p[0])
                        index_stack.append(index)

            elif a[index] == p[0]:
                inside.append(p[0])
                index_stack.append(index)

        if len(index_stack):
            continue

        if a[index] == ':':
            key = thing
            thing = ''

        if(a[index] == ',' or
           index == max_index or
           a[index-1:index+2] == '] [' # in our horrible world this is an implied comma
           ):
            if thing != '':
                value = thing
                thing = ''

                if re.search('\(.*?\)\(0x[0-9a-f]+\)', value):
                    # Don't care about map of thing to pointer, the key tends
                    # to be the interesting bit!
                    value = key
                    key = ''

                if key == '':
                    if value == a:
                        # We just found a single item in a list - parse what is inside it, because this is too dull.
                        return parse_structure(a[1:-1])
                    parsed.append(value)
                else:
                    parsed.append((key, value))

            key, value = '', ''

    if sort_before_return:
        parsed = sorted(parsed)
    return parsed


def diff_structures(old, new):
    if old == '':
        # Bail early for the first diff, where the old value is empty
        return None, None
    o = parse_structure(old)
    n = parse_structure(new)
    # if o != n and o != []:
    #     if len(o) == len(n):
    #         exit(0)
    if o != n:
        return o, n
    else:
        return None, None


def main():
    #input_files = '/home/dooferlad/dbg/1510651/*.log'
    input_files = '/home/dooferlad/Downloads/Juju_HA_logs/machine4/*rabbitmq*.log'
    output_file = '/home/dooferlad/dbg/1510651/filtered.txt'
    exclude_patterns = [
        ['DEBUG juju.apiserver utils.go:', 'validate env uuid: state server environment'],
        ['TRACE juju.apiserver.common resource.go:', 'registered named resource: machineID'],
        ['TRACE juju.apiserver.common resource.go:', 'registered named resource: dataDir'],
        ['TRACE juju.apiserver.common resource.go:', 'registered named resource: logDir'],
        ['TRACE juju.state.watcher watcher.go:', 'got request: watcher.reqWatch'],
        ['INFO juju.apiserver apiserver.go', 'API connection terminated after'],
        ['INFO juju.apiserver apiserver.go', 'API connection from'],
        ['TRACE juju.utils http.go:', 'hostname SSL verification enabled'],
        ['TRACE juju.state.watcher watcher.go:', 'got request: watcher.reqUnwatch'],
        ['TRACE juju.state.watcher watcher.go:', 'got changelog document:'],
        ['TRACE juju.state txns.go:', 'rewrote transaction:'],
        ['DEBUG juju.worker.peergrouper desired.go', 'extra'],
        ['DEBUG juju.worker.peergrouper desired.go', 'maxId'],
        ['DEBUG juju.worker.peergrouper desired.go', 'assessed'],
        ['DEBUG juju.worker.peergrouper worker.go:', 'no change in desired peer group'],
        ['DEBUG juju.worker.peergrouper desired.go:', 'assessing possible peer group changes:'],
        ['DEBUG juju.worker.peergrouper publish.go:', 'API host ports have not changed'],
        ['DEBUG juju.worker.peergrouper desired.go:', 'calculating desired peer group'],
        ['TRACE juju.state.watch watcher.go:', 'read', 'events for', 'documents'],
        ['TRACE juju.provisioner provisioner_task.go:', 'processMachinesWithTransientErrors([])'],
        ['INFO juju.apiserver.common password.go:', 'setting password for'],
        ['DEBUG juju.worker.rsyslog worker.go:', 'Reloading rsyslog configuration'],
        ['DEBUG juju.service discovery.go:', 'discovered init system "upstart" from local host'],
        ['DEBUG juju.network network.go:', 'no lxc bridge addresses to filter for machine'],
        ['INFO juju.apiserver.metricsender metricsender.go:', 'nothing to send'],
        ['INFO juju.apiserver.metricsender metricsender.go:', 'metrics collection summary: sent:0 unsent:0'],
        ['WARNING juju.worker.instanceupdater updater.go:', 'cannot get instance info for instance', 'Request limit exceeded. (RequestLimitExceeded)'],
        ['INFO juju.worker runner.go:', 'start'],
        ['juju.worker runner.go:', 'started'],
        ['INFO install'],
        ['INFO config-changed'],
        ['INFO worker.uniter.jujuc server.go:', 'running hook tool'],
        ['DEBUG worker.uniter.jujuc server.go:', 'hook context id'],
        ['INFO juju-log'],
        ['DEBUG juju-log'],
        ['DEBUG juju.worker.uniter'],
        ['INFO juju.worker.uniter'],
        ['Building dependency tree...'],
        ['Reading package lists...'],
        ['Reading state information...'],
    ]
    exclude_strings = [
        'TRACE juju.apiserver apiserver.go',
        'TRACE juju.apiserver.common resource.go',
        'TRACE juju.state.presence presence.go',
        'TRACE juju.rpc.jsoncodec codec.go',
        'TRACE juju.worker.diskmanager',
        'juju.environs.simplestreams simplestreams.go',
        ' juju.worker.storageprovisioner ',
        ' juju.environs.tools ',
        'DEBUG juju.utils.ssh authorisedkeys.go',
    ]
    for s in exclude_strings:
        exclude_patterns.append([s])

    here_is_strings = [
        'INFO here here.go:29 github.com/juju/juju/apiserver/client.processUnitLost',
        'INFO here here.go:29 github.com/juju/juju/state.(*State).stateServerAddresses',
        'INFO here here.go:29 github.com/juju/juju/state.(*State).Addresses',
    ]
    exclude_multiline = [
        'TRACE juju.cloudconfig.providerinit providerinit.go:59 Generated cloud init',
    ]
    squash = [
        'DEBUG juju.apiserver.client status.go:125 Services:',
        'DEBUG juju.apiserver admin.go:149 hostPorts:',
        'TRACE juju.state service.go:1251 service',
        'DEBUG juju.worker.peergrouper desired.go:130 machine "0"',
        'DEBUG juju.worker.peergrouper desired.go:130 machine "1"',
        'DEBUG juju.worker.peergrouper desired.go:130 machine "2"',
        'DEBUG juju.worker.peergrouper desired.go:130 machine "3"',
        'DEBUG juju.worker.peergrouper desired.go:130 machine "4"',
        'DEBUG juju.mongo open.go:117 connection failed, will retry: dial tcp ',
        'INFO juju.mongo open.go:125 dialled mongo successfully on address',
        'DEBUG juju.worker.peergrouper desired.go:116 machine "0"',
        'DEBUG juju.worker.peergrouper desired.go:116 machine "1"',
        'DEBUG juju.worker.peergrouper desired.go:116 machine "2"',
        'DEBUG juju.worker.peergrouper desired.go:116 machine "3"',
        'DEBUG juju.worker.peergrouper desired.go:116 machine "4"',
        'DEBUG juju.worker.peergrouper desired.go:39 members:',
        'WARNING juju.worker.instanceupdater updater.go:248 cannot get instance info for instance',
        'INFO juju.worker.apiaddressupdater apiaddressupdater.go:78 API addresses updated to',
        'DEBUG juju.state address.go:140 setting API hostPorts',
    ]
    sort_squash = [
        'DEBUG juju.apiserver admin.go:149 hostPorts:',
        'INFO juju.worker.apiaddressupdater apiaddressupdater.go:78 API addresses updated to',
        'DEBUG juju.state address.go:140 setting API hostPorts',
    ]

    squash_state = []
    for _ in squash:
        # squash_state.append({
        #     'last': '',
        #     'full': '',
        # })
        squash_state.append({})

    #exclude_re = []
    #for p in exclude_patterns:
    #    exclude_re.append(re.compile(p))

    talking_things = {}

    skip_lines = 0
    skip_until_timestamp = False
    with open(output_file, 'w') as out:
        for fname in sorted(glob.glob(input_files)):
            with open(fname) as f:
                for line in f.readlines():
                    thing = line.find(':')
                    if thing != -1:
                        thing = line[:thing]
                        if thing not in talking_things:
                            print thing
                            talking_things[thing] = True

                    for r in exclude_patterns:
                        miss = False
                        for p in r:
                            if line.find(p) == -1:
                                miss = True
                                break
                        if not miss:
                            skip_lines = 1
                            continue

                    if skip_lines:
                        skip_lines -= 1
                        continue

                    for i in range(len(squash)):
                        s = squash[i]
                        n = line.find(s)
                        if n != -1:
                            blob = line[n + len(s):].rstrip()
                            key = line[:line.find(':')]
                            if key not in squash_state[i]:
                                squash_state[i][key] = {
                                        'last': '',
                                        'full': '',
                                    }
                            # sometimes the log has had some de-duplicating done already,
                            # so we need to cope with 'message repeated [thing]' to just
                            # extract 'thing'.
                            if blob[-1] == ']' and line.find('message repeated') != -1:
                                blob = blob[:-1]

                            if squash_state[i][key]['last'] != blob:
                                o, n = diff_structures(squash_state[i][key]['last'], blob)
                                if s in sort_squash and o is not None:
                                    if sorted(o) == sorted(n):
                                        o = None # Signal that we don't care about this change

                                if o is not None:
                                    out.write('-' * 80)
                                    out.write('\n')
                                    out.write(pformat(o) + '\n')
                                    out.write(pformat(n) + '\n')

                                    if sorted(o) == sorted(n):
                                        out.write(' ! ! Matches if sorted ! !\n')
                                        print key

                                    #out.write(">> " + squash_state[i]['last'] + '\n')
                                    #out.write("   " + blob + '\n')
                                    out.write("<< " + squash_state[i][key]['full'])
                                    out.write(">> " + line)
                                squash_state[i][key]['last'] = blob
                                squash_state[i][key]['full'] = line

                            skip_lines = 1
                            continue

                    for s in here_is_strings:
                        if line.find(s) != -1:
                            skip_lines = 4
                            continue

                    for s in exclude_multiline:
                        if line.find(s) != -1:
                            skip_until_timestamp = True
                            skip_lines = 1
                            continue

                    if skip_lines:
                        skip_lines -= 1
                        continue

                    if skip_until_timestamp:
                        if re.search('\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d', line):
                            skip_until_timestamp = False
                        else:
                            continue

                    out.write("   " + line)


if __name__ == '__main__':
    # test_string = 'map[*peergrouper.machine]*replicaset.Member{&peergrouper.machine' \
    #               '{id: "0", wantsVote: false, hostPort: "172.31.16.138:37017"}:(*replicaset.Member)(0xc8205f0640), &peergrouper.machine' \
    #               '{id: "2", wantsVote: true, hostPort: "172.31.8.70:37017"}:(*replicaset.Member)(0xc8205f0730), &peergrouper.machine' \
    #               '{id: "3", wantsVote: true, hostPort: "172.31.20.190:37017"}:(*replicaset.Member)(0xc8205f07d0), &peergrouper.machine' \
    #               '{id: "4", wantsVote: true, hostPort: "172.31.23.160:37017"}:(*replicaset.Member)(0xc8205f0870)}'
    # print parse_structure(test_string)

    test_string = '  [[52.29.98.139:17070 172.31.16.138:17070 127.0.0.1:17070 [::1]:17070]' \
                  ' [52.29.62.54:17070 172.31.8.70:17070 127.0.0.1:17070 [::1]:17070]' \
                  ' [52.29.106.226:17070 172.31.20.190:17070 127.0.0.1:17070 [::1]:17070]' \
                  ' [52.28.93.57:17070 172.31.23.160:17070 127.0.0.1:17070 [::1]:17070]]'
    test_string = '  [[52.29.98.139:17070 172.31.16.138:17070 127.0.0.1:17070 [::1]:17070] [52.29.62.54:17070 172.31.8.70:17070 127.0.0.1:17070 [::1]:17070] [52.29.106.226:17070 172.31.20.190:17070 127.0.0.1:17070 [::1]:17070] [52.28.93.57:17070 172.31.23.160:17070 127.0.0.1:17070 [::1]:17070]]  '
    #v = parse_structure(test_string)
    #pprint(v)
    #exit(0)
    main()
