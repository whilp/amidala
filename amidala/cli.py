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

    candidates = ec2.get_all_snapshots(filters={"tag:ami": base}, owner="self")
    if not candidates:
        log.error("failed to find snapshots matching: %s", base)
        return 1

    snapshot = sorted(candidates, key=lambda x: x.start_time)[-1]
    log.debug("using base snapshot %s", snapshot.id)

    with volume(snapshot, instance.placement) as vol:
        device = next_device(instance)
        
        with attachment(vol, instance, device) as dev:
            ret = subprocess.call(exe, env={"DEVICE": dev}, shell=True)

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

    
def log_level(n, default=logging.DEBUG):
    return max(default - (10 * n), 1)

def next_device(block_device_mapping):
    # TODO: flesh this out.
    return "/dev/xvdc"

class Error(Exception): pass
class Timeout(Error): pass
