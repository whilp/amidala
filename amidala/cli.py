"""amidala

Usage:
        amidala [options] <build>
        amidala [options] <base> <build>

Options:
        -h --help       help
        -v --version    version
        -V --verbose=n  verbosity [default: 0]
"""

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

    meta = boto.utils.get_instance_metadata()
    instance = meta["instance-id"]
    zone = meta["placement"]["availability-zone"]
    region = zone[:-1]
    log.debug("running on instance %s in %s", instance, zone)

    log.debug("connecting to %s", region)
    ec2 = boto.ec2.connect_to_region(region)

    base = args["<base>"]
    exe = args["<build>"]
    device = "/dev/xvdc"

    cmd = build
    if base is None:
        cmd = build_base

    return cmd(ec2)

def build_base(ec2):
    pass

def build(ec2):
    volume = ec2.create_volume(parent.size, parent.zone, snapshot=base)

    log.debug("attaching volume %s to instance %s at %s", volume.id, instance, device)
    ec2.attach_volume(volume.id, instance, device)

    mount = tempfile.mkdtemp()

    log.debug("running build in chroot %s at %s: %s", device, mount, exe)
    ret = subprocess.call(["sudo", "/home/will/amidala/scripts/amichroot", device, mount, exe])

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
