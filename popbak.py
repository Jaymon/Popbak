# -*- coding: utf-8 -*-
"""
Popbak makes it easy to back up a POP accessible email in box

The email parsing portion of the code is based on code that I got from Larry Bates here:
http://mail.python.org/pipermail/python-list/2004-June/265634.html

author -- Jay Marcyes <jay@marcyes.com>

todo -- this script is like 6 years old now and so there are some naming problems (eg, I used camelCase
    method names, some indents are 2 spaces, others 4) that I need to clean up,
    I went through and fixed some of the issues, but not all, I'm just happy it still works after all this time
"""
from __future__ import unicode_literals, division, print_function, absolute_import
import poplib
import email
from email.parser import Parser
from email.header import decode_header
import os
import sys
import errno
import mimetypes
import re
import time
import datetime
from types import *
import argparse
import logging
import codecs
from distutils import dir_util
from collections import defaultdict


__version__ = "0.4"


is_py2 = (sys.version_info[0] == 2)


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

errlogger = logging.getLogger("{}.err".format(__name__))
if len(errlogger.handlers) == 0:
    errlogger.setLevel(logging.DEBUG)
    errlogger.addHandler(err_handler)



class Echo(object):
    """
    simple class that wraps print, why? so I can handle verbosity levels in one place
    """

    verbosity = 0

    @classmethod
    def stdout(cls, format_msg, *args, **kwargs):
        '''print format_msg to stdout, taking into account verbosity level'''
        if not cls.verbosity: return
        outlogger.info(format_msg.format(*args))

    @classmethod
    def stderr(cls, format_msg, *args, **kwargs):
        '''print format_msg to stderr'''
        errlogger.error(format_msg.format(*args))

    @classmethod
    def err(cls, e):
        '''print an exception message to stderr'''
        errlogger.exception(e)


class ByteString(bytes):
    def __new__(cls, val, encoding="UTF-8"):
        if not encoding:
            encoding = sys.getdefaultencoding()

        if isinstance(val, unicode):
            val = val.encode(encoding)

        instance = super(ByteString, cls).__new__(cls, val)
        instance.encoding = encoding
        return instance

    def unicode(self):
        try:
            return self.decode(self.encoding)
        except UnicodeError:
            pout.v(self.encoding)
            raise

    __unicode__ = unicode

    def __str__(self):
        return self if is_py2 else self.unicode()

    def __bytes__(self):
        return self


class String(unicode):
    def __new__(cls, val, encoding="UTF-8"):
        if not isinstance(val, unicode):
            val = ByteString(val, encoding).unicode()
        return super(String, cls).__new__(cls, val)


class Filepath(str):
    def __new__(cls, basedir, fileroot, ext=""):
        fileroot = cls.sanitize(fileroot)
        fileroot = cls.truncate(fileroot, 123)
        if ext and not ext.startswith("."):
            ext = "." + ext

        s = os.path.join(basedir, fileroot + ext).decode("UTF-8")
        return super(Filepath, cls).__new__(cls, s)

    @classmethod
    def truncate(cls, s, size, postfix=''):
        """similar to a normal string split but it actually will split on a word boundary"""
        if len(s) < size: return s

        ret = s[0:size - len(postfix)]
        ret = ret[:-1].rsplit(None, 1)[0].rstrip()
        return ret + postfix

    @classmethod
    def sanitize(cls, s):
        # make sure the fileroot is filename safe
        #s = s.strip().replace(' ', '_')
        s = s.strip()
        s = re.sub(r'(?u)[^-\w.@]', '', s)
        return s

    def exists(self):
        return os.path.exists(self)


class EmailPart(object):
    def __init__(self, email, content_type, contents, encoding, filename=""):
        '''
        arguments:

        :param messagenum: message number of this message in the Inbox
        :param attachmentnum: attachment number for this attachment
        :param filename: filename for this attachment
        :param contents: attachment's contents
        '''
        self.email = email
        self.content_type = content_type
        self.filename = filename

        if self.filename:
            # don't mess with the contents since this will be treated like a
            # binary file
            self.contents = contents
        else:
            if not encoding:
                encoding = "UTF-8"
            self.contents = String(contents, encoding)

        self.encoding = encoding

    def save(self, basedir, filename=""):
        '''Method to save the contents of an attachment to a file
        arguments:

        :param savepath: string, path where file is to be saved
        :param safefilename: string, optional name (if None will use filename of attachment)
        '''
        if not self.contents: return

        ret = True
        p = self._normalize_path(basedir, filename)
        try:
            if self.filename:
                with open(p, "w+b") as f:
                    f.write(self.contents)

            else:
                with codecs.open(p, mode="w+", encoding=self.encoding) as f:
                    f.write(self.contents)

        except IOError as e:
            Echo.stderr(
                "Could not save {}: IO error({}): {}, moving on...",
                p,
                e.errno,
                e.strerror
            )
            ret = False

        except Exception as e:
            Echo.err(e)
            ret = False

        return ret

    def _normalize_path(self, basedir, filename):
        if filename:
            fileroot, ext = os.path.splitext(filename)

        else:
            if self.filename:
                fileroot, ext = os.path.splitext(self.filename)

            else:
                content_type = self.content_type
                fileroot = self.email.subject
                if content_type.endswith("plain"):
                    ext = ".txt"

                else:
                    ext = mimetypes.guess_extension(self.content_type, False)
                    if not ext:
                        ext = ".txt"

        return Filepath(basedir, fileroot, ext)

    def is_attachment(self):
        return bool(self.filename)


class EmailMsg(object):
    @property
    def raw(self):
        return String(self.msg)

    @property
    def headers(self):
        # TODO -- convert the tuples to a dict?
        for name, value in self.msg.items():
            yield String(name), String(value)

    @property
    def subject(self):
        ret = self.msg.get('Subject', "")
        # https://stackoverflow.com/a/7331577/5006
        ds = decode_header(ret)
        if ds:
            ret, encoding = ds[0]
            ret = String(ret, encoding)

        if not ret:
            ret = "(no subject) {}".format(self.isodate)
        return ret

    @property
    def recipient_addrs(self):
        """return all the recipient email addresses

        https://docs.python.org/3/library/email.util.html#email.utils.getaddresses

        :returns: list, the list of recipients
        """
        tos = self.msg.get_all('to', [])
        ccs = self.msg.get_all('cc', [])
        ccs = self.msg.get_all('bcc', [])
        resent_tos = self.msg.get_all('resent-to', [])
        resent_ccs = self.msg.get_all('resent-cc', [])
        recipient_addrs = email.utils.getaddresses(tos + bccs + ccs + resent_tos + resent_ccs)
        return [String(a[1]) for a in recipient_addrs]

    @property
    def to_addrs(self):
        to_addrs = email.utils.getaddresses(self.msg.get_all('To', []))
        to_addrs = [String(a[1]) for a in to_addrs]
        return to_addrs

    @property
    def from_addr(self):
        from_addr = ""
        from_addrs = email.utils.getaddresses(self.msg.get_all('From', []))
        return String(from_addrs[0][1]) if from_addrs else ""

    @property
    def date(self):
        ret = String(self.msg.get('Date', ""))
        return ret

    @property
    def datetime(self):
        d = self.date
        # https://docs.python.org/3/library/email.util.html#email.utils.parsedate_tz
        t = email.utils.parsedate_tz(d)
        tz_offset = t[9]
        stamp = time.mktime(t[0:9])
        if tz_offset:
            stamp -= tz_offset
        return datetime.datetime.fromtimestamp(stamp)

    @property
    def isodate(self):
        return "{}Z".format(self.datetime.isoformat())

    @property
    def plain(self):
        ret = self.parts["text/plain"]
        return ret[0].contents

    @property
    def html(self):
        ret = self.parts.get("text/html", [])
        if ret:
            ret = ret[0].contents
        return ret

    def __init__(self, messagenum, contents):
        """Encapsulate a pop email message

        :param messagenum: int, basically the count of the message for this particular
            message in the pop connection
        :param contents: tuple, (response, ['mesg_num octets', ...], octets), contents[2]
            is really what you care about, it's the body lines
        """
        self.messagenum = messagenum
        self.contents = contents
        self.parts = defaultdict(list)

        self.msg = Parser().parsestr('\n'.join(String(line) for line in contents[1]))
        if self.msg.is_multipart():
            for part in self.msg.walk():
                # multipart/* are just containers
                mptype=part.get_content_maintype()
                if mptype == "multipart": continue

                # NOTE -- I'm not sure the lower is needed here, but just in case
                content_type = part.get_content_type().lower()
                encoding = part.get_content_charset()
                filename = part.get_filename()
                contents = part.get_payload(decode=1)

                self.parts[content_type].append(EmailPart(
                    email=self,
                    content_type=content_type,
                    contents=contents,
                    encoding=encoding,
                    filename=filename,
                ))

        else: # Not multipart, only body portion exists

            # RFC 2045 defines a message’s default type to be text/plain unless
            # it appears inside a multipart/digest container, in which case it
            # would be message/rfc822
            content_type = self.msg.get_content_type()
            encoding = self.msg.get_content_charset()
            contents = self.msg.get_payload(decode=1)
            self.parts[content_type].append(EmailPart(
                email=self,
                content_type=content_type,
                contents=contents,
                encoding=encoding
            ))

    def attachments(self):
        for ps in self.parts.values():
            for a in ps:
                if a.is_attachment():
                    yield a

    def has_attachments(self):
        attachments = list(self.attachments())
        return len(attachments) > 0

    def save(self, basedir):
        ret = True
        addr_dir = Filepath(basedir, self.from_addr)
        email_dir = Filepath(addr_dir, self.subject)
        # handle duplicates
        if email_dir.exists():
            email_dir = Filepath(addr_dir, self.subject + self.isodate)
        dir_util.mkpath(email_dir)

        for ps in self.parts.values():
            for p in ps:
                ret = ret & p.save(email_dir)

        p = Filepath(email_dir, "headers", ".txt")
        with codecs.open(p, mode="w+", encoding="UTF-8") as f:
            f.write("From:\t{}\n".format(self.from_addr))
            f.write("Recipients:\n\t{}\n".format("\n\t".join(self.recipient_addrs)))
            f.write("Subject:\t{}\n".format(self.subject))
            f.write("Date:\t{}\n\n".format(self.isodate))

            for name, val in self.headers:
                f.write("{}:\t{}\n".format(name, val))

        return ret


class Pop3Inbox(object):
    def __init__(self, server, port, userid, password):
        Echo.stdout(
            "Connecting Pop3Inbox({}, {}, {}, {})".format(server, port, userid, password)
        )

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
        Echo.stdout("msgcount: {}, size: {}", self.msgcount, self.size)

    def close(self):
        if self.connection:
            self.connection.quit()

    def remove(self, *msgnums):
        """if I want to delete the messages, though this is a backup script, so
        why would I want to?"""
        msgnums = map(int, msgnums)
        map(self.connection.dele, msgnums)

    def __iter__(self):
        for msgnum in range(1, self.msgcount + 1):
            msg = EmailMsg(msgnum, self.connection.retr(msgnum))
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
    Echo.verbosity = options.verbosity

    while True:
        Echo.stdout("CONNECTING")

        try:
            inbox = Pop3Inbox(options.server, options.port, options.userid, options.password)

        except Exception as e:
            Echo.err(e)
            sys.exit(2)

        Echo.stdout("Message count={}, Inbox size={}", inbox.msgcount, inbox.size)

        if not inbox.msgcount:
            inbox.close()
            break

        for counter, em in enumerate(inbox, 1):
            total += 1
            Echo.stdout("saving ({}) [{}] {} from {}", total, em.isodate, em.subject, em.from_addr)
            em.save(options.dir)

        inbox.close() # close the connection
        Echo.stdout("Resting for 5 seconds before reconnecting to check for more messages.")
        time.sleep(5)



