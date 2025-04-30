# -*- coding: utf-8 -*-
"""
Popbak makes it easy to back up an IMAP accessible email in box
"""
from contextlib import contextmanager # https://docs.python.org/3/library/contextlib.html
import imaplib
import re

from datatypes import (
    Email,
    String,
    Dirpath,
    Datetime,
)
from captain import Command, application, arg, args


__version__ = "0.7.0"


class Mailbox(object):
    """Represents an IMAP mailbox

    list query and response docs:
        * https://www.rfc-editor.org/rfc/rfc3501#section-6.3.8
        * https://www.rfc-editor.org/rfc/rfc3501#section-7.2.2
    """
    @classmethod
    def imap_name(self, name):
        """So I would rather have the name be like NAME but IMAP wants the
        name to be "NAME" (wrapped in double quotes) so this takes the name
        and wraps it so it can be used when making IMAP requests

        :param name: str, the mailbox name
        :returns: str, the name in the format IMAP wants it to make a request
        """
        return f"\"{name}\""

    def __init__(self, imap, raw):
        """
        :param raw: str, string in the form of: ([ATTRIBUTES]) "DELIM" "NAME"
        """
        self.imap = imap

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

    def select(self, readonly=True):
        """Select this mailbox so you can read from it

        https://www.rfc-editor.org/rfc/rfc3501#section-6.3.1

        :param readonly: bool, True if you don't want to modify the mailbox
            but only read from it
        :returns: Mailbox
        """
        if not self.imap.is_selected(self):
            with self.imap:
                resp_code, mail_count = self.imap.connection.select(
                    mailbox=Mailbox.imap_name(self.name),
                    readonly=readonly
                )
                self.count = int(String(mail_count[0]))
                self.imap.selected_mailbox = self

    def get_ids(self, limit, offset):
        """Internal method. Given a limit and/or offset return the get_ids
        that should be checked for this mailbox

        IMAP fetches email by a mail_id, this takes limit and offset and
        generates the list of ids that should be checked

        :param limit: int, at most, how many ids should be generated
        :param offset: int, what id should be the start id
        :returns: generator[int], all the mail ids between start_id
            and stop_id
        """
        start_id = max(offset, 1)

        if limit > 0:
            stop_id = offset + limit - 1

        else:
            stop_id = self.count

        if stop_id > self.count:
            stop_id = self.count

        for mail_id in range(start_id, stop_id + 1):
            yield mail_id

    def find_id_since(self, dt):
        """Use a binary search to find the first id after the date and time

        :param dt: Datetime
        :returns: int
        """
        with self.imap:
            self.select()

            low_id = 1
            high_id = self.count
            mid_id = low_id

            while low_id <= high_id:
                mid_id = (low_id + high_id) // 2
                em = self.get_email(mid_id)

                if em.datetime > dt:
                    high_id = mid_id - 1

                else:
                    low_id = mid_id + 1

            return low_id

    def get_emails(self, limit, offset):
        """Retrieve emails for the given mailbox

        :param mailbox: Mailbox, see .get_mailboxes()
        :param limit: int, see Mailbox.get_ids()
        :param offset: int, see Mailbox.get_ids()
        :returns: generator[Email]
        """
        with self.imap:
            for mail_id in self.get_ids(limit, offset):
                yield self.get_email(mail_id)

    def get_email(self, mail_id):
        """Get the specific email at id `mail_id`

        :param mail_id: int
        :returns: Email
        """
        with self.imap:
            self.select()

            resp_code, mail_data = self.imap.connection.fetch(
                String(mail_id),
                "(RFC822)"
            )
            em = Email(mail_data[0][1], errors="ignore")
            em.id = mail_id
            return em


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
        # when using context, don't close the connection unless this is 0
        self.enter_count = 0
        self.connection = None
        self.selected_mailbox = None

        self.server = server
        self.port = port
        self.username = username
        self.password = password

    def __enter__(self):
        """Makes this class a context manager so it's easier to cleanup"""
        self.connect()
        self.enter_count += 1
        return self

    def __exit__(self, exception_type, exception_val, trace):
        """clean up when exiting the context of the IMAP connection

        https://docs.python.org/3/reference/datamodel.html#context-managers
            If the method wishes to suppress the exception (i.e., prevent it
            from being propagated), it should return a true value. Otherwise,
            the exception will be processed normally upon exit from
            this method.
        """
        self.enter_count -= 1
        if self.enter_count <= 0:
            self.close()

    def connect(self):
        if not self.connection:
            self.enter_count = 0

            self.connection = imaplib.IMAP4_SSL(
                host=self.server,
                port=self.port
            )

            self.connection.login(self.username, self.password)

    def close(self):
        """Closes and cleans up the connection"""
        if self.connection:
            try:
                self.connection.close()

            except imaplib.IMAP4.error as e:
                # ignore any imap errors since we're trying to close
                # everything out anyway
                pass

            self.connection.logout()

        self.enter_count = 0
        self.connection = None

    def is_selected(self, mailbox):
        """Return True if mailbox is currently selected"""
        if self.selected_mailbox:
            return self.selected_mailbox.name == mailbox.name

        return False

    def get_mailboxes(self, mailbox_names=None):
        """Return username's mailboxes on this IMAP server

        :param mailbox_names: list, the mailboxes you are searching for
        :returns: generator, yields the found mailboxes matching mailbox_names
            or all mailboxes
        """
        with self:
            if mailbox_names:
                mailboxes = []
                for mailbox_name in mailbox_names:
                    resp_code, mbs = self.connection.list(
                        pattern=Mailbox.imap_name(mailbox_name)
                    )
                    mailboxes.extend(mbs)

            else:
                resp_code, mailboxes = self.connection.list()

            for mailbox in mailboxes:
                mb = Mailbox(self, mailbox)
                if mb.is_selectable():
                    mb.select()
                    yield mb


class Mailboxes(Command):
    """Retrieve all username's mailboxes and how many messages those mailboxes
    contain"""
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
        "mailbox_names",
        metavar="MAILBOX",
        nargs="*",
        help="The mailboxes you would like information on"
    )
    def handle(self, imap_config, mailbox_names):
        imap = IMAP(
            imap_config.server,
            imap_config.port,
            imap_config.username,
            imap_config.password
        )
        with imap:
            for mb in self.output.increment(imap.get_mailboxes(mailbox_names)):
                s = "message" if mb.count == 1 else "messages"
                attrs = " ".join(mb.attributes)
                self.output.out(
                    f"{mb.name} - {mb.count} {s} - Attributes: {attrs}"
                )


class Sync(Command):
    """Sync mailboxes to the local filesystem

    Each email will get its own directory with the message bodies and the
    attachments
    """
    def find_dt(self, basedir):
        dt = None
        sentinel = basedir.get_file(".popbak")
        if sentinel.exists():
            dt = Datetime(sentinel.read_text().strip())
            self.output.out("Found datetime {} in {}", dt, sentinel)

        else:
            dt = None
            for fp in basedir.iterator.pattern("headers.txt"):
                m = re.search(
                    r"Date:\s+(\d+-\d+-\d+T\d+:\d+:\d+Z)",
                    fp.read_text()
                )

                if m:
                    mdt = Datetime(m.group(1))
                    if dt is None or mdt > dt:
                        dt = mdt

            if dt:
                self.output.out("Found datetime {} using headers", dt)

        return dt

    @args(Mailboxes)
    @arg(
        "-d", "--dir",
        dest="basedir",
        default=Datetime.today().date(),
        help="the directory to backup to"
    )
    def handle(self, imap_config, basedir, mailbox_names):
        imap = IMAP(
            imap_config.server,
            imap_config.port,
            imap_config.username,
            imap_config.password
        )
        with imap:
            for mb in self.output.increment(imap.get_mailboxes(mailbox_names)):
                s = "message" if mb.count == 1 else "messages"
                self.output.out(
                    f"Syncing {mb.name} with {mb.count} {s}"
                )

                mb_basedir = Dirpath(basedir, mb.name)
                offset = 0

                dt = self.find_dt(mb_basedir)
                if dt:
                    self.output.out("Mailbox {} last synced {}", mb.name, dt)
                    offset = mb.find_id_since(dt)

                else:
                    self.output.out("Mailbox {} is new", mb.name)

                for em in mb.get_emails(0, offset):
                    self.output.out(
                        "{}/{}. Saving {} - {} - {}",
                        em.id,
                        mb.count,
                        em.datestamp("%Y-%m-%d %H:%M:%S"),
                        em.from_addr,
                        em.subject
                    )
                    em.save(mb_basedir, save_original=True)

                    fp = mb_basedir.get_file(".popbak")
                    fp.write_text(str(em.datetime))


class Backup(Command):
    """Backup mailboxes to the local filesystem

    Each email will get its own directory with the message bodies and the
    attachments
    """
    @args(Sync)
    @arg(
        "mailbox_names",
        metavar="MAILBOX",
        nargs="+",
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
        default=0,
        type=int,
        help="the message id (mail id) you want to start on"
    )
    @arg(
        "--since",
        dest="dt",
        type=Datetime,
        help="The ISO8601 datestamp that messages should be after"
    )
    @arg(
        "--discard-originals",
        dest="save_original",
        action="store_false",
        help="Pass this flag in to discard saving the full original message"
    )
    def handle(
        self,
        imap_config,
        mailbox_names,
        basedir,
        limit,
        offset,
        dt,
        save_original
    ):
        mail_info = {}

        try:
            imap = IMAP(
                imap_config.server,
                imap_config.port,
                imap_config.username,
                imap_config.password
            )
            with imap:
                for mb in imap.get_mailboxes(mailbox_names):
                    mail_info[mb.name] = 0

                    if dt:
                        self.output.out(
                            "Backing up mailbox: {} from {}",
                            mb.name,
                            dt,
                        )

                        offset = mb.find_id_since(dt) + offset

                    else:
                        self.output.out("Backing up mailbox: {}", mb.name)

                    for em in mb.get_emails(limit, offset):
                        self.output.out(
                            "{}. Saving {} - {} - {}",
                            em.id,
                            em.datestamp("%Y-%m-%d %H:%M:%S"),
                            em.from_addr,
                            em.subject
                        )
                        em.save(
                            Dirpath(basedir, mb.name),
                            save_original=save_original
                        )
                        mail_info[mb.name] = em.id

        except Exception as e:
            self.output.exception(e)

        self.output.out(
            "Last mail_ids successfully backed up for each mailbox"
        )
        self.output.table(mail_info.items())


if __name__ == "__main__":
    application()

