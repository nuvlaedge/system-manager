#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Common set of managament methods to be used by
 the different system manager classes """

import docker
import requests
import logging

data_volume = "/srv/nuvlabox/shared"
log_filename = "system-manager.log"

server_cert_file = "nuvlabox-api-server-cert.pem"
server_key_file = "nuvlabox-api-server-key.pem"
client_cert_file = "nuvlabox-api-client-cert.pem"
client_key_file = "nuvlabox-api-client-key.pem"
ca_file = "ca.pem"

nuvlabox_api_certs_folder = "{}/nuvlabox-api".format(data_volume)


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


def change_operational_status(status):
    """ Requests the agent to change the operational status """

    url = "http://agent:5000/api/status?value={}".format(status)
    requests.get(url)
