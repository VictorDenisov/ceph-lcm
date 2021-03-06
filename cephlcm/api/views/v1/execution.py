# -*- coding: utf-8 -*-
"""This module contains view for /v1/execution API."""


import flask

from cephlcm.api import auth
from cephlcm.api import exceptions as http_exceptions
from cephlcm.api import validators
from cephlcm.api.views import generic
from cephlcm.common import exceptions as base_exceptions
from cephlcm.common import log
from cephlcm.common.models import execution
from cephlcm.common.models import execution_step
from cephlcm.common.models import playbook_configuration
from cephlcm.common.models import task


POST_SCHEMA = {
    "playbook_configuration": {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "version"],
        "properties": {
            "id": {"$ref": "#/definitions/uuid4"},
            "version": {"$ref": "#/definitions/positive_integer"}
        }
    }
}
POST_SCHEMA = validators.create_data_schema(POST_SCHEMA, True)
"""Schema for creating new execution."""

LOG = log.getLogger(__name__)
"""Logger."""


class ExecutionView(generic.VersionedCRUDView):
    """Implementation of view for /v1/execution API."""

    decorators = [
        auth.require_authorization("api", "view_execution"),
        auth.require_authentication
    ]

    NAME = "execution"
    MODEL_NAME = "execution"
    ENDPOINT = "/execution/"
    PARAMETER_TYPE = "uuid"

    def get_all(self):
        return execution.ExecutionModel.list_models(self.pagination)

    @validators.with_model(execution.ExecutionModel)
    def get_item(self, item_id, item, *args):
        return item

    @auth.require_authorization("api", "view_execution_version")
    def get_versions(self, item_id):
        return execution.ExecutionModel.list_versions(
            str(item_id), self.pagination
        )

    def get_version(self, item_id, version):
        model = execution.ExecutionModel.find_version(
            str(item_id), int(version)
        )

        if not model:
            LOG.info("Cannot find model with ID %s", item_id)
            raise http_exceptions.NotFound

        return model

    @auth.require_authorization("api", "create_execution")
    @validators.require_schema(POST_SCHEMA)
    def post(self):
        pc_id = self.request_json["playbook_configuration"]["id"]
        pc_version = self.request_json["playbook_configuration"]["version"]

        config = playbook_configuration.PlaybookConfigurationModel
        config = config.find_version(pc_id, pc_version)
        if not config:
            LOG.warning(
                "Cannot find playbook configuration %s of version %s",
                pc_id, pc_version
            )
            raise http_exceptions.UnknownPlaybookConfiguration(
                pc_id, pc_version
            )

        auth.check_auth_permission(flask.g.token.user,
                                   "playbook", config.playbook)

        model = execution.ExecutionModel.create(config, self.initiator_id)
        LOG.info(
            "Created execution %s for playbook configuration %s of "
            "version %s",
            model.model_id, config.model_id, config.version
        )

        try:
            tsk = task.PlaybookPluginTask(
                config.playbook, config._id, model.model_id
            )
            tsk.create()
        except Exception as exc:
            LOG.error("Cannot create task for execution %s: %s",
                      model.model_id, exc)
            model.state = execution.ExecutionState.failed
            model.save()
            raise
        else:
            LOG.info("Created task for execution %s: %s",
                     model.model_id, tsk._id)

        return model

    @auth.require_authorization("api", "delete_execution")
    @validators.with_model(execution.ExecutionModel)
    def delete(self, item_id, item):
        if item.state == execution.ExecutionState.created:
            try:
                return self.cancel_created_execution(item)
            except base_exceptions.UniqueConstraintViolationError:
                LOG.debug("Execution %s already changed it's state")
                item = execution.ExecutionModel.find_by_model_id(item_id)

        if item.state == execution.ExecutionState.started:
            item = self.cancel_started_execution(item)

        return item

    def cancel_created_execution(self, item):
        item.initiator_id = self.initiator_id
        item.state = execution.ExecutionState.canceled
        item.save()

        LOG.info("Not started execution %s was canceled", item.model_id)

        return item

    def cancel_started_execution(self, item):
        item.initiator_id = self.initiator_id
        item.state = execution.ExecutionState.canceling
        item.save()

        LOG.info("Execution %s is cancelling now", item.model_id)

        tsk = task.CancelPlaybookPluginTask(item.model_id)
        tsk.create()

        LOG.info("Task for cancelling execution %s is %s",
                 item.model_id, tsk._id)

        return item


class ExecutionStepsView(generic.CRUDView):

    NAME = "execution_step"
    MODEL_NAME = "execution_step"

    decorators = [
        auth.require_authorization("api", "view_execution"),
        auth.require_authorization("api", "view_execution_steps"),
        auth.require_authentication
    ]

    @classmethod
    def register_to(cls, application):
        main_endpoint = generic.make_endpoint(
            ExecutionView.ENDPOINT,
            "<{0}:item_id>".format(ExecutionView.PARAMETER_TYPE),
            "steps"
        )

        application.add_url_rule(
            main_endpoint,
            view_func=cls.as_view(cls.NAME), methods=["GET"]
        )

    @validators.with_model(execution.ExecutionModel)
    def get(self, item_id, item):
        return execution_step.ExecutionStep.list_models(
            str(item_id), self.pagination
        )
