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

import boto.ec2
import boto.utils
import docopt

import amidala

log = logging.getLogger("amidala.cli")

def main():
    args = docopt.docopt(__doc__, version=amidala.__version__)

    log.addHandler(logging.StreamHandler())
    log.level = log_level(int(args["--verbose"]))

    if args["--version"]:
        sys.stdout.write(amidala.__version__)
        return 0

    region = "us-west-1"
    ec2 = boto.ec2.connect_to_region(region)

    instance = boto.utils.get_instance_metadata()["instance-id"]
    device = "/dev/xvdb"

    volume = None
    size = 10
    if volume:
        parent = ec2.get_all_volumes([volume])
        snapshot = ec2.create_snapshot(parent)
        volume = ec2.create_volume(parent.size, parent.zone, snapshot=snapshot)
    else:    
        volume = ec2.create_volume(size, region)

    ec2.attach_volume(volume.id, instance, device)

    mount = tempfile.mkdtemp()

    ret = subprocess.call(["sudo", "mount", device, mount])

    exe = args["<build>"]
    subprocess.call(exe)

    ret = subprocess.call(["sudo", "umount", mount])

    ec2.detach_volume(volume.id, instance, device)

    snap = ec2.create_snapshot(volume)

    ebs = boto.ec2.blockdevicemapping.EBSBlockDeviceType(snapshot_id=snap.id)
    blocks = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    blocks["/dev/sda1"] = ebs
    
    ami = ec2.register_image(
        name="amidala-test",
        architecture="x86_64",
        #kernel_id
        #ramdisk_id
        root_device_name="/dev/sda1",
        block_device_map=blocks)

def log_level(n, default=logging.ERROR):
    return max(default - (10 * n), 1)
