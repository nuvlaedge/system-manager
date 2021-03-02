#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Contains the supervising class for all NuvlaBox Engine components """

import docker
import json
import time
import os
import glob
import OpenSSL
import random
import requests
import socket
import string
from datetime import datetime
from system_manager.common.logging import logging
from system_manager.common import utils


class ClusterNodeCannotManageDG(Exception):
    pass


def cluster_workers_cannot_manage(func):
    def wrapper(self, *args):
        if self.is_swarm_enabled and not self.i_am_manager:
            raise ClusterNodeCannotManageDG()
        return func(self, *args)
    return wrapper


class Supervise(object):
    """ The Supervise class contains all the methods and
    definitions for making sure the NuvlaBox Engine is running smoothly,
    including all methods for dealing with system disruptions and
    graceful shutdowns
    """

    def __init__(self):
        """ Constructs the Supervise object """

        self.docker_client = docker.from_env()
        self.log = logging.getLogger(__name__)
        self.system_usages = {}
        self.on_stop_docker_image = self.infer_on_stop_docker_image()
        self.data_gateway_image = os.getenv('NUVLABOX_DATA_GATEWAY_IMAGE', 'eclipse-mosquitto:1.6.12')
        self.data_gateway_object = None
        self.data_gateway_name = 'data-gateway'
        self.i_am_manager = self.is_swarm_enabled = self.node = None
        self.operational_status = []

    @staticmethod
    def printer(content, file):
        """ Pretty prints to template file """

        with open("{}/{}".format(utils.html_templates, file), 'w') as p:
            p.write("{}".format(content))

    @staticmethod
    def reader(file):
        """ Reads template file

        :returns file content as a string
        """

        with open("{}/{}".format(utils.html_templates, file)) as r:
            return r.read()

    def launch_nuvlabox_on_stop(self):
        """
        Launches the on-stop graceful shutdown

        :return:
        """

        error_msg = 'Cannot launch NuvlaBox On-Stop graceful shutdown. ' \
                    'If decommissioning, container resources might be left behind'

        if not self.on_stop_docker_image:
            self.on_stop_docker_image = self.infer_on_stop_docker_image()
            if not self.on_stop_docker_image:
                self.log.warning(f'{error_msg}: Docker image not found for NuvlaBox On-Stop service')
                return

        try:
            myself = self.docker_client.containers.get(socket.gethostname())
            myself_labels = myself.labels
        except docker.errors.NotFound:
            self.log.warning(f'Cannot find this container by hostname: {socket.gethostname()}')
            myself_labels = {}

        project_name = myself_labels.get('com.docker.compose.project')

        random_identifier = ''.join(random.choices(string.ascii_uppercase, k=5))
        now = datetime.strftime(datetime.utcnow(), '%d-%m-%Y_%H%M%S')
        on_stop_container_name = f"nuvlabox-on-stop-{random_identifier}-{now}"

        self.docker_client.containers.run(self.on_stop_docker_image,
                                          name=on_stop_container_name,
                                          environment=[f'PROJECT_NAME={project_name}'],
                                          volumes={
                                              '/var/run/docker.sock': {
                                                  'bind': '/var/run/docker.sock',
                                                  'mode': 'ro'
                                              }
                                          },
                                          detach=True)

    def infer_on_stop_docker_image(self):
        """
        On stop, the SM launches the NuvlaBox cleaner, called on-stop, and which is also launched in paused mode
        at the beginning of the NB lifetime.

        Here, we find that service and infer its Docker image for later usage

        :return: image name (str)
        """

        on_stop_container_name = "nuvlabox-on-stop"

        try:
            container = self.docker_client.containers.get(on_stop_container_name)
        except docker.errors.NotFound:
            return None
        except Exception as e:
            self.log.error(f"Unable to search for container {on_stop_container_name}. Reason: {str(e)}")
            return None

        try:
            if container.status.lower() == "paused":
                return container.attrs['Config']['Image']
        except (AttributeError, KeyError) as e:
            self.log.error(f'Unable to infer Docker image for {on_stop_container_name}: {str(e)}')

        return None

    def classify_this_node(self):
        swarm_info = self.get_docker_info().get('Swarm', {})

        # is it running in Swarm mode?
        node_id = swarm_info.get('NodeID')
        # might have a Node ID but still, LocalNodeState might be inactive
        local_node_state = swarm_info.get('LocalNodeState', 'inactive')
        if not node_id or local_node_state.lower() == "inactive":
            self.i_am_manager = self.is_swarm_enabled = False
            return

        # if it got here, there Swarm is active
        self.is_swarm_enabled = True

        remote_managers = [rm.get('NodeID') for rm in swarm_info.get('RemoteManagers', [])]
        self.i_am_manager = True if node_id in remote_managers else False

        if self.i_am_manager:
            self.node = self.docker_client.nodes.get(node_id)
            try:
                node_spec = self.node.attrs['Spec']
            except KeyError as e:
                self.log.error(f'Cannot get node Spec for {node_id}: {str(e)}')
                return
            node_labels = node_spec.get('Labels', {})
            if utils.node_label_key not in node_labels.keys() and isinstance(node_spec, dict):
                node_labels[utils.node_label_key] = 'True'
                node_spec['Labels'] = node_labels
                self.log.info(f'Updating this node ({node_id}) with label {utils.node_label_key}')
                self.node.update(node_spec)

    def get_nuvlabox_status(self):
        """ Re-uses the consumption metrics from NuvlaBox Agent """

        try:
            with open(utils.nuvlabox_status_file) as nbsf:
                usages = json.loads(nbsf.read())
        except FileNotFoundError:
            self.log.warning("NuvlaBox status metrics file not found locally...wait for Agent to create it")
            usages = {}
        except:
            self.log.exception("Unknown issues while retrieving NuvlaBox status metrics")
            usages = self.system_usages

        # update in-mem copy of usages
        self.system_usages = usages

        return usages

    def get_docker_disk_usage(self):
        """ Runs docker system df and gets disk usage """

        return round(float(self.docker_client.df()["LayersSize"] / 1000 / 1000 / 1000), 2)

    def get_docker_info(self):
        """ Gets everything from the Docker client info """

        return self.docker_client.info()

    def get_nuvlabox_peripherals(self):
        """ Reads the list of peripherals discovered by the other NuvlaBox microservices,
        via the shared volume folder

        :returns list of peripherals [{...}, {...}] with the original data schema (see Nuvla nuvlabox-peripherals)
        """

        peripherals = []
        try:
            peripheral_files = glob.iglob(utils.nuvlabox_peripherals_folder + '**/**', recursive=True)
        except FileNotFoundError:
            return peripherals

        for per_file_path in peripheral_files:
            if os.path.isdir(per_file_path):
                continue
            try:
                with open(per_file_path) as p:
                    peripheral_content = json.loads(p.read())
            except FileNotFoundError:
                logging.warning("Cannot read peripheral {}".format(per_file_path))
                continue

            peripherals.append(peripheral_content)

        return peripherals

    def get_internal_logs_html(self, tail=30, since=None):
        """ Get the logs for all NuvlaBox containers

        :returns list of log generators
        :returns timestamp for when the logs were fetched
        """

        nb_containers = utils.list_internal_containers()
        logs = ''
        for container in nb_containers:
            container_log = self.docker_client.api.logs(container.id,
                                                        timestamps=True,
                                                        tail=tail,
                                                        since=since).decode('utf-8')

            if container_log:
                log_id = '<b style="color: #{};">{} |</b> '.format(container.id[:6], container.name)
                logs += '{} {}'.format(log_id,
                                       '<br/>{}'.format(log_id).join(container_log.splitlines()))
                logs += '<br/>'
        return logs, int(time.time())

    def write_docker_stats_table_html(self):
        """ Run docker stats """

        stats = '<table class="table table-striped table-hover mt-5 mr-auto">' \
                ' <caption>Docker Stats, last update: {} UTC</caption>' \
                ' <thead class="bg-secondary text-light">' \
                '  <tr>' \
                '    <th scope="col">CONTAINER ID</th>' \
                '    <th scope="col">NAME</th>' \
                '    <th scope="col">CPU %</th>' \
                '    <th scope="col">MEM USAGE/LIMIT</th>' \
                '    <th scope="col">MEM %</th>' \
                '    <th scope="col">NET I/O</th>' \
                '    <th scope="col">BLOCK I/O</th>' \
                '    <th scope="col">STATUS</th>' \
                '    <th scope="col">RESTARTED</th>' \
                '  </tr>' \
                ' </thead>' \
                ' <tbody>'.format(datetime.utcnow())

        errors = []
        for container in self.docker_client.containers.list():
            previous_cpu = previous_system = cpu_percent = mem_percent = mem_usage = mem_limit = net_in = net_out = blk_in = blk_out = 0.0
            restart_count = 0
            container_status = "unknown"
            x = 0
            # TODO: this should be executed in parallel, one thread per generator
            for container_stats in self.docker_client.api.stats(container.id, stream=True, decode=True):
                cpu_percent = 0.0

                try:
                    cpu_total = float(container_stats["cpu_stats"]["cpu_usage"]["total_usage"])
                    cpu_system = float(container_stats["cpu_stats"]["system_cpu_usage"])
                    online_cpus = container_stats["cpu_stats"] \
                        .get("online_cpus", len(container_stats["cpu_stats"]["cpu_usage"].get("percpu_usage", -1)))

                    cpu_delta = cpu_total - previous_cpu
                    system_delta = cpu_system - previous_system

                    if system_delta > 0.0 and online_cpus > -1:
                        cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0

                    previous_system = cpu_system
                    previous_cpu = cpu_total
                except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
                    self.log.debug(f"Cannot get CPU stats for container {container.name}: {str(e)}. Moving on")
                    cpu_percent = 0.0
                    error_name = f'{container.name}:cpu:{str(e)}'
                    if error_name not in errors:
                        errors.append(error_name)

                # generate stats at least twice
                x += 1
                if x >= 2:
                    try:
                        mem_usage = float(container_stats["memory_stats"]["usage"] / 1024 / 1024)
                        mem_limit = float(container_stats["memory_stats"]["limit"] / 1024 / 1024)
                        if round(mem_limit, 2) == 0.00:
                            mem_percent = 0.00
                        else:
                            mem_percent = round(float(mem_usage / mem_limit) * 100, 2)
                    except (IndexError, KeyError, ValueError) as e:
                        self.log.debug(f"Cannot get Mem stats for container {container.name}: {str(e)}. Moving on")
                        mem_percent = mem_usage = mem_limit = 0.00
                        error_name = f'{container.name}:mem:{str(e)}'
                        if error_name not in errors:
                            errors.append(error_name)

                    if "networks" in container_stats:
                        net_in = sum(container_stats["networks"][iface]["rx_bytes"] for iface in container_stats["networks"]) / 1000 / 1000
                        net_out = sum(container_stats["networks"][iface]["tx_bytes"] for iface in container_stats["networks"]) / 1000 / 1000

                    try:
                        blk_in = float(container_stats.get("blkio_stats", {}).get("io_service_bytes_recursive", [{"value": 0}])[0]["value"] / 1000 / 1000)
                    except Exception as e:
                        self.log.debug(f"Cannot get Block stats for container {container.name}: {str(e)}. Moving on")
                        blk_in = 0.0
                        error_name = f'{container.name}:block-in:{str(e)}'
                        if error_name not in errors:
                            errors.append(error_name)
                    try:
                        blk_out = float(container_stats.get("blkio_stats", {}).get("io_service_bytes_recursive", [0, {"value": 0}])[1]["value"] / 1000 / 1000)
                    except Exception as e:
                        self.log.debug(f"Cannot get Block stats for container {container.name}: {str(e)}. Moving on")
                        blk_out = 0.0
                        error_name = f'{container.name}:block-out:{str(e)}'
                        if error_name not in errors:
                            errors.append(error_name)

                    container_status = container.status
                    restart_count = int(container.attrs["RestartCount"]) if "RestartCount" in container.attrs else 0

                    stats += '<tr>' \
                             ' <th scope="row">{}</th> ' \
                             ' <td>{}</td>' \
                             ' <td>{}</td>' \
                             ' <td>{}</td>' \
                             ' <td>{}</td>' \
                             ' <td>{}</td>' \
                             ' <td>{}</td>' \
                             ' <td>{}</td>' \
                             ' <td>{}</td>' \
                             '</tr>'.format(container.id[:12],
                                            container.name[:25],
                                            "%.2f" % round(cpu_percent, 2),
                                            "%sMiB / %sGiB" % (round(mem_usage, 2), round(mem_limit / 1024, 2)),
                                            "%.2f" % mem_percent,
                                            "%sMB / %sMB" % (round(net_in, 2), round(net_out, 2)),
                                            "%sMB / %sMB" % (round(blk_in, 2), round(blk_out, 2)),
                                            container_status,
                                            restart_count)
                    # stop streaming
                    break

        if errors:
            self.log.debug(f'Failed to get some container stats. List (container:metric:error): {", ".join(errors)}')

        stats += ' </tbody>' \
                 '</table>'
        self.printer(stats, utils.docker_stats_html_file)

    def is_cert_rotation_needed(self):
        """ Checks whether the Docker and NB API certs are about to expire """

        # certificates to be checked for expiration dates:
        check_expiry_date_on = ["ca.pem", "server-cert.pem", "cert.pem"]

        # if the TLS sync file does not exist, then the compute-api is going to generate the certs by itself, by default
        if not os.path.isfile(utils.tls_sync_file):
            return False

        for file in check_expiry_date_on:
            file_path = f"{utils.data_volume}/{file}"

            if os.path.isfile(file_path):
                with open(file_path) as fp:
                    content = fp.read()

                cert_obj = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, content)

                end_date = cert_obj.get_notAfter().decode()
                formatted_end_date = datetime(int(end_date[0:4]),
                                              int(end_date[4:6]),
                                              int(end_date[6:8]))

                days_left = formatted_end_date - datetime.now()
                # if expiring in less than d days, rotate all
                d = 5
                if days_left.days < d:
                    self.log.warning(f"{file_path} is expiring in less than {d} days. Requesting rotation of all certs")
                    return True

        return False

    def request_rotate_certificates(self):
        """ Deletes the existing .tls sync file from the shared volume and restarts the compute-api container

        This restart will force the regeneration of the certificates and consequent recommissioning """

        compute_api_container = "compute-api"

        if os.path.isfile(utils.tls_sync_file):
            os.remove(utils.tls_sync_file)
            self.log.info(f"Removed {utils.tls_sync_file}. Restarting {compute_api_container} container")
            try:
                self.docker_client.api.restart(compute_api_container, timeout=30)
            except docker.errors.NotFound:
                self.log.exception(f"Container {compute_api_container} is not running. Nothing to do...")

    @cluster_workers_cannot_manage
    def launch_data_gateway(self, name: str) -> bool:
        """
        Starts the DG services/containers, depending on the mode

        :param name: name of the dg component

        :return: bool
        """

        # At this stage, the DG network is setup
        # let's create the DG component
        labels = {
            "nuvlabox.component": "True",
            "nuvlabox.deployment": "production",
            "nuvlabox.data-gateway": "True"
        }
        try:
            cmd = "sh -c 'sleep 10 && /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf'"
            if self.is_swarm_enabled and self.i_am_manager:
                self.docker_client.services.create(self.data_gateway_image,
                                                   name=name,
                                                   hostname=name,
                                                   labels=labels,
                                                   init=True,
                                                   container_labels=labels,
                                                   networks=[utils.nuvlabox_shared_net],
                                                   constraints=[
                                                       'node.role==manager',
                                                       f'node.labels.{utils.node_label_key}==True'
                                                   ],
                                                   command=cmd
                                                   )
            elif not self.is_swarm_enabled:
                # Docker standalone mode
                self.docker_client.containers.run(self.data_gateway_image,
                                                  name=name,
                                                  hostname=name,
                                                  init=True,
                                                  detach=True,
                                                  labels=labels,
                                                  restart={"Name": "always"},
                                                  oom_score_adj=-900,
                                                  network=utils.nuvlabox_shared_net,
                                                  command=cmd
                                                  )
        except docker.errors.APIError as e:
            try:
                if '409' in str(e):
                    # already exists
                    self.log.warning(f'Despite the request to launch the Data Gateway, '
                                     f'{name} seems to exist already. Forcing its restart just in case')
                    if self.is_swarm_enabled and self.i_am_manager:
                        self.docker_client.services.get(name).force_update()
                    else:
                        self.docker_client.containers.get(name).restart()

                    return True
                else:
                    raise e
            except Exception as e:
                self.log.error(f'Unable to launch Data Gateway router {name}: {str(e)}')
                return False

    def find_nuvlabox_agent(self) -> object or None:
        """
        Connect the NB agent to the DG network

        :return: agent container object or None
        """

        try:
            agent_container_id = requests.get('http://agent/api/agent-container-id')
        except requests.exceptions.ConnectionError:
            self.log.warning('Agent API is not ready yet. Trying again later')
            self.operational_status.append(utils.status_degraded)
            return None

        agent_container_id.raise_for_status()

        return self.docker_client.containers.get(agent_container_id.json())

    def manage_data_gateway(self):
        """ Sets the DG service.

        If we need to start or restart the DG or any of its components, we always "return" and resume the DG setup
        on the next cycle

        :return:
        """

        # ## 1: if the DG network already exists, then chances are that the DG has already been deployed
        dg_network = self.find_network(utils.nuvlabox_shared_net)
        if not dg_network:
            # network doesn't exist, so let's create it as well
            try:
                self.setup_network(utils.nuvlabox_shared_net)
            except ClusterNodeCannotManageDG:
                # this node can't setup networks. Do nothing
                pass
            # resume the DG mgmt activities on the next cycle
            return
        else:
            # make sure the network driver makes sense, to avoid having a bridge network on a Swarm node
            dg_net_driver = dg_network.attrs.get('Driver')
            if dg_net_driver.lower() == 'bridge' and self.is_swarm_enabled:
                self.destroy_network(dg_network)
                # reset cycle cause network needs to be recreated
                return

        # ## 2: DG network exists, but does the DG?
        # check the existence of the DG
        # this function sets self.data_gateway_object
        self.data_gateway_object = None
        try:
            self.find_data_gateway(self.data_gateway_name)
        except ClusterNodeCannotManageDG:
            # ## 2.1: this means this node is a Swarm worker. It can't manage the DG
            pass
        else:
            # ## 2.2: at this stage, this is either a Swarm manager or a standalone Docker node
            if not self.data_gateway_object:
                launched_dg = False
                self.log.info(f'Data Gateway not found. Launching it')
                try:
                    launched_dg = self.launch_data_gateway(self.data_gateway_name)
                except ClusterNodeCannotManageDG:
                    # this isn't actually needed, cause we should never get here if ClusterNodeCannotManageDG
                    # due to the above catch...but it doesn't harm, just in case there's a sudden change in the cluster
                    pass
                finally:
                    if not launched_dg:
                        self.operational_status.append(utils.status_degraded)

                # NOTE: resume on the next cycle
                return

        # ## 3: finally, connect this node's Agent container to DG
        agent_container = self.find_nuvlabox_agent()
        if agent_container:
            if dg_network.name not in agent_container.attrs.get('NetworkSettings', {}).get('Networks', {}).keys():
                self.log.info(f'Connecting NuvlaBox Agent ({agent_container.name}) to network {dg_network.name}')
                try:
                    dg_network.connect(agent_container.id)
                except Exception as e:
                    self.log.error(f'Error while connecting NuvlaBox Agent to Data Gateway network: {str(e)}')
        else:
            self.operational_status.append(utils.status_degraded)

    @cluster_workers_cannot_manage
    def find_data_gateway(self, name: str) -> bool:
        try:
            if self.is_swarm_enabled and self.i_am_manager:
                # in swarm
                self.data_gateway_object = self.docker_client.services.get(name)
            elif not self.is_swarm_enabled and not self.i_am_manager:
                # in single Docker machine
                self.data_gateway_object = self.docker_client.containers.get(name)

            return True
        except (docker.errors.NotFound, docker.errors.APIError) as e:
            self.log.warning(f'Unable to look up Data Gateway component {name}: {str(e)}')
            self.data_gateway_object = None
            return False

    def find_network(self, network_name: str) -> object or None:
        """
        Finds a network by name

        :param network_name: name of the network
        :return: Docker network object or None
        """
        try:
            return self.docker_client.networks.get(network_name)
        except docker.errors.NotFound:
            self.log.info(f'Shared network {network_name} not found')

            return None

    def destroy_network(self, network: object):
        """
        Deletes a network locally by disconnecting it from any container in use, and removing it

        :param network: Docker network object
        :return:
        """
        self.log.warning(f'About to destroy network {network.name}')

        containers_attached = network.attrs.get('Containers')

        if containers_attached:
            for container_id in containers_attached.keys():
                try:
                    network.disconnect(container_id)
                except docker.errors.NotFound as e:
                    self.log.debug(f'Unable to disconnect container {container_id} from net {network.name}: {str(e)}')
                    continue

                self.log.warning(f'Disconnected container {container_id} from network {network.name}')

        network.remove()

    @cluster_workers_cannot_manage
    def setup_network(self, net_name: str) -> bool:
        """
        Creates a Docker network.
        If driver is overlay, then the network is also attachable and a propagation global service is also launched

        :param net_name: network name
        :return: bool
        """

        labels = {
            "nuvlabox.network": "True",
            "nuvlabox.data-gateway": "True"
        }
        self.log.info(f'Creating Data Gateway network {net_name}')
        try:
            if not self.is_swarm_enabled:
                # standalone Docker nodes create bridge network
                self.docker_client.networks.create(net_name,
                                                   labels=labels)
                return True
            elif self.is_swarm_enabled and self.i_am_manager:
                # Swarm managers create overlay network
                self.docker_client.networks.create(net_name,
                                                   driver="overlay",
                                                   attachable=True,
                                                   options={"encrypted": "True"},
                                                   labels=labels)
        except docker.errors.APIError as e:
            if '409' in str(e):
                # already exists
                self.log.warning(f'Unexpected conflict (moving on): {str(e)}')
                if not self.is_swarm_enabled:
                    # in this case there's nothing else to do
                    return True
            else:
                self.log.error(f'Unable to create NuvlaBox network {net_name}: {str(e)}')
                return False

        # if we got here, then we are handling an overlay network, and thus we need the propagation service
        ack_service = None
        try:
            ack_service = self.docker_client.services.get(utils.overlay_network_service)
        except docker.errors.NotFound:
            # good, it doesn't exist
            pass
        except docker.errors.APIError as e:
            self.log.error(f'Unable to manage service {utils.overlay_network_service}: {str(e)}')
            return False

        if ack_service:
            # if we got a request to propagate, even though there's already a service, then there might be something
            # wrong with the service. Let's force an update to see if it fixes something
            self.log.warning(f'Network propagation service {utils.overlay_network_service} already exists. '
                             f'Forcing update')
            ack_service.force_update()
            return True

        # otherwise, let's create the global service
        labels = {
            "nuvlabox.component": "True",
            "nuvlabox.deployment": "production",
            "nuvlabox.overlay-network-service": "True",
            "nuvlabox.data-gateway": "True"
        }
        restart_policy = {
            "condition": "on-failure"
        }

        self.log.info(f'Launching global network propagation service {utils.overlay_network_service}')
        self.docker_client.services.create('alpine',
                                           command=f"echo {self.docker_client.info()}",
                                           container_labels=labels,
                                           labels=labels,
                                           mode="global",
                                           name=utils.overlay_network_service,
                                           networks=[net_name],
                                           restart_policy=restart_policy,
                                           stop_grace_period=3,
                                           )

        return True

    def keep_datagateway_containers_up(self):
        """ Restarts the datagateway containers, if any. These are identified by their labels

        :return:
        """

        container_label = 'nuvlabox.data-source-container=True'

        datagateway_containers = self.docker_client.containers.list(all=True, filters={'label': container_label})

        if datagateway_containers:
            peripherals = self.get_nuvlabox_peripherals()
        else:
            return

        peripheral_ids = list(map(lambda x: x.get("id"), peripherals))

        for dg_container in datagateway_containers:
            id = f"nuvlabox-peripheral/{dg_container.name}"
            if id not in peripheral_ids:
                # then it means the peripheral is gone, and the DG container was not removed
                self.log.warning(f"Found old DG container {dg_container.name}. Trying to disable it")
                try:
                    # TODO: this is only considering the mjpg streamer. It is not generic!
                    r = requests.post("https://management-api:5001/api/data-source-mjpg/disable",
                                      verify=False,
                                      cert=(utils.cert_file, utils.key_file),
                                      json={"id": id})
                    r.raise_for_status()
                except:
                    # force disable manual
                    self.log.exception(f"Could not disable DG container {dg_container.name} via the management-api. Force deleting it...")
                    try:
                        dg_container.remove(force=True)
                    except Exception as e:
                        self.log.error(f"Unable to cleanup old DG container {dg_container.name}: {str(e)}")

                continue

            if dg_container.status.lower() not in ["running", "paused"]:
                self.log.warning(f'The data-gateway container {dg_container.name} is down. Forcing its restart...')

                try:
                    dg_container.start()
                except Exception as e:
                    self.log.exception(f'Unable to force restart {dg_container.name}. Reason: {str(e)}')
