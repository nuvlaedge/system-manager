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
import subprocess
import threading
from flask import Flask, render_template, request
from multiprocessing import Process
from system_manager.common import utils
from system_manager.Requirements import SystemRequirements, SoftwareRequirements
from system_manager.Supervise import Supervise


__copyright__ = "Copyright (C) 2020 SixSq"
__email__ = "support@sixsq.com"

app = Flask(__name__)
debug_app = Flask(__name__)


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


def generate_certificates():
    """ Generates self signed certificate """

    log = logging.getLogger("app")

    if os.path.exists(utils.nuvlabox_api_certs_folder):
        # it already exists, then just check of the certificates
        if os.path.exists("{}/{}".format(utils.nuvlabox_api_certs_folder, utils.server_cert_file)) and \
                os.path.exists("{}/{}".format(utils.nuvlabox_api_certs_folder, utils.server_key_file)) and \
                os.path.exists("{}/{}".format(utils.nuvlabox_api_certs_folder, utils.client_cert_file)) and \
                os.path.exists("{}/{}".format(utils.nuvlabox_api_certs_folder, utils.client_key_file)) and \
                os.path.exists("{}/{}".format(utils.nuvlabox_api_certs_folder, utils.ca_file)):
            # if all certificated already exist, then we are good...this was just a soft restart
            log.info("NuvlaBox API certificates already exist.")
            return
        else:
            # somehow not all certs are there...let's rebuild them all from scratch

            log.warning("Re-generating all NuvlaBox API certificates...")
    else:
        os.mkdir(utils.nuvlabox_api_certs_folder)
        log.info("Generating NuvlaBox API certificates for the first time")

    try:
        subprocess.check_output(["./generate-nuvlabox-api-certs.sh",
                                 "--certs-folder", utils.nuvlabox_api_certs_folder,
                                 "--server-key", utils.server_key_file,
                                 "--server-cert", utils.server_cert_file,
                                 "--client-key", utils.client_key_file,
                                 "--client-cert", utils.client_cert_file])
    except FileNotFoundError:
        logging.exception("Command to generate NuvlaBox API certs not found!")
        raise
    except (OSError, subprocess.CalledProcessError):
        logging.exception("Failed to generate NuvlaBox API certs!")
        raise


@app.route('/')
@debug_app.route('/')
def dashboard():
    """ Dashboard """

    # index_file = app.config["index_file"]
    return render_template("dashboard.html", msg="hi")


@app.route('/debug')
def debug():
    """ API endpoint to let other components set the NuvlaBox status """

    enabled = str(request.args.get('enabled'))
    debug_server = app.config.get("debug_server", None)

    if enabled.lower() == "true":
        if debug_server and debug_server.is_alive():
            log.exception("Debug mode is already enabled")
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

    set_logger()
    log = logging.getLogger("app")

    # Check if the system complies with the minimum hw and sw requirements for the NuvlaBox
    system_requirements = SystemRequirements()
    software_requirements = SoftwareRequirements()

    # Generate NB API certificates
    generate_certificates()

    supervisor = Supervise()

    # app.config["index_file"] = supervisor.printer_file
    # app.config["templates"] = supervisor.html_templates
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    debug_app.config["TEMPLATES_AUTO_RELOAD"] = True

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

        # web_server = threading.Thread(target=app.run, kwargs=dict(host="0.0.0.0", port=3636))
        # web_server.daemon = True
        # web_server.start()
        os.system("gunicorn --bind=0.0.0.0:3636 --keyfile {} --certfile {} --ca-certs {} --cert-reqs 2 --workers=3 wsgi:app".format(utils.nuvlabox_api_certs_folder+"/"+utils.server_key_file,
                                                                                                                                    utils.nuvlabox_api_certs_folder+"/"+utils.server_cert_file,
                                                                                                                                    utils.nuvlabox_api_certs_folder+"/"+utils.ca_file))

        while True:
            supervisor.build_content()




