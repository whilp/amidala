"""amidala

Usage:
        amidala
Options:
        -h --help       help
        -v --version    version
"""

import sys

import docopt

import amidala

def main():
    args = docopt.docopt(__doc__, version=amidala.__version__)
    if args["--version"]:
        sys.stdout.write(amidala.__version__)
        return 0

