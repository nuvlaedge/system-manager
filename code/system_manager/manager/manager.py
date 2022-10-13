"""
Container manager class
"""
import json
import logging
from typing import List, Dict
from pathlib import Path

import docker
from docker.models.containers import Container

from system_manager.common.constants import (UUID_CONTAINER_LABEL, MS_TYPE_LABEL,
                                             COMPOSE_PROJECT_LABEL, MS_CONFIG_PATH)
from system_manager.manager.schemas import (InitialSettings, EngineComponents,
                                            WorkerConfig)
from system_manager.manager.schemas.worker_config import NetworkConfig, Ports


class Manager:
    """
    NuvlaEdge microservice manager and watchdog

    """
    ENGINE_COMPONENTS: Dict[EngineComponents, WorkerConfig] = {}

    def __init__(self, config: InitialSettings):
        """

        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

        self.static_settings: InitialSettings = config
        self.docker_client: docker.DockerClient = docker.from_env()

    @staticmethod
    def get_component_type_from_label(labels: Dict[str, str]) -> EngineComponents:
        """
        Iterates a list of labels
        Args:
            labels: Labels from which gather the component type

        Returns: Component type from EngineComponents Enum
        """
        component_type_name: str = labels.get(MS_TYPE_LABEL, '')

        if component_type_name:
            return EngineComponents.value_of(component_type_name)

    def find_engine_components(self):
        """

        :return:
        """
        self.ENGINE_COMPONENTS = {}
        engine_unique_id: str = UUID_CONTAINER_LABEL.format(
            uuid=self.static_settings.NUVLAEDGE_UUID)

        containers: List[Container] = self.docker_client.containers.list(
            filters={'label': engine_unique_id})

        for i in containers:

            component_id = self.get_component_type_from_label(i.labels)
            self.ENGINE_COMPONENTS[component_id] = WorkerConfig(
                worker_id=component_id.name,
                container_id=i.id,
                container_name=i.name,
                project_name=i.labels.get(COMPOSE_PROJECT_LABEL, 'NO_PROJECT'),
                networks={
                    key: NetworkConfig.parse_obj(value)
                    for key, value in
                    i.attrs.get("NetworkSettings").get("Networks").items()
                }
            )

            it_ports: Dict = i.attrs.get("NetworkSettings").get("Ports")
            if it_ports:
                for key, value in it_ports.items():
                    self.ENGINE_COMPONENTS[component_id].ports[key] = \
                        Ports.parse_obj(value[0])

    def engine_ready(self) -> bool:
        """

        :returns:
        """
        for ms in EngineComponents:
            if ms not in self.ENGINE_COMPONENTS.keys():
                self.logger.info(f'Microservice {ms} not ready yet, waiting...')
                return False
        return True

    def register_components(self):
        """

        :returns:
        """
        if not MS_CONFIG_PATH.exists():
            MS_CONFIG_PATH.mkdir(exist_ok=True)

        for k, v in self.ENGINE_COMPONENTS.items():
            it_file: Path = MS_CONFIG_PATH / (k.name + '.json')

            self.logger.info(f'Saving {k} configuration')
            with it_file.open('w') as file:
                json.dump(v.dict(), file, indent=4)
