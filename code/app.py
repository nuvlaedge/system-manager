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
from flask import Flask, render_template, request
import threading
from multiprocessing import Process
from system_manager.common import utils
from system_manager.Requirements import SystemRequirements, SoftwareRequirements
from system_manager.Supervise import Supervise


__copyright__ = "Copyright (C) 2019 SixSq"
__email__ = "support@sixsq.com"

app = Flask(__name__)
debug_app = Flask(__name__)

data_volume = "/srv/nuvlabox/shared"
log_filename = "system-manager.log"


def set_logger(log_level, log_file):
    """ Configures logging """

    logging.basicConfig(level=log_level)
    root_logger = logging.getLogger()

    file_handler = logging.FileHandler(log_file)
    root_logger.addHandler(file_handler)

    # stdout_handler = logging.StreamHandler(sys.stdout)
    # root_logger.addHandler(stdout_handler)

    return root_logger


@app.route('/')
@debug_app.route('/')
def dashboard():
    """ Dashboard """

    index_file = app.config["index_file"]
    return render_template(index_file)


@app.route('/debug')
def debug():
    """ API endpoint to let other components set the NuvlaBox status """

    enabled = str(request.args.get('enabled'))
    debug_server = app.config.get("debug_server", None)

    if enabled.lower() == "true":
        if debug_server and debug_server.is_alive():
            logging.exception("Debug mode is already enabled")
        else:
            debug_server = Process(target=debug_app.run, kwargs=dict(host="0.0.0.0", port=3637))
            debug_server.daemon = True
            app.config["debug_server"] = debug_server
            debug_server.start()

        return '<a href="http://localhost:3637">Enter debug mode</a>'
    else:
        if debug_server and debug_server.is_alive():
            debug_server.terminate()
            debug_server.join()
            debug_server.close()
            app.config["debug_server"] = None
            return 'Exited debug mode'
        else:
            return 'Call "/debug?enabled=true" to start debug mode'


if __name__ == "__main__":
    """ Main """

    logging = set_logger(logging.INFO, "{}/{}".format(data_volume, log_filename))

    system_requirements = SystemRequirements()
    software_requirements = SoftwareRequirements()
    supervisor = Supervise()

    app.config["index_file"] = supervisor.printer_file
    app.config["templates"] = supervisor.html_templates
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    debug_app.config["TEMPLATES_AUTO_RELOAD"] = True

    if not software_requirements.check_docker_requirements() or not system_requirements.check_all_hw_requirements():
        logging.error("System does not meet the minimum requirements! Stopping")
        utils.cleanup(supervisor.list_internal_containers(), supervisor.docker_id)
        sys.exit(1)
    else:
        with open("{}/.status".format(data_volume), 'w') as s:
            s.write("OPERATIONAL")
        logging.info("Successfully created status file")

        peripherals = '{}/.peripherals'.format(data_volume)

        try:
            # Create Directory
            os.mkdir(peripherals)
            logging.info("Successfully created peripherals directory")
        except FileExistsError:
            logging.info("Directory " + peripherals + " already exists")

        # setup printer webserver
        logging.info("Starting local dashboard...")

        web_server = threading.Thread(target=app.run, kwargs=dict(host="0.0.0.0", port=3636))
        web_server.daemon = True
        web_server.start()

        while True:
            supervisor.build_content()




