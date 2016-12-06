#!/usr/bin/env python3

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
Generate a bunch of docker stuff

This runs _outside_ the docker containers, and should leave the `docker`
directory with:
- `docker-compose.yaml`
- a bunch of `<kernel-name>-<install-type>/` directories

When these are actually run, they get:
- `scripts/`
- `features/`
- `reports/`
as volumes
"""

import argparse
import os
from os.path import (
    abspath,
    basename,
    dirname,
    exists,
    join,
    relpath,
    split,
)
import shutil
from glob import glob
import subprocess
import logging

import yaml

import jinja2

logging.basicConfig()

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

HERE = dirname(__file__)
TEMPLATES = join(HERE, "templates")
KERNELS = abspath(join(HERE, "..", "kernels"))
DOCKER = abspath(join(HERE, "..", "docker"))


with open(join(TEMPLATES, "docker-compose.yaml")) as fp:
    compose_template = jinja2.Template(fp.read())

dockerfile_templates = {}

for tmpl in glob(join(TEMPLATES, "Dockerfile", "*")):
    with open(tmpl) as fp:
        dockerfile_templates[basename(tmpl)] = jinja2.Template(fp.read())


def clean():
    if os.path.exists(DOCKER):
        shutil.rmtree(DOCKER)


def prep():
    os.makedirs(DOCKER)


def stage():
    scenarios = {}

    for dirpath, dirnames, filenames in os.walk(KERNELS):
        for filename in [f for f in filenames if f.endswith("scenario.yaml")]:
            frag = relpath(dirpath, KERNELS)

            bits = frag.split(os.sep)
            kernel_name = bits[0]
            platform = bits[1]

            if platform not in dockerfile_templates:
                log.warn("Dockerfile template `%s` doesn't exist", platform)
                continue

            scenario_name = frag.replace("/", "-")

            scenario = abspath(join(DOCKER, scenario_name))

            shutil.copytree(dirpath, join(scenario, "kernel-install"))

            os.makedirs(join(scenario, "kernels", kernel_name))

            shutil.copy(
                join(KERNELS, kernel_name, "kernel.yaml"),
                join(scenario, "kernels", kernel_name, "kernel.yaml"))

            with open(join(dirpath, filename)) as fp:
                context = yaml.safe_load(fp.read())

            context.update(
                kernel_name=kernel_name,
                needs_language_install=exists(join(dirpath, "language.sh")),
                needs_kernel_install=exists(join(dirpath, "kernel.sh")),
                needs_spec_install=exists(join(dirpath, "spec.sh"))
            )

            with open(join(scenario, "Dockerfile"), "w+") as fp:
                fp.write(dockerfile_templates[platform].render(context))

            scenarios[scenario_name] = context


    with open(join(DOCKER, "docker-compose.yaml"), "w+") as fp:
        fp.write(compose_template.render(scenarios=scenarios))

    return scenarios


def filter_services(services, kernels):
    selected = []

    if not kernels:
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
    services = list(stage())
    built = list(build(filter_services(services, kernels)))
    ran = list(run(built))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test some kernels")
    parser.add_argument("kernels", nargs="*", help="kernel names to test")
    args = parser.parse_args()
    main(kernels=args.kernels)
