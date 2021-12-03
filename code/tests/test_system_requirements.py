#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from system_manager.Requirements import SystemRequirements
import json
import logging
import mock
import requests
import unittest
from tests.utils.fake import Fake, FakeNuvlaApi


class SystemRequirementsTestCase(unittest.TestCase):

    def setUp(self):

        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

