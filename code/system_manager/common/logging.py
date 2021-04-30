#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Set logging conf """

import logging

logging.basicConfig(format='%(levelname)s - %(filename)s/%(module)s/%(funcName)s - %(message)s', level='INFO')
