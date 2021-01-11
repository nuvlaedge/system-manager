#!/usr/local/bin/python
# -*- coding: utf-8 -*-

"""NuvlaBox System Manager service - check requirements

This service makes sure the NuvlaBox engine can be
installed in the device

Arguments:

"""

# import logging
import sys
import os
import system_manager.Requirements as MinReq
from system_manager.common import utils
from system_manager.common.logging import logging

__copyright__ = "Copyright (C) 2020 SixSq"
__email__ = "support@sixsq.com"


log = logging.getLogger(__name__)


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


if __name__ == "__main__":
    run_requirements_check()



