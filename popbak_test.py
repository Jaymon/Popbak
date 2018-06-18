# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

import testdata

from popbak import EmailMsg, ByteString


class TestCase(testdata.TestCase):
    def get_email(self, fileroot):
        body = testdata.get_contents(fileroot)
        lines = body.splitlines(False)
        contents = (b'+OK message follows', [ByteString(l) for l in lines], len(lines))
        return EmailMsg(1, contents)


class EmailMsgTest(TestCase):
    def test_parse_multipart(self):
        em = self.get_email("emoji-html-attachment")

        self.assertTrue(em.has_attachments())
        self.assertEqual(1, len(list(em.attachments())))
        self.assertEqual("foo@example.com", em.from_addr)

        emoji = b'\xf0\x9f\x98\x82\xf0\x9f\x98\x8e\xf0\x9f\x91\x8d'
        self.assertTrue(emoji in em.plain)
        self.assertTrue(emoji in em.html)

    def test_parse_simple(self):
        em = self.get_email("simple-text")

        self.assertFalse(em.has_attachments())
        self.assertEqual("", em.html)

        shrug = b'\xc2\xaf\\_(\xe3\x83\x84)_/\xc2\xaf'
        self.assertTrue(shrug in em.plain)

    def test_parse_subject_multi_to(self):
        em = self.get_email("no-subject")
        self.assertEqual(2, len(em.to_addrs))
        self.assertTrue("(no subject)" in em.subject)

    def test_parse_cc(self):
        em = self.get_email("cc")
        self.assertEqual("foo@example.com", em.from_addr)

    def test_save(self):
        basedir = testdata.create_dir()
        em = self.get_email("emoji-html-attachment")
        em.save(basedir)
        pout.v(basedir)

        em = self.get_email("cc")
        em.save(basedir)

        em = self.get_email("no-subject")
        em.save(basedir)

        em = self.get_email("simple-text")
        em.save(basedir)

    def test_bad_subject(self):
        em = self.get_email("bad-1")
        self.assertEqual(
            "PitchBook PE & VC News: Changing Course — PE Pivots Away from B2C Education, Toward B2B",
            em.subject
        )

    def test_bad_2(self):
        basedir = testdata.create_dir()
        em = self.get_email("bad-2")
        em.save(basedir)
        pout.v(basedir)

        email_dir = basedir.children[0].children[0]
        email_dir = basedir.first_dir().first_dir()
        email_dir = basedir.child_dir().child_dir()
        self.assertEqual(5, len(email_dir.files))


        pout.v(em.recipient_addrs)

