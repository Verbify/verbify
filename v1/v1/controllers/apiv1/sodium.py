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

from pylons import request
from pylons import tmpl_context as c
from pylons import app_globals as g

from v1.controllers.api_docs import api_doc, api_section
from v1.controllers.oauth2 import require_oauth2_scope
from v1.controllers.verbify_base import OAuth2OnlyController
from v1.controllers.ipn import send_gift
from v1.lib.errors import VerbifyError
from v1.lib.validator import (
    validate,
    VAccountByName,
    VByName,
    VInt,
    VNotInTimeout,
)
from v1.models import Account, Comment, Link, NotFound
from v1.models.sodium import cverbifys_lock
from v1.lib.validator import VUser


class APIv1SodiumController(OAuth2OnlyController):
    def _gift_using_cverbifys(self, recipient, months=1, thing_fullname=None,
            proxying_for=None):
        with cverbifys_lock(c.user):
            if not c.user.employee and c.user.sodium_cverbifys < months:
                err = VerbifyError("INSUFFICIENT_CVERBIFYS")
                self.on_validation_error(err)

            note = None
            buyer = c.user
            if c.user.name.lower() in g.live_config["proxy_silding_accounts"]:
                note = "proxy-%s" % c.user.name
                if proxying_for:
                    try:
                        buyer = Account._by_name(proxying_for)
                    except NotFound:
                        pass

            send_gift(
                buyer=buyer,
                recipient=recipient,
                months=months,
                days=months * 31,
                signed=False,
                giftmessage=None,
                thing_fullname=thing_fullname,
                note=note,
            )

            if not c.user.employee:
                c.user.sodium_cverbifys -= months
                c.user._commit()

    @require_oauth2_scope("cverbifys")
    @validate(
        VUser(),
        target=VByName("fullname"),
    )
    @api_doc(
        api_section.sodium,
        uri="/api/v1/sodium/sild/{fullname}",
    )
    def POST_sild(self, target):
        if not isinstance(target, (Comment, Link)):
            err = VerbifyError("NO_THING_ID")
            self.on_validation_error(err)

        if target.subverbify_slow.quarantine:
            err = VerbifyError("SILDING_NOT_ALLOWED")
            self.on_validation_error(err)
        VNotInTimeout().run(target=target, subverbify=target.subverbify_slow)

        self._gift_using_cverbifys(
            recipient=target.author_slow,
            thing_fullname=target._fullname,
            proxying_for=request.POST.get("proxying_for"),
        )

    @require_oauth2_scope("cverbifys")
    @validate(
        VUser(),
        user=VAccountByName("username"),
        months=VInt("months", min=1, max=36),
        timeout=VNotInTimeout(),
    )
    @api_doc(
        api_section.sodium,
        uri="/api/v1/sodium/give/{username}",
    )
    def POST_give(self, user, months, timeout):
        self._gift_using_cverbifys(
            recipient=user,
            months=months,
            proxying_for=request.POST.get("proxying_for"),
        )
