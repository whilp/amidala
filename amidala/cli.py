"""amidala

Usage:
        amidala [options] <build>
        amidala [options] <base> <build>

Options:
        -h --help       help
        -v --version    version
        -V --verbose=n  verbosity [default: 0]
        -s --size=n     size in GB [default: 10]
"""

import contextlib
import logging
import subprocess
import sys
import tempfile
import time

import boto.ec2
import boto.utils
import docopt

import amidala

log = logging.getLogger("amidala.cli")

def main():
    args = docopt.docopt(__doc__, version=amidala.__version__)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(fmt="%(asctime)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.level = log_level(int(args["--verbose"]))

    if args["--version"]:
        sys.stdout.write(amidala.__version__)
        return 0

    size = int(args["--size"])
    build = args["<build>"]
    base = args["<base>"]

    metadata = boto.utils.get_instance_metadata()
    instance = metadata['instance-id']
    zone = metadata['placement']['availability-zone']
    region = zone[:-1]

    log.debug("connecting to %s", region)
    ec2 = boto.ec2.connect_to_region(region)

    instance = ec2.get_all_instances([instance])[0].instances[0]

    if base is not None:
        candidates = sorted(snapshots(ec2, base))
        if not candidates:
            log.error("failed to find base snapshots matching: %s", base)
            return 1
        base = candidates[-1]
        log.debug("using base %s", base)

    with volume(ec2, instance.placement, snapshot=base, size=size) as vol:
        device = next_device(instance)
        with attachment(ec2, vol, instance, device) as dev:
            ret = subprocess.call(exe, env={"DEVICE": dev}, shell=True)

        if args["--register"]:
            image = ec2.register_image(
                name = "xxx",
                description = "xxx",
                architecture = "x86_64",
                #kernel_id,
                root_device_name = "/dev/sda1",
                block_device_map = "xxx")

@contextlib.contextmanager
def volume(snapshot, zone):
    size = snapshot.volume_size
    log.debug("creating volume in %s from %s", zone, snapshot.id)
    vol = snapshot.create_volume(zone)
    poll(vol.update, "available")
        
    try:
        yield vol
    finally:
        vol.delete()

@contextlib.contextmanager
def attachment(vol, instance, device):
    log.debug("attaching %s to %s at %s", vol.id, instance.id, device)
    vol.attach(instance.id, device)
    poll(vol.update, "in-use")

    try:
        yield device
    finally:
        vol.detach()
        poll(vol.update, "available")

def poll(fn, expect, timeout=5, interval=.1):
    start = time.time()
    stop = start + timeout
    result = fn()
    while (time.time() < stop) and (result != expect):
        time.sleep(interval)
        result = fn()

    if result != expect:
        raise Timeout("exceeded timeout %d" % timeout)

def snapshots(ec2, name):
    matches = ec2.get_all_snapshots(filters={"tag:ami": name})
    for match in sorted(matches, key=lambda x: x.start_time):
        yield match
    
def log_level(n, default=logging.DEBUG):
    return max(default - (10 * n), 1)

def next_device(block_device_mapping):
    # TODO: flesh this out.
    return "/dev/xvdc"

class Error(Exception): pass
class Timeout(Error): pass
