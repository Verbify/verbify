#!/usr/bin/env python
# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.verbify.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is verbify.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is verbify Inc.
#
# All portions of the code written by verbify are Copyright (c) 2006-2015 verbify
# Inc. All Rights Reserved.
###############################################################################

import unittest

from mock import patch

from v1.lib.media import _get_scrape_url
from v1.models import Link

class TestGetScrapeUrl(unittest.TestCase):
    @patch('v1.lib.media.Link')
    def test_link_post(self, Link):
        post = Link()
        post.url = 'https://example.com'
        post.is_self = False
        url = _get_scrape_url(post)
        self.assertEqual(url, 'https://example.com')

    def test_simple_self_post(self):
        post = Link(is_self=True, selftext='''
Some text here.
https://example.com
https://verbify.com''')
        url = _get_scrape_url(post)
        self.assertEqual(url, 'https://example.com')

    def test_imgur_link(self):
        post = Link(is_self=True, selftext='''
Some text here.
https://example.com
https://imgur.com''')
        url = _get_scrape_url(post)
        self.assertEqual(url, 'https://imgur.com')

    def test_image_link(self):
        post = Link(is_self=True, selftext='''
Some text here.
https://example.com
https://verbify.com/a.jpg''')
        url = _get_scrape_url(post)
        self.assertEqual(url, 'https://verbify.com/a.jpg')

        post = Link(is_self=True, selftext='''
Some text here.
https://example.com
https://verbify.com/a.PNG''')
        url = _get_scrape_url(post)
        self.assertEqual(url, 'https://verbify.com/a.PNG')

        post = Link(is_self=True, selftext='''
Some text here.
https://example.com
https://verbify.com/a.jpg/b''')
        url = _get_scrape_url(post)
        self.assertEqual(url, 'https://example.com')
