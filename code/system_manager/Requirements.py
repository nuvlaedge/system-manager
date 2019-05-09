#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Check system requirements for the NuvlaBox Engine """

import multiprocessing
import logging



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
            logging.info("You have enough CPUs to run the NuvlaBox: {}".format(cpu_count))
            return True
