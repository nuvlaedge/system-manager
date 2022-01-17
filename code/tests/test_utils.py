#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import unittest
import system_manager.common.utils as utils


class DockerTestCase(unittest.TestCase):

    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_set_operational_status(self):
        # writes twice
        with mock.patch("system_manager.common.utils.open") as mock_open:
            self.assertIsNone(utils.set_operational_status('status', []),
                              'Failed to set operational status')
            self.assertEqual(mock_open.call_count, 2,
                             'Should write two files when setting operational status')

    @mock.patch('os.path.exists')
    def test_status_file_exists(self, mock_exists):
        # simple check for file existence
        mock_exists.return_value = False
        self.assertFalse(utils.status_file_exists(),
                         'Says status file exists when it does not')

        mock_exists.return_value = True
        self.assertTrue(utils.status_file_exists(),
                        'Says status file does not exist when it does')
