#!/usr/local/bin/python
# -*- coding: utf-8 -*-

""" NuvlaBox System Manager service

checks requirements and supervises all internal components of the NuvlaBox

Arguments:

"""
import requests
import time
import sys
import os
import subprocess
import system_manager.Requirements as MinReq
from system_manager.common import utils
from system_manager.common.logging import logging
from system_manager.Supervise import Supervise

__copyright__ = "Copyright (C) 2020 SixSq"
__email__ = "support@sixsq.com"

log = logging.getLogger(__name__)
self_sup = Supervise()


def run_requirements_check():
    if not MinReq.SKIP_MINIMUM_REQUIREMENTS:
        # Check if the system complies with the minimum hw and sw requirements for the NuvlaBox
        system_requirements = MinReq.SystemRequirements()
        software_requirements = MinReq.SoftwareRequirements()

        if not software_requirements.check_docker_requirements() or not system_requirements.check_all_hw_requirements():
            log.error("System does not meet the minimum requirements! Stopping")
            utils.cleanup(utils.list_internal_containers(), utils.docker_id)
            sys.exit(1)
    else:
        log.warning("You've decided to skip the system requirements verification. "
                    "It is not guaranteed that the NuvlaBox will perform as it should. Continuing anyway...")

    utils.set_operational_status("OPERATIONAL")
    log.info("Successfully created status file")

    peripherals = '{}/.peripherals'.format(utils.data_volume)

    try:
        # Create Directory
        os.mkdir(peripherals)
        log.info("Successfully created peripherals directory")
    except FileExistsError:
        log.info("Directory " + peripherals + " already exists")


run_requirements_check()

api_launch = 'gunicorn --bind=0.0.0.0:3636 --threads=2 --worker-class=gthread --workers=1 --reload wsgi:app --daemon'
api = None

while True:
    if not api or not api.pid:
        api = subprocess.Popen(api_launch.split())

    # docker_stats streaming
    try:
        self_sup.write_docker_stats_table_html()
    except requests.exceptions.ConnectionError:
        raise
    except:
        # catch all exceptions, cause if there's any problem, we simply want the thread to restart
        log.exception("Restarting Docker stats streamer...")

    # certificate rotation check
    if self_sup.is_cert_rotation_needed():
        log.info("Rotating NuvlaBox certificates...")
        self_sup.request_rotate_certificates()

    # COPING WITH CORNER CASE ISSUES 1
    # https://github.com/docker/for-linux/issues/293
    # this bug causes Traefik (datagateway) to go into a exited state, regardless of the Docker restart policy
    # it can happen because of abrupt system reboots, broken bind-mounts, or even Docker daemon error
    # This check serves as an external boost for the datagateway to recover when in such situations
    self_sup.keep_datagateway_up()

    # COPING WITH CORNER CASE ISSUES 2
    # https://github.com/docker/compose/issues/6385
    # occasionally, a container restart might fail to
    # find the overlay nuvlabox-shared-netword: "failed to get network during CreateEndpoint: network"
    # It might be solved in recent versions of Docker: https://github.com/moby/moby/pull/41189
    # But for older versions, this routine makes sure the datagateway data-source* containers are kept alive
    self_sup.keep_datagateway_containers_up()

    time.sleep(3)
