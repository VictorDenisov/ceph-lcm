# -*- coding: utf-8 -*-
"""This module contains a set of utilities, used to manage email send."""


import smtplib

from email.mime import multipart
from email.mime import text

from cephlcm.common import config
from cephlcm.common import log


CONF = config.make_config()
"""Config."""

LOG = log.getLogger(__name__)
"""Logger."""


def send(to, subject, text_body, html_body=None, cc=None, bcc=None,
         from_=None, host=None, port=None, login=None, password=None):
    """Send email.

    to, cc and bcc are user email lists.
    """
    from_ = from_ or CONF.COMMON_EMAIL["from"]
    host = host or CONF.COMMON_EMAIL["host"]
    port = port or CONF.COMMON_EMAIL["port"]
    login = login or CONF.COMMON_EMAIL["login"]
    password = password or CONF.COMMON_EMAIL["password"]

    to, cc, bcc = make_lists(to, cc, bcc)
    message = make_message(from_, to, cc, subject, text_body, html_body)
    if not CONF.COMMON_EMAIL["enabled"]:
        LOG.info(
            "Send email(to=%r, cc=%r, bcc=%r, subject=%r): %s",
            to, cc, bcc, subject, text_body
        )
        return

    client = make_client(host, port, login, password)

    LOG.info("Send email to %s (CC: %s, BCC: %s), subject is '%s'",
             to, cc, bcc, subject)

    client.sendmail(from_, to + bcc, message)
    client.quit()


def make_lists(to, cc, bcc):
    """Cleanup to, cc and bcc (removes duplicates)."""

    to = set(to or [])
    cc = set(cc or [])
    bcc = set(bcc or [])

    to -= cc | bcc
    cc -= to | bcc
    bcc -= to | cc

    return list(to), list(cc), list(bcc)


def make_message(from_, to, cc, subject, text_body, html_body):
    """Makes email message with text and html bodies."""

    message = multipart.MIMEMultipart("alternative")

    message["Subject"] = subject
    message["To"] = ", ".join(to)
    message["Cc"] = ", ".join(cc)

    text_part = text.MIMEText(text_body, "plain")
    message.attach(text_part)

    if html_body:
        html_part = text.MIMEText(html_body, "html")
        message.attach(html_part)

    return message.as_string()


def make_client(host, port, login, password):
    """Creates SMTP client (supports STARTTLS)."""

    smtp = smtplib.SMTP(host, port)
    smtp.ehlo()

    if smtp.has_extn("STARTTLS"):
        smtp.starttls()
        smtp.ehlo()

    if login and password:
        smtp.login(login, password)

    return smtp
