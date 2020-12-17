#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Common set of managament methods to be used by
 the different system manager classes """

import docker
import logging

data_volume = "/srv/nuvlabox/shared"
log_filename = "system-manager.log"
nuvlabox_status_file = "{}/.nuvlabox-status".format(data_volume)
nuvlabox_peripherals_folder = "{}/.peripherals".format(data_volume)
operational_status_file = f'{data_volume}/.status'

docker_stats_html_file = "docker_stats.html"
html_templates = "templates"

tls_sync_file = f"{data_volume}/.tls"


def cleanup(containers=None, exclude=None):
    """
    Cleans up all the NuvlaBox Engine containers gracefully

    :param containers: list of container objects
    :param exclude: ID to exclude
    :return:
    """

    if containers and isinstance(containers, list):

        for cont in containers:
            if exclude and exclude == cont.id:
                pass

            logging.warning("Stopping container %s" % cont)
            docker.from_env().api.stop(cont.id, timeout=5)


def set_operational_status(status: str):
    with open(operational_status_file, 'w') as s:
        s.write(status)
