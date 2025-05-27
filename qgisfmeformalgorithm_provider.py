# -*- coding: utf-8 -*-

__author__ = 'GIS Innovation Sdn. Bhd.'
__date__ = '2025-04-17'
__copyright__ = '(C) 2025 by GIS Innovation Sdn. Bhd.'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QgsProcessingProvider
from .qgisfmeformalgorithm_algorithm import QGISFMEFormAlgorithmAlgorithm


class QGISFMEFormAlgorithmProvider(QgsProcessingProvider):

    def __init__(self):
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)

    def unload(self):
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider.
        """
        self.addAlgorithm(QGISFMEFormAlgorithmAlgorithm())
        # add additional algorithms here
        # self.addAlgorithm(MyOtherAlgorithm())

    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return 'QGIS-FME Platform Algorithms'

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr('QGIS-FME Platform Algorithms')

    def icon(self):
        """Returns the algorithm icon for display in the toolbox and model designer"""
        import os
        from qgis.PyQt.QtGui import QIcon
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(plugin_dir, 'platform_icon.png')
        
        # Check if the icon file exists
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            # Return a default icon if the file doesn't exist
            return QIcon()

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()