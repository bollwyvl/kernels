#!/usr/bin/env python
import argparse
import asyncio
import enum
import json
import logging

from glob import glob
from pprint import pprint

from os.path import (
    abspath,
    dirname,
    join,
    basename,
)

from concurrent.futures._base import TimeoutError

import jsonschema

from jupyter_client.manager import KernelManager

logging.basicConfig()

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


HERE = dirname(__file__)

FEATURE_ROOT = abspath(join(HERE, "..", "features"))
KERNEL_ROOT = abspath(join(HERE, "..", "kernels"))

FEATURES = glob(join(FEATURE_ROOT, "*", "*"))
KERNELS = glob(join(KERNEL_ROOT, "*"))

TIMEOUT = 2


class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, enum.Enum):
            return obj.value
        return super(EnumEncoder, self).default(self, obj)


json_encoder = EnumEncoder()


class STATUS(enum.Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


async def test_kernel(kernel_path):
    loop = asyncio.get_event_loop()
    log.info("testing {}".format(basename(kernel_path)))
    with open(join(kernel_path, "meta.json")) as fp:
        kernel_meta = json.load(fp)

    result = {}

    for feature in FEATURES:
        feature_name = feature.replace(FEATURE_ROOT, "")[1:]
        future = loop.run_in_executor(
            None, test_feature,
            kernel_meta["kernel_name"],
            feature)
        try:
            result[feature_name] = await asyncio.wait_for(future, TIMEOUT,
                                                          loop=loop)
        except TimeoutError:
            result[feature_name] = STATUS.TIMEOUT

    return {basename(kernel_path): result}


def test_feature(kernel_name, feature):
    manager = KernelManager(kernel_name=kernel_name)
    manager.start_kernel()
    client = manager.client()

    with open(join(feature, "provided.json")) as fp:
        provided = json.load(fp)

    with open(join(feature, "expected.schema.json")) as fp:
        expected = json.load(fp)

    msg = client.session.msg(provided["header"]["msg_type"],
                             provided["content"])
    client.shell_channel.send(msg)

    response = client.shell_channel.get_msg(timeout=TIMEOUT)

    try:
        jsonschema.validate(instance=response, schema=expected)
    except Exception as err:
        log.exception(err)
        return STATUS.ERROR

    return STATUS.OK


async def main(kernels=None):
    if not kernels:
        kernel_paths = KERNELS
    else:
        kernel_paths = [kernel for kernel in KERNELS
                        if basename(kernel) in kernels]

    result = {"kernels": {}}

    for kernel_path in kernel_paths:
        kernel_result = await test_kernel(kernel_path)
        result["kernels"].update(kernel_result)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test some kernels")
    parser.add_argument("kernels", nargs="*", help="kernel names to test")
    args = parser.parse_args()
    loop = asyncio.get_event_loop()
    output = loop.run_until_complete(main(kernels=args.kernels))
    pprint(output)
