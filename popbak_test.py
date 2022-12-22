# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

import testdata

from popbak import Email
from popbak import Mailbox


class MailboxTest(testdata.TestCase):
    def test_create(self):
        m = Mailbox(b'(\\HasChildren \\Noselect) "/" "[Gmail]"')

    def test_ids(self):
        m = Mailbox(b'() "/" "foo"')
        m.count = 100

        #pout.x(list(m.ids(1000, 5)))

        ids = list(m.ids(1000, 5))
        self.assertEqual(5, ids[0])
        self.assertEqual(100, ids[-1])

        ids = list(m.ids(10, 5))
        self.assertEqual(5, ids[0])
        self.assertEqual(14, ids[-1])

        ids = list(m.ids(0, 1))
        self.assertEqual(1, ids[0])
        self.assertEqual(m.count, ids[-1])

        ids = list(m.ids(0, 0))
        self.assertEqual(1, ids[0])
        self.assertEqual(m.count, ids[-1])

        self.assertEqual([1], list(m.ids(1, 1)))

