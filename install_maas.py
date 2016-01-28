#!/usr/bin/python3
import os
import tempfile

import shelly
import yaml
import json
import time


class Runner:
    def __init__(self, settings_file_name):
        with open(settings_file_name) as f:
            self.settings = yaml.load(f)
            self.settings_file_name = settings_file_name

    def sudo(self, cmd, fail_ok=False):
        return shelly.sudo(cmd.format(**self.settings), fail_ok=fail_ok)

    def run(self, cmd, fail_ok=False):
        return shelly.run(cmd.format(**self.settings), fail_ok=fail_ok)

    def maas(self, cmd, quiet=False):
        cmd = 'maas {profile} ' + cmd

        rc = 1
        tries_remaining = 20
        out = ''
        while rc and tries_remaining:
            tries_remaining -= 1
            out, rc = shelly.run(cmd.format(**self.settings), timeout=5,
                                 fail_ok=True, quiet=quiet)
            if rc:
                print('command failed (rc={}), {} attempts remaining'.format(
                        rc, tries_remaining))
            time.sleep(5)

        try:
            return json.loads(out)
        except ValueError:
            return []

    def save_settings(self):
        with open(self.settings_file_name, 'w') as f:
            yaml.dump(self.settings, f)


def setup_maas_server(r, settings):
    # We can find if there is an admin already created by asking for its API
    # key.
    settings['apikey'], rc = r.sudo('maas-region-admin apikey '
                                    '--username {username}', fail_ok=True)
    if rc > 0:
        # Our admin user doesn't exist - create it
        r.sudo('maas-region-admin createadmin --username={username} '
               '--password={password} --email={email}')

        # Fetch the API key if we need it.
        settings['apikey'] = r.sudo('maas-region-admin apikey '
                                    '--username {username}').rstrip()
    r.save_settings()

    while r.run('maas login {profile} http://{ipaddress}/MAAS {apikey}',
                fail_ok=True)[1]:
        time.sleep(3)

    r.maas('boot-resources import')


def setup_network(r, settings):
    # Get information about node-group-interfaces that we need to set up the
    # network.
    node_groups = r.maas('node-groups list')
    r.settings['cluster_master_uuid'] = node_groups[0]['uuid']
    interface_list = r.maas('node-group-interfaces list {cluster_master_uuid}')

    # Find the interface we want to manage then copy the settings from our
    # settings YAML's network section over to MAAS.
    # Note that router_ip is used to set the default gateway, but isn't listed
    # by node-group-interface read!
    for interface in interface_list:
        if interface['ip'] == settings['network']['ip']:
            cmd = 'node-group-interface update {cluster_master_uuid} '
            cmd += interface['name']
            for k, v in settings['network'].items():
                cmd += ' {}={}'.format(k, v)
            r.maas(cmd)


def setup_mirror(r):
    r.sudo("sstream-mirror"
           " --keyring=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
           " http://maas.ubuntu.com/images/ephemeral-v2/daily/"
           " /var/www/html/maas/images/ephemeral-v2/daily"
           " 'arch=amd64'"
           " 'subarch~(generic|hwe-t)'"
           " 'release~(trusty|precise)'"
           " --max=1")

    r.maas('boot-sources create url=http://{ipaddress}/MAAS '
           'keyring_filename=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg')
    r.maas('boot-resources import')

    r.maas('maas set-config name=main_archive '
           'value="http://mirror.bytemark.co.uk/ubuntu/"')


def set_maas_defaults(r, settings):
    shelly.install_packages(['debconf-utils'])
    deb_config = [
        'maas-cluster-controller	maas-cluster-controller/maas-url	string	http://{ipaddress}/MAAS',
        'maas-region-controller-min	maas/default-maas-url	string	{ipaddress}',
    ]

    f = tempfile.NamedTemporaryFile(mode='w', delete=False)
    for cfg in deb_config:
        f.write(cfg.format(**settings) + '\n')
    f.close()

    r.sudo('sudo debconf-set-selections ' + f.name)
    os.unlink(f.name)


def wait_for_quiet(silence=30):
    # Wait for the maas log to have no new entries for <silence> seconds.
    while time.time() < os.path.getmtime('/var/log/maas/maas.log') + silence:
        time.sleep(1)


def setup_maas_nodes(r, settings):
    # If we haven't enlisted all the nodes, do so now
    nodes = r.maas('nodes list', quiet=True)
    if len(nodes) < len(settings['nodes']):
        r.run('{pdu_path}/all_off.py')
        r.run('{pdu_path}/all_on.py')

    # Wait for the nodes to appear
    while len(nodes) < len(settings['nodes']):
        print('found {} of {} nodes'.format(len(nodes), len(settings['nodes'])))
        time.sleep(5)
        nodes = r.maas('nodes list')

    # We know the mac address of a network card in each node. Use that to find
    # per-node settings and set them.
    for node in nodes:
        for mac in node['macaddress_set']:
            node_settings = settings['nodes'].get(mac['mac_address'])

            if not node_settings:
                continue

            r.maas(
                'node update {system_id} power_type="amt" '
                'power_parameters_power_address={n} '
                'power_parameters_power_pass={n} '
                'hostname={hostname}'.format(
                    system_id=node['system_id'],
                    n=node_settings['pdu_index'] + 1,
                    hostname=node_settings['hostname']))

    r.run('{pdu_path}/all_off.py')
    r.maas('nodes accept-all')


def setup_maas_fabrics(r):
    fabric_name = None
    subnets = r.maas('subnets read')
    for subnet in subnets:
        if subnet['cidr'] == '192.168.1.0/24':
            fabric_name = subnet['vlan']['fabric']
            break

    fabrics = r.maas('fabrics read')
    for fabric in fabrics:
        if fabric['name'] == fabric_name:
            r.maas('fabric update {id} name=managed'.format(**fabric))
            break


def main():
    runner = Runner('maas.yaml')
    settings = runner.settings

    set_maas_defaults(runner, settings)

    ppas = [
        'ppa:maas/stable',
    ]
    shelly.install_ppas(ppas)
    packages = [
        'maas',
        'wsmancli',
        'amtterm',
        'simplestreams',
        'ubuntu-cloudimage-keyring',
        'apache2',
    ]
    shelly.install_packages(packages)

    if not os.path.islink('/usr/local/bin/amttool'):
        runner.sudo('ln -s {pdu_path}/amttool /usr/local/bin/amttool')

    setup_maas_server(runner, settings)
    setup_mirror(runner)
    setup_network(runner, settings)
    wait_for_quiet(90)
    setup_maas_nodes(runner, settings)

    setup_maas_fabrics(runner)

    runner.save_settings()


if __name__ == '__main__':
    main()
