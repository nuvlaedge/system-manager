#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Check system requirements for the NuvlaBox Engine """

import multiprocessing
import logging
import shutil
import docker


class SystemRequirements(object):
    """ The SystemRequirements contains all the methods and
    definitions for checking whether a device is physically capable of
    hosting the NuvlaBox Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs an SystemRequirements object """

        self.log = logging.getLogger("app")
        self.minimum_requirements = {
            "cpu": 1,
            "ram": 768,
            "disk": 1
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

        self.log = logging.getLogger("app")

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
            if not self.check_active_swarm():
                self.log.error("The minimum requirements for your Docker setup are not met!")
                return False
            else:
                return True

    def check_active_swarm(self):
        """ Checks that the device is running on Swarm mode """

        if not self.docker_client.swarm.attrs:
            self.log.error("Your device is not running in Swarm mode! "
                            "To install the NuvlaBox Engine, please first run 'docker swarm init'")
            return False
        elif not self.check_is_swarm_manager():
            self.log.error("Your device is not a Swarm manager! "
                          "The NuvlaBox Engine can only run in Swarm Manager nodes")
            return False
        else:
            return True

    def check_is_swarm_manager(self):
        """ Checks that the device is a Swarm manager """

        return self.docker_client.info()["Swarm"]["NodeID"] in \
            [manager["NodeID"] for manager in self.docker_client.info()["Swarm"]["RemoteManagers"]]

