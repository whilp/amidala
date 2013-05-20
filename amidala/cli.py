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
    
def snapshots(ec2, name):
    matches = ec2.get_all_snapshots(filters={"tag:ami": name})
    for match in sorted(matches, key=lambda x: x.start_time):
        yield match

def build(ec2, instance, base):
    base = snapshots(ec2, base).next()

    with volume(ec2, instance.placement, snapshot=base) as vol:
        with attachment(ec2, vol, instance) as dev:
            yield dev

def build_base(ec2, instance, exe, size=10):
    with volume(ec2, instance.placement, size) as vol:
        with attachment(ec2, vol.id, instance.id) as dev:
            subprocess.call(exe, env=dict(DEVICE=dev), shell=True)
    snap = snapshot(vol.id)
    
def build(ec2, instance, exe, snapshot):
    with volume(ec2, instance.placement, snapshot=snapshot) as vol:
        with attachment(ec2, vol, instance.id) as dev:
            subprocess.call(exe, env=dict(DEVICE=dev), shell=True)
    snap = snapshot(vol.id)
    image = register(snap)

@contextlib.contextmanager
def volume(ec2, placement, size=None, snapshot=None, timeout=5, interval=.1):
    if snapshot and size is None:
        size = snapshot.volume_size
        log.debug("creating %sGB volume in %s from %s", size, placement, snapshot.id)
    else:
        log.debug("creating %sGB volume in %s", size, placement)

    vol = ec2.create_volume(size, placement, snapshot=snapshot)
    while vol.status != "available":
        time.sleep(interval)
        vol.update()
    if vol.status != "available":
        raise Timeout("exceeded timeout %d while creating %s" % (timeout, vol.id))
        
    try:
        yield vol
    finally:
        ec2.delete_volume(vol.id)

@contextlib.contextmanager
def attachment(ec2, vol, instance, device, timeout=5, interval=.1):
    log.debug("attaching %s to %s at %s", vol.id, instance.id, device)
    ec2.attach_volume(vol.id, instance.id, device)
    
    while vol.status != "in-use":
        time.sleep(interval)
        vol.update()
    if vol.status != "in-use":
        raise Timeout("exceeded timeout %d while attaching %s" % (timeout, vol.id))

    try:
        yield device
    finally:
        ec2.detach_volume(vol.id)

def build_base(ec2, size, instance, exe):
    device = next_device(instance.block_device_mapping)

    log.debug("creating %dGB volume in %s", size, instance.placement)
    volume = ec2.create_volume(size, instance.placement)

    log.debug("attaching volume %s to %s at %s", volume.id, instance.id, device)
    ec2.attach_volume(volume.id, instance.id, device)
    
    while volume.status != "in-use":
        time.sleep(1)
        volume.update()

    log.debug("running build on %s at %s: %s", volume.id, device, exe)
    env = os.environ.copy()
    env.update(dict(
        DEVICE=device,
    ))        
    ret = subprocess.call(exe, env=env, shell=True)

    log.debug("detaching %s", volume.id)
    ec2.detach_volume(volume.id)

    while volume.status != "available":
        time.sleep(1)
        volume.update()

    log.debug("snapshotting %s", volume.id)    
    snapshot = ec2.create_snapshot(volume.id)

    while snapshot.status != "completed":
        time.sleep(1)
        snapshot.update()

    snapshot.add_tag("ami", "base")

def build(ec2):
    volume = ec2.create_volume(parent.size, parent.zone, snapshot=base)

    log.debug("attaching volume %s to instance %s at %s", volume.id, instance, device)
    ec2.attach_volume(volume.id, instance, device)

    mount = tempfile.mkdtemp()

    log.debug("running build in chroot %s at %s: %s", device, mount, exe)
    ret = subprocess.call(["sudo", "/home/will/amidala/scripts/amichroo", device, mount, exe])

    log.debug("detaching volume %s from instance %s at %s", volume.id, instance, device)
    ec2.detach_volume(volume.id, instance, device)

    log.debug("snapshotting %s", volume.id)
    snap = ec2.create_snapshot(volume.id)

    while volume.status != "available":
        log.debug("waiting for volume %s to detach", volume.id)
        time.sleep(1)
        volume.update()

    log.debug("deleting %s", volume.id)
    ec2.delete_volume(volume.id)

    while snap.status != "completed":
        log.debug("waiting for snapshot %s to complete", snap.id)
        time.sleep(1)
        snap.update()

    ebs = boto.ec2.blockdevicemapping.EBSBlockDeviceType(snapshot_id=snap.id)
    blocks = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    blocks["/dev/sda1"] = ebs

    name = "amidala-test"
    architecture = "x86_64"
    root_device_name = "/dev/sda1"
    log.debug("registering %s image '%s' with root snapshot %s at device %s",
              architecture,
              name,
              snap.id,
              root_device_name,
    )
    image = ec2.register_image(
        name=name,
        architecture=architecture,
        #kernel_id
        #ramdisk_id
        root_device_name=root_device_name,
        block_device_map=blocks)

    log.debug("created ami %s", image)
    
def log_level(n, default=logging.DEBUG):
    return max(default - (10 * n), 1)

def next_device(block_device_mapping):
    # TODO: flesh this out.
    return "/dev/xvdc"

class Error(Exception): pass
class Timeout(Error): pass
