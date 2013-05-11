"""amidala

Usage:
        amidala --help
"""

import sys

import docopt

import amidala

def main():
    args = docopt.docopt(__doc__, version=amidala.__version__)

