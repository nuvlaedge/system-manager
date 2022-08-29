# system-manager

[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge)](https://github.com/nuvlaedge/system-manager/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/nuvlaedge/system-manager?style=for-the-badge&logo=github&logoColor=white)](https://GitHub.com/nuvlaedge/system-manager/issues/)
[![Docker pulls](https://img.shields.io/docker/pulls/nuvlaedge/system-manager?style=for-the-badge&logo=Docker&logoColor=white)](https://cloud.docker.com/u/nuvlaedge/repository/docker/nuvlaedge/system-manager)
[![Docker image size](https://img.shields.io/docker/image-size/nuvladev/system-manager/master?logo=docker&logoColor=white&style=for-the-badge)](https://cloud.docker.com/u/nuvlaedge/repository/docker/nuvlaedge/system-manager)

![CI Build](https://github.com/nuvlaedge/system-manager/actions/workflows/main.yml/badge.svg)
![CI Release](https://github.com/nuvlaedge/system-manager/actions/workflows/release.yml/badge.svg)


**This repository contains the source code for the NuvlaEdge System Manager - this microservice supervisions all the other microservices and environment that compose the [NuvlaEdge](https://sixsq.com/products-and-services/nuvlaedge/overview)**

This microservice is an integral component of the NuvlaEdge Engine.

---

**NOTE:** this microservice is part of a loosely coupled architecture, thus when deployed by itself, it might not provide all of its functionalities. Please refer to https://github.com/nuvlaedge/deployment for a fully functional deployment

---

## Build the NuvlaEdge System Manager

This repository is already linked with Travis CI, so with every commit, a new Docker image is released.

There is a [POM file](pom.xml) which is responsible for handling the multi-architecture and stage-specific builds.

**If you're developing and testing locally in your own machine**, simply run `docker build .` or even deploy the microservice via the local [compose files](docker-compose.yml) to have your changes built into a new Docker image, and saved into your local filesystem.

**If you're developing in a non-master branch**, please push your changes to the respective branch, and wait for Travis CI to finish the automated build. You'll find your Docker image in the [nuvladev](https://hub.docker.com/u/nuvladev) organization in Docker hub, names as _nuvladev/system-manager:\<branch\>_.

## Deploy the NuvlaEdge System Manager

### Prerequisites

 - *Docker (version 18 or higher)*
 - *Docker Compose (version 1.23.2 or higher)*

### Launching the NuvlaEdge System Manager

Simply run `docker-compose up --build`


## Test the NuvlaEdge System Manager

This microservice comes with a Docker healtcheck, so your first check should be done by running `docker ps` and ensuring that the container status is "_healthy_". If that's not the case, then please check the Docker logs of this container because maybe your system has failed to meet the minimum requirements.

Once your container is healthy, you can also navigate to [localhost:3636](http://localhost:3636) where you'll find an overview dashboard. By default this page can only be accessed from localhost. **If you want to make this page available from outside localhost as well** (for debugging purposes for example), then simply go to [localhost:3636/debug?enabled=true](http://localhost:3636/debug?enabled=true), and the same page will also be published onto port 3637.

[localhost:3636/debug?enabled=false](http://localhost:3636/debug?enabled=false) will close port 3637 to the outside again.

## Contributing

This is an open-source project, so all community contributions are more than welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md)

## Copyright

Copyright &copy; 2021, SixSq SA
