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
from v1.tests import VerbifyControllerTestCase
from v1.lib.errors import error_list
from v1.lib.unicode import _force_unicode
from v1.models import Subverbify
from common import LoginRegBase


class PostLoginRegTests(LoginRegBase, VerbifyControllerTestCase):
    CONTROLLER = "post"
    ACTIONS = {
        "register": "reg",
    }

    def setUp(self):
        super(PostLoginRegTests, self).setUp()
        self.autopatch(Subverbify, "_byID", return_value=[])
        self.dest = "/foo"

    def assert_success(self, res):
        # On sucess, we redirect the user to the provided "dest" parameter
        # that has been added in make_qs
        self.assertEqual(res.status, 302)
        self.assert_headers(
            res,
            "Location",
            lambda value: value.endswith(self.dest)
        )
        self.assert_headers(
            res,
            "Set-Cookie",
            lambda value: value.startswith("verbify_session=")
        )

    def assert_failure(self, res, code=None):
        # counterintuitively, failure to login will return a 200
        # (compared to a redirect).
        self.assertEqual(res.status, 200)
        # recaptcha is done entirely in JS
        if code != "BAD_CAPTCHA":
            self.assertTrue(error_list[code] in _force_unicode(res.body))

    def make_qs(self, **kw):
        kw['dest'] = self.dest
        return super(PostLoginRegTests, self).make_qs(**kw)
