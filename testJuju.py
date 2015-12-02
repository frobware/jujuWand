#!/usr/bin/python

import os
import subprocess
import re
from argparse import ArgumentParser

"""
Run juju tests.
1. Build Juju
2. If anything changed, run tests
3. If any tests didn't compile, exit
4. If any tests failed, re-run them.

Options:
 --force to run tests even if 'make install' didn't return any output.
 --rerun just re-run the failing tests from the last run, don't rebuild.
"""


def run(cmd, write_to=None, fail_ok=False):
    """Run a command in a shell, return its output.

    If fail_ok == True, will return the text output of cmd and the return code
    of the command. If fail_ok == False, just return the output of cmd.

    At some point I will just change this to raise an exception.

    :param cmd: command to run
    :param write_to: file write to
    :param fail_ok: if true, won't exit program on cmd failure
    :return: combined stdout and stderr of cmd. If fail_ok, also return code.
    """
    out = []
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         shell=True, bufsize=1)
    lines_iterator = iter(p.stdout.readline, b'')

    for line in lines_iterator:
        print line,  # yield line
        out.append(line)
        if write_to is not None:
            write_to.write(line)

    p.poll()

    if p.returncode and not fail_ok:
        exit(p.returncode)

    elif fail_ok:
        return out, p.returncode

    return out


def main(args):
    install_out = run('go install  -v github.com/juju/juju/...')
    output_filename = os.path.join(os.path.expanduser('~'),
                                   '.jujutestoutput.txt')
    rerun_filename = os.path.join(os.path.expanduser('~'),
                                  '.jujutestoutput_rerun.txt')

    if (len(install_out) or args.force) and not args.rerun:
        if os.path.isfile(rerun_filename):
            os.remove(rerun_filename)

        with file(output_filename, 'w') as f:
            test_out, rc = run('go test ./...', f, fail_ok=True)
            f.writelines(test_out)

    else:
        # Don't have a new binary, so just re-run tests
        if os.path.isfile(rerun_filename):
            filename = rerun_filename
        elif os.path.isfile(output_filename):
            filename = output_filename

        with file(filename) as f:
            test_out = f.readlines()

    unrecoverable = False
    re_run = []
    for line in test_out:
        if(not re.search('FAIL\s+github.*\n', line) and
           not line.startswith('# github.com')):
            continue

        if re.search('failed\]\s*$', line):
            # Build failed or setup failed. No point re-running, but need
            # to report
            unrecoverable = True
        elif line.startswith('# github.com'):
            unrecoverable = True
        else:
            s = re.search('FAIL\s+(github.com.*)\s[\d\.]+s\s*$', line)
            re_run.append(s.group(1))

    if len(re_run) == 0:
        return

    print '-' * 20, 'Failing packages', '-' * 20
    for package in re_run:
        print ' ', package

    if not unrecoverable:
        print 'Re-running failed tests...'
        with file(rerun_filename, 'w') as f:
            for package in re_run:
                out, rc = run('go test ' + package, f, fail_ok=True)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--rerun', action='store_true')
    args = parser.parse_args()
    main(args)
