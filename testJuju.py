#!/usr/bin/python

import os
import subprocess
import re
from argparse import ArgumentParser
from wand import run

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


def main(args):
    try:
        install_out = run('go install  -v github.com/juju/juju/...')
    except subprocess.CalledProcessError as e:
        exit(e.returncode)
    output_filename = os.path.join(os.path.expanduser('~'),
                                   '.jujutestoutput.txt')
    rerun_filename = os.path.join(os.path.expanduser('~'),
                                  '.jujutestoutput_rerun.txt')

    if (len(install_out) or args.force) and not args.rerun:
        if os.path.isfile(rerun_filename):
            os.remove(rerun_filename)

        filename = output_filename
        with open(output_filename, 'w') as f:
            test_out, rc = run('go test ./...', write_to=f, fail_ok=True)

    else:
        # Don't have a new binary, so just re-run tests
        if os.path.isfile(rerun_filename):
            filename = rerun_filename
        elif os.path.isfile(output_filename):
            filename = output_filename

    with open(filename) as f:
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
        with open(rerun_filename, 'w') as f:
            for package in re_run:
                out, rc = run('go test ' + package, write_to=f, fail_ok=True)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--rerun', action='store_true')
    args = parser.parse_args()
    main(args)
