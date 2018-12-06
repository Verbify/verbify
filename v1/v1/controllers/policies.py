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

from pylons import tmpl_context as c
from pylons import app_globals as g
from pylons.i18n import _
from BeautifulSoup import BeautifulSoup, Tag

from v1.lib.base import abort
from v1.controllers.verbify_base import VerbifyController
from v1.models.subverbify import Frontpage
from v1.models.wiki import WikiPage, WikiRevision, WikiBadRevision
from v1.lib.db import tdb_cassandra
from v1.lib.filters import unsafe, wikimarkdown, generate_table_of_contents
from v1.lib.validator import validate, nop
from v1.lib.pages import PolicyPage, PolicyView


class PoliciesController(VerbifyController):
    @validate(requested_rev=nop('v'))
    def GET_policy_page(self, page, requested_rev):
        if c.render_style == 'compact':
            self.redirect('/wiki/' + page)
        if page == 'privacypolicy':
            wiki_name = g.wiki_page_privacy_policy
            pagename = _('privacy policy')
        elif page == 'useragreement':
            wiki_name = g.wiki_page_user_agreement
            pagename = _('user agreement')
        elif page == 'contentpolicy':
            wiki_name = g.wiki_page_content_policy
            pagename = _('content policy')
        else:
            abort(404)

        wp = WikiPage.get(Frontpage, wiki_name)

        revs = list(wp.get_revisions())

        # collapse minor edits into revisions with reasons
        rev_info = []
        last_edit = None
        for rev in revs:
            if rev.is_hidden:
                continue

            if not last_edit:
                last_edit = rev

            if rev._get('reason'):
                rev_info.append({
                    'id': str(last_edit._id),
                    'title': rev._get('reason'),
                })
                last_edit = None

        if requested_rev:
            try:
                display_rev = WikiRevision.get(requested_rev, wp._id)
            except (tdb_cassandra.NotFound, WikiBadRevision):
                abort(404)
        else:
            display_rev = revs[0]

        doc_html = wikimarkdown(display_rev.content, include_toc=False)
        soup = BeautifulSoup(doc_html.decode('utf-8'))
        toc = generate_table_of_contents(soup, prefix='section')
        self._number_sections(soup)
        self._linkify_headings(soup)

        content = PolicyView(
            body_html=unsafe(soup),
            toc_html=unsafe(toc),
            revs=rev_info,
            display_rev=str(display_rev._id),
        )
        return PolicyPage(
            pagename=pagename,
            content=content,
        ).render()

    def _number_sections(self, soup):
        count = 1
        for para in soup.find('div', 'md').findAll(['p'], recursive=False):
            a = Tag(soup, 'a', [
                ('class', 'p-anchor'),
                ('id', 'p_%d' % count),
                ('href', '#p_%d' % count),
            ])
            a.append(str(count))
            para.insert(0, a)
            para.insert(1, ' ')
            count += 1

    def _linkify_headings(self, soup):
        md_el = soup.find('div', 'md')
        for heading in md_el.findAll(['h1', 'h2', 'h3'], recursive=False):
            heading_a = Tag(soup, "a", [('href', '#%s' % heading['id'])])
            heading_a.contents = heading.contents
            heading.contents = []
            heading.append(heading_a)
