#!/usr/local/bin/python
# -*- coding: utf-8 -*-

"""NuvlaBox System Manager service

This service makes sure the NuvlaBox engine can be
installed in the device and supervises all internal
components of the NuvlaBox

Arguments:

"""

import logging
import sys
import os
import signal
import subprocess
from flask import Flask, render_template, request
from multiprocessing import Process
from system_manager.common import utils
from system_manager.Requirements import SystemRequirements, SoftwareRequirements
from system_manager.Supervise import Supervise


__copyright__ = "Copyright (C) 2020 SixSq"
__email__ = "support@sixsq.com"

app = Flask(__name__)
app.config["supervisor"] = Supervise()
app.config["TEMPLATES_AUTO_RELOAD"] = True


def set_logger():
    """ Configures logging """
    # give logger a name: app
    root = logging.getLogger("app")
    root.setLevel(logging.DEBUG)
    # log into file
    fh = logging.FileHandler("{}/{}".format(utils.data_volume, utils.log_filename))
    fh.setLevel(logging.ERROR)
    # print to console
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.DEBUG)
    # format log messages
    formatter = logging.Formatter('%(levelname)s - %(funcName)s - %(message)s')
    c_handler.setFormatter(formatter)
    fh.setFormatter(formatter)
    # add handlers
    root.addHandler(c_handler)
    root.addHandler(fh)


@app.route('/')
def dashboard():
    """ Dashboard """

    info = app.config["supervisor"].get_docker_info()
    usages = app.config["supervisor"].get_system_usage()

    try:
        if not usages:
            return render_template("loading.html")
        else:
            return render_template("dashboard.html", cpus_total=usages.get("cpus"),
                                   memory_total="%.2f GB" % float(int(usages.get("memory"))/1024),
                                   disk_total="%s GB" % usages.get("disk"),
                                   cpu_usage=usages.get("cpu-usage"), memory_usage=usages.get("memory-usage"),
                                   disk_usage=usages.get("disk-usage"), os=usages.get("os"),
                                   arch=usages.get("architecture"), ip=usages.get("ip"),
                                   docker_version=usages.get("docker-server-version"))
    except:
        logging.exception("Server side error")
        os.kill(os.getppid(), signal.SIGKILL)


if __name__ == "__main__":
    """ Main """

    set_logger()
    log = logging.getLogger("app")

    # Check if the system complies with the minimum hw and sw requirements for the NuvlaBox
    system_requirements = SystemRequirements()
    software_requirements = SoftwareRequirements()

    supervisor = Supervise()

    if not software_requirements.check_docker_requirements() or not system_requirements.check_all_hw_requirements():
        log.error("System does not meet the minimum requirements! Stopping")
        utils.cleanup(supervisor.list_internal_containers(), supervisor.docker_id)
        sys.exit(1)
    else:
        with open("{}/.status".format(utils.data_volume), 'w') as s:
            s.write("OPERATIONAL")
        log.info("Successfully created status file")

        peripherals = '{}/.peripherals'.format(utils.data_volume)

        try:
            # Create Directory
            os.mkdir(peripherals)
            log.info("Successfully created peripherals directory")
        except FileExistsError:
            log.info("Directory " + peripherals + " already exists")

        # setup printer webserver
        log.info("Starting local dashboard...")

        try:
            subprocess.check_output(["gunicorn", "--bind=0.0.0.0:3636", "--threads=2",
                                     "--worker-class=gthread", "--workers=2", "--reload",
                                     "wsgi:app"])
        except FileNotFoundError:
            logging.exception("Gunicorn not available!")
            utils.cleanup(supervisor.list_internal_containers(), supervisor.docker_id)
            raise
        except (OSError, subprocess.CalledProcessError):
            logging.exception("Failed start local dashboard!")
            raise




