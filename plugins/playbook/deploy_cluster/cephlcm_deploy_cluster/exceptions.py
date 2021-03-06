# -*- coding: utf-8 -*-
"""Exceptions for deploy cluster playbook."""


from cephlcm.common import exceptions as base_exceptions


class ClusterDeployError(base_exceptions.CephLCMError):
    """Exception family, specific for CephLCM plugin for cluster deployment."""


class SecretWasNotFound(ClusterDeployError):
    """Exception raised if it is not possible to find monitor secret."""

    def __init__(self, fsid):
        super().__init__("Cannot find secret for cluster with FSID {0}".format(
            fsid
        ))


class UnknownPlaybookConfiguration(ClusterDeployError):
    """Exception raised if playbook configuration is unknown."""

    def __init__(self):
        super().__init__(
            "Unknown playbook configuration. Check your environment variables."
        )


class NotEmptyServerList(ClusterDeployError):
    """Exception raised if cluster is not empty."""

    def __init__(self, cluster_id):
        super().__init__("Cluster {0} already has servers".format(cluster_id))
