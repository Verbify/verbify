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
from pylons import request, response
from pylons import app_globals as g

from v1.controllers.verbify_base import MinimalController
from v1.lib.base import abort
from v1.lib.pages import Robots, CrossDomain
from v1.lib import utils


class RobotsController(MinimalController):
    def pre(self):
        pass

    def post(self):
        pass

    def on_crawlable_domain(self):
        # This ensures we don't have the port included.
        requested_domain = utils.domain(request.host)

        # If someone CNAMEs myspammysite.com to verbify.com or something, we
        # don't want search engines to index that.
        if not utils.is_subdomain(requested_domain, g.domain):
            return False

        # Only allow the canonical desktop site and mobile subdomains, since
        # we have canonicalization set up appropriately for them.
        # Note: in development, DomainMiddleware needs to be temporarily
        # modified to not skip assignment of verbify-domain-extension on
        # localhost for this to work properly.
        return (requested_domain == g.domain or
                request.environ.get('verbify-domain-extension') in
                    ('mobile', 'compact'))

    def GET_robots(self):
        response.content_type = "text/plain"
        if self.on_crawlable_domain():
            return Robots().render(style='txt')
        else:
            return "User-Agent: *\nDisallow: /\n"

    def GET_crossdomain(self):
        # Our middleware is weird and won't let us add a route for just
        # '/crossdomain.xml'. Just 404 for other extensions.
        if request.environ.get('extension', None) != 'xml':
            abort(404)
        response.content_type = "text/x-cross-domain-policy"
        return CrossDomain().render(style='xml')
