# Changelog
## [2.4.0] - 2022-07-18
### Added
### Changed
 - Use common base image for all NE components
 - Changed main script name to manager_main.py
 - Changed base docker image to match the rest of the NuvlaEdge services
## [2.3.0] - 2022-03-24
### Added 
 - Add org.opencontainers labels
### Changed
 - Network nuvlabox-shared-network encryption can optionally be disabled
## [2.2.0] - 2021-12-06
### Added 
 - explicit reporting of missing minimum requirements
### Changed
## [2.1.5] - 2021-10-19
### Added 
 - report status notes when minimum requirements are not met
### Changed
## [2.1.4] - 2021-10-07
### Added
### Changed
 - fix discovery of Docker server version, when Docker is installed from source
## [2.1.3] - 2021-10-04
### Added
### Changed
 - fix bug in variable names
## [2.1.2] - 2021-10-01
### Added
### Changed
 - cope with faulty multiple Docker networks with the same name
## [2.1.1] - 2021-08-02
### Added
### Changed
 - refactored internal container healer
 - schedule container restarts for the near future to cope with NBE uninstall
## [2.1.0] - 2021-07-09
### Added 
 - support for execution in Kubernetes 
 - make Swarm mode a soft requirement
### Changed
## [2.0.1] - 2021-06-11
### Added
### Changed
 - fix self-healing of the agent component
 - fix quoting for ack service
 - use low level Docker api for getting container info
## [2.0.0] - 2021-04-30
### Added 
 - support for clustering 
 - self-managed data gateway 
 - gracefull handling of shutdowns
### Changed
 - improve supervisioning
## [1.4.1] - 2021-01-12
### Added 
 - reap obsolete data-gateway containers, based on their Nuvla resource ID
### Changed
## [1.4.0] - 2021-01-12
### Added 
 - supervision of datagateway containers
### Changed
 - run internal dashboard as a daemon
 - code refactoring
## [1.3.2] - 2021-01-08
### Added
### Changed
 - fixed double logging
 - improve container monitoring
## [1.3.1] - 2021-01-05
### Added
### Changed
 - fixed peripherals page in internal dashboard
 - code refactoring
## [1.3.0] - 2020-12-17
### Added 
 - supervise datagateway and restart it when necessary
### Changed
 - remove duplicate instantiation of the Supervise class
## [1.2.1] - 2020-10-02
### Added 
- ONBUILD SixSq license dump
### Changed
## [1.2.0] - 2020-08-19
### Added 
- optional env var SKIP_MINIMUM_REQUIREMENTS to avoid checking the system requirements before installation
### Changed
- cleanup logging
## [1.1.1] - 2020-08-10
### Added
### Changed
- removed file logging
## [1.1.0] - 2020-08-06
### Added 
- pyopenssl to Docker image 
- supervisioning checks to issue certificates rotation when they are about to expire
### Changed
## [1.0.2] - 2020-03-30
### Added
### Changed
- retrieve resource metrics for internal dashboard according to new telemetry format
## [1.0.1] - 2020-03-16
### Added
### Changed
- fixed network plot with duplicate values in dashboard
## [1.0.0] - 2020-02-14
### Added 
- internal local dashboard 
- collection of nuvlabox logs to dashboard 
- system information into dashboard via gauges, plots and tables 
- graphical visualization of peripherals 
- gunicorn local server for dashboard
### Changed
- collect all metrics from NuvlaBox agent
- remove psutil dependency
- fixed docker stats collection and slowliness
## [0.4.1] - 2019-11-19
### Added
### Changed
- upgrade to Python 3.8
## [0.4.0] - 2019-07-30
### Added 
- debug port mapping to expose local dashboard outside localhost 
- API switch for debug mode
### Changed
- fixed KeyError when retrieving Docker stats
## [0.3.1] - 2019-07-29
### Added
### Changed
- fixed index error exception in docker stats
## [0.3.0] - 2019-07-29
### Added 
- docker stats and general NB info to local dashboard
### Changed
## [0.2.3] - 2019-07-03
### Added 
- creation of local peripherals folder 
- extra logging
### Changed

## [0.2.2] - 2019-06-12
### Added
  - build for arm platform

## [0.2.1] - 2019-06-04
## Changed
  - Reduced minimum RAM requirement to 768 MB to make
    it accept a RPi 3 as platform

## [0.2.0] - 2019-06-03
### Added
  - support for multi-architecture images
### Changed
  - reduced minimum memory to 512 MB

## [0.1.2] - 2019-05-21
### Added 
  - added curl to Docker image

## [0.1.1] - 2019-05-20
### Changed
  - renamed state to status and ONLINE to OPERATIONAL

## [0.1.0] - 2019-05-17
### Added
  - web server to display system monitoring
  - check for minimum requirements
  - coordination with nuvlabox agent
  - state management

