"""amidala

Usage:
        amidala [options]

Options:
        -h --help       help
        -v --version    version
        -V --verbose=n  verbosity [default: 0]
"""

import logging
import sys

import docopt

import amidala

log = logging.getLogger("amidala.cli")

def main():
    args = docopt.docopt(__doc__, version=amidala.__version__)

    print args
    log.addHandler(logging.StreamHandler())
    log.level = log_level(int(args["--verbose"]))

    if args["--version"]:
        sys.stdout.write(amidala.__version__)
        return 0

def log_level(n, default=logging.ERROR):
    return max(default - (10 * n), 1)
