from pathlib import Path

# File based database locations
DATA_VOLUME: Path = Path("/srv/nuvlabox/shared")
MS_CONFIG_PATH: Path = DATA_VOLUME / '.microservices'

# Manager label handling
UUID_CONTAINER_LABEL: str = 'nuvlaedge.uuid={uuid}'
MS_TYPE_LABEL: str = 'nuvlaedge.engine.microservice'
COMPOSE_PROJECT_LABEL: str = 'com.docker.compose.project'
