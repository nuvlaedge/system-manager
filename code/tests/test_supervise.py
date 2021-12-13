#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import docker
import logging
import mock
import requests
import unittest
import system_manager.Supervise as Supervise
import tests.utils.fake as fake
from system_manager.common.ContainerRuntime import Containers


class SuperviseTestCase(unittest.TestCase):

    def setUp(self) -> None:
        Supervise.__bases__ = (fake.Fake.imitate(Containers),)

        self.obj = Supervise.Supervise()
        self.obj.container_runtime = mock.MagicMock()
        # logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        # the base class should also have been set
        self.assertEqual(self.obj.agent_dg_failed_connection, 0,
                         'Failed to initialize Supervise class')

    def test_printer(self):
        # just make sure the write happens
        with mock.patch('system_manager.Supervise.open') as mock_open:
            self.assertIsNone(self.obj.printer('content', 'file'),
                              'Failed to write to file')

    def test_reader(self):
        # read string from file
        with mock.patch('system_manager.Supervise.open', mock.mock_open(read_data='content')):
            self.assertEqual(self.obj.reader('file'), 'content',
                             'Failed to read content from file')

    def test_classify_this_node(self):
        self.obj.container_runtime.get_node_id.return_value = 'id'
        # if COE is disabled, get None and set attrs to false
        self.obj.container_runtime.is_coe_enabled.return_value = False
        self.assertIsNone(self.obj.classify_this_node(),
                          'Tried to classify node where COE is disabled')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (False, False),
                         'Saying node has cluster mode enabled when it has not')

        self.obj.container_runtime.is_coe_enabled.return_value = True
        self.obj.container_runtime.get_node_id.return_value = None
        self.assertIsNone(self.obj.classify_this_node(),
                          'Tried to classify node without a node ID')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (False, False),
                         'Saying node has cluster mode enabled when it does not even have a node ID')

        # otherwise, cluster mode is True
        self.obj.container_runtime.get_node_id.return_value = 'id'
        self.obj.container_runtime.get_cluster_managers.return_value = []
        self.assertIsNone(self.obj.classify_this_node(),
                          'Failed to classify node which is not a manager')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (False, True),
                         'Failed to classify when node is not a manager but cluster is enabled')

        # and if cluster is a manager, also label it
        self.obj.container_runtime.get_cluster_managers.return_value = ['id']
        self.obj.container_runtime.set_nuvlabox_node_label.return_value = (None, None)
        self.assertIsNone(self.obj.classify_this_node(),
                          'Failed to classify manager node')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (True, True),
                         'Node should be a manager in cluster mode')
        self.obj.container_runtime.set_nuvlabox_node_label.assert_called_once_with('id')

        # and is labeling fails, set degraded state
        self.obj.container_runtime.set_nuvlabox_node_label.return_value = (None, 'label-error')
        self.obj.classify_this_node()
        self.assertIn((Supervise.utils.status_degraded, 'label-error'), self.obj.operational_status,
                      'Failed to set degraded state')

    def test_get_nuvlabox_status(self):
        # cope with error while opening status file for reading
        with mock.patch('system_manager.Supervise.open') as mock_open:
            # file not found
            mock_open.side_effect = FileNotFoundError
            self.assertEqual(self.obj.get_nuvlabox_status(), {},
                             'Failed to set system usages when NB status is not found')

        with mock.patch('system_manager.Supervise.open', mock.mock_open(read_data="'bad-content'")):
            # bad json
            self.assertEqual(self.obj.get_nuvlabox_status(), self.obj.system_usages,
                             'Failed to set system usages when NB status is malformed')

        with mock.patch('system_manager.Supervise.open', mock.mock_open(read_data='{"usages": true}')):
            # read well
            self.assertEqual(self.obj.get_nuvlabox_status(), {"usages": True},
                             'Failed to set system usages from NB status')

    @mock.patch('os.path.isdir')
    @mock.patch('glob.iglob')
    def test_get_nuvlabox_peripherals(self, mock_iglob, mock_isdir):
        # if peripherals folder doe snot exist get nothing
        mock_iglob.side_effect = FileNotFoundError
        self.assertEqual(self.obj.get_nuvlabox_peripherals(), [],
                         'Got NB peripherals even though peripherals folder does not exist')

        mock_iglob.reset_mock(side_effect=True)
        mock_iglob.return_value = ['per1', 'per2']
        # if all returned "filed" are dirs, get nothing again
        mock_isdir.return_value = True
        self.assertEqual(self.obj.get_nuvlabox_peripherals(), [],
                         'Got NB peripherals even though there are no files, just folders')
        self.assertEqual(mock_isdir.call_count, 2,
                         'Should have checked the 2 returned paths from iglob')

        # otherwise, open files for reading
        mock_isdir.return_value = False
        # if files do not exist, get nothing
        with mock.patch('system_manager.Supervise.open') as mock_open:
            mock_open.side_effect = [FileNotFoundError, FileNotFoundError]
            self.assertEqual(self.obj.get_nuvlabox_peripherals(), [],
                             'Got NB peripherals even though there are no files')

        # otherwise, get their content
        with mock.patch('system_manager.Supervise.open', mock.mock_open(read_data='{"foo": "bar"}')):
            self.assertEqual(self.obj.get_nuvlabox_peripherals(), [{"foo": "bar"}, {"foo": "bar"}],
                             'Failed to get NB peripherals from local volume')

    def test_get_internal_logs_html(self):
        # if there are no components, there are no logs
        self.obj.container_runtime.list_internal_components.return_value = []
        self.assertEqual(self.obj.get_internal_logs_html()[0], '',
                         'Got internal logs even though there are no components to log from')
        self.obj.container_runtime.list_internal_components.assert_called_once()

        # otherwise, fetch logs from the respective containers
        self.obj.container_runtime.list_internal_components.return_value = ['component1', 'component2']
        self.obj.container_runtime.fetch_container_logs.return_value = 'multiline\nlogs'
        self.obj.container_runtime.get_component_id.return_value = 'id'
        self.obj.container_runtime.get_component_name.return_value = 'name'

        out = self.obj.get_internal_logs_html()
        self.assertGreater(len(out[0]), 0,
                           'There are logs but got empty string')
        self.assertIsInstance(out[0], str,
                              'Logs should be a string')
        self.assertIsInstance(out[1], int,
                              'Time should be passed with each log')

    @mock.patch.object(Supervise.Supervise, 'printer')
    @mock.patch('os.path.exists')
    def test_write_container_stats_table_html(self, mock_exists, mock_printer):
        # if stats json file does not exist, don't read it
        mock_printer.return_value = None
        mock_exists.return_value = False
        with mock.patch('system_manager.Supervise.open') as mock_open:
            self.assertIsNone(self.obj.write_container_stats_table_html(),
                              'Should have just written the HTML template onto the stats table')
            mock_open.assert_not_called()

        mock_printer.assert_called_once()

        # otherwise, print the stats content
        mock_exists.return_value = True
        with mock.patch('system_manager.Supervise.open', mock.mock_open(read_data='[{}, {}]')) as mock_open:
            self.assertIsNone(self.obj.write_container_stats_table_html(),
                              'Failed to write container stats into HTML table')
            mock_open.assert_called_once_with(Supervise.utils.container_stats_json_file)

    @mock.patch('OpenSSL.crypto.load_certificate')
    @mock.patch('OpenSSL.crypto')
    @mock.patch('os.path.isfile')
    def test_is_cert_rotation_needed(self, mock_isfile, mock_crypto, mock_load_cert):
        # if tls sync is not a file, get False
        mock_isfile.return_value = False
        self.assertFalse(self.obj.is_cert_rotation_needed(),
                         'Failed to check that TLS sync file is not a real file')

        # otherwise
        mock_isfile.reset_mock(return_value=True)

        # if cert files do no exist, get False
        mock_isfile.side_effect = [True, False, False, False]  # TLS file + 3 cert files
        self.assertFalse(self.obj.is_cert_rotation_needed(),
                         'Got True even though cert files do not exist')

        # otherwise
        mock_crypto.FILETYPE_PEM = ''
        cert_obj = mock.MagicMock()
        # a valid certificate is in the future, more than 5 days
        cert_obj.get_notAfter.return_value = b'99990309161546Z'
        mock_load_cert.return_value = cert_obj
        mock_isfile.side_effect = [True, True, True, True]  # TLS file + 3 cert files
        with mock.patch('system_manager.Supervise.open'):
            self.assertFalse(self.obj.is_cert_rotation_needed(),
                             'Failed to recognize valid certificates')

        # with less than 5 days to expire, return false
        cert_obj.get_notAfter.return_value = b'20200309161546Z'
        mock_load_cert.return_value = cert_obj
        mock_isfile.side_effect = [True, True, True, True]  # TLS file + 3 cert files
        with mock.patch('system_manager.Supervise.open'):
            self.assertTrue(self.obj.is_cert_rotation_needed(),
                            'Failed to recognize certificates in need of renewal')

    @mock.patch('os.remove')
    @mock.patch('os.path.isfile')
    def test_request_rotate_certificates(self, mock_isfile, mock_rm):
        self.obj.container_runtime.restart_credentials_manager.return_value = None
        # always returns None, but if file exists, calls fn to remove certs and recreate them
        mock_isfile.return_value = False
        self.assertIsNone(self.obj.request_rotate_certificates(),
                          'Tried to rotate certs without needing it')
        mock_rm.assert_not_called()
        self.obj.container_runtime.restart_credentials_manager.assert_not_called()

        mock_isfile.return_value = True
        self.assertIsNone(self.obj.request_rotate_certificates(),
                          'Failed to rotate certs')
        mock_rm.assert_called_once_with(Supervise.utils.tls_sync_file)
        self.obj.container_runtime.restart_credentials_manager.assert_called_once()

    def test_launch_data_gateway(self):
        # if self.is_cluster_enabled and not self.i_am_manager, cannot even start fn
        self.obj.i_am_manager = False
        self.obj.is_cluster_enabled = True
        self.assertRaises(Supervise.ClusterNodeCannotManageDG, self.obj.launch_data_gateway, 'dg')

        # otherwise, run
        self.obj.i_am_manager = True
        self.obj.container_runtime.client.services.create.return_value = None
        self.obj.container_runtime.client.containers.run.return_value = None

        # if in swarm, CREATE DG
        self.assertIsNone(self.obj.launch_data_gateway('dg'),
                          'Failed to create data-gateway service')
        self.obj.container_runtime.client.services.create.assert_called_once()
        self.obj.container_runtime.client.containers.run.assert_not_called()

        # otherwise, RUN DG container
        self.obj.is_cluster_enabled = False
        self.assertIsNone(self.obj.launch_data_gateway('dg'),
                          'Failed to create data-gateway container')
        self.obj.container_runtime.client.containers.run.assert_called_once()

        # if docker fails, parse error
        self.obj.container_runtime.client.containers.run.side_effect = docker.errors.APIError('', requests.Response())
        self.assertFalse(self.obj.launch_data_gateway('dg'),
                         'Says it launched the DG even though DG failed with an exception')

        self.obj.container_runtime.client.services.create.side_effect = docker.errors.APIError('409',
                                                                                               requests.Response())
        # when 409, simply restart the DG
        component = mock.MagicMock()
        component.restart.return_value = None
        component.force_update.return_value = None
        self.obj.container_runtime.client.containers.get.return_value = component
        self.obj.container_runtime.client.services.get.return_value = component
        self.obj.is_cluster_enabled = True
        self.assertTrue(self.obj.launch_data_gateway('dg'),
                        'Failed to restart data-gateway service')
        self.obj.container_runtime.client.services.get.assert_called_once_with('dg')
        self.obj.container_runtime.client.containers.get.assert_not_called()

        self.obj.is_cluster_enabled = False
        self.obj.container_runtime.client.containers.run.side_effect = docker.errors.APIError('409',
                                                                                              requests.Response())
        self.assertTrue(self.obj.launch_data_gateway('dg'),
                        'Failed to restart data-gateway container')
        self.obj.container_runtime.client.containers.get.assert_called_once_with('dg')

    def test_find_nuvlabox_agent(self):
        # if cannot find it, get None and append to op status
        l = len(self.obj.operational_status)
        self.obj.container_runtime.find_nuvlabox_agent_container.return_value = (None, True)
        self.assertIsNone(self.obj.find_nuvlabox_agent(),
                          'Claming the agent was found when it does not exist')
        self.assertEqual(len(self.obj.operational_status), l+1,
                         'Failed to append operational status due to agent not being found')

        # otherwise succeed
        self.obj.container_runtime.find_nuvlabox_agent_container.return_value = ('container', False)
        self.assertEqual(self.obj.find_nuvlabox_agent(), 'container',
                         'Failed to find NB agent container')

    def test_check_dg_network(self):
        target_network = mock.MagicMock()
        target_network.connect.return_value = None

        # if no data_gateway_object, get None
        self.obj.data_gateway_object = None
        self.assertIsNone(self.obj.check_dg_network(mock.MagicMock()),
                          'Tried to check DG net even though data_gateway_object does not exist')

        # when in container mode
        self.obj.is_cluster_enabled = False
        self.obj.data_gateway_object = fake.MockContainer()
        # if network is already set, do nothing
        target_network.name = list(fake.MockContainer().attrs['NetworkSettings']['Networks'].keys())[0]
        target_network.id = list(fake.MockContainer().attrs['NetworkSettings']['Networks'].keys())[0]
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is already set')
        target_network.connect.assert_not_called()

        # same for cluster mode
        self.obj.is_cluster_enabled = True
        self.obj.data_gateway_object = fake.MockService('service-name', 'net-id')
        target_network.name = 'net-id'
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is already set in cluster mode')
        target_network.connect.assert_not_called()

        # and if it is not set, connect DG to it
        target_network.name = 'new-net'
        target_network.id = 'new-net-id'
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is not set in cluster mode')
        self.assertTrue(self.obj.data_gateway_object.updated,
                        'Should have updated DG service to connect to DG network, but did not')

        # same for containers
        self.obj.is_cluster_enabled = False
        self.obj.data_gateway_object = fake.MockContainer('container-name')
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is not set')
        target_network.connect.assert_called_once_with('container-name')

    def test_





