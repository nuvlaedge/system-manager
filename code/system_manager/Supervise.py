#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Contains the supervising class for all NuvlaBox Engine components """

import docker
import time
import logging


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
        # self.state = "ACTIVE"
        self.html_templates = "templates"
        self.printer_file = "index.html"

        with open("/proc/self/cgroup", 'r') as f:
            self.docker_id = f.readlines()[0].replace('\n', '').split("/")[-1]

    def list_internal_containers(self):
        """ Gets all the containers that compose the NuvlaBox Engine """

        return self.docker_client.containers.list(filters={"label": self.base_label})

    def printer(self, content):
        """ Pretty prints """

        with open("{}/{}".format(self.html_templates, self.printer_file), 'w') as p:
            p.write("{}".format(content))

    def build_content(self):
        """ Builds the HTML content for the web server """

        info = self._get_docker_info()
        content = '<!DOCTYPE html>' \
                  '<html>' \
                  '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />' \
                  '<meta http-equiv="Pragma" content="no-cache" />' \
                  '<meta http-equiv="Expires" content="0" />' \
                  '<head>' \
                  '<style>' \
                  ' body {{background-color: #001f3f;' \
                  '         color: #7dbbfb;' \
                  '         margin-top: 0;}}' \
                  ' #top {{font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif;' \
                  '         margin-top: 0;}}' \
                  ' #upper {{font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif;' \
                  '         margin: 0;}}' \
                  ' #stats {{font-family: "Courier New", Courier, monospace;' \
                  '          border-spacing: 20px 5px;}}' \
                  ' #top td:first-child {{text-align: right;}}' \
                  '</style>' \
                  '</head>' \
                  '<body>' \
                  '<div id="upper">' \
                  '<center><i style="color:white;">Last updated: {}</i></center> <br>' \
                  '<table id="top" align="center">' \
                  '<tr><td><b>HOSTNAME:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>CONTAINERS RUNNING:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>NUVLABOX CONTAINERS RUNNING:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>LOCAL IMAGES:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>DOCKER DISK USAGE:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>OPERATING SYSTEM:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>ARCHITECTURE:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>DEVICE SPECS:</b></td> <td>{}</td></tr> ' \
                  '<tr><td><b>ADDRESS:</b></td> <td>{}</td></tr> ' \
                  '</table><br></div><hr><br>' \
                  '{}' \
            .format(time.ctime(),
                    info['Name'],
                    info['ContainersRunning'],
                    len(self.list_internal_containers()),
                    info['Images'],
                    "%.2f GB" % self._get_docker_disk_usage(),
                    info['OperatingSystem'],
                    info['Architecture'],
                    "%s CPUs and %s GiB of memory" % (info['NCPU'], round((info['MemTotal']/1024/1024/1024), 2)),
                    info['Swarm']['NodeAddr'],
                    self._get_stats_table_html())

        self.printer(content)

    def _get_docker_disk_usage(self):
        """ Runs docker system df and gets disk usage """

        return round(float(self.docker_client.df()["LayersSize"] / 1000 / 1000 / 1000), 2)

    def _get_docker_info(self):
        """ Gets everything from the Docker client info """

        return self.docker_client.info()

    def _get_stats_table_html(self):
        """ Run docker stats """

        stats = '<table id="stats" align="center">' \
                '<tr>' \
                '<th>CONTAINER ID</th>' \
                '<th>NAME</th>' \
                '<th>CPU %</th>' \
                '<th>MEM USAGE/LIMIT</th>' \
                '<th>MEM %</th>' \
                '<th>NET I/O</th>' \
                '<th>BLOCK I/O</th>' \
                '<th>STATUS</th>' \
                '<th>RESTARTED</th></tr>'

        for container in self.docker_client.containers.list():
            previous_cpu = previous_system = cpu_percent = mem_percent = mem_usage = mem_limit = net_in = net_out = blk_in = blk_out = 0.0
            restart_count = 0
            container_status = "unknown"
            x = 0
            for container_stats in self.docker_client.api.stats(container.id, stream=True, decode=True):
                cpu_percent = 0.0
                cpu_total = float(container_stats["cpu_stats"]["cpu_usage"]["total_usage"])
                cpu_delta = cpu_total - previous_cpu
                cpu_system = float(container_stats["cpu_stats"]["system_cpu_usage"])
                system_delta = cpu_system - previous_system
                online_cpus = container_stats["cpu_stats"].get("online_cpus", len(container_stats["cpu_stats"]["cpu_usage"]["percpu_usage"]))
                if system_delta > 0.0:
                    cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
                previous_system = cpu_system
                previous_cpu = cpu_total

                x += 1
                if x >= 2:
                    mem_usage = float(container_stats["memory_stats"]["usage"] / 1024 / 1024)
                    mem_limit = float(container_stats["memory_stats"]["limit"] / 1024 / 1024)
                    if round(mem_limit, 2) == 0.00:
                        mem_percent = 0.00
                    else:
                        mem_percent = round(float(mem_usage / mem_limit) * 100, 2)

                    if "networks" in container_stats:
                        net_in = sum(container_stats["networks"][iface]["rx_bytes"] for iface in container_stats["networks"]) / 1000 / 1000
                        net_out = sum(container_stats["networks"][iface]["tx_bytes"] for iface in container_stats["networks"]) / 1000 / 1000

                    try:
                        blk_in = float(container_stats.get("blkio_stats", {}).get("io_service_bytes_recursive", [{"value": 0}])[0]["value"] / 1000 / 1000)
                    except IndexError:
                        blk_in = 0.0
                    try:
                        blk_out = float(container_stats.get("blkio_stats", {}).get("io_service_bytes_recursive", [0, {"value": 0}])[1]["value"] / 1000 / 1000)
                    except IndexError:
                        blk_out = 0.0
                    container_status = container.status
                    restart_count = int(container.attrs["RestartCount"])
                    break

            stats += '<tr>' \
                     '<td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td>' \
                     '</tr>'.format(container.id[:12],
                                    container.name[:25],
                                    "%.2f%%" % round(cpu_percent, 2),
                                    "%sMiB / %sGiB" % (round(mem_usage, 2), round(mem_limit / 1024, 2)),
                                    "%.2f%%" % mem_percent,
                                    "%sMB / %sMB" % (round(net_in, 2), round(net_out, 2)),
                                    "%sMB / %sMB" % (round(blk_in, 2), round(blk_out, 2)),
                                    container_status,
                                    restart_count)

        stats += '</table>'

        return stats




