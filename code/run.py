#!/usr/local/bin/python
# -*- coding: utf-8 -*-

""" NuvlaBox System Manager service

checks requirements and supervises all internal components of the NuvlaBox

Arguments:

"""
import sys
import os
import subprocess
import system_manager.Requirements as MinReq
import signal
import time
from system_manager.common import utils
from system_manager.common.logging import logging
from system_manager.Supervise import Supervise

__copyright__ = "Copyright (C) 2020 SixSq"
__email__ = "support@sixsq.com"

log = logging.getLogger(__name__)
self_sup = Supervise()


class GracefulShutdown:

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        log.info(f'Starting on-stop graceful shutdown of the NuvlaBox...')
        self_sup.container_runtime.launch_nuvlabox_on_stop(self_sup.on_stop_docker_image)
        sys.exit(0)


on_stop = GracefulShutdown()


def run_requirements_check():
    utils.set_operational_status(utils.status_unknown)
    if not MinReq.SKIP_MINIMUM_REQUIREMENTS:
        # Check if the system complies with the minimum hw and sw requirements for the NuvlaBox
        system_requirements = MinReq.SystemRequirements()
        software_requirements = MinReq.SoftwareRequirements()

        if not software_requirements.check_sw_requirements() or not system_requirements.check_all_hw_requirements():
            log.error("System does not meet the minimum requirements!")
            utils.set_operational_status(utils.status_degraded)
        else:
            utils.set_operational_status(utils.status_operational)
    else:
        log.warning("You've decided to skip the system requirements verification. "
                    "It is not guaranteed that the NuvlaBox will perform as it should. Continuing anyway...")
        utils.set_operational_status(utils.status_operational)

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
    self_sup.operational_status = []
    if not api or not api.pid:
        api = subprocess.Popen(api_launch.split())

    self_sup.write_container_stats_table_html()

    # refresh this node's status, to capture any changes in the COE/Cluster configuration
    self_sup.classify_this_node()

    # certificate rotation check
    if self_sup.is_cert_rotation_needed():
        log.info("Rotating NuvlaBox certificates...")
        self_sup.request_rotate_certificates()

    if self_sup.container_runtime.orchestrator != 'kubernetes':
        # in k8s there are no switched from uncluster - cluster, so there's no need for connectivity check
        self_sup.check_nuvlabox_docker_connectivity()

        # the Data Gateway comes out of the box for k8s installations
        self_sup.manage_docker_data_gateway()

        # in k8s everything runs as part of a Dep (restart policies are in place), so there's nothing to fix
        self_sup.docker_container_healer()

    statuses = [s[0] for s in self_sup.operational_status]
    status_notes = [s[-1] for s in self_sup.operational_status]

    if utils.status_degraded in statuses:
        utils.set_operational_status(utils.status_degraded, status_notes)
    elif all([x == utils.status_operational for x in statuses]) or not self_sup.operational_status:
        utils.set_operational_status(utils.status_operational)
    else:
        utils.set_operational_status(utils.status_unknown)

    time.sleep(5)

