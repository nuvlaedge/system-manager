#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import unittest
import werkzeug


class APITestCase(unittest.TestCase):

    def setUp(self) -> None:
        with mock.patch('system_manager.Supervise.Supervise') as mock_supervise:
            mock_supervise.return_value = mock.MagicMock()
            import api as SMApi
            self.obj = SMApi
            self.obj.render_template = mock.MagicMock()
            self.obj.Response = mock.MagicMock()
            self.obj.request = mock.MagicMock()
            self.obj.render_template.return_value = True
            self.obj.Response.return_value = 'foo'
        # logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        self.assertIsNotNone(self.obj.app,
                             'Failed to initialize Flask app')

    def test_main(self):
        self.assertIsInstance(self.obj.main(), werkzeug.wrappers.response.Response,
                              'Failed to get a redirection from the API main endpoint')

    @mock.patch('os.kill')
    def test_dashboard(self, mock_kill):
        self.obj.app.config["supervisor"].get_nuvlaedge_status.return_value = {}
        self.obj.app.config["supervisor"].reader.return_value = []
        # if no stats, get loading page
        self.assertTrue(self.obj.dashboard(),
                        'Failed to get loading page')
        self.obj.render_template.assert_called_once_with("loading.html")
        self.obj.app.config["supervisor"].container_runtime.list_all_containers_in_this_node.assert_not_called()

        # otherwise, get the dashboard
        self.obj.render_template.reset_mock()
        self.obj.app.config["supervisor"].get_nuvlaedge_status.return_value = {'resources': {}}
        self.assertTrue(self.obj.dashboard(),
                        'Failed to get dashboard page')
        self.obj.app.config["supervisor"].container_runtime.list_all_containers_in_this_node.assert_called_once()
        self.assertRaises(AssertionError, self.obj.render_template.assert_called_once_with, "loading.html")

        # in error, kill the process
        mock_kill.assert_not_called()
        self.obj.render_template.side_effect = Exception
        self.assertIsNone(self.obj.dashboard(),
                          'Failed to handle dashboard composition error')
        mock_kill.assert_called_once()

    @mock.patch('os.kill')
    def test_logs(self, mock_kill):
        self.obj.app.config["supervisor"].get_internal_logs_html.return_value = ('log', 'time')
        self.assertTrue(self.obj.logs(),
                        'Failed to get container logs')
        self.obj.app.config['supervisor'].get_internal_logs_html.assert_called_once_with()
        mock_kill.assert_not_called()

        # rendering error kill the process
        self.obj.render_template.side_effect = Exception
        self.assertIsNone(self.obj.logs(),
                          'Failed to handle rendering error')
        mock_kill.assert_called_once()

        # if event-stream, get a Response
        self.obj.request.headers = {'accept': 'text/event-stream'}
        self.assertEqual(self.obj.logs(), 'foo',
                         'Failed to stream logs')

    @mock.patch('os.kill')
    def test_peripherals(self, mock_kill):
        self.obj.app.config["supervisor"].get_nuvlaedge_peripherals.return_value = [
            {'classes': ['phone']},
            {'classes': ['n/a']},
            {'classes': ['gpu', 'video', 'n/a']},
            {'wrong-classes': []},
            {}
        ]

        self.assertTrue(self.obj.peripherals(),
                        'Failed to get peripherals HTML template')
        mock_kill.assert_not_called()

        self.obj.render_template.side_effect = Exception
        self.assertIsNone(self.obj.peripherals(),
                          'Failed handle error while getting peripherals template')
        mock_kill.assert_called_once()
