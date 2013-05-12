"""amidala

Usage:
        amidala [options] <build>

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

    device = "/dev/xvdc"

    volume = None
    size = 10
    if volume:
        parent = ec2.get_all_volumes([volume])
        snapshot = ec2.create_snapshot(parent.id)
        while snap.status != "completed":
            log.debug("waiting for snapshot %s to complete", snapshot.id)
            time.sleep(1)
            snapshot.update()

        volume = ec2.create_volume(parent.size, parent.zone, snapshot=snapshot.id)
    else:
        log.debug("creating %dGB volume in %s", size, zone)
        volume = ec2.create_volume(size, zone)

    log.debug("attaching volume %s to instance %s at %s", volume.id, instance, device)
    ec2.attach_volume(volume.id, instance, device)

    mount = tempfile.mkdtemp()

    
    log.debug("mounting device %s at temporary mount %s", device, mount)
    ret = subprocess.call(["sudo", "/bin/mount", device, mount])

    exe = args["<build>"]
    log.debug("running build phase `%s`", exe)    
    subprocess.call(exe)

    log.debug("umounting temporary mount %s", mount)
    ret = subprocess.call(["sudo", "/bin/umount", "-l", mount])

    log.debug("detaching volume %s from instance %s at %s", volume.id, instance, device)
    ec2.detach_volume(volume.id, instance, device)

    log.debug("snapshotting %s", volume.id)
    snap = ec2.create_snapshot(volume.id)

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
