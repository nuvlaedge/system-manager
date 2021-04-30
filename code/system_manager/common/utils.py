#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Common set of managament methods to be used by
 the different system manager classes """

import docker
from system_manager.common.logging import logging

data_volume = "/srv/nuvlabox/shared"
log_filename = "system-manager.log"
nuvlabox_status_file = "{}/.nuvlabox-status".format(data_volume)
cert_file = f"{data_volume}/cert.pem"
key_file = f"{data_volume}/key.pem"
nuvlabox_peripherals_folder = "{}/.peripherals".format(data_volume)
operational_status_file = f'{data_volume}/.status'
operational_status_notes_file = f'{data_volume}/.status_notes'
base_label = "nuvlabox.component=True"
node_label_key = "nuvlabox"

nuvlabox_shared_net = 'nuvlabox-shared-network'
overlay_network_service = 'nuvlabox-ack'

docker_stats_html_file = "docker_stats.html"
html_templates = "templates"

status_degraded = 'DEGRADED'
status_operational = 'OPERATIONAL'
status_unknown = 'UNKNOWN'

tls_sync_file = f"{data_volume}/.tls"

log = logging.getLogger(__name__)

with open("/proc/self/cgroup", 'r') as f:
    docker_id = f.readlines()[0].replace('\n', '').split("/")[-1]


def list_internal_containers():
    """ Gets all the containers that compose the NuvlaBox Engine """

    return docker.from_env().containers.list(filters={"label": base_label})


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

            log.warning("Stopping container %s" % cont)
            docker.from_env().api.stop(cont.id, timeout=5)


def set_operational_status(status: str, notes: list = []):
    with open(operational_status_file, 'w') as s:
        s.write(status)

    try:
        with open(operational_status_notes_file, 'w') as sn:
            sn.write('\n'.join(notes))
    except Exception as e:
        log.warning(f'Failed to write status notes {notes} in {operational_status_notes_file}: {str(e)}')
        pass
