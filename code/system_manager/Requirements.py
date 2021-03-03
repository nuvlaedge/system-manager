#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Check system requirements for the NuvlaBox Engine """

import multiprocessing
import logging
import shutil
import docker
import os


SKIP_MINIMUM_REQUIREMENTS = False
if 'SKIP_MINIMUM_REQUIREMENTS' in os.environ and \
        str(os.environ.get('SKIP_MINIMUM_REQUIREMENTS', "false")).lower() == "true":
    SKIP_MINIMUM_REQUIREMENTS = True


class SystemRequirements(object):
    """ The SystemRequirements contains all the methods and
    definitions for checking whether a device is physically capable of
    hosting the NuvlaBox Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs an SystemRequirements object """

        self.log = logging.getLogger(__name__)
        self.minimum_requirements = {
            "cpu": 1,
            "ram": 512,
            "disk": 2
        }
        self.docker_client = docker.from_env()

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

        total_ram = round((self.docker_client.info()['MemTotal']/1024/1024), 2)

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


class SoftwareRequirements(object):
    """ The SoftwareRequirements contains all the methods and
    definitions for checking whether a device has all the Software
    dependencies and configurations required by the NuvlaBox Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs the class """

        self.log = logging.getLogger(__name__)

        self.minimum_requirements = {
            "docker_version": 18
        }
        self.docker_client = docker.from_env()

    def check_docker_requirements(self):
        """ Checks if Docker version is high enough """

        docker_major_version = int(self.docker_client.version()["Components"][0]["Version"].split(".")[0])

        if docker_major_version < self.minimum_requirements["docker_version"]:
            self.log.error("Your Docker version is too old: {}. MIN REQUIREMENTS: Docker {} or newer"
                           .format(docker_major_version, self.minimum_requirements["docker_version"]))
            return False
        else:
            if self.check_active_swarm():
                self.log.info("Running in Swarm mode")
            return True

    def check_active_swarm(self):
        """ Checks that the device is running on Swarm mode """

        return False if not self.docker_client.swarm.attrs else True
