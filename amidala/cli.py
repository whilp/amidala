"""amidala

Usage:
        amidala
Options:
        -h --help       help
        -v --version    version
"""

import logging
import sys

import docopt

import amidala

log = logging.getLogger("amidala.cli")

def main():
    args = docopt.docopt(__doc__, version=amidala.__version__)
    log.addHandler(logging.StreamHandler())

    if args["--version"]:
        sys.stdout.write(amidala.__version__)
        return 0

