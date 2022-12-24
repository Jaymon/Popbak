# -*- coding: utf-8 -*-
"""
Popbak makes it easy to back up an IMAP accessible email in box
"""
from __future__ import unicode_literals, division, print_function, absolute_import
import poplib
import sys
import time
import datetime
import argparse
import logging
from contextlib import contextmanager # https://docs.python.org/3/library/contextlib.html
import imaplib

from datatypes import (
    Email,
    String,
    ByteString,
    Dirpath,
)
from captain import Command, handle, arg, args


__version__ = "0.6.1"


class Mailbox(object):
    """Represents an IMAP mailbox

    list query and response docs:
        * https://www.rfc-editor.org/rfc/rfc3501#section-6.3.8
        * https://www.rfc-editor.org/rfc/rfc3501#section-7.2.2
    """
    @classmethod
    def imap_name(self, name):
        """So I would rather have the name be like NAME but IMAP wants the name to
        be "NAME" (wrapped in double quotes) so this takes the name and wraps it
        so it can be used when making IMAP requests

        :param name: str, the mailbox name
        :returns: str, the name in the format IMAP wants it to make a request
        """
        return f"\"{name}\""

    def __init__(self, raw):
        """
        :param raw: str, string in the form of: ([ATTRIBUTES]) "DELIM" "NAME"
        """
        # via: https://www.rfc-editor.org/rfc/rfc3501#section-7.2.2
        # the list response is: (attributes) "delim" "name"
        raw = String(raw)
        m = raw.regex(r"^\(([^\)]*)\)\s+\"([^\"]*)\"\s+\"([^\"]*)\"$").match()
        self.attributes = set(m.group(1).split(" "))
        self.hierarchy_delim = m.group(2)
        self.name = m.group(3)

        self.count = 0

    def is_selectable(self):
        """Return True if this mailbox can be selected

        https://www.rfc-editor.org/rfc/rfc3501#section-7.2.2

        from the docs:

            Noselect
                It is not possible to use this name as a selectable mailbox.

        :returns: bool
        """
        return "\\Noselect" not in self.attributes

    def ids(self, limit, offset):
        """Given a limit and/or offset return the ids that should be checked for
        this mailbox

        IMAP fetches email by a mail_id, this takes limit and offset and generates
        the list of ids that should be checked

        :param limit: int, at most, how many ids should be generated
        :param offset: int, what id should be the start id
        :returns: generator, all the mail ids between start_id and stop_id
        """
        start_id = offset or 1

        if limit > 0:
            stop_id = offset + limit - 1
        else:
            stop_id = self.count

        if stop_id > self.count:
            stop_id = self.count

        for mail_id in range(start_id, stop_id + 1):
            yield mail_id


class IMAP(object):
    """Makes IMAP requests

    * https://www.rfc-editor.org/rfc/rfc3501
    * https://docs.python.org/3/library/imaplib.html
    * https://coderzcolumn.com/tutorials/python/imaplib-simple-guide-to-manage-mailboxes-using-python
    """
    def __init__(self, server, port, username, password, **kwargs):
        """
        :param server: str, the host/server this IMAP connection should use
        :param port: int, the port on the server to use
        :param username: str, the username connecting to the server
        :param password: str, the password for username
        :param **kwargs: dict, any other things you want to pass
        """
        self.enter_count = 0 # when using context, don't close the connection unless this is 0
        self.connection = None
        try:
            self.connection = imaplib.IMAP4_SSL(host=server, port=port)
            self.connection.login(username, password)

        except Exception:
            self.close()
            raise

    def __enter__(self):
        """Makes this class a context manager so it's easier to cleanup"""
        self.enter_count = max(self.enter_count + 1, 1)
        return self

    def __exit__(self, exception_type, exception_val, trace):
        """clean up when exiting the context of the IMAP connection

        https://docs.python.org/3/reference/datamodel.html#context-managers
            If the method wishes to suppress the exception (i.e., prevent it from
            being propagated), it should return a true value. Otherwise, the exception
            will be processed normally upon exit from this method.
        """
        self.enter_count -= 1
        if self.enter_count <= 0:
            self.close()

    def close(self):
        """Closes and cleans up the connection"""
        if self.connection:
            try:
                self.connection.close()

            except imaplib.IMAP4.error as e:
                # ignore any imap errors since we're trying to close everything
                # out anyway
                pass

            self.connection.logout()

        self.connection = None

    def mailboxes(self, mailbox_names=None):
        """Return username's mailboxes on this IMAP server

        :param mailbox_names: list, the mailboxes you are searching for
        :returns: generator, yields the found mailboxes matching mailbox_names or
            all mailboxes
        """
        with self:
            if mailbox_names:
                mailboxes = []
                for mailbox_name in mailbox_names:
                    resp_code, mbs = self.connection.list(pattern=Mailbox.imap_name(mailbox_name))
                    mailboxes.extend(mbs)

            else:
                resp_code, mailboxes = self.connection.list()

            for mailbox in mailboxes:
                mb = Mailbox(mailbox)
                if mb.is_selectable():
                    yield self.select(mb)

    def select(self, mailbox, readonly=True):
        """Select this mailbox so you can read from it

        https://www.rfc-editor.org/rfc/rfc3501#section-6.3.1

        :param mailbox: Mailbox, the mailbox you want to select, this will update
            the mailbox instance with .count, representing how many messages the
            mailbox has on the server
        :param readonly: bool, True if you don't want to modify the mailbox but
            only read from it
        :returns: Mailbox
        """
        with self:
            resp_code, mail_count = self.connection.select(mailbox=Mailbox.imap_name(mailbox.name), readonly=readonly)
            mailbox.count = int(String(mail_count[0]))
        return mailbox

    def emails(self, mailbox, limit, offset):
        """Retrieve emails for the given mailbox

        :param mailbox: Mailbox, see .mailboxes()
        :param limit: int, see Mailbox.ids()
        :param offset: int, see Mailbox.ids()
        :returns: generator<Email>
        """
        self.select(mailbox)

        with self:
            #resp_code, mail_ids = conn.search(None, "ALL")
            #pout.v(mail_ids)
            for mail_id in mailbox.ids(limit, offset):
                resp_code, mail_data = self.connection.fetch(String(mail_id), '(RFC822)')
                em = Email(mail_data[0][1])
                em.id = mail_id
                yield em


class Mailboxes(Command):
    """Retrieve all username's mailboxes and how many messages those mailboxes contain"""
    @arg(
        "-u", "--username", "--userid", "--user",
        dest="username",
        help="Your email username (eg, username@example.com)",
        group="IMAP Config",
    )
    @arg(
        "-p", "--password",
        dest="password",
        help="Your email password",
        group="IMAP Config",
    )
    @arg(
        "-s", "--server", "--host", "--hostname",
        dest="server",
        default="imap.gmail.com",
        help="The server you want to connect to",
        group="IMAP Config",
    )
    @arg(
        "-o", "--port",
        dest="port",
        default=993,
        type=int,
        help="The port you want to connect to",
        group="IMAP Config",
    )
    @arg(
        "mailboxes",
        metavar="MAILBOX",
        nargs="*",
        dest="mailbox_names",
        help="The mailboxes you would like information on"
    )
    def handle(self, imap_config, mailbox_names):
        with IMAP(imap_config.server, imap_config.port, imap_config.username, imap_config.password) as imap:
            for mb in self.output.increment(imap.mailboxes(mailbox_names)):
                s = "message" if mb.count == 1 else "messages"
                attrs = " ".join(mb.attributes)
                self.output.out(f"{mb.name} - {mb.count} {s} - Attributes: {attrs}")


class Backup(Command):
    """Backup mailboxes to the local filesystem

    Each email will get its own directory with the message bodies and the attachments
    """
    @args(Mailboxes)
    @arg(
        "-d", "--dir",
        dest="basedir",
        default=datetime.date.today(),
        help="the directory to backup to"
    )
    @arg(
        "mailboxes",
        metavar="MAILBOX",
        nargs="+",
        dest="mailbox_names",
        help="The mailboxes you would like to backup"
    )
    @arg(
        "--limit",
        dest="limit",
        default=0,
        type=int,
        help="How many messages you want to backup"
    )
    @arg(
        "--offset",
        dest="offset",
        default=1,
        type=int,
        help="the message id (mail id) you want to start on"
    )
    @arg(
        "--discard-originals",
        dest="save_original",
        action="store_false",
        help="Pass this flag in to discard saving the full original message"
    )
    def handle(self, imap_config, mailbox_names, basedir, limit, offset, save_original):
        mail_info = {}
        try:
            with IMAP(imap_config.server, imap_config.port, imap_config.username, imap_config.password) as imap:
                for mb in imap.mailboxes(mailbox_names):
                    mail_info[mb.name] = 0

                    self.output.out("Backing up mailbox: {}", mb.name)

                    for em in imap.emails(mb, limit, offset):
                        self.output.out(
                            "{}. Saving {} - {} - {}",
                            em.id,
                            em.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                            em.from_addr,
                            em.subject
                        )
                        em.save(Dirpath(basedir, mb.name), save_original=save_original)
                        mail_info[mb.name] = em.id



        except Exception as e:
            self.output.exception(e)

        self.output.out("Last mail_Ids successfully backed up for each mailbox")
        self.output.table(mail_info.items())


if __name__ == "__main__":
    handle()

