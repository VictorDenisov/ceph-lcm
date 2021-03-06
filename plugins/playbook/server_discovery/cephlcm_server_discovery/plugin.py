# -*- coding: utf-8 -*-
"""Playbook plugin for server discovery."""


import os
import os.path
import re
import shutil
import socket
import tempfile

try:
    import simplejson as json
except ImportError:
    import json

from cephlcm.common import log
from cephlcm.common import playbook_plugin
from cephlcm.common import retryutils
from cephlcm.common.models import server


DESCRIPTION = """
Plugin to register server into CephLCM.

Basically, server should send only limited information about self into
CephLCM. All other verification and discovery should be done by CephLCM
controller service using Ansible. This involves collecting of facts and
verification that host is accesible.

This playbook is not intended to be public.
""".strip()
"""Plugin description."""

LOG = log.getLogger(__name__)
"""Logger."""

NOT_IP_REGEXP = re.compile("[^0-9\.]")
"""Regexp for characters which tells that it is not IP."""


class ServerDiscovery(playbook_plugin.Ansible):

    NAME = "Server Discovery"
    DESCRIPTION = DESCRIPTION
    PUBLIC = False
    MODULE = "setup"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tempdir = None

    def get_dynamic_inventory(self):
        if not self.task:
            raise RuntimeError("No task is defined for inventory.")

        return {
            "new": {
                "hosts": [self.task.data["host"]]
            },
            "_meta": {
                "hostvars": {
                    self.task.data["host"]: {
                        "ansible_user": self.task.data["username"]
                    }
                }
            }
        }

    def compose_command(self, task):
        cmdline = super().compose_command(task)
        cmdline.extend(["--tree", self.tempdir])
        cmdline.append("new")

        return cmdline

    def on_pre_execute(self, task):
        self.tempdir = tempfile.mkdtemp()

    def on_post_execute(self, task, exc_value, exc_type, exc_tb):
        try:
            if exc_value:
                LOG.info("Do not execute anything because of %s: %s",
                         exc_type, exc_value)
                return

            filenames = [os.path.join(self.tempdir, name)
                         for name in os.listdir(self.tempdir)]
            if len(filenames) != 1:
                raise RuntimeError(
                    "One file has to be present in temporary directory. "
                    "Found: {0!r}".format(filenames))
            filename = filenames[0]

            with open(filename, "r") as filefp:
                return self.create_server(task, json.load(filefp))
        finally:
            shutil.rmtree(self.tempdir)

    def create_server(self, task, json_result):
        facts = json_result["ansible_facts"]
        ip_addr = self.get_host_ip(task)
        create_method = retryutils.mongo_retry()(server.ServerModel.create)

        try:
            server_model = create_method(
                server_id=task.data["id"],
                name=facts["ansible_nodename"],
                fqdn=facts["ansible_nodename"],
                username=task.data["username"],
                ip=ip_addr,
                facts=facts
            )
        except Exception as exc:
            LOG.exception("Cannot create server for task %s: %s",
                          task._id, exc)
            raise
        else:
            LOG.info("Creates server %s for task %s",
                     server_model.model_id, task._id)

        return server_model

    def get_host_ip(self, task):
        if not NOT_IP_REGEXP.search(task.data["host"]):
            return task.data["host"]

        try:
            return socket.gethostbyname(task.data["host"])
        except socket.error as exc:
            LOG.warning("Cannot resolve hostname %s", task.data["host"])
