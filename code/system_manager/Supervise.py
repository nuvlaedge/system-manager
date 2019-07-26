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
        self.printer_file = "index.html"

        with open("/proc/self/cgroup", 'r') as f:
            self.docker_id = f.readlines()[0].replace('\n', '').split("/")[-1]

    def list_internal_containers(self):
        """ Gets all the containers that compose the NuvlaBox Engine """

        return self.docker_client.containers.list(filters={"label": self.base_label})

    def printer(self, content):
        """ Pretty prints """

        with open(self.printer_file, 'w') as p:
            p.write("{} \n\n{}".format(content, time.ctime()))

    def build_content(self):
        """ Builds the HTML content for the web server """

        info = self._get_docker_info()
        content = '<!DOCTYPE html>' \
                  '<html>' \
                  '<head>' \
                  '<style>' \
                  ' body {{background-color: powderblue;}}' \
                  ' #top {{font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif;}}' \
                  ' #stats {{font-family: "Courier New", Courier, monospace;' \
                  '          border-spacing: 20px 5px;}}' \
                  '</style>' \
                  '</head>' \
                  '<body>' \
                  '<table id="top" align="center">' \
                  '<tr><td><b>HOSTNAME:</b></td> <td>{}</td></tr> <br>' \
                  '<tr><td><b>CONTAINERS RUNNING:</b></td> <td>{}</td></tr> <br>' \
                  '<tr><td><b>NUVLABOX CONTAINERS RUNNING:</b></td> <td>{}</td></tr> <br>' \
                  '<tr><td><b>LOCAL IMAGES:</b></td> <td>{}</td></tr> <br>' \
                  '<tr><td><b>OPERATING SYSTEM:</b></td> <td>{}</td></tr> <br>' \
                  '<tr><td><b>ARCHITECTURE:</b></td> <td>{}</td></tr> <br>' \
                  '<tr><td><b>DEVICE SPECS:</b></td> <td>{}</td></tr> <br>' \
                  '<tr><td><b>ADDRESS:</b></td> <td>{}</td></tr> <br>' \
                  '</table><br><hr><br>' \
                  '{}' \
            .format(info['Name'],
                    info['ContainersRunning'],
                    len(self.list_internal_containers()),
                    info['Images'],
                    info['OperatingSystem'],
                    info['Architecture'],
                    "%s CPUs and %s GiB of memory" % (info['NCPU'], info['MemTotal']),
                    info['Swarm']['NodeAddr'],
                    self._get_stats_table_html())

        self.printer(content)

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
                '<th>BLOCK I/O</th></tr>'
        for container in self.docker_client.containers.list():
            previous_cpu = previous_system = cpu_percent = mem_percent = mem_usage = mem_limit = net_in = net_out = blk_in = blk_out = 0.0
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
                        mem_percent = round(float(mem_usage / mem_limit), 2)
                    net_in = sum(container_stats["networks"][iface]["rx_bytes"] for iface in container_stats["networks"]) / 1000 / 1000
                    net_out = sum(container_stats["networks"][iface]["tx_bytes"] for iface in container_stats["networks"]) / 1000 / 1000
                    blk_in = float(container_stats["blkio_stats"]["io_service_bytes_recursive"][0]["value"] / 1000 / 1000)
                    blk_out = float(container_stats["blkio_stats"]["io_service_bytes_recursive"][1]["value"] / 1000 / 1000)
                    break

            stats += '<tr>' \
                     '<td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td> <td>{}</td>' \
                     '</tr>'.format(container.id[:12],
                                    container.name,
                                    round(cpu_percent, 2),
                                    "%s MiB / %s GiB" % (round(mem_usage, 2), round(mem_limit / 1024, 2)),
                                    "%s %%" % mem_percent,
                                    "%s MB / %s MB" % (round(net_in, 2), round(net_out, 2)),
                                    "%s MB / %s MB" % (round(blk_in, 2), round(blk_out, 2)))

        stats += '</table>'

        return stats




