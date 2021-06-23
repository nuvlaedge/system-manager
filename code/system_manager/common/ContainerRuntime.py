import os
from abc import ABC, abstractmethod

KUBERNETES_SERVICE_HOST = os.getenv('KUBERNETES_SERVICE_HOST')
if KUBERNETES_SERVICE_HOST:
    from kubernetes import client, config
    ORCHESTRATOR = 'kubernetes'
else:
    import docker
    ORCHESTRATOR = 'docker'


class ContainerRuntime(ABC):
    """
    Base abstract class for the Docker and Kubernetes clients
    """

    @abstractmethod
    def __init__(self):
        self.client = None


class Kubernetes(ContainerRuntime):
    """
    Kubernetes client
    """

    def __init__(self):
        super().__init__()

        config.load_incluster_config()
        self.client = client.CoreV1Api()
        self.client_apps = client.AppsV1Api()


class Docker(ContainerRuntime):
    """
    Docker client
    """

    def __init__(self):
        super().__init__()
        self.client = docker.from_env()


# --------------------
class Containers:
    """ Common set of methods and variables for the NuvlaBox system-manager
    """
    def __init__(self):
        """ Constructs an Container object
        """
        self.docker_socket_file = '/var/run/docker.sock'

        if ORCHESTRATOR == 'kubernetes':
            self.container_runtime = Kubernetes()
        else:
            if os.path.exists(self.docker_socket_file):
                self.container_runtime = Docker()
            else:
                raise Exception(f'Orchestrator is "{ORCHESTRATOR}", but file {self.docker_socket_file} is not present')
