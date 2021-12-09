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
        self.obj = SystemRequirements()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        self.assertEqual(self.obj.minimum_requirements, {
            "cpu": 1,
            "ram": 512,
            "disk": 2
        },
                         'Failed to initialize System Requirements class')
