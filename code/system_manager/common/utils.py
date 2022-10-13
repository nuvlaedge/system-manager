#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Common set of managament methods to be used by
 the different system manager classes """
import logging
import os

data_volume = "/srv/nuvlabox/shared"
log_filename = "system-manager.log"
nuvlaedge_status_file = "{}/.nuvlabox-status".format(data_volume)
cert_file = f"{data_volume}/cert.pem"
key_file = f"{data_volume}/key.pem"
nuvlaedge_peripherals_folder = "{}/.peripherals".format(data_volume)
operational_status_file = f'{data_volume}/.status'
operational_status_notes_file = f'{data_volume}/.status_notes'
base_label = "nuvlaedge.component=True"
node_label_key = "nuvlaedge"

nuvlaedge_shared_net = 'nuvlabox-shared-network'
nuvlaedge_shared_net_unencrypted = f'{data_volume}/.nuvlabox-shared-net-unencrypted'
overlay_network_service = 'nuvlaedge-ack'

container_stats_html_file = "docker_stats.html"
container_stats_json_file = f"{data_volume}/docker_stats.json"

html_templates = "templates"

status_degraded = 'DEGRADED'
status_operational = 'OPERATIONAL'
status_unknown = 'UNKNOWN'

tls_sync_file = f"{data_volume}/.tls"

log = logging.getLogger(__name__)


def set_operational_status(status: str, notes: list = []):
    with open(operational_status_file, 'w') as s:
        s.write(status)

    try:
        with open(operational_status_notes_file, 'w') as sn:
            sn.write('\n'.join(notes))
    except Exception as e:
        log.warning(f'Failed to write status notes {notes} in {operational_status_notes_file}: {str(e)}')
        pass


def status_file_exists() -> bool:
    if os.path.exists(operational_status_file):
        return True

    return False
