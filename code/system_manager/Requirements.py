#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Check system requirements for the NuvlaBox Engine """

import multiprocessing
import logging
import psutil


recommended_requirements = {
    "cpu": 1,

}

class SystemRequirements(object):
    """ The SystemRequirements contains all the methods and
    definitions for checking whether a device is capable of
    hosting the NuvlaBox Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs an SystemRequirements object """

        self.minimum_requirements = {
            "cpu": 1,
            "ram": 1024,
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

        total_ram = round(psutil.virtual_memory()[0]/1024/1024)

        if total_ram < self.minimum_requirements["ram"]:
            logging.error("Your device only provides {} MBs of memory. MIN REQUIREMENTS: {} MBs"
                          .format(total_ram, self.minimum_requirements["ram"]))
            return False
        else:
            return True
