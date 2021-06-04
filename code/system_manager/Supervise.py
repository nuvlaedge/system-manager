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
        self.agent_dg_failed_connection = 0
        self.lost_quorum_hint = 'possible that too few managers are online'
        self.nuvlabox_containers = []

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

        label = {
            "nuvlabox.on-stop": "True"
        }
        self.docker_client.containers.run(self.on_stop_docker_image,
                                          name=on_stop_container_name,
                                          labels=label,
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
            # default to dev image
            return 'nuvladev/on-stop:main'
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

        remote_managers = swarm_info.get('RemoteManagers')
        managers = []
        if remote_managers:
            managers = [rm.get('NodeID') for rm in remote_managers]
        self.i_am_manager = True if node_id in managers else False

        if self.i_am_manager:
            try:
                self.node = self.docker_client.nodes.get(node_id)
            except docker.errors.APIError as e:
                if self.lost_quorum_hint in str(e):
                    # quorum is lost
                    msg = 'Quorum is lost. This node will not support Service and Cluster management'
                    self.log.warning(msg)
                    err_msg = swarm_info.get('Error') if swarm_info.get('Error') else msg
                    self.operational_status.append((utils.status_degraded, err_msg))

                return
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

        if os.path.exists(utils.docker_stats_json_file):
            with open(utils.docker_stats_json_file) as cstats:
                container_stats = json.load(cstats)

            for container_stat in container_stats:
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
                         '</tr>'.format(container_stat.get('id', '')[:12],
                                        container_stat.get('name', '')[:25],
                                        container_stat.get('cpu-percent', 0.0),
                                        container_stat.get('mem-usage-limit', "MB / MB"),
                                        container_stat.get('mem-percent', 0.0),
                                        container_stat.get('net-in-out', "MB / MB"),
                                        container_stat.get('blk-in-out', "MB / MB"),
                                        container_stat.get('container-status'),
                                        container_stat.get('restart-count', 0))

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
                                                  restart_policy={"Name": "always"},
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
            self.operational_status.append((utils.status_degraded, 'Agent API is not available'))
            return None

        agent_container_id.raise_for_status()

        return self.docker_client.containers.get(agent_container_id.json())

    def check_dg_network(self, target_network: docker.DockerClient.networks):
        """
        Makes sure the DG is connected to the right network

        :param target_network: network to be checked (object)
        :return:
        """

        if not self.data_gateway_object:
            self.log.warning('Data Gateway object does not exist. Cannot check its network')
            return

        try:
            if self.is_swarm_enabled:
                current_networks = [vip.get('NetworkID') for vip in self.data_gateway_object.attrs.get('Endpoint', {}).get('VirtualIPs', [])]
            else:
                current_networks = self.data_gateway_object.attrs.get('NetworkSettings', {}).get('Networks', {}).keys()

            if target_network.name not in current_networks and target_network.id not in current_networks:
                self.log.info(f'Adding network {target_network.name} to {self.data_gateway_object.name}')
                if self.is_swarm_enabled:
                    self.data_gateway_object.update(networks=[target_network.name] + current_networks)
                else:
                    target_network.connect(self.data_gateway_object.name)
        except Exception as e:
            self.log.error(f'Cannot add network {target_network.name} to DG {self.data_gateway_object.name}: {str(e)}')

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
                # this node can't setup networks
                # However, the network might already exist, we simply don't see it. Try to connect agent to it anyway
                pass
            else:
                # resume the DG mgmt activities on the next cycle
                return
        else:
            # make sure the network driver makes sense, to avoid having a bridge network on a Swarm node
            dg_net_driver = dg_network.attrs.get('Driver')
            if dg_net_driver.lower() == 'bridge' and self.is_swarm_enabled:
                self.destroy_network(dg_network)
                # if swarm is enabled, a container-based data-gateway doesn't make sense
                try:
                    self.docker_client.containers.get(self.data_gateway_name)
                except docker.errors.NotFound:
                    pass
                else:
                    try:
                        self.docker_client.api.remove_container(self.data_gateway_name, force=True)
                    except Exception as e:
                        self.log.error(f'Could not remove old {self.data_gateway_name} container: {str(e)}')
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
                        self.operational_status.append((utils.status_degraded, 'Unable to launch Data Gateway'))

                # NOTE: resume on the next cycle
                return
            else:
                # double check DG still has the right network
                self.check_dg_network(dg_network)

        # ## 3: finally, connect this node's Agent container (+data source containers) to DG
        agent_container = self.find_nuvlabox_agent()
        data_source_containers = self.docker_client.containers.list(filters={'label': 'nuvlabox.data-source-container'})

        if agent_container:
            agent_container_id = agent_container.id
        else:
            self.operational_status.append((utils.status_degraded, 'NuvlaBox Agent is dead'))
            return

        connecting_containers = [agent_container] + data_source_containers
        for ccont in connecting_containers:
            if utils.nuvlabox_shared_net not in \
                    ccont.attrs.get('NetworkSettings', {}).get('Networks', {}).keys():
                self.log.info(f'Connecting ({ccont.name}) '
                              f'to network {utils.nuvlabox_shared_net}')
                try:
                    self.docker_client.api.connect_container_to_network(ccont.id, utils.nuvlabox_shared_net)
                except Exception as e:
                    if "notfound" in str(e).replace(' ', '').lower():
                        # nothing to do. Network doesn't exist at all
                        pass
                    else:
                        if ccont.id == agent_container_id:
                            self.log.error(f'Error while connecting NuvlaBox Agent to Data Gateway network: {str(e)}')
                            self.operational_status.append((utils.status_degraded,
                                                            f'Data Gateway connection error: {str(e)}'))
                            return
                        # else, this is a data-source container and not as critical
                    err_msg = f'Cannot connect {ccont.name} to Data Gateway network'
                    self.operational_status.append((utils.status_degraded, err_msg))

                    self.log.warning(f'{err_msg}: {str(e)}')

        # test agent connection with data-gateway
        try:
            r = requests.get('http://agent/api/agent-container-id')
        except requests.exceptions.ConnectionError as e:
            msg = f'Agent API connection error: {str(e)}'
            self.log.warning(msg)
            self.operational_status.append((utils.status_degraded, msg))
            return

        if r.status_code == 404:
            self.agent_dg_failed_connection += 1

        if self.agent_dg_failed_connection > 3:
            # do something after 3 reports
            self.log.warning('Agent seems unable to reach the Data Gateway. Restarting the Data Gateway')
            self.agent_dg_failed_connection = 0
            if self.is_swarm_enabled and self.i_am_manager:
                self.data_gateway_object.force_update()
            else:
                self.data_gateway_object.restart()

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
        cmd = f"sh -c 'echo \"{json.dumps(self.docker_client.info(), indent=2)}\" && sleep 300'"
        self.docker_client.services.create('alpine',
                                           command=cmd,
                                           container_labels=labels,
                                           labels=labels,
                                           mode="global",
                                           name=utils.overlay_network_service,
                                           networks=[net_name],
                                           restart_policy=restart_policy,
                                           stop_grace_period=3,
                                           )

        return True

    def check_nuvlabox_connectivity(self):
        """
        Makes sure all NBE containers are connected to the original bridge network (at least)

        This is mainly because of a connectivity bug in Docker, whereby docker-compose container loose their
        bridge network when the Swarm state changes:

        https://github.com/docker/compose/issues/8110

        :return:
        """

        # reload the docker client just in case
        self.docker_client = docker.from_env()

        try:
            myself = self.docker_client.containers.get(socket.gethostname())
        except docker.errors.NotFound:
            self.log.error(f'Cannot find this container by hostname: {socket.gethostname()}. Cannot proceed')
            self.operational_status.append((utils.status_degraded, 'System Manager container lookup error'))
            return

        try:
            project_name = myself.labels['com.docker.compose.project']
        except KeyError:
            self.log.warning(f'Cannot infer Docker Compose project name from the labels in {myself.name}.'
                             f'Trying to infer from container name')
            project_name = myself.name.split('_')[0] if len(myself.name.split('_')) > 1 else None
            if not project_name:
                msg = 'Impossible to infer Docker Compose project name!'
                self.log.error(msg)
                self.operational_status.append((utils.status_degraded, msg))
                return

        original_project_label = f'com.docker.compose.project={project_name}'
        original_nb_containers = self.docker_client.containers.list(filters={'label': original_project_label})
        self.nuvlabox_containers = self.docker_client.containers.list(filters={'label': original_project_label}, all=True)
        original_nb_internal_network = self.docker_client.networks.list(filters={'label': original_project_label,
                                                                                 'driver': 'bridge'})

        if not original_nb_containers or not original_nb_internal_network:
            self.operational_status.append((utils.status_degraded, 'Original NuvlaBox network not found'))
            self.log.warning('Unable to check nuvlabox connectivity: original containers/network not found')
            return

        for container in original_nb_containers:
            if container.attrs.get('HostConfig', {}).get('NetworkMode', '') == 'host':
                # containers in host mode are not affected
                continue

            # there should only be 1 original nb internal network, so take the 1st one
            if not any(net_id in container.attrs.get('NetworkSettings', {}).get('Networks', {}).keys()
                       for net_id in [original_nb_internal_network[0].name, original_nb_internal_network[0].id]):
                self.log.warning(f'Container {container.name} lost its network {original_nb_internal_network[0].name}.'
                                 f'Reconnecting...')

                service_name = [container.labels['com.docker.compose.service']] if container.labels.get('com.docker.compose.service') else []
                try:
                    original_nb_internal_network[0].connect(container.name, aliases=service_name)
                except docker.errors.APIError as e:
                    if "already exists in network" in str(e).lower():
                        continue
                    elif "notfound" in str(e).replace(' ', '').lower():
                        self.log.warning(f'Network {original_nb_internal_network[0].name} ceased to exist '
                                         f'during connectivity check. Nothing to do.')
                        return
                    self.log.error(f'Unable to reconnect {container.name} to '
                                   f'network {original_nb_internal_network[0].name}: {str(e)}')
                    self.operational_status.append((utils.status_degraded,
                                                    'NuvlaBox containers lost their network connection'))

    def healer(self):
        """
        Loops through the NB containers and tries to fix the ones that are broken

        :return:
        """

        if not self.nuvlabox_containers:
            return

        for container in self.nuvlabox_containers:
            status = container.status.lower()
            if status not in ["paused", "running", "restarting"]:
                # what to do if:
                # . status is "created"?
                # .. just start the container
                if status == 'created':
                    try:
                        self.docker_client.start()
                        continue
                    except docker.errors.APIError as e:
                        self.log.error(f'Cannot resume container {container.name}. Reason: {str(e)}')

                # . status is "exited"?
                # .. understand why. If exit code is 0, then it exited gracefully...thus it is not broken
                if status == 'exited':
                    attrs = container.attrs
                    state = attrs.get('State', {})
                    exit_code = state.get('ExitCode', 0)
                    if exit_code > 0:
                        # is it already restarting?
                        if state.get('Restarting', False):
                            # nothing to do then
                            continue

                        if attrs.get('HostConfig', {}).get('RestartPolicy', 'no').lower() in ['no', 'unless-stopped']:
                            continue

                        # at this stage we simply need to try to restart it
                        try:
                            self.log.info(f'Container {container.name} exited and is not restarting. Forcing restart')
                            container.restart()
                        except docker.errors.APIError as e:
                            self.log.error(f'Cannot heal container {container.name}. Reason: {str(e)}')
