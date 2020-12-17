# Changelog
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

