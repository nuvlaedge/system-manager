#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Contains the supervising class for all NuvlaBox Engine components """

import docker
import time


class Supervise(object):
    """ The Supervise class contains all the methods and
    definitions for making sure the NuvlaBox Engine is running smoothly,
    including all methods for dealing with system disruptions and
    graceful shutdowns
    """

    def __init__(self):
        """ Constructs the Supervise object """

        self.docker_client = docker.from_env()
        self.base_label = "nuvlabox.component=True"
        self.state = "ACTIVE"
        self.printer_file = "index.html"

        with open("/proc/self/cgroup", 'r') as f:
            self.docker_id = f.readlines()[0].replace('\n', '').split("/")[-1]

    def list_internal_containers(self):
        """ Gets all the containers that compose the NuvlaBox Engine """

        return self.docker_client.containers.list(filters={"label": self.base_label})

    def printer(self, text):
        """ Pretty prints """

        with open(self.printer_file, 'w') as p:
            p.write("{} \n\n{}".format(text, time.ctime()))




