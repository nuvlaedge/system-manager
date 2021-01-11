#!/usr/local/bin/python
# -*- coding: utf-8 -*-

"""NuvlaBox System Manager service - api

Internal dashboard

Arguments:

"""

import os
import signal
import time
from flask import Flask, render_template, redirect, Response, request
from system_manager.common import utils
from system_manager.common.logging import logging
from system_manager.Supervise import Supervise


__copyright__ = "Copyright (C) 2020 SixSq"
__email__ = "support@sixsq.com"

log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["supervisor"] = Supervise()
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.route('/')
def main():
    return redirect("/dashboard", code=302)


@app.route('/dashboard')
def dashboard():
    """ Dashboard """

    docker_info = app.config["supervisor"].get_docker_info()
    nuvlabox_status = app.config["supervisor"].get_nuvlabox_status()
    docker_stats = app.config["supervisor"].reader(utils.docker_stats_html_file)

    # net_stats is provided in the form of {"iface1": {"rx_bytes": X, "tx_bytes": Y}, "iface2": ...}
    # Reference: nuvlabox/agent
    #
    # Need to parse it into a chartjs dataset
    net_stats = {
        "labels": []
    }

    rx = []
    tx = []
    for nstat in nuvlabox_status.get("resources", {}).get("net-stats", []):
        iface = nstat.get('interface')
        if not iface:
            continue

        net_stats['labels'].append(iface)
        rx.append(float(nstat['bytes-received']))
        tx.append(float(nstat['bytes-transmitted']))

    net_stats["datasets"] = [{
        "label": "rx_bytes",
        "backgroundColor": "#d88d0e",
        "borderColor": "#d88d0e",
        "borderWidth": 1,
        "data": rx
    }, {
        "label": "tx_bytes",
        "backgroundColor": "#61acb5",
        "borderColor": "#61acb5",
        "borderWidth": 1,
        "data": tx
    }]

    try:
        if not nuvlabox_status:
            return render_template("loading.html")
        else:
            return render_template("dashboard.html", cpus_total=nuvlabox_status.get("cpus"),
                                   memory_total="%.2f GB" % float(int(nuvlabox_status.get("memory"))/1024),
                                   disk_total="%s GB" % nuvlabox_status.get("disk"),
                                   cpu_usage=nuvlabox_status.get("cpu-usage"),
                                   memory_usage=nuvlabox_status.get("memory-usage"),
                                   disk_usage=nuvlabox_status.get("disk-usage"),
                                   os=nuvlabox_status.get("operating-system"),
                                   arch=nuvlabox_status.get("architecture"), ip=nuvlabox_status.get("ip"),
                                   docker_version=nuvlabox_status.get("docker-server-version"),
                                   hostname=nuvlabox_status.get("hostname"),
                                   containers_running=docker_info.get("ContainersRunning"),
                                   docker_images=docker_info.get("Images"),
                                   swarm_node_id=docker_info["Swarm"].get("NodeID"),
                                   docker_stats=docker_stats, net_stats=net_stats,
                                   last_boot=nuvlabox_status.get("last-boot unknown"))
    except:
        log.exception("Server side error")
        os.kill(os.getppid(), signal.SIGKILL)


@app.route('/dashboard/logs')
def logs():
    """ Logs """

    past_logs, now = app.config["supervisor"].get_internal_logs_html()
    if request.headers.get('accept') == 'text/event-stream':
        def generate_logs(since):
            while True:
                new_logs, timestamp = app.config["supervisor"].get_internal_logs_html(since=since)
                since = timestamp
                yield "data: %s \n\n" % (new_logs)
                time.sleep(5)
        return Response(generate_logs(now), content_type='text/event-stream')

    try:
        return render_template("logs.html", logs=past_logs)
    except:
        log.exception("Server side error")
        os.kill(os.getppid(), signal.SIGKILL)


@app.route('/dashboard/peripherals')
def peripherals():
    """ Logs """

    peripherals_list = app.config["supervisor"].get_nuvlabox_peripherals()
    for i, per in enumerate(peripherals_list):
        classes = list(map(str.lower, per.get("classes", [])))

        if "root_hub" in classes:
            peripherals_list[i]["font-awesome"] = "fab fa-lg fa-usb"
        elif "video" in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-video"
        elif "gpu" in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-microchip"
        elif "phone" in classes or 'smartphone' in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-mobile"
        elif "networkvideotransmitter" in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-network"
        elif "audio" in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-microphone-alt"
        elif "wireless" in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-wifi"
        elif "human interface device" in classes:
            peripherals_list[i]["font-awesome"] = "far fa-lg fa-keyboard"
        elif "communications" in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-satellite-dish"
        elif "fieldtalk" in classes or "modbus" in classes:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-exchange-alt"
        elif "hub" in classes:
            peripherals_list[i]["font-awesome"] = "fab fa-lg fa-usb"
        else:
            peripherals_list[i]["font-awesome"] = "fas fa-lg fa-slash"

    try:
        return render_template("peripherals.html", peripherals=peripherals_list)
    except:
        log.exception("Server side error")
        os.kill(os.getppid(), signal.SIGKILL)





