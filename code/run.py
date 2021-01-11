#!/usr/local/bin/python
# -*- coding: utf-8 -*-

""" NuvlaBox System Manager service - Supervisor

supervises all internal components of the NuvlaBox

Arguments:

"""
import requests
import time
from system_manager.common.logging import logging
from system_manager.Supervise import Supervise

__copyright__ = "Copyright (C) 2020 SixSq"
__email__ = "support@sixsq.com"

log = logging.getLogger(__name__)
self_sup = Supervise()


while True:
    # docker_stats streaming
    try:
        self_sup.write_docker_stats_table_html()
    except requests.exceptions.ConnectionError:
        raise
    except:
        # catch all exceptions, cause if there's any problem, we simply want the thread to restart
        log.exception("Restarting Docker stats streamer...")

    # certificate rotation check
    if self_sup.is_cert_rotation_needed():
        log.info("Rotating NuvlaBox certificates...")
        self_sup.request_rotate_certificates()

    # COPING WITH CORNER CASE ISSUES 1
    # https://github.com/docker/for-linux/issues/293
    # this bug causes Traefik (datagateway) to go into a exited state, regardless of the Docker restart policy
    # it can happen because of abrupt system reboots, broken bind-mounts, or even Docker daemon error
    # This check serves as an external boost for the datagateway to recover when in such situations
    self_sup.keep_datagateway_up()

    # COPING WITH CORNER CASE ISSUES 2
    # https://github.com/docker/compose/issues/6385
    # occasionally, a container restart might fail to
    # find the overlay nuvlabox-shared-netword: "failed to get network during CreateEndpoint: network"
    # It might be solved in recent versions of Docker: https://github.com/moby/moby/pull/41189
    # But for older versions, this routine makes sure the datagateway data-source* containers are kept alive
    self_sup.keep_datagateway_containers_up()

    time.sleep(3)
