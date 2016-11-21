#!/usr/bin/env python3
"""
Generate a bunch of docker stuff

This runs _outside_ the docker containers.
"""
import argparse
import os
from os.path import (
    abspath,
    dirname,
    join,
    relpath,
    split,
)
import shutil
from glob import glob
import subprocess
import logging

import yaml


logging.basicConfig()

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

HERE = dirname(__file__)
KERNELS = abspath(join(HERE, "..", "kernels"))
DOCKER = abspath(join(HERE, "..", "docker"))

TEMPLATE = """FROM jupyter/base-notebook
USER jovyan
WORKDIR $HOME
COPY ./kernel-install/pre-install.sh $HOME/kernel-install/pre-install.sh
USER root
WORKDIR /home/jovyan
RUN /bin/bash ./kernel-install/pre-install.sh
COPY ./kernels/{name} $HOME/kernels/{name}
COPY ./kernel-install/install.sh $HOME/kernel-install/install.sh
USER jovyan
RUN /bin/bash ./kernel-install/install.sh
CMD ["python3", "scripts/test_kernels.py"]
"""

services = {}


def clean():
    if os.path.exists(DOCKER):
        shutil.rmtree(DOCKER)


def prep():
    os.makedirs(DOCKER)


def stage():
    for dirpath, dirnames, filenames in os.walk(KERNELS):
        for filename in [f for f in filenames if f.endswith("scenario.yaml")]:
            if "debian" not in dirpath:
                continue

            frag = relpath(dirpath, KERNELS)
            kernel_name = frag.split(os.sep)[0]
            scenario_name = frag.replace("/", "_")
            scenario = abspath(join(DOCKER, scenario_name))

            shutil.copytree(dirpath, join(scenario, "kernel-install"))

            os.makedirs(join(scenario, "kernels", kernel_name))

            shutil.copy(
                join(KERNELS, kernel_name, "kernel.yaml"),
                join(scenario, "kernels", kernel_name, "kernel.yaml"))

            with open(join(scenario, "Dockerfile"), "w+") as fp:
                fp.write(TEMPLATE.format(name=kernel_name))

            services[scenario_name] = {
                "build": {
                    "context": scenario_name
                },
                "volumes": [
                    "../reports:/home/jovyan/reports",
                    "../scripts:/home/jovyan/scripts",
                    "../features:/home/jovyan/features"
                ]
            }

            yield scenario_name

    with open(join(DOCKER, "docker-compose.yml"), "w+") as fp:
        yaml.safe_dump(
            data=dict(
                version="2",
                services=services
            ),
            stream=fp,
            default_flow_style=False
        )

    return services


def filter_services(services, kernels):
    selected = []

    if kernels is None:
        selected = list(services)
    else:
        for svc in services:
            for kernel in kernels:
                if svc.startswith(kernel):
                    selected += [svc]

    return list(set(selected))


def build(services):
    log.info("Running %s", services)

    for svc in services:
        try:
            p = subprocess.Popen(["docker-compose", "build", svc], cwd=DOCKER)
            p.wait()
            yield(svc)
        except Exception as err:
            log.error("Couldn't build %s", svc)


def run(services):
    log.info("Running %s", services)
    for svc in services:
        try:
            p = subprocess.Popen(["docker-compose", "up", svc], cwd=DOCKER)
            p.wait()
            yield svc
        except Exception as err:
            log.error("Couldn't run %s", svc)


def main(kernels=None):
    clean()
    prep()
    services = stage()
    built = list(build(filter_services(services, kernels)))
    ran = list(run(built))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test some kernels")
    parser.add_argument("kernels", nargs="*", help="kernel names to test")
    args = parser.parse_args()
    main(kernels=args.kernels)
