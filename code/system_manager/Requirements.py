#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Check system requirements for the NuvlaBox Engine """

import multiprocessing
import logging
import shutil
import os
from system_manager.common.ContainerRuntime import Containers


SKIP_MINIMUM_REQUIREMENTS = False
if 'SKIP_MINIMUM_REQUIREMENTS' in os.environ and \
        str(os.environ.get('SKIP_MINIMUM_REQUIREMENTS', "false")).lower() == "true":
    SKIP_MINIMUM_REQUIREMENTS = True


class SystemRequirements(Containers):
    """ The SystemRequirements contains all the methods and
    definitions for checking whether a device is physically capable of
    hosting the NuvlaBox Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs an SystemRequirements object """

        self.log = logging.getLogger(__name__)
        super().__init__(self.log)

        self.minimum_requirements = {
            "cpu": 1,
            "ram": 512,
            "disk": 2
        }

    def check_cpu_requirements(self):
        """ Check the device for the CPU requirements according to the
         recommended ones """

        cpu_count = int(multiprocessing.cpu_count())

        if cpu_count < self.minimum_requirements["cpu"]:
            logging.error("Your device only provides {} CPUs. MIN REQUIREMENTS: {}"
                          .format(cpu_count, self.minimum_requirements["cpu"]))
            return False
        else:
            return True

    def check_ram_requirements(self):
        """ Check the device for the RAM requirements according to the
         recommended ones """

        total_ram = round(self.container_runtime.get_ram_capacity(), 2)

        if total_ram < self.minimum_requirements["ram"]:
            self.log.error("Your device only provides {} MBs of memory. MIN REQUIREMENTS: {} MBs"
                           .format(total_ram, self.minimum_requirements["ram"]))
            return False
        else:
            return True

    def check_disk_requirements(self):
        """ Check the device for the disk requirements according to the
         recommended ones """

        total_disk = round(shutil.disk_usage("/")[0]/1024/1024/1024)

        if total_disk < self.minimum_requirements["disk"]:
            self.log.error("Your device only provides {} GBs of disk. MIN REQUIREMENTS: {} GBs"
                           .format(total_disk, self.minimum_requirements["disk"]))
            return False
        else:
            return True

    def check_all_hw_requirements(self):
        """ Runs all checks """

        return self.check_cpu_requirements() and self.check_disk_requirements() and self.check_ram_requirements()


class SoftwareRequirements(Containers):
    """ The SoftwareRequirements contains all the methods and
    definitions for checking whether a device has all the Software
    dependencies and configurations required by the NuvlaBox Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs the class """

        self.log = logging.getLogger(__name__)
        super().__init__(self.log)

    def check_sw_requirements(self):
        """ Checks all the SW requirements """
        if self.container_runtime.is_version_compatible() and self.container_runtime.is_coe_enabled():
            return True

        return False
