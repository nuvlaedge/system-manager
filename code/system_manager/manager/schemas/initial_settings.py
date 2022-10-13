"""

"""

from pydantic import BaseSettings, Field
from enum import Enum


class InitialSettings(BaseSettings):
    SKIP_MINIMUM_REQUIREMENTS: str = Field('', env='SKIP_MINIMUM_REQUIREMENTS')
    NUVLAEDGE_UUID: str = ''
    NUVLAEDGE_DATA_GATEWAY_NAME: str = 'data-gateway'
    NUVLAEDGE_DATA_GATEWAY_IMAGE: str = 'eclipse-mosquitto:1.6.12'
    SYSTEM_MANAGER_DEBUG: bool = Field(False, env='SYSTEM_MANAGER_DEBUG')

    class Config:
        fields = {
            'NUVLAEDGE_UUID': {
                'env': ['NUVLAEDGE_UUID', 'NUVLABOX_UUID']
            },
            'NUVLAEDGE_DATA_GATEWAY_IMAGE': {
                'env': ['NUVLAEDGE_DATA_GATEWAY_IMAGE', 'NUVLABOX_DATA_GATEWAY_IMAGE']
            },
            'NUVLAEDGE_DATA_GATEWAY_NAME': {
                'env': ['NUVLAEDGE_DATA_GATEWAY_NAME', 'NUVLABOX_DATA_GATEWAY_NAME']
            }
        }


class EngineComponents(Enum):
    vpn_client = 'vpn-client'
    agent = 'agent'
    system_manager = 'system-manager'
    job_engine_lite = 'job-engine-lite'
    on_stop = 'on-stop'
    compute_api = 'compute-api'

    @classmethod
    def value_of(cls, value):
        for k, v in cls.__members__.items():

            if k == value.replace('-', '_'):
                return v
        else:
            raise ValueError(f"'{cls.__name__}' enum not found for '{value}'")
