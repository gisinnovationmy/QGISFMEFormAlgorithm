# -*- coding: utf-8 -*-

__author__ = 'GIS Innovation Sdn. Bhd.'
__date__ = '2025-04-17'
__copyright__ = '(C) 2025 by GIS Innovation Sdn. Bhd.'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import sys
import inspect

from qgis.core import QgsProcessingAlgorithm, QgsApplication
from .qgisfmeformalgorithm_provider import QGISFMEFormAlgorithmProvider

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)


class QGISFMEFormAlgorithmPlugin(object):

    def __init__(self):
        self.provider = None

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = QGISFMEFormAlgorithmProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)