#!/usr/local/bin/python
# -*- coding: utf-8 -*-

""" NuvlaEdge System Manager service

checks requirements and supervises all internal components of the NuvlaEdge

Arguments:

"""
import sys
import os
import subprocess
import system_manager.Requirements as MinReq
import signal
import time
import logging

from system_manager.common import utils

from system_manager.Supervise import Supervise
from system_manager.manager.manager import Manager
from system_manager.manager.schemas import EngineComponents, InitialSettings


__copyright__ = "Copyright (C) 2021 SixSq"
__email__ = "support@sixsq.com"


# Watchdog for compulsory NuvlaEdge engine microservices
manager_settings: InitialSettings = InitialSettings()
microservice_manager: Manager = Manager(manager_settings)
microservice_manager.find_engine_components()

while not microservice_manager.engine_ready():
    time.sleep(1)
    microservice_manager.find_engine_components()

# Publish main microservice configuration
microservice_manager.register_components()

log = logging.getLogger(__name__)
logging.basicConfig(format='%(levelname)s - %(filename)s/%(module)s/%(funcName)s '
                           '- %(message)s', level='INFO')

supervisor = Supervise(
    manager_settings,
    compute_api=microservice_manager.ENGINE_COMPONENTS.get(EngineComponents.compute_api),
    agent=microservice_manager.ENGINE_COMPONENTS.get(EngineComponents.agent))


class GracefulShutdown:

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        log.info(f'Starting on-stop graceful shutdown of the NuvlaEdge...')
        supervisor.container_runtime.launch_nuvlaedge_on_stop(supervisor.on_stop_docker_image)
        sys.exit(0)


on_stop = GracefulShutdown()


def requirements_check(sw_rq: MinReq.SoftwareRequirements,
                       system_rq: MinReq.SystemRequirements,
                       operational_status: list):
    """
    Checks if the NuvlaEdge requirements are met

    :param sw_rq: instance of MinReq.SoftwareRequirements
    :param system_rq: instance of MinReq.SystemRequirements
    :param operational_status: list of tuples (status, status_notes)

    :return:
    """
    sw_rq.not_met = []
    system_rq.not_met = []
    meet_sw_rq = sw_rq.check_sw_requirements()
    meet_hw_rq = system_rq.check_all_hw_requirements()
    if not meet_sw_rq or not meet_hw_rq:
        not_met = sw_rq.not_met + system_rq.not_met
        not_met_msg = "\n\t* " + "\n\t* ".join(not_met) if not_met else ''
        err_msg = f"System does not meet the minimum requirements! {not_met_msg} \n"

        log.warning(err_msg)
        if not MinReq.SKIP_MINIMUM_REQUIREMENTS:
            if not utils.status_file_exists():
                log.error("Cannot continue...")
                # sleep to make sure we don't fall into Docker's exponential restart time
                time.sleep(10)
                sys.exit(1)

            operational_status.append((utils.status_degraded, err_msg))
        else:
            operational_status.append((utils.status_unknown,
                                       'Minimum requirements not met, but '
                                       'SKIP_MINIMUM_REQUIREMENTS is enabled'))
            log.warning("You've decided to skip the system requirements verification. "
                        "It is not guaranteed that the NuvlaEdge will perform as it "
                        "should. Continuing anyway...")

    if not utils.status_file_exists():
        utils.set_operational_status(utils.status_operational)

        peripherals = '{}/.peripherals'.format(utils.data_volume)

        try:
            # Dynamically create directory for peripheral managers
            os.mkdir(peripherals)
            log.info("Successfully created peripherals directory")
        except FileExistsError:
            log.info("Directory " + peripherals + " already exists")


system_requirements = MinReq.SystemRequirements(
    compute_api=microservice_manager.ENGINE_COMPONENTS.get(EngineComponents.compute_api),
    agent=microservice_manager.ENGINE_COMPONENTS.get(EngineComponents.agent)
)
software_requirements = MinReq.SoftwareRequirements(
    compute_api=microservice_manager.ENGINE_COMPONENTS.get(EngineComponents.compute_api),
    agent=microservice_manager.ENGINE_COMPONENTS.get(EngineComponents.agent)
)


while True:

    supervisor.operational_status = []
    requirements_check(software_requirements, system_requirements,
                       supervisor.operational_status)

    # refresh this node's status, to capture any changes in the COE/Cluster configuration
    supervisor.classify_this_node()

    # certificate rotation check
    if supervisor.is_cert_rotation_needed():
        log.info("Rotating NuvlaEdge certificates...")
        supervisor.request_rotate_certificates()

    if supervisor.container_runtime.orchestrator != 'kubernetes':
        # in k8s there are no switched from uncluster - cluster, so there's no need
        # for connectivity check
        supervisor.check_nuvlaedge_docker_connectivity()

        # the Data Gateway comes out of the box for k8s installations
        supervisor.manage_docker_data_gateway()

        # in k8s everything runs as part of a Dep (restart policies are in place),
        # so there's nothing to fix
        supervisor.docker_container_healer()

    statuses = [s[0] for s in supervisor.operational_status]
    status_notes = [s[-1] for s in supervisor.operational_status]

    if utils.status_degraded in statuses:
        utils.set_operational_status(utils.status_degraded, status_notes)
    elif all([x == utils.status_operational for x in statuses]) \
            or not supervisor.operational_status:
        utils.set_operational_status(utils.status_operational)
    else:
        utils.set_operational_status(utils.status_unknown)

    time.sleep(5)

    # Update engine MS
    microservice_manager.find_engine_components()
    microservice_manager.register_components()
