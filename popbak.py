# -*- coding: utf-8 -*-
"""
Popbak makes it easy to back up a POP accessible email in box
"""
from __future__ import unicode_literals, division, print_function, absolute_import
import poplib
import sys
import time
import datetime
import argparse
import logging

from datatypes import (
    Email,
    String,
    ByteString,
)


__version__ = "0.5.0"


class Echo(object):
    """simple class that wraps print, why? so I can handle verbosity levels in one place"""
    verbosity = 0

    def __init__(self, verbosity):
        self.verbosity = verbosity

        #logging.basicConfig(format="[%(levelname).1s] %(message)s", level=logging.DEBUG, stream=sys.stdout)
        log_formatter = logging.Formatter('%(message)s')
        out_handler = logging.StreamHandler(stream=sys.stdout)
        out_handler.setFormatter(log_formatter)
        err_handler = logging.StreamHandler(stream=sys.stderr)
        err_handler.setFormatter(log_formatter)

        outlogger = logging.getLogger("{}.out".format(__name__))
        if len(outlogger.handlers) == 0:
            outlogger.setLevel(logging.DEBUG)
            outlogger.addHandler(out_handler)
        self.outlogger = outlogger

        errlogger = logging.getLogger("{}.err".format(__name__))
        if len(errlogger.handlers) == 0:
            errlogger.setLevel(logging.DEBUG)
            errlogger.addHandler(err_handler)
        self.errlogger = errlogger

    def stdout(self, format_msg, *args, **kwargs):
        '''print format_msg to stdout, taking into account verbosity level'''
        if not self.verbosity: return
        self.outlogger.info(format_msg.format(*args))

    def stderr(self, format_msg, *args, **kwargs):
        '''print format_msg to stderr'''
        self.errlogger.error(format_msg.format(*args))

    def err(self, e):
        '''print an exception message to stderr'''
        self.errlogger.exception(e)


class Pop3Inbox(object):
    def __init__(self, server, port, userid, password):
        # See if I can connect using information provided
        try:
            self.connection = poplib.POP3_SSL(server, port)
            self.connection.user(userid)
            self.connection.pass_(password)

        except Exception as e:
            self.close()
            raise

        # Get count of messages and size of mailbox
        self.msgcount, self.size = self.connection.stat()

    def close(self):
        if self.connection:
            self.connection.quit()
        self.connection = None

    def remove(self, *msgnums):
        """if I want to delete the messages, though this is a backup script, so
        why would I want to?"""
        raise NotImplementedError()
        msgnums = map(int, msgnums)
        map(self.connection.dele, msgnums)

    def __iter__(self):
        for msgnum in range(1, self.msgcount + 1):
            msg = self.connection.retr(msgnum)
            contents = '\n'.join(String(line) for line in msg[1])
            msg = Email(contents)
            yield msg


if __name__ == "__main__":
    # http://docs.python.org/library/argparse.html#module-argparse
    parser = argparse.ArgumentParser(description='Easily backup a POP accessible email account')
    parser.add_argument(
        "-u", "--username", "--userid", "--user",
        dest="userid",
        help="Your email username (eg, username@example.com)"
    )
    parser.add_argument(
        "-p", "--password",
        dest="password",
        help="Your email password"
    )
    parser.add_argument(
        "-s", "--server",
        dest="server",
        default="pop.gmail.com",
        help="The server you want to connect to"
    )
    parser.add_argument(
        "-o", "--port",
        dest="port",
        default=995,
        type=int,
        help="The port you want to connect to"
    )
    parser.add_argument(
        "-v", "--verbose",
        dest="verbosity",
        action='count',
        help="the verbosity level, more v's, more output"
    )
    parser.add_argument(
        "-V", "--version",
        action='version',
        version="%(prog)s {}".format(__version__)
    )
    parser.add_argument(
        "-d", "--dir",
        dest="dir",
        default=datetime.date.today(),
        help="the directory to backup to"
    )

    options = parser.parse_args()
    total = 0
    echo = Echo(options.verbosity)
    Echo.verbosity = options.verbosity

    while True:
        try:
            echo.stdout(
                "Connecting Pop3Inbox({}, {}, {}, {})".format(
                    options.server,
                    options.port,
                    options.userid,
                    options.password
                )
            )

            inbox = Pop3Inbox(options.server, options.port, options.userid, options.password)

        except Exception as e:
            echo.err(e)
            sys.exit(2)

        else:
            echo.stdout("Connected! Message count={}, Inbox size={}", inbox.msgcount, inbox.size)

            if not inbox.msgcount:
                inbox.close()
                break

            for counter, em in enumerate(inbox, 1):
                try:
                    total += 1
                    echo.stdout("{}. Saving {} - {}", total, em.from_addr, em.subject_basename)
                    em.save(options.dir)

                except Exception as e:
                    raise

            inbox.close() # close the connection
            echo.stdout("Resting for 5 seconds before reconnecting to check for more messages.")
            time.sleep(5)

