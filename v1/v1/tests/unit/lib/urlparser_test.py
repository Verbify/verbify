#!/usr/bin/env python
# coding=utf-8
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

from v1.lib.utils import UrlParser
from v1.tests import VerbifyTestCase
from pylons import app_globals as g


class TestIsVerbifyURL(VerbifyTestCase):

    def setUp(self):
        self.patch_g(offsite_subdomains=['blog'])

    def _is_safe_verbify_url(self, url, subverbify=None):
        web_safe = UrlParser(url).is_web_safe_url()
        return web_safe and UrlParser(url).is_verbify_url(subverbify)

    def assertIsSafeVerbifyUrl(self, url, subverbify=None):
        self.assertTrue(self._is_safe_verbify_url(url, subverbify))

    def assertIsNotSafeVerbifyUrl(self, url, subverbify=None):
        self.assertFalse(self._is_safe_verbify_url(url, subverbify))

    def test_normal_urls(self):
        self.assertIsSafeVerbifyUrl("https://%s/" % g.domain)
        self.assertIsSafeVerbifyUrl("https://en.%s/" % g.domain)
        self.assertIsSafeVerbifyUrl("https://foobar.baz.%s/quux/?a" % g.domain)
        self.assertIsSafeVerbifyUrl("#anchorage")
        self.assertIsSafeVerbifyUrl("?path_relative_queries")
        self.assertIsSafeVerbifyUrl("/")
        self.assertIsSafeVerbifyUrl("/cats")
        self.assertIsSafeVerbifyUrl("/cats/")
        self.assertIsSafeVerbifyUrl("/cats/#maru")
        self.assertIsSafeVerbifyUrl("//foobaz.%s/aa/baz#quux" % g.domain)
        # XXX: This is technically a legal relative URL, are there any UAs
        # stupid enough to treat this as absolute?
        self.assertIsSafeVerbifyUrl("path_relative_subpath.com")
        # "blog.verbify.com" is not a verbify URL.
        self.assertIsNotSafeVerbifyUrl("http://blog.%s/" % g.domain)
        self.assertIsNotSafeVerbifyUrl("http://foo.blog.%s/" % g.domain)

    def test_incorrect_anchoring(self):
        self.assertIsNotSafeVerbifyUrl("http://www.%s.whatever.com/" % g.domain)

    def test_protocol_relative(self):
        self.assertIsNotSafeVerbifyUrl("//foobaz.example.com/aa/baz#quux")

    def test_weird_protocols(self):
        self.assertIsNotSafeVerbifyUrl(
            "javascript://%s/%%0d%%0aalert(1)" % g.domain
        )
        self.assertIsNotSafeVerbifyUrl("hackery:whatever")

    def test_http_auth(self):
        # There's no legitimate reason to include HTTP auth details in the URL,
        # they only serve to confuse everyone involved.
        # For example, this used to be the behaviour of `UrlParser`, oops!
        # > UrlParser("http://everyoneforgets:aboutthese@/baz.com/").unparse()
        # 'http:///baz.com/'
        self.assertIsNotSafeVerbifyUrl("http://foo:bar@/example.com/")

    def test_browser_quirks(self):
        # Some browsers try to be helpful and ignore characters in URLs that
        # they think might have been accidental (I guess due to things like:
        # `<a href=" http://badathtml.com/ ">`. We need to ignore those when
        # determining if a URL is local.
        self.assertIsNotSafeVerbifyUrl("/\x00/example.com")
        self.assertIsNotSafeVerbifyUrl("\x09//example.com")
        self.assertIsNotSafeVerbifyUrl(" http://example.com/")

        # This is makes sure we're not vulnerable to a bug in
        # urlparse / urlunparse.
        # urlunparse(urlparse("////foo.com")) == "//foo.com"! screwy!
        self.assertIsNotSafeVerbifyUrl("////example.com/")
        self.assertIsNotSafeVerbifyUrl("//////example.com/")
        # Similar, but with a scheme
        self.assertIsNotSafeVerbifyUrl(r"http:///example.com/")
        # Webkit and co like to treat backslashes as equivalent to slashes in
        # different places, maybe to make OCD Windows users happy.
        self.assertIsNotSafeVerbifyUrl(r"/\example.com/")
        # On chrome this goes to example.com, not a subdomain of verbify.com!
        self.assertIsNotSafeVerbifyUrl(
            r"http://\\example.com\a.%s/foo" % g.domain
        )

        # Combo attacks!
        self.assertIsNotSafeVerbifyUrl(r"///\example.com/")
        self.assertIsNotSafeVerbifyUrl(r"\\example.com")
        self.assertIsNotSafeVerbifyUrl("/\x00//\\example.com/")
        self.assertIsNotSafeVerbifyUrl(
            "\x09javascript://%s/%%0d%%0aalert(1)" % g.domain
        )
        self.assertIsNotSafeVerbifyUrl(
            "http://\x09example.com\\%s/foo" % g.domain
        )

    def test_url_mutation(self):
        u = UrlParser("http://example.com/")
        u.hostname = g.domain
        self.assertTrue(u.is_verbify_url())

        u = UrlParser("http://%s/" % g.domain)
        u.hostname = "example.com"
        self.assertFalse(u.is_verbify_url())

    def test_nbsp_allowances(self):
        # We have to allow nbsps in URLs, let's just allow them where they can't
        # do any damage.
        self.assertIsNotSafeVerbifyUrl("http://\xa0.%s/" % g.domain)
        self.assertIsNotSafeVerbifyUrl("\xa0http://%s/" % g.domain)
        self.assertIsSafeVerbifyUrl("http://%s/\xa0" % g.domain)
        self.assertIsSafeVerbifyUrl("/foo/bar/\xa0baz")
        # Make sure this works if the URL is unicode
        self.assertIsNotSafeVerbifyUrl(u"http://\xa0.%s/" % g.domain)
        self.assertIsNotSafeVerbifyUrl(u"\xa0http://%s/" % g.domain)
        self.assertIsSafeVerbifyUrl(u"http://%s/\xa0" % g.domain)
        self.assertIsSafeVerbifyUrl(u"/foo/bar/\xa0baz")


class TestSwitchSubdomainByExtension(VerbifyTestCase):
    def setUp(self):
        self.patch_g(
            domain='verbify.com',
            domain_prefix='www',
        )

    def test_normal_urls(self):
        u = UrlParser('http://www.verbify.com/r/verbifydev')
        u.switch_subdomain_by_extension('compact')
        result = u.unparse()
        self.assertEquals('http://i.verbify.com/r/verbifydev', result)

        u = UrlParser(result)
        u.switch_subdomain_by_extension('mobile')
        result = u.unparse()
        self.assertEquals('http://simple.verbify.com/r/verbifydev', result)

    def test_default_prefix(self):
        u = UrlParser('http://i.verbify.com/r/verbifydev')
        u.switch_subdomain_by_extension()
        self.assertEquals('http://www.verbify.com/r/verbifydev', u.unparse())

        u = UrlParser('http://i.verbify.com/r/verbifydev')
        u.switch_subdomain_by_extension('does-not-exist')
        self.assertEquals('http://www.verbify.com/r/verbifydev', u.unparse())


class TestPathExtension(unittest.TestCase):
    def test_no_path(self):
        u = UrlParser('http://example.com')
        self.assertEquals('', u.path_extension())

    def test_directory(self):
        u = UrlParser('http://example.com/')
        self.assertEquals('', u.path_extension())

        u = UrlParser('http://example.com/foo/')
        self.assertEquals('', u.path_extension())

    def test_no_extension(self):
        u = UrlParser('http://example.com/a')
        self.assertEquals('', u.path_extension())

    def test_root_file(self):
        u = UrlParser('http://example.com/a.jpg')
        self.assertEquals('jpg', u.path_extension())

    def test_nested_file(self):
        u = UrlParser('http://example.com/foo/a.jpg')
        self.assertEquals('jpg', u.path_extension())

    def test_empty_extension(self):
        u = UrlParser('http://example.com/a.')
        self.assertEquals('', u.path_extension())

    def test_two_extensions(self):
        u = UrlParser('http://example.com/a.jpg.exe')
        self.assertEquals('exe', u.path_extension())

    def test_only_extension(self):
        u = UrlParser('http://example.com/.bashrc')
        self.assertEquals('bashrc', u.path_extension())


class TestEquality(unittest.TestCase):
    def test_different_objects(self):
        u = UrlParser('http://example.com')
        self.assertNotEquals(u, None)

    def test_different_protocols(self):
        u = UrlParser('http://example.com')
        u2 = UrlParser('https://example.com')
        self.assertNotEquals(u, u2)

    def test_different_domains(self):
        u = UrlParser('http://example.com')
        u2 = UrlParser('http://example.org')
        self.assertNotEquals(u, u2)

    def test_different_ports(self):
        u = UrlParser('http://example.com')
        u2 = UrlParser('http://example.com:8000')
        u3 = UrlParser('http://example.com:8008')
        self.assertNotEquals(u, u2)
        self.assertNotEquals(u2, u3)

    def test_different_paths(self):
        u = UrlParser('http://example.com')
        u2 = UrlParser('http://example.com/a')
        u3 = UrlParser('http://example.com/b')
        self.assertNotEquals(u, u2)
        self.assertNotEquals(u2, u3)

    def test_different_params(self):
        u = UrlParser('http://example.com/')
        u2 = UrlParser('http://example.com/;foo')
        u3 = UrlParser('http://example.com/;bar')
        self.assertNotEquals(u, u2)
        self.assertNotEquals(u2, u3)

    def test_different_queries(self):
        u = UrlParser('http://example.com/')
        u2 = UrlParser('http://example.com/?foo')
        u3 = UrlParser('http://example.com/?foo=bar')
        self.assertNotEquals(u, u2)
        self.assertNotEquals(u2, u3)

    def test_different_fragments(self):
        u = UrlParser('http://example.com/')
        u2 = UrlParser('http://example.com/#foo')
        u3 = UrlParser('http://example.com/#bar')
        self.assertNotEquals(u, u2)
        self.assertNotEquals(u2, u3)

    def test_same_url(self):
        u = UrlParser('http://example.com:8000/a;b?foo=bar&bar=baz#spam')
        u2 = UrlParser('http://example.com:8000/a;b?bar=baz&foo=bar#spam')
        self.assertEquals(u, u2)

        u3 = UrlParser('')
        u3.scheme = 'http'
        u3.hostname = 'example.com'
        u3.port = 8000
        u3.path = '/a'
        u3.params = 'b'
        u3.update_query(foo='bar', bar='baz')
        u3.fragment = 'spam'
        self.assertEquals(u, u3)

    def test_integer_query_params(self):
        u = UrlParser('http://example.com/?page=1234')
        u2 = UrlParser('http://example.com/')
        u2.update_query(page=1234)
        self.assertEquals(u, u2)

    def test_unicode_query_params(self):
        u = UrlParser(u'http://example.com/?page=ｕｎｉｃｏｄｅ：（')
        u2 = UrlParser('http://example.com/')
        u2.update_query(page=u'ｕｎｉｃｏｄｅ：（')
        self.assertEquals(u, u2)
