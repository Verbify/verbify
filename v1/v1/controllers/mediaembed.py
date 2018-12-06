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

import hashlib
import hmac

from pylons import request
from pylons import tmpl_context as c
from pylons import app_globals as g
from pylons.controllers.util import abort

from v1.controllers.verbify_base import MinimalController
from v1.lib.pages import MediaEmbedBody
from v1.lib.media import get_media_embed
from v1.lib.utils import constant_time_compare
from v1.lib.validator import validate, VLink, nop
from v1.models import Subverbify


class MediaembedController(MinimalController):
    @validate(
        link=VLink('link'),
        credentials=nop('credentials'),
    )
    def GET_mediaembed(self, link, credentials):
        if request.host != g.media_domain:
            # don't serve up untrusted content except on our
            # specifically untrusted domain
            abort(404)

        if link.subverbify_slow.type in Subverbify.private_types:
            expected_mac = hmac.new(g.secrets["media_embed"], link._id36,
                                    hashlib.sha1).hexdigest()
            if not constant_time_compare(credentials or "", expected_mac):
                abort(404)

        if not c.secure:
            media_object = link.media_object
        else:
            media_object = link.secure_media_object

        if not media_object:
            abort(404)
        elif isinstance(media_object, dict):
            # otherwise it's the new style, which is a dict(type=type, **args)
            media_embed = get_media_embed(media_object)
            content = media_embed.content

        c.allow_framing = True

        return MediaEmbedBody(body = content).render()


class AdController(MinimalController):
    def GET_ad(self):
        return "This is a placeholder ad."
