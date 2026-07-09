# -*- coding: utf-8 -*-

__author__ = 'GIS Innovation Sdn. Bhd.'
__date__ = '2025-04-17'
__copyright__ = '(C) 2025 by GIS Innovation Sdn. Bhd.'


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load QGISFMEFormAlgorithm class from file QGISFMEFormAlgorithm.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .qgisfmeformalgorithm import QGISFMEFormAlgorithmPlugin
    return QGISFMEFormAlgorithmPlugin()