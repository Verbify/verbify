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

from __future__ import with_statement

import base64
import collections
import datetime
import itertools
import json
import re
import struct

from pycassa import types
from pycassa.util import convert_uuid_to_time
from pycassa.system_manager import ASCII_TYPE, DATE_TYPE, FLOAT_TYPE, UTF8_TYPE
from pylons import request
from pylons import tmpl_context as c
from pylons import app_globals as g
from pylons.i18n import _, N_
from thrift.protocol.TProtocol import TProtocolException
from thrift.Thrift import TApplicationException
from thrift.transport.TTransport import TTransportException

from v1.config import feature
from v1.lib.db.thing import Thing, Relation, NotFound
from account import (
    Account,
    FakeAccount,
    QuarantinedSubverbifyOptInsByAccount,
)
from printable import Printable
from v1.lib.db.userrel import UserRel, MigratingUserRel
from v1.lib.db.operators import lower, or_, and_, not_, desc
from v1.lib.errors import VerbifyError
from v1.lib.geoip import get_request_location
from v1.lib.memoize import memoize
from v1.lib.permissions import ModeratorPermissionSet
from v1.lib.utils import (
    UrlParser,
    in_chunks,
    summarize_markdown,
    timeago,
    to36,
    tup,
    unicode_title_to_ascii,
)
from v1.lib.cache import MemcachedError
from v1.lib.sgm import sgm
from v1.lib.strings import strings, Score
from v1.lib.filters import _force_unicode
from v1.lib.db import tdb_cassandra
from v1.lib.db.tdb_sql import CreationError
from v1.models.wiki import WikiPage, ImagesByWikiPage
from v1.models.trylater import TryLater, TryLaterBySubject
from v1.lib.merge import ConflictException
from v1.lib.cache import CL_ONE
from v1.lib import hooks
from v1.models.query_cache import MergedCachedQuery
from v1.models.rules import SubverbifyRules
import pycassa

from v1.models.keyvalue import NamedGlobals
from v1.models.wiki import WikiPage
import os.path
import random

trylater_hooks = hooks.HookRegistrar()


def get_links_sr_ids(sr_ids, sort, time):
    from v1.lib.db import queries

    if not sr_ids:
        return []

    results = [queries._get_links(sr_id, sort, time) for sr_id in sr_ids]
    return queries.merge_results(*results)


def get_user_location():
    """Determine country of origin for the current user

    This is provided via a call to geoip.get_request_location unless the
    user has opted into the global default location.
    """
    # The default location is just the unset one
    if c.user and c.user.pref_use_global_defaults:
        return ""

    # this call has the side effect of memoizing on c.location
    return get_request_location(request, c)


subverbify_rx = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_]{2,20}\Z")
language_subverbify_rx = re.compile(r"\A[a-z]{2}\Z")
time_subverbify_rx = re.compile(r"\At:[A-Za-z0-9][A-Za-z0-9_]{2,22}\Z")


class BaseSite(object):
    _defaults = dict(
        static_path=g.static_path,
        header=None,
        header_title='',
        login_required=False,
        sticky_fullnames=None,
    )

    def __getattr__(self, name):
        if name in self._defaults:
            return self._defaults[name]
        raise AttributeError

    @property
    def path(self):
        return "/r/%s/" % self.name

    @property
    def user_path(self):
        return self.path

    @property
    def analytics_name(self):
        return self.name

    @property
    def allows_referrers(self):
        return True

    def is_moderator_with_perms(self, user, *perms):
        rel = self.is_moderator(user)
        if rel:
            return all(rel.has_permission(perm) for perm in perms)

    def is_limited_moderator(self, user):
        rel = self.is_moderator(user)
        return bool(rel and not rel.is_superuser())

    def is_unlimited_moderator(self, user):
        rel = self.is_moderator(user)
        return bool(rel and rel.is_superuser())

    def get_links(self, sort, time):
        from v1.lib.db import queries
        return queries.get_links(self, sort, time)

    def get_spam(self, include_links=True, include_comments=True):
        from v1.lib.db import queries
        return queries.get_spam(self, user=c.user, include_links=include_links,
                                include_comments=include_comments)

    def get_reported(self, include_links=True, include_comments=True):
        from v1.lib.db import queries
        return queries.get_reported(self, user=c.user,
                                    include_links=include_links,
                                    include_comments=include_comments)

    def get_modqueue(self, include_links=True, include_comments=True):
        from v1.lib.db import queries
        return queries.get_modqueue(self, user=c.user,
                                    include_links=include_links,
                                    include_comments=include_comments)

    def get_unmoderated(self):
        from v1.lib.db import queries
        return queries.get_unmoderated(self, user=c.user)

    def get_edited(self, include_links=True, include_comments=True):
        from v1.lib.db import queries
        return queries.get_edited(self, user=c.user,
                                  include_links=include_links,
                                  include_comments=include_comments)

    def get_all_comments(self):
        from v1.lib.db import queries
        return queries.get_sr_comments(self)

    def get_silded(self):
        from v1.lib.db import queries
        return queries.get_silded(self._id)

    @classmethod
    def get_modactions(cls, srs, mod=None, action=None):
        # Get a query that will yield ModAction objects with mod and action
        from v1.models import ModAction
        return ModAction.get_actions(srs, mod=mod, action=action)

    def get_live_promos(self):
        raise NotImplementedError


class SubverbifyExists(Exception): pass


class Subverbify(Thing, Printable, BaseSite):
    _cache = g.thingcache

    # Note: As of 2010/03/18, nothing actually overrides the static_path
    # attribute, even on a cname. So c.site.static_path should always be
    # the same as g.static_path.
    _defaults = dict(BaseSite._defaults,
        stylesheet_url="",
        stylesheet_url_http="",
        stylesheet_url_https="",
        header_size=None,
        allow_top=False, # overridden in "_new"
        reported=0,
        valid_votes=0,
        show_media=False,
        show_media_preview=True,
        domain=None,
        suggested_comment_sort=None,
        wikimode="disabled",
        wiki_edit_karma=100,
        wiki_edit_age=0,
        over_18=False,
        exclude_banned_modqueue=False,
        mod_actions=0,
        # do we allow self-posts, links only, or any?
        link_type='any', # one of ('link', 'self', 'any')
        sticky_fullnames=None,
        submit_link_label='',
        submit_text_label='',
        comment_score_hide_mins=0,
        flair_enabled=True,
        flair_position='right', # one of ('left', 'right')
        link_flair_position='', # one of ('', 'left', 'right')
        flair_self_assign_enabled=False,
        link_flair_self_assign_enabled=False,
        use_quotas=True,
        description="",
        public_description="",
        submit_text="",
        public_traffic=False,
        spam_links='high',
        spam_selfposts='high',
        spam_comments='low',
        archive_age=g.ARCHIVE_AGE,
        silding_server_seconds=0,
        contest_mode_upvotes_only=False,
        collapse_deleted_comments=False,
        icon_img='',
        icon_size=None,
        banner_img='',
        banner_size=None,
        key_color='',
        hide_ads=False,
        ban_count=0,
        quarantine=False,
    )

    # special attributes that shouldn't set Thing data attributes because they
    # have special setters that set other data attributes
    _derived_attrs = (
        'related_subverbifys',
    )

    _essentials = ('type', 'name', 'lang')
    _data_int_props = Thing._data_int_props + ('mod_actions', 'reported',
                                               'wiki_edit_karma', 'wiki_edit_age',
                                               'silding_server_seconds',
                                               'ban_count')

    sr_limit = 50
    sodium_limit = 100
    DEFAULT_LIMIT = object()

    ICON_EXACT_SIZE = (256, 256)
    BANNER_MIN_SIZE = (640, 192)
    BANNER_MAX_SIZE = (1280, 384)
    BANNER_ASPECT_RATIO = 10.0 / 3

    valid_types = {
        'archived',
        'employees_only',
        'sodium_only',
        'sodium_restricted',
        'private',
        'public',
        'restricted',
    }

    # this holds the subverbify types where content is not accessible
    # unless you are a contributor or mod
    private_types = {
        'employees_only',
        'sodium_only',
        'private',
    }

    KEY_COLORS = collections.OrderedDict([
        ('#ea0027', N_('red')),
        ('#ff4500', N_('orangered')),
        ('#ff8717', N_('orange')),
        ('#ffb000', N_('mango')),
        ('#94e044', N_('lime')),
        ('#46d160', N_('green')),
        ('#0dd3bb', N_('mint')),
        ('#25b79f', N_('teal')),
        ('#24a0ed', N_('blue')),
        ('#0079d3', N_('alien blue')),
        ('#ff66ac', N_('pink')),
        ('#7e53c1', N_('purple')),
        ('#ddbd37', N_('sodium')),
        ('#a06a42', N_('brown')),
        ('#efefed', N_('pale grey')),
        ('#a5a4a4', N_('grey')),
        ('#545452', N_('dark grey')),
        ('#222222', N_('semi black')),
    ])
    ACCENT_COLORS = (
        '#f44336', # red
        '#9c27b0', # purple
        '#3f51b5', # indigo
        '#03a9f4', # light blue
        '#009688', # teal
        '#8bc34a', # light green
        '#ffeb3b', # yellow
        '#ff9800', # orange
        '#795548', # brown
        '#607d8b', # blue grey
        '#e91e63', # pink
        '#673ab7', # deep purple
        '#2196f3', # blue
        '#00bcd4', # cyan
        '#4caf50', # green
        '#cddc39', # lime
        '#ffc107', # amber
        '#ff5722', # deep orange
        '#9e9e9e', # grey
    )

    MAX_STICKIES = 2

    @classmethod
    def _cache_prefix(cls):
        return "sr:"

    def __setattr__(self, attr, val, make_dirty=True):
        if attr in self._derived_attrs:
            object.__setattr__(self, attr, val)
        else:
            Thing.__setattr__(self, attr, val, make_dirty=make_dirty)

    # note: for purposely unrenderable verbifys (like promos) set author_id = -1
    @classmethod
    def _new(cls, name, title, author_id, ip, lang = g.lang, type = 'public',
             over_18 = False, **kw):
        if not cls.is_valid_name(name):
            raise ValueError("bad subverbify name")
        with g.make_lock("create_sr", 'create_sr_' + name.lower()):
            try:
                sr = Subverbify._by_name(name)
                raise SubverbifyExists
            except NotFound:
                if "allow_top" not in kw:
                    kw['allow_top'] = True
                sr = Subverbify(name = name,
                               title = title,
                               lang = lang,
                               type = type,
                               over_18 = over_18,
                               author_id = author_id,
                               ip = ip,
                               **kw)
                sr._commit()

                #clear cache
                Subverbify._by_name(name, _update = True)
                return sr

    @classmethod
    def is_valid_name(cls, name, allow_language_srs=False, allow_time_srs=False,
                      allow_verbify_dot_com=False):
        if not name:
            return False

        if allow_verbify_dot_com and name.lower() == "verbify.com":
            return True

        valid = bool(subverbify_rx.match(name))

        if not valid and allow_language_srs:
            valid = bool(language_subverbify_rx.match(name))

        if not valid and allow_time_srs:
            valid = bool(time_subverbify_rx.match(name))

        return valid

    _specials = {}

    SRNAME_NOTFOUND = "n"
    SRNAME_TTL = int(datetime.timedelta(hours=12).total_seconds())

    @classmethod
    def _by_name(cls, names, stale=False, _update = False):
        '''
        Usages:
        1. Subverbify._by_name('funny') # single sr name
        Searches for a single subverbify. Returns a single Subverbify object or
        raises NotFound if the subverbify doesn't exist.
        2. Subverbify._by_name(['aww','iama']) # list of sr names
        Searches for a list of subverbifys. Returns a dict mapping srnames to
        Subverbify objects. Items that were not found are ommitted from the dict.
        If no items are found, an empty dict is returned.
        '''
        names, single = tup(names, True)

        to_fetch = {}
        ret = {}

        for name in names:
            try:
                ascii_only = str(name.decode("ascii", errors="ignore"))
            except UnicodeEncodeError:
                continue

            lname = ascii_only.lower()

            if lname in cls._specials:
                ret[name] = cls._specials[lname]
            else:
                valid_name = cls.is_valid_name(lname, allow_language_srs=True,
                                               allow_time_srs=True,
                                               allow_verbify_dot_com=True)
                if valid_name:
                    to_fetch[lname] = name
                else:
                    g.log.debug("Subverbify._by_name() ignoring invalid srname: %s", lname)

        if to_fetch:
            if not _update:
                srids_by_name = g.gencache.get_multi(
                    to_fetch.keys(), prefix='srid:', stale=True)
            else:
                srids_by_name = {}

            missing_srnames = set(to_fetch.keys()) - set(srids_by_name.keys())
            if missing_srnames:
                for srnames in in_chunks(missing_srnames, size=10):
                    q = cls._query(
                        lower(cls.c.name) == srnames,
                        cls.c._spam == (True, False),
                        # subverbifys can't actually be deleted, but the combo
                        # of allowing for deletion and turning on optimize_rules
                        # gets rid of an unnecessary join on the thing table
                        cls.c._deleted == (True, False),
                        limit=len(srnames),
                        optimize_rules=True,
                        data=True,
                    )
                    with g.stats.get_timer('subverbify_by_name'):
                        fetched = {sr.name.lower(): sr._id for sr in q}
                    srids_by_name.update(fetched)

                    still_missing = set(srnames) - set(fetched)
                    fetched.update((name, cls.SRNAME_NOTFOUND) for name in still_missing)
                    try:
                        g.gencache.set_multi(
                            keys=fetched,
                            prefix='srid:',
                            time=cls.SRNAME_TTL,
                        )
                    except MemcachedError:
                        pass

            srs = {}
            srids = [v for v in srids_by_name.itervalues() if v != cls.SRNAME_NOTFOUND]
            if srids:
                srs = cls._byID(srids, data=True, return_dict=False, stale=stale)

            for sr in srs:
                ret[to_fetch[sr.name.lower()]] = sr

        if ret and single:
            return ret.values()[0]
        elif not ret and single:
            raise NotFound, 'Subverbify %s' % name
        else:
            return ret

    @classmethod
    @memoize('subverbify._by_domain')
    def _by_domain_cache(cls, name):
        q = cls._query(cls.c.domain == name,
                       limit = 1)
        l = list(q)
        if l:
            return l[0]._id

    @classmethod
    def _by_domain(cls, domain, _update = False):
        sr_id = cls._by_domain_cache(_force_unicode(domain).lower(),
                                     _update = _update)
        if sr_id:
            return cls._byID(sr_id, True)
        else:
            return None

    @property
    def allowed_types(self):
        if self.link_type == "any":
            return set(("link", "self"))
        return set((self.link_type,))

    @property
    def allows_referrers(self):
        return self.type in {'public', 'restricted',
                             'sodium_restricted', 'archived'}

    @property
    def author_slow(self):
        if self.author_id:
            return Account._byID(self.author_id, data=True)
        else:
            return None

    def add_moderator(self, user, **kwargs):
        if not user.modmsgtime:
            user.modmsgtime = False
            user._commit()

        hook = hooks.get_hook("subverbify.add_moderator")
        hook.call(subverbify=self, user=user)

        return super(Subverbify, self).add_moderator(user, **kwargs)

    def remove_moderator(self, user, **kwargs):
        hook = hooks.get_hook("subverbify.remove_moderator")
        hook.call(subverbify=self, user=user)

        ret = super(Subverbify, self).remove_moderator(user, **kwargs)

        is_mod_somewhere = bool(Subverbify.reverse_moderator_ids(user))
        if not is_mod_somewhere:
            user.modmsgtime = None
            user._commit()

        return ret

    @property
    def moderators(self):
        return self.moderator_ids()

    def moderators_with_perms(self):
        return collections.OrderedDict(
            (r._thing2_id, r.get_permissions())
            for r in self.each_moderator())

    def moderator_invites_with_perms(self):
        return collections.OrderedDict(
            (r._thing2_id, r.get_permissions())
            for r in self.each_moderator_invite())

    def fetch_stylesheet_source(self):
        try:
            return WikiPage.get(self, 'config/stylesheet')._get('content','')
        except tdb_cassandra.NotFound:
            return ""

    @property
    def prev_stylesheet(self):
        try:
            return WikiPage.get(self, 'config/stylesheet')._get('revision','')
        except tdb_cassandra.NotFound:
            return ''

    @property
    def wikibanned(self):
        return self.wikibanned_ids()

    @property
    def wikicontributor(self):
        return self.wikicontributor_ids()

    @property
    def _should_wiki(self):
        return True

    @property
    def subscribers(self):
        return self.subscriber_ids()

    @property
    def wiki_use_subverbify_karma(self):
        return True

    @property
    def hide_subscribers(self):
        return self.name.lower() in g.hide_subscribers_srs

    @property
    def hide_contributors(self):
        return self.type in {'employees_only', 'sodium_only'}

    @property
    def hide_num_users_info(self):
        return self.quarantine

    @property
    def _related_multipath(self):
        return '/r/%s/m/related' % self.name.lower()

    @property
    def related_subverbifys(self):
        try:
            multi = LabeledMulti._byID(self._related_multipath)
        except tdb_cassandra.NotFound:
            multi = None
        return  [sr.name for sr in multi.srs] if multi else []

    @property
    def allow_ads(self):
        return not (self.hide_ads or self.quarantine)

    @property
    def discoverable(self):
        return self.allow_top and not self.quarantine

    @property
    def community_rules(self):
        return SubverbifyRules.get_rules(self)

    @related_subverbifys.setter
    def related_subverbifys(self, related_subverbifys):
        try:
            multi = LabeledMulti._byID(self._related_multipath)
        except tdb_cassandra.NotFound:
            if not related_subverbifys:
                return
            multi = LabeledMulti.create(self._related_multipath, self)

        if related_subverbifys:
            srs = Subverbify._by_name(related_subverbifys)
            try:
                sr_props = {srs[sr_name]: {} for sr_name in related_subverbifys}
            except KeyError as e:
                raise NotFound, 'Subverbify %s' % e.args[0]

            multi.clear_srs()
            multi.add_srs(sr_props)
            multi._commit()
        else:
            multi.delete()

    activity_contexts = (
        "logged_in",
    )
    SubverbifyActivity = collections.namedtuple(
        "SubverbifyActivity", activity_contexts)

    def record_visitor_activity(self, context, visitor_id):
        """Record a visit to this subverbify in the activity service.

        This is used to show "here now" numbers. Multiple contexts allow us
        to bucket different kinds of visitors (logged-in vs. logged-out etc.)

        :param str context: The category of visitor. Must be one of
            Subverbify.activity_contexts.
        :param str visitor_id: A unique identifier for this visitor within the
            given context.

        """
        assert context in self.activity_contexts

        # we don't actually support other contexts yet
        assert self.activity_contexts == ("logged_in",)

        if not c.activity_service:
            return

        try:
            c.activity_service.record_activity(self._fullname, visitor_id)
        except (TApplicationException, TProtocolException, TTransportException):
            pass

    def count_activity(self):
        """Count activity in this subverbify in all known contexts.

        :returns: a named tuple of activity information for each context.

        """
        # we don't actually support other contexts yet
        assert self.activity_contexts == ("logged_in",)

        if not c.activity_service:
            return None

        try:
            # TODO: support batch lookup of multiple contexts (requires changes
            # to activity service)
            with c.activity_service.retrying(attempts=4, budget=0.1) as svc:
                activity = svc.count_activity(self._fullname)
            return self.SubverbifyActivity(activity)
        except (TApplicationException, TProtocolException, TTransportException):
            return None

    def spammy(self):
        return self._spam

    def is_contributor(self, user):
        if self.type == 'employees_only':
            return user.employee
        else:
            return super(Subverbify, self).is_contributor(user)

    def can_comment(self, user):
        if c.user_is_admin:
            return True

        override = hooks.get_hook("subverbify.can_comment").call_until_return(
                                                            sr=self, user=user)

        if override is not None:
            return override
        elif self.is_banned(user):
            return False
        elif self.type == 'sodium_restricted' and user.sodium:
            return True
        elif self.type in ('public','restricted'):
            return True
        elif self.is_moderator(user) or self.is_contributor(user):
            #private requires contributorship
            return True
        elif self.type == 'sodium_only':
            return user.sodium or user.sodium_charter
        else:
            return False

    def wiki_can_submit(self, user):
        return self.can_submit(user)

    def can_submit(self, user, promotion=False):
        if c.user_is_admin:
            return True
        elif self.is_banned(user) and not promotion:
            return False
        elif self.spammy():
            return False
        elif self.type == 'public':
            return True
        elif self.is_moderator(user) or self.is_contributor(user):
            #restricted/private require contributorship
            return True
        elif self.type == 'sodium_only':
            return user.sodium or user.sodium_charter
        elif self.type == 'sodium_restricted' and user.sodium:
            return True
        elif self.type == 'restricted' and promotion:
            return True
        else:
            return False

    def can_submit_link(self, user):
        if c.user_is_admin or self.is_moderator_with_perms(user, "posts"):
            return True
        return "link" in self.allowed_types

    def can_submit_text(self, user):
        if c.user_is_admin or self.is_moderator_with_perms(user, "posts"):
            return True
        return "self" in self.allowed_types

    def can_ban(self, user):
        return (user
                and (c.user_is_admin
                     or self.is_moderator_with_perms(user, 'posts')))

    def can_mute(self, muter, user):
        return (user.is_mutable(self) and
            (c.user_is_admin or
                self.is_moderator_with_perms(muter, 'access', 'mail'))
        )

    def can_distinguish(self,user):
        return (user
                and (c.user_is_admin
                     or self.is_moderator_with_perms(user, 'posts')))

    def can_change_stylesheet(self, user):
        if c.user_is_loggedin:
            return (
                c.user_is_admin or self.is_moderator_with_perms(user, 'config'))
        else:
            return False

    def parse_css(self, content, verify=True):
        from v1.lib import cssfilter
        from v1.lib.template_helpers import (
            make_url_protocol_relative,
            static,
        )

        if g.css_killswitch or (verify and not self.can_change_stylesheet(c.user)):
            return (None, None)

        if not content:
            return ([], "")

        # parse in regular old http mode
        images = ImagesByWikiPage.get_images(self, "config/stylesheet")

        if self.quarantine:
            images = {name: static('blank.png') for name, url in images.iteritems()}

        protocol_relative_images = {
            name: make_url_protocol_relative(url)
            for name, url in images.iteritems()}
        parsed, errors = cssfilter.validate_css(
            content,
            protocol_relative_images,
        )

        return (errors, parsed)

    def change_css(self, content, parsed, prev=None, reason=None, author=None, force=False):
        from v1.models import ModAction
        from v1.lib.media import upload_stylesheet

        if not author:
            author = c.user

        if content is None:
            content = ''
        try:
            wiki = WikiPage.get(self, 'config/stylesheet')
        except tdb_cassandra.NotFound:
            wiki = WikiPage.create(self, 'config/stylesheet')
        wr = wiki.revise(content, previous=prev, author=author._id36, reason=reason, force=force)

        if parsed:
            self.stylesheet_url = upload_stylesheet(parsed)
            self.stylesheet_url_http = ""
            self.stylesheet_url_https = ""
        else:
            self.stylesheet_url = ""
            self.stylesheet_url_http = ""
            self.stylesheet_url_https = ""
        self._commit()

        if wr:
            ModAction.create(self, author, action='wikirevise', details='Updated subverbify stylesheet')

        return wr

    def is_special(self, user):
        return (user
                and (c.user_is_admin
                     or self.is_moderator(user)
                     or self.is_contributor(user)))

    def should_ratelimit(self, user, kind):
        if self.is_special(user):
            return False

        hook = hooks.get_hook("account.is_ratelimit_exempt")
        ratelimit_exempt = hook.call_until_return(account=c.user)
        if ratelimit_exempt:
            return False

        if kind == 'comment':
            rl_karma = g.MIN_RATE_LIMIT_COMMENT_KARMA
        else:
            rl_karma = g.MIN_RATE_LIMIT_KARMA

        return user.karma(kind, self) < rl_karma

    def can_view(self, user):
        if c.user_is_admin:
            return True

        if self.spammy() or not self.is_exposed(user):
            return False
        else:
            return self.is_allowed_to_view(user)

    def can_view_in_modlist(self, user):
        if c.user_is_admin:
            return True
        elif self.spammy():
            return False
        else:
            return self.is_allowed_to_view(user)

    def is_allowed_to_view(self, user):
        """Returns whether user can view based on permissions and settings"""
        if self.type in ('public', 'restricted',
                         'sodium_restricted', 'archived'):
            return True
        elif c.user_is_loggedin:
            if self.type == 'sodium_only':
                return (user.sodium or
                    user.sodium_charter or
                    self.is_moderator(user) or
                    self.is_moderator_invite(user))

            return (self.is_contributor(user) or
                    self.is_moderator(user) or
                    self.is_moderator_invite(user))

    def is_exposed(self, user):
        """Return whether user is opted in to the subverbify's content.

        If a subverbify is quarantined, users must opt-in before viewing its
        content. Logged out users cannot opt-in, and all users are considered
        opted-in to non-quarantined subverbifys.
        """
        if not self.quarantine:
            return True
        elif not user:
            return False
        elif (user.email_verified and
              QuarantinedSubverbifyOptInsByAccount.is_opted_in(user, self)):
            return True

        return False

    @property
    def is_embeddable(self):
        return (self.type not in Subverbify.private_types and
                not self.over_18 and not self._spam and not self.quarantine)

    def can_demod(self, bully, victim):
        bully_rel = self.get_moderator(bully)
        if bully_rel is not None and bully == victim:
            # mods can always demod themselves
            return True
        victim_rel = self.get_moderator(victim)
        return (
            bully_rel is not None
            and victim_rel is not None
            and bully_rel.is_superuser()  # limited mods can't demod
            and bully_rel._date <= victim_rel._date)

    @classmethod
    def load_subverbifys(cls, links, return_dict = True, stale=False):
        """returns the subverbifys for a list of links. it also preloads the
        permissions for the current user."""
        srids = set(l.sr_id for l in links
                    if getattr(l, "sr_id", None) is not None)
        subverbifys = {}
        if srids:
            subverbifys = cls._byID(srids, data=True, stale=stale)

        if subverbifys and c.user_is_loggedin:
            # dict( {Subverbify,Account,name} -> Relationship )
            SRMember._fast_query(subverbifys.values(), (c.user,), ('moderator',),
                                 data=True)

        return subverbifys if return_dict else subverbifys.values()

    def keep_for_rising(self, sr_id):
        """Return whether or not to keep a thing in rising for this SR."""
        return sr_id == self._id

    @classmethod
    def get_sr_user_relations(cls, user, srs):
        """Return SubverbifyUserRelations for the user and subverbifys.

        The SubverbifyUserRelation objects indicate whether the user is a
        moderator, contributor, subscriber, banned, or muted. This method
        batches the lookups of all the relations for all the subverbifys.

        """

        moderator_srids = set()
        contributor_srids = set()
        banned_srids = set()
        muted_srids = set()
        subscriber_srids = cls.user_subverbifys(user, limit=None)

        if user and c.user_is_loggedin:
            res = SRMember._fast_query(
                thing1s=srs,
                thing2s=user,
                name=["moderator", "contributor", "banned", "muted"],
            )
            # _fast_query returns a dict of {(t1, t2, name): rel}, with rel of
            # None if the relation doesn't exist
            rels = [rel for rel in res.itervalues() if rel]
            for rel in rels:
                rel_name = rel._name
                sr_id = rel._thing1_id

                if rel_name == "moderator":
                    moderator_srids.add(sr_id)
                elif rel_name == "contributor":
                    contributor_srids.add(sr_id)
                elif rel_name == "banned":
                    banned_srids.add(sr_id)
                elif rel_name == "muted":
                    muted_srids.add(sr_id)

        ret = {}
        for sr in srs:
            sr_id = sr._id
            ret[sr_id] = SubverbifyUserRelations(
                subscriber=sr_id in subscriber_srids,
                moderator=sr_id in moderator_srids,
                contributor=sr_id in contributor_srids,
                banned=sr_id in banned_srids,
                muted=sr_id in muted_srids,
            )
        return ret

    @classmethod
    def add_props(cls, user, wrapped):
        srs = {item.lookups[0] for item in wrapped}
        sr_user_relations = cls.get_sr_user_relations(user, srs)

        for item in wrapped:
            relations = sr_user_relations[item._id]
            item.subscriber = relations.subscriber
            item.moderator = relations.moderator
            item.contributor = relations.contributor
            item.banned = relations.banned
            item.muted = relations.muted

            if item.hide_subscribers and not c.user_is_admin:
                item._ups = 0

            item.score_hidden = (
                not item.can_view(user) or
                item.hide_num_users_info
            )

            item.score = item._ups

            # override "voting" score behavior (it will override the use of
            # item.score in builder.py to be ups-downs)
            item.likes = item.subscriber or None
            base_score = item.score - (1 if item.likes else 0)
            item.voting_score = [(base_score + x - 1) for x in range(3)]
            item.score_fmt = Score.subscribers

            #will seem less horrible when add_props is in pages.py
            from v1.lib.pages import UserText
            if item.public_description or item.description:
                text = (item.public_description or
                        summarize_markdown(item.description))
                item.public_description_usertext = UserText(item, text)
            else:
                item.public_description_usertext = None


        Printable.add_props(user, wrapped)

    cache_ignore = {
        "description",
        "public_description",
        "subscribers",
    }.union(Printable.cache_ignore)

    @staticmethod
    def wrapped_cache_key(wrapped, style):
        s = Printable.wrapped_cache_key(wrapped, style)
        return s

    @classmethod
    def default_subverbifys(cls, ids=True):
        """Return the subverbifys a user with no subscriptions would see."""
        location = get_user_location()
        srids = LocalizedDefaultSubverbifys.get_defaults(location)

        srs = Subverbify._byID(srids, data=True, return_dict=False, stale=True)
        srs = filter(lambda sr: sr.allow_top, srs)

        if ids:
            return [sr._id for sr in srs]
        else:
            return srs

    @classmethod
    def featured_subverbifys(cls):
        """Return the curated list of subverbifys shown during onboarding."""
        location = get_user_location()
        srids = LocalizedFeaturedSubverbifys.get_featured(location)

        srs = Subverbify._byID(srids, data=True, return_dict=False, stale=True)
        srs = filter(lambda sr: sr.discoverable, srs)

        return srs

    @classmethod
    @memoize('random_verbifys', time = 1800)
    def random_verbifys_cached(cls, user_name, sr_ids, limit):
        # First filter out any subverbifys that don't have a new enough post
        # to be included in the front page (just doing this may remove enough
        # to get below the limit anyway)
        sr_ids = SubverbifysActiveForFrontPage.filter_inactive_ids(sr_ids)
        if len(sr_ids) <= limit:
            return sr_ids

        return random.sample(sr_ids, limit)

    @classmethod
    def random_verbifys(cls, user_name, sr_ids, limit):
        """Select a random subset from sr_ids.

        Used for limiting the number of subscribed subverbifys shown on a user's
        front page. Selection is cached for a while so the front page doesn't
        jump around.

        """

        if not limit:
            return sr_ids

        # if the user is subscribed to them, the automatic subverbifys should
        # always be in the front page set and not count towards the limit
        if g.automatic_verbifys:
            automatics = Subverbify._by_name(
                g.automatic_verbifys, stale=True).values()
            automatic_ids = [sr._id for sr in automatics if sr._id in sr_ids]
            sr_ids = [sr_id for sr_id in sr_ids if sr_id not in automatic_ids]
        else:
            automatic_ids = []

        if len(sr_ids) > limit:
            sr_ids = sorted(sr_ids)
            sr_ids = cls.random_verbifys_cached(user_name, sr_ids, limit)

        return sr_ids + automatic_ids

    @classmethod
    def random_verbify(cls, over18=False, user=None):
        if over18:
            sr_ids = NamedGlobals.get("popular_over_18_sr_ids")
        else:
            sr_ids = NamedGlobals.get("popular_sr_ids")

        if user:
            excludes = set(cls.user_subverbifys(user, limit=None))
            sr_ids = list(set(sr_ids) - excludes)

        if not sr_ids:
            return Subverbify._by_name(g.default_sr)

        sr_id = random.choice(sr_ids)
        sr = Subverbify._byID(sr_id, data=True)
        return sr

    @classmethod
    def update_popular_subverbifys(cls, limit=5000):
        q = cls._query(cls.c.type == "public", sort=desc('_downs'), limit=limit,
                       data=True)
        srs = list(q)

        # split the list into two based on whether the subverbify is 18+ or not
        sr_ids = []
        over_18_sr_ids = []

        # /r/promos is public but has special handling to make it unviewable
        promo_sr_id = cls.get_promote_srid()

        for sr in srs:
            if not sr.discoverable:
                continue

            if sr._id == promo_sr_id:
                continue

            if not sr.over_18:
                sr_ids.append(sr._id)
            else:
                over_18_sr_ids.append(sr._id)

        NamedGlobals.set("popular_sr_ids", sr_ids)
        NamedGlobals.set("popular_over_18_sr_ids", over_18_sr_ids)

    @classmethod
    def random_subscription(cls, user):
        if user.has_subscribed:
            sr_ids = Subverbify.subscribed_ids_by_user(user)
        else:
            sr_ids = Subverbify.default_subverbifys(ids=True)

        return (Subverbify._byID(random.choice(sr_ids), data=True)
                if sr_ids else Subverbify._by_name(g.default_sr))

    @classmethod
    def user_subverbifys(cls, user, ids=True, limit=DEFAULT_LIMIT):
        """
        subverbifys that appear in a user's listings. If the user has
        subscribed, returns the stored set of subscriptions.

        limit - if it's Subverbify.DEFAULT_LIMIT, limits to 50 subs
                (100 for sodium users)
                if it's None, no limit is used
                if it's an integer, then that many subs will be returned

        Otherwise, return the default set.
        """
        # Limit the number of subs returned based on user status,
        # if no explicit limit was passed
        if limit is Subverbify.DEFAULT_LIMIT:
            if user and user.sodium:
                # Sodiumies get extra subverbifys
                limit = Subverbify.sodium_limit
            else:
                limit = Subverbify.sr_limit

        # note: for user not logged in, the fake user account has
        # has_subscribed == False by default.
        if user and user.has_subscribed:
            sr_ids = Subverbify.subscribed_ids_by_user(user)
            sr_ids = cls.random_verbifys(user.name, sr_ids, limit)

            return sr_ids if ids else Subverbify._byID(sr_ids,
                                                      data=True,
                                                      return_dict=False,
                                                      stale=True)
        else:
            return cls.default_subverbifys(ids=ids)


    # Used to pull all of the SRs a given user moderates or is a contributor
    # to (which one is controlled by query_param)
    @classmethod
    def special_verbifys(cls, user, query_param):
        lookup = getattr(cls, 'reverse_%s_ids' % query_param)
        return lookup(user)

    @classmethod
    def subscribe_defaults(cls, user):
        if not user.has_subscribed:
            user.has_subscribed = True
            user._commit()
            srs = cls.user_subverbifys(user=None, ids=False, limit=None)
            cls.subscribe_multiple(user, srs)

    def keep_item(self, wrapped):
        if c.user_is_admin:
            return True

        user = c.user if c.user_is_loggedin else None
        return self.can_view(user)

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        if isinstance(self, FakeSubverbify):
            return self is other

        return self._id == other._id

    def __ne__(self, other):
        return not self.__eq__(other)

    @staticmethod
    def get_all_mod_ids(srs):
        from v1.lib.db.thing import Merge
        srs = tup(srs)
        queries = [
            SRMember._simple_query(
                ["_thing2_id"],
                SRMember.c._thing1_id == sr._id,
                SRMember.c._name == 'moderator',
            ) for sr in srs
        ]

        merged = Merge(queries)
        return [rel._thing2_id for rel in list(merged)]

    def update_moderator_permissions(self, user, **kwargs):
        """Grants or denies permissions to this moderator.

        Does nothing if the given user is not a moderator. Args are named
        parameters with bool or None values (use None to all back to the default
        for a permission).
        """
        rel = self.get_moderator(user)
        if rel:
            rel.update_permissions(**kwargs)
            rel._commit()

    def add_rel_note(self, type, user, note):
        rel = getattr(self, "get_%s" % type)(user)
        if not rel:
            raise ValueError("User is not %s." % type)
        rel.note = note
        rel._commit()

    def get_live_promos(self):
        from v1.lib import promote
        return promote.get_live_promotions([self.name])

    def schedule_unban(self, kind, victim, banner, duration):
        return SubverbifyTempBan.schedule(
            self,
            kind,
            victim,
            banner,
            datetime.timedelta(days=duration),
        )

    def unschedule_unban(self, victim, type):
        SubverbifyTempBan.unschedule(self.name, victim.name, type)

    def get_tempbans(self, type=None, names=None):
        return SubverbifyTempBan.search(self.name, type, names)

    def get_muted_items(self, names=None):
        return MutedAccountsBySubverbify.search(self, names)

    def add_silding_seconds(self):
        from v1.models.sodium import get_current_value_of_month
        seconds = get_current_value_of_month()
        self._incr("silding_server_seconds", int(seconds))

    @property
    def allow_silding(self):
        return not self.quarantine

    @classmethod
    def get_promote_srid(cls):
        try:
            return cls._by_name(g.promo_sr_name, stale=True)._id
        except NotFound:
            return None

    def is_subscriber(self, user):
        try:
            return bool(SubscribedSubverbifysByAccount.fast_query(user, self))
        except tdb_cassandra.NotFound:
            return False

    def add_subscriber(self, user):
        SubscribedSubverbifysByAccount.create(user, self)
        SubscriptionsByDay.create(self, user)
        add_legacy_subscriber(self, user)
        self._incr('_ups', 1)

    @classmethod
    def subscribe_multiple(cls, user, srs):
        SubscribedSubverbifysByAccount.create(user, srs)
        SubscriptionsByDay.create(srs, user)
        add_legacy_subscriber(srs, user)
        for sr in srs:
            sr._incr('_ups', 1)

    def remove_subscriber(self, user):
        SubscribedSubverbifysByAccount.destroy(user, self)
        remove_legacy_subscriber(self, user)
        self._incr('_ups', -1)

    @classmethod
    def subscribed_ids_by_user(cls, user):
        return SubscribedSubverbifysByAccount.get_all_sr_ids(user)

    @classmethod
    def reverse_subscriber_ids(cls, user):
        # This is just for consistency with all the other UserRel types
        return cls.subscribed_ids_by_user(user)

    def get_rgb(self, fade=0.8):
        r = int(256 - (hash(str(self._id)) % 256)*(1-fade))
        g = int(256 - (hash(str(self._id) + ' ') % 256)*(1-fade))
        b = int(256 - (hash(str(self._id) + '  ') % 256)*(1-fade))
        return (r, g, b)

    def set_sticky(self, link, log_user=None, num=None):
        unstickied_fullnames = []

        if not self.sticky_fullnames:
            self.sticky_fullnames = [link._fullname]
        else:
            # don't re-sticky something that's already stickied
            if link._fullname in self.sticky_fullnames:
                return

            # XXX: have to work with a copy of the list instead of modifying
            #   it directly, because it doesn't get marked as "dirty" and
            #   saved properly unless we assign a new list to the attr
            sticky_fullnames = self.sticky_fullnames[:]

            # if a particular slot was specified and is in use, replace it
            if num and num <= len(sticky_fullnames):
                unstickied_fullnames.append(sticky_fullnames[num-1])
                sticky_fullnames[num-1] = link._fullname
            else:
                # either didn't specify a slot or it's empty, just append

                # if we're already at the max number of stickies, remove
                # the bottom-most to make room for this new one
                if self.has_max_stickies:
                    unstickied_fullnames.extend(
                        sticky_fullnames[self.MAX_STICKIES-1:])
                    sticky_fullnames = sticky_fullnames[:self.MAX_STICKIES-1]

                sticky_fullnames.append(link._fullname)

            self.sticky_fullnames = sticky_fullnames

        self._commit()

        if log_user:
            from v1.models import Link, ModAction
            for fullname in unstickied_fullnames:
                unstickied = Link._by_fullname(fullname)
                ModAction.create(self, log_user, "unsticky",
                    target=unstickied, details="replaced")
            ModAction.create(self, log_user, "sticky", target=link)

    def remove_sticky(self, link, log_user=None):
        # XXX: have to work with a copy of the list instead of modifying
        #   it directly, because it doesn't get marked as "dirty" and
        #   saved properly unless we assign a new list to the attr
        sticky_fullnames = self.sticky_fullnames[:]
        try:
            sticky_fullnames.remove(link._fullname)
        except ValueError:
            return

        self.sticky_fullnames = sticky_fullnames
        self._commit()

        if log_user:
            from v1.models import ModAction
            ModAction.create(self, log_user, "unsticky", target=link)

    @property
    def has_max_stickies(self):
        if not self.sticky_fullnames:
            return False
        return len(self.sticky_fullnames) >= self.MAX_STICKIES


class SubscribedSubverbifysByAccount(tdb_cassandra.DenormalizedRelation):
    _use_db = True
    _write_last_modified = False
    _read_consistency_level = tdb_cassandra.CL.ONE
    _write_consistency_level = tdb_cassandra.CL.QUORUM
    _connection_pool = 'main'
    _views = []
    _extra_schema_creation_args = {
        "default_validation_class": DATE_TYPE,
    }

    @classmethod
    def value_for(cls, user, sr):
        return datetime.datetime.now(g.tz)

    @classmethod
    def get_all_sr_ids(cls, user):
        key = cls.__name__ + user._id36
        sr_ids = g.cassandra_local_cache.get(key)
        if sr_ids is None:
            r = cls._cf.xget(user._id36)
            sr_ids = [int(sr_id36, 36) for sr_id36, val in r]
            g.cassandra_local_cache.set(key, sr_ids)

        return sr_ids


class SubscriptionsByDay(tdb_cassandra.View):
    _use_db = True
    _connection_pool = 'main'
    _compare_with = types.CompositeType(types.AsciiType(), types.AsciiType())
    _extra_schema_creation_args = {
        "key_validation_class": DATE_TYPE,
    }

    @classmethod
    def create(cls, srs, user):
        rowkey = datetime.datetime.now(g.tz).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        srs = tup(srs)
        columns = {(sr._id36, user._id36): "" for sr in srs}
        cls._cf.insert(rowkey, columns)

    @classmethod
    def get_all_counts(cls, date):
        date = date.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=g.tz,
        )

        gen = cls._cf.xget(date)
        (prev_sr_id36, user_id36), val = next(gen)

        count = 1
        for (sr_id36, user_id36), val in gen:
            if sr_id36 == prev_sr_id36:
                count += 1
            else:
                yield (prev_sr_id36, count)
                prev_sr_id36 = sr_id36
                count = 1
        yield (prev_sr_id36, count)

    @classmethod
    def write_counts(cls, days_ago=1):
        from sqlalchemy.orm import scoped_session, sessionmaker
        from v1.models.traffic import SubscriptionsBySubverbify, engine

        Session = scoped_session(sessionmaker(bind=engine))

        date = datetime.datetime.now(g.tz) - datetime.timedelta(days=days_ago)
        pg_date = date.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=None,
        )
        print "writing subscribers for %s" % date

        num_srs = 0
        num_subscribers = 0
        for sr_id36, count in cls.get_all_counts(date):
            sr = Subverbify._byID36(sr_id36, data=True)
            row = SubscriptionsBySubverbify(
                subverbify=sr.name,
                date=pg_date,
                subscriber_count=count,
            )
            Session.merge(row)
            Session.commit()
            num_srs += 1
            num_subscribers += count
        print "%s subscribers in %s subverbifys" % (num_subscribers, num_srs)
        Session.remove()


class FakeSubverbify(BaseSite):
    _defaults = dict(Subverbify._defaults,
        link_flair_position='right',
        flair_enabled=False,
    )

    def __init__(self):
        BaseSite.__init__(self)

    def keep_for_rising(self, sr_id):
        return False

    @property
    def _should_wiki(self):
        return False

    @property
    def allow_silding(self):
        return True

    @property
    def allow_ads(self):
        return True

    def is_moderator(self, user):
        if c.user_is_loggedin and c.user_is_admin:
            return FakeSRMember(ModeratorPermissionSet)

    def can_view(self, user):
        return True

    def can_comment(self, user):
        return False

    def can_submit(self, user, promotion=False):
        return False

    def can_change_stylesheet(self, user):
        return False

    def is_banned(self, user):
        return False

    def is_muted(self, user):
        return False

    def get_all_comments(self):
        from v1.lib.db import queries
        return queries.get_all_comments()

    def get_silded(self):
        raise NotImplementedError()

    def spammy(self):
        return False

class FriendsSR(FakeSubverbify):
    name = 'friends'
    title = 'friends'
    _defaults = dict(
        FakeSubverbify._defaults,
        login_required=True,
    )

    def get_links(self, sort, time):
        from v1.lib.db import queries

        friends = c.user.get_recently_submitted_friend_ids()
        if not friends:
            return []

        # with the precomputer enabled, this Subverbify only supports
        # being sorted by 'new'. it would be nice to have a
        # cleaner UI than just blatantly ignoring their sort,
        # though
        sort = 'new'
        time = 'all'

        friends = Account._byID(friends, return_dict=False)

        crs = [queries.get_submitted(friend, sort, time)
               for friend in friends]
        return queries.MergedCachedResults(crs)

    def get_all_comments(self):
        from v1.lib.db import queries

        friends = c.user.get_recently_commented_friend_ids()
        if not friends:
            return []

        # with the precomputer enabled, this Subverbify only supports
        # being sorted by 'new'. it would be nice to have a
        # cleaner UI than just blatantly ignoring their sort,
        # though
        sort = 'new'
        time = 'all'

        friends = Account._byID(friends,
                                return_dict=False)

        crs = [queries.get_comments(friend, sort, time)
               for friend in friends]
        return queries.MergedCachedResults(crs)

    def get_silded(self):
        from v1.lib.db.queries import get_silded_users

        friends = c.user.friend_ids()

        if not friends:
            return []

        return get_silded_users(friends)


class AllSR(FakeSubverbify):
    name = 'all'
    title = 'all subverbifys'
    path = '/r/all'

    def keep_for_rising(self, sr_id):
        return True

    def get_links(self, sort, time):
        from v1.models import Link
        from v1.lib.db import queries
        q = Link._query(
            sort=queries.db_sort(sort),
            read_cache=True,
            write_cache=True,
            cache_time=60,
            data=True,
            filter_primary_sort_only=True,
        )
        if time != 'all':
            q._filter(queries.db_times[time])
        return q

    def get_all_comments(self):
        from v1.lib.db import queries
        return queries.get_all_comments()

    def get_silded(self):
        from v1.lib.db import queries
        return queries.get_all_silded()

    def get_reported(self, include_links=True, include_comments=True):
        from v1.lib.db import queries
        from v1.lib.db.thing import Merge
        qs = []

        if include_links:
            qs.append(queries.get_reported_links(None))

        if include_comments:
            qs.append(queries.get_reported_comments(None))

        return MergedCachedQuery(qs)

class AllMinus(AllSR):
    analytics_name = "all"
    name = _("%s (filtered)") % "all"

    def __init__(self, srs):
        AllSR.__init__(self)
        self.exclude_srs = srs
        self.exclude_sr_ids = [sr._id for sr in srs]

    def keep_for_rising(self, sr_id):
        return sr_id not in self.exclude_sr_ids

    @property
    def title(self):
        sr_names = ', '.join(sr.name for sr in self.exclude_srs)
        return 'all subverbifys except ' + sr_names

    @property
    def path(self):
        return '/r/all-' + '-'.join(sr.name for sr in self.exclude_srs)

    def get_links(self, sort, time):
        from v1.models import Link
        from v1.lib.db.operators import not_
        q = AllSR.get_links(self, sort, time)
        if c.user.sodium and self.exclude_sr_ids:
            q._filter(not_(Link.c.sr_id.in_(self.exclude_sr_ids)))
        return q


class Filtered(object):
    unfiltered_path = None

    @property
    def path(self):
        return '/me/f/%s' % self.filtername

    @property
    def title(self):
        return self.name

    @property
    def name(self):
        return _("%s (filtered)") % self.filtername

    @property
    def multi_path(self):
        return ('/user/%s/f/%s' % (c.user.name, self.filtername)).lower()

    def _get_filtered_subverbifys(self):
        try:
            multi = LabeledMulti._byID(self.multi_path)
        except tdb_cassandra.NotFound:
            multi = None
        filtered_srs = multi.srs if multi else []
        return sorted(filtered_srs, key=lambda sr: sr.name)


class AllFiltered(Filtered, AllMinus):
    unfiltered_path = '/r/all'
    filtername = 'all'

    def __init__(self):
        filters = self._get_filtered_subverbifys() if c.user.sodium else []
        AllMinus.__init__(self, filters)


class _DefaultSR(FakeSubverbify):
    analytics_name = 'frontpage'
    #notice the space before verbify.com
    name = ' verbify.com'
    path = '/'
    header = g.default_header_url

    def _get_sr_ids(self):
        if not c.defaultsr_cached_sr_ids:
            user = c.user if c.user_is_loggedin else None
            c.defaultsr_cached_sr_ids = Subverbify.user_subverbifys(user)
        return c.defaultsr_cached_sr_ids

    def keep_for_rising(self, sr_id):
        return sr_id in self._get_sr_ids()

    def is_moderator(self, user):
        return False

    def get_links(self, sort, time):
        sr_ids = self._get_sr_ids()
        return get_links_sr_ids(sr_ids, sort, time)

    @property
    def title(self):
        return _(g.short_description)

# This is the base class for the instantiated front page verbify
class DefaultSR(_DefaultSR):
    @property
    def _base(self):
        try:
            return Subverbify._by_name(g.default_sr, stale=True)
        except NotFound:
            return None

    def wiki_can_submit(self, user):
        return True

    @property
    def wiki_use_subverbify_karma(self):
        return False

    @property
    def _should_wiki(self):
        return True

    @property
    def wikimode(self):
        return self._base.wikimode if self._base else "disabled"

    @property
    def wiki_edit_karma(self):
        return self._base.wiki_edit_karma

    @property
    def wiki_edit_age(self):
        return self._base.wiki_edit_age

    def is_wikicontributor(self, user):
        return self._base.is_wikicontributor(user)

    def is_wikibanned(self, user):
        return self._base.is_wikibanned(user)

    def is_wikicreate(self, user):
        return self._base.is_wikicreate(user)

    @property
    def _fullname(self):
        return "t5_6"

    @property
    def _id36(self):
        return self._base._id36

    @property
    def type(self):
        return self._base.type if self._base else "public"

    @property
    def header(self):
        return (self._base and self._base.header) or _DefaultSR.header

    @property
    def header_title(self):
        return (self._base and self._base.header_title) or ""

    @property
    def header_size(self):
        return (self._base and self._base.header_size) or None

    @property
    def stylesheet_url(self):
        return self._base.stylesheet_url if self._base else ""

    @property
    def stylesheet_url_http(self):
        return self._base.stylesheet_url_http if self._base else ""

    @property
    def stylesheet_url_https(self):
        return self._base.stylesheet_url_https if self._base else ""

    def get_all_comments(self):
        from v1.lib.db.queries import _get_sr_comments, merge_results
        sr_ids = Subverbify.user_subverbifys(c.user)
        results = [_get_sr_comments(sr_id) for sr_id in sr_ids]
        return merge_results(*results)

    def get_silded(self):
        from v1.lib.db.queries import get_silded
        return get_silded(Subverbify.user_subverbifys(c.user))

    def get_live_promos(self):
        from v1.lib import promote
        srs = Subverbify.user_subverbifys(c.user, ids=False)
        # '' is for promos targeted to the frontpage
        sr_names = [self.name] + [sr.name for sr in srs]
        return promote.get_live_promotions(sr_names)


class MultiVerbify(FakeSubverbify):
    name = 'multi'
    header = ""
    _defaults = dict(
        FakeSubverbify._defaults,
        weighting_scheme="classic",
    )

    # See comment in normalized_hot before adding new values here.
    AGEWEIGHTS = {
        "classic": 0.0,
        "fresh": 0.15,
    }

    def __init__(self, path=None, srs=None):
        FakeSubverbify.__init__(self)
        if path is not None:
            self._path = path
        self._srs = srs or []

    @property
    def srs(self):
        return self._srs

    @property
    def sr_ids(self):
        return [sr._id for sr in self.srs]

    @property
    def kept_sr_ids(self):
        return [sr._id for sr in self.srs if not sr._spam]

    @property
    def banned_sr_ids(self):
        return [sr._id for sr in self.srs if sr._spam]

    @property
    def allows_referrers(self):
        return all(sr.allows_referrers for sr in self.srs)

    def keep_for_rising(self, sr_id):
        return sr_id in self.kept_sr_ids

    def is_moderator(self, user):
        if not user:
            return False

        # Get moderator SRMember relations for all in srs
        # if a relation doesn't exist there will be a None entry in the
        # returned dict
        mod_rels = SRMember._fast_query(self.srs, user, 'moderator', data=True)
        if None in mod_rels.values():
            return False
        else:
            return FakeSRMember(ModeratorPermissionSet)

    def srs_with_perms(self, user, *perms):
        return [sr for sr in self.srs
                if sr.is_moderator_with_perms(user, *perms) and not sr._spam]

    @property
    def title(self):
        return _('posts from %s') % ', '.join(sr.name for sr in self.srs)

    @property
    def path(self):
        return self._path

    @property
    def over_18(self):
        return any(sr.over_18 for sr in self.srs)

    @property
    def ageweight(self):
        return self.AGEWEIGHTS.get(self.weighting_scheme, 0.0)

    def get_links(self, sort, time):
        return get_links_sr_ids(self.kept_sr_ids, sort, time)

    def get_all_comments(self):
        from v1.lib.db.queries import _get_sr_comments, merge_results
        results = [_get_sr_comments(sr_id) for sr_id in self.kept_sr_ids]
        return merge_results(*results)

    def get_silded(self):
        from v1.lib.db.queries import get_silded
        return get_silded(self.kept_sr_ids)

    def get_live_promos(self):
        from v1.lib import promote
        srs = Subverbify._byID(self.kept_sr_ids, return_dict=False)
        sr_names = [sr.name for sr in srs]
        return promote.get_live_promotions(sr_names)


class TooManySubverbifysError(Exception):
    pass


class BaseLocalizedSubverbifys(tdb_cassandra.View):
    """Mapping of location to subverbify ids"""
    _use_db = False
    _compare_with = ASCII_TYPE
    _read_consistency_level = tdb_cassandra.CL.QUORUM
    _write_consistency_level = tdb_cassandra.CL.QUORUM
    _extra_schema_creation_args = {
        "key_validation_class": ASCII_TYPE,
        "default_validation_class": ASCII_TYPE,
    }
    GLOBAL = "GLOBAL"

    @classmethod
    def _rowkey(cls, location):
        return str(location)

    @classmethod
    def lookup(cls, keys, update=False):
        def _lookup(keys):
            rows = cls._cf.multiget(keys)
            ret = {}
            for key in keys:
                columns = rows[key] if key in rows else {}
                id36s = columns.keys()
                ret[key] = id36s
            return ret

        id36s_by_location = sgm(
            cache=g.gencache,
            keys=keys,
            miss_fn=_lookup,
            prefix=cls.CACHE_PREFIX,
            stale=True,
            _update=update,
            ignore_set_errors=True,
        )
        ids_by_location = {location: [int(id36, 36) for id36 in id36s]
                           for location, id36s in id36s_by_location.iteritems()}
        return ids_by_location

    @classmethod
    def set_srs(cls, location, srs):
        rowkey = cls._rowkey(location)
        columns = {sr._id36: '' for sr in srs}

        # update cassandra
        try:
            existing = cls._cf.get(rowkey)
        except tdb_cassandra.NotFoundException:
            existing = {}

        cls._set_values(rowkey, columns)
        removed_srid36s = set(existing.keys()) - set(columns.keys())
        cls._remove(rowkey, removed_srid36s)

        # update cache
        id36s = columns.keys()
        g.gencache.set_multi({rowkey: id36s}, prefix=cls.CACHE_PREFIX)

    @classmethod
    def set_global_srs(cls, srs):
        location = cls.GLOBAL
        cls.set_srs(location, srs)

    @classmethod
    def get_srids(cls, location):
        if not location:
            return []

        rowkey = cls._rowkey(location)
        ids_by_location = cls.lookup([rowkey])
        srids = ids_by_location[rowkey]
        return srids

    @classmethod
    def get_global_defaults(cls):
        return cls.get_srids(cls.GLOBAL)

    @classmethod
    def get_localized_srs(cls, location):
        location_key = cls._rowkey(location) if location else None
        global_key = cls._rowkey(cls.GLOBAL)
        keys = filter(None, [location_key, global_key])

        ids_by_location = cls.lookup(keys)

        if location_key and ids_by_location[location_key]:
            c.used_localized_defaults = True
            return ids_by_location[location_key]
        else:
            return ids_by_location[global_key]


class LocalizedDefaultSubverbifys(BaseLocalizedSubverbifys):
    _use_db = True
    _type_prefix = "LocalizedDefaultSubverbifys"
    CACHE_PREFIX = "defaultsrs:"

    @classmethod
    def get_defaults(cls, location):
        return cls.get_localized_srs(location)


class LocalizedFeaturedSubverbifys(BaseLocalizedSubverbifys):
    _use_db = True
    _type_prefix = "LocalizedFeaturedSubverbifys"
    CACHE_PREFIX = "featuredsrs:"

    @classmethod
    def get_featured(cls, location):
        return cls.get_localized_srs(location)


class LabeledMulti(tdb_cassandra.Thing, MultiVerbify):
    """Thing with special columns that hold Subverbify ids and properties."""
    _use_db = True
    _views = []
    _bool_props = ('is_symlink', )
    _defaults = dict(
        MultiVerbify._defaults,
        visibility='private',
        is_symlink=False,
        description_md='',
        display_name='',
        copied_from=None,
        key_color="#cee3f8",  # A lovely shade of blue
        icon_id='',
        weighting_scheme="classic",
    )
    _extra_schema_creation_args = {
        "key_validation_class": UTF8_TYPE,
        "column_name_class": UTF8_TYPE,
        "default_validation_class": UTF8_TYPE,
        "column_validation_classes": {
            "date": pycassa.system_manager.DATE_TYPE,
        },
    }
    _float_props = (
        "base_normalized_age_weight",
    )
    _compare_with = UTF8_TYPE
    _read_consistency_level = tdb_cassandra.CL.ONE
    _write_consistency_level = tdb_cassandra.CL.QUORUM

    SR_PREFIX = 'SR_'
    MAX_SR_COUNT = 100

    def __init__(self, _id=None, *args, **kwargs):
        tdb_cassandra.Thing.__init__(self, _id, *args, **kwargs)
        MultiVerbify.__init__(self)
        self._owner = None

    @classmethod
    def _byID(cls, ids, return_dict=True, properties=None, load_subverbifys=True,
              load_linked_multis=True):
        ret = super(cls, cls)._byID(ids, return_dict=False,
                                    properties=properties)
        if not ret:
            # the falsy return object must be converted to the proper type
            # based on whether ids was an iterable and return_dict
            if ret == []:
                if return_dict:
                    return {}
                else:
                    return []
            else:
                return

        ret = cls._load(ret, load_subverbifys=load_subverbifys,
                        load_linked_multis=load_linked_multis)
        if isinstance(ret, cls):
            return ret
        elif return_dict:
            return {thing._id: thing for thing in ret}
        else:
            return ret

    @classmethod
    def _load(cls, things, load_subverbifys=True, load_linked_multis=True):
        things, single = tup(things, ret_is_single=True)

        # some objects are being loaded for the first time and need basic setup
        never_loaded = [t for t in things if not t._owner]
        if never_loaded:
            owner_fullnames = set(t.owner_fullname for t in never_loaded)
            owners = Thing._by_fullname(
                owner_fullnames, data=True, return_dict=True)
            for t in things:
                if t in never_loaded:
                    t._owner = owners[t.owner_fullname]
                    t._srs_loaded = False
                    t._linked_multi = None

        if load_linked_multis:
            needs_linked_multis = [t.copied_from for t in things
                                   if t.is_symlink and not t._linked_multi]
            if needs_linked_multis:
                multis = LabeledMulti._byID(needs_linked_multis, return_dict=True)
                for t in things:
                    if t.copied_from in needs_linked_multis:
                        t._linked_multi = multis[t.copied_from]

        # some objects may have been retrieved from cache and need srs
        if load_subverbifys:
            needs_srs = [t for t in things if not t._srs_loaded]
            if needs_srs:
                sr_ids = set(
                    itertools.chain.from_iterable(t.sr_ids for t in needs_srs))
                srs = Subverbify._byID(
                    sr_ids, data=True, return_dict=True, stale=True)
                for t in things:
                    if t in needs_srs:
                        t._srs = [srs[sr_id] for sr_id in t.sr_ids]
                        t._srs_loaded = True

        return things[0] if single else things

    @property
    def linked_multi(self):
        return self._linked_multi

    @property
    def sr_ids(self):
        return self.sr_props.keys()

    @property
    def srs(self):
        if self.is_symlink:
            if (not self.copied_from or self.copied_from == self._id
                    or not self.linked_multi):
                raise VerbifyError("Upstream symlinked multi can't be retrieved.")
            if not self.linked_multi.can_view(self.owner):
                raise VerbifyError("Upstream symlinked multi is not visible.")

            return self.linked_multi.srs

        if not self._srs_loaded:
            g.log.error("%s: accessed subverbifys without loading", self)
            self._srs = Subverbify._byID(
                self.sr_ids, data=True, return_dict=False)
        return self._srs

    @property
    def owner(self):
        return self._owner

    @property
    def sr_columns(self):
        # limit to max subverbify count, allowing a little fudge room for
        # cassandra inconsistency
        if self.is_symlink:
            if not getattr(self, '_linked_multi', None):
                self._linked_multi = LabeledMulti._byID(self.copied_from)
            return self.linked_multi.sr_columns

        remaining = self.MAX_SR_COUNT + 10
        sr_columns = {}
        for k, v in self._t.iteritems():
            if not k.startswith(self.SR_PREFIX):
                continue

            sr_columns[k] = v

            remaining -= 1
            if remaining <= 0:
                break
        return sr_columns

    @property
    def kind(self):
        return self._id.split('/')[3]

    @property
    def sr_props(self):
        return self.columns_to_sr_props(self.sr_columns)

    @property
    def path(self):
        if isinstance(self.owner, Account):
            return '/user/%(username)s/%(kind)s/%(multiname)s' % {
                'username': self.owner.name,
                'kind': self.kind,
                'multiname': self.name,
            }
        if isinstance(self.owner, Subverbify):
            return '/r/%(srname)s/%(kind)s/%(multiname)s' % {
                'srname': self.owner.name,
                'kind': self.kind,
                'multiname': self.name,
            }

    @property
    def user_path(self):
        if self.owner == c.user:
            return '/me/%s/%s' % (self.kind, self.name)
        else:
            return self.path

    @property
    def name(self):
        return self._id.split('/')[-1]

    @property
    def analytics_name(self):
        # classify as "multi" (as for unnamed multis) until our traffic system
        # is smarter
        return 'multi'

    @property
    def allows_referrers(self):
        if not self.is_public():
            return False
        return super(LabeledMulti, self).allows_referrers

    @property
    def title(self):
        if isinstance(self.owner, Account):
            return _('%s subverbifys curated by /u/%s') % (self.name, self.owner.name)
        return _('%s subverbifys') % self.name

    def is_public(self):
        return self.visibility == "public"

    def is_hidden(self):
        return self.visibility == "hidden"

    def can_view(self, user):
        if c.user_is_admin:
            return True

        if self.is_public():
            return True

        if isinstance(user, FakeAccount):
            return False

        # subverbify multiverbify (mod can view)
        if isinstance(self.owner, Subverbify):
            return self.owner.is_moderator_with_perms(user, 'config')

        return user == self.owner

    def can_edit(self, user):
        if isinstance(user, FakeAccount):
            return False

        # subverbify multiverbify (admin can edit)
        if isinstance(self.owner, Subverbify):
            return (c.user_is_admin or
                    self.owner.is_moderator_with_perms(user, 'config'))

        if c.user_is_admin and self.owner == Account.system_user():
            return True

        return user == self.owner

    @property
    def icon_url(self):
        from v1.lib.template_helpers import static
        if self.icon_id:
            path = "multi_icons/{}.png".format(self.icon_id.replace(" ", "_"))
            return static(path)
        else:
            return None

    def set_icon_by_name(self, name):
        """Set this multi's icon information by icon name

        Note: tdb_cassandra.Thing doesn't support property.setter properly;
        it appears to write through directly to self._t['icon_name'].

        """
        if not name:
            self.icon_id = ''
        elif name in g.multi_icons:
            self.icon_id = name
        else:
            raise ValueError("invalid multi icon name")

    @classmethod
    def by_owner(cls, owner, kinds=None, load_subverbifys=True):
        try:
            multi_ids = LabeledMultiByOwner._byID(owner._fullname)._t.keys()
        except tdb_cassandra.NotFound:
            return []

        kinds = ('m',) if not kinds else kinds
        multis = cls._byID(
            multi_ids, return_dict=False, load_subverbifys=load_subverbifys)
        return [multi for multi in multis if multi.kind in kinds]

    @classmethod
    def create(cls, path, owner):
        obj = cls(_id=path, owner_fullname=owner._fullname)
        obj._commit()
        obj._owner = owner
        obj._srs_loaded = False
        return obj

    @classmethod
    def copy(cls, path, multi, owner, symlink=False):
        if symlink:
            # remove all the sr_ids from the properties
            props = {k: v for k, v in multi._t.iteritems()
                     if k not in multi.sr_columns.keys()}
            props["is_symlink"] = True
        else:
            props = multi._t

        obj = cls(_id=path, **props)
        obj._srs = multi._srs
        obj._srs_loaded = multi._srs_loaded
        obj.owner_fullname = owner._fullname
        obj.copied_from = multi.path.lower()
        obj._commit()
        obj._linked_multi = multi if symlink else None
        obj._owner = owner

        return obj

    @classmethod
    def slugify(cls, owner, display_name, type_="m"):
        """Generate user multi path from display name."""
        slug = unicode_title_to_ascii(display_name)
        if isinstance(owner, Subverbify):
            prefix = "/r/" + owner.name + "/" + type_ + "/"
        else:
            prefix = "/user/" + owner.name + "/" + type_ + "/"
        new_path = prefix + slug
        try:
            existing = LabeledMultiByOwner._byID(owner._fullname)._t.keys()
        except tdb_cassandra.NotFound:
            existing = []
        count = 0
        while new_path in existing:
            count += 1
            new_path = prefix + slug + str(count)
        return new_path

    @classmethod
    def sr_props_to_columns(cls, sr_props):
        columns = {}
        sr_ids = []
        for sr_id, props in sr_props.iteritems():
            if isinstance(sr_id, BaseSite):
                sr_id = sr_id._id
            sr_ids.append(sr_id)
            columns[cls.SR_PREFIX + str(sr_id)] = json.dumps(props)
        return sr_ids, columns

    @classmethod
    def columns_to_sr_props(cls, columns):
        ret = {}
        for s, sr_prop_dump in columns.iteritems():
            sr_id = long(s.strip(cls.SR_PREFIX))
            sr_props = json.loads(sr_prop_dump)
            ret[sr_id] = sr_props
        return ret

    def _on_create(self):
        for view in self._views:
            view.add_object(self)

    def unlink(self):
        if not self.is_symlink:
            return

        self._srs = self.srs
        sr_props = dict.fromkeys(self.srs, {})
        sr_ids, sr_columns = self.sr_props_to_columns(sr_props)
        for attr, val in sr_columns.iteritems():
            self.__setattr__(attr, val)

        self.is_symlink = False

    def add_srs(self, sr_props):
        """Add/overwrite subverbify(s)."""
        if self.is_symlink:
            self.unlink()
        sr_ids, sr_columns = self.sr_props_to_columns(sr_props)

        if len(set(sr_columns) | set(self.sr_columns)) > self.MAX_SR_COUNT:
            raise TooManySubverbifysError

        new_sr_ids = set(sr_ids) - set(self.sr_ids)
        new_srs = Subverbify._byID(
            new_sr_ids, data=True, return_dict=False, stale=True)
        self._srs.extend(new_srs)

        for attr, val in sr_columns.iteritems():
            self.__setattr__(attr, val)

    def del_srs(self, sr_ids):
        """Delete subverbify(s)."""
        if self.is_symlink:
            self.unlink()

        sr_props = dict.fromkeys(tup(sr_ids), {})
        sr_ids, sr_columns = self.sr_props_to_columns(sr_props)

        for key in sr_columns.iterkeys():
            self.__delitem__(key)

        self._srs = [sr for sr in self._srs if sr._id not in sr_ids]

    def clear_srs(self):
        self.del_srs(self.sr_ids)

    def delete(self):
        # Do we want to actually delete objects?
        self._destroy()
        for view in self._views:
            rowkey = view._rowkey(self)
            column = view._obj_to_column(self)
            view._remove(rowkey, column)


@tdb_cassandra.view_of(LabeledMulti)
class LabeledMultiByOwner(tdb_cassandra.View):
    _use_db = True

    @classmethod
    def _rowkey(cls, lm):
        return lm.owner_fullname


class RandomVerbify(FakeSubverbify):
    name = 'random'
    header = ""

class RandomNSFWVerbify(FakeSubverbify):
    name = 'randnsfw'
    header = ""

class RandomSubscriptionVerbify(FakeSubverbify):
    name = 'myrandom'
    header = ""

class ModContribSR(MultiVerbify):
    name  = None
    title = None
    query_param = None
    _defaults = dict(
        MultiVerbify._defaults,
        login_required=True,
    )

    def __init__(self):
        # Can't lookup srs right now, c.user not set
        MultiVerbify.__init__(self)

    @property
    def sr_ids(self):
        if c.user_is_loggedin:
            return Subverbify.special_verbifys(c.user, self.query_param)
        else:
            return []

    @property
    def srs(self):
        return Subverbify._byID(self.sr_ids, data=True, return_dict=False)

    @property
    def allows_referrers(self):
        return False


class ModSR(ModContribSR):
    name  = "subverbifys you moderate"
    title = "subverbifys you moderate"
    query_param = "moderator"
    path = "/r/mod"

    def is_moderator(self, user):
        return FakeSRMember(ModeratorPermissionSet)


class ModMinus(ModSR):
    analytics_name = "mod"

    def __init__(self, exclude_srs):
        ModSR.__init__(self)
        self.exclude_srs = exclude_srs
        self.exclude_sr_ids = [sr._id for sr in exclude_srs]

    @property
    def sr_ids(self):
        sr_ids = super(ModMinus, self).sr_ids
        return [sr_id for sr_id in sr_ids if not sr_id in self.exclude_sr_ids]

    @property
    def name(self):
        exclude_text = ', '.join(sr.name for sr in self.exclude_srs)
        return 'subverbifys you moderate except ' + exclude_text

    @property
    def title(self):
        return self.name

    @property
    def path(self):
        return '/r/mod-' + '-'.join(sr.name for sr in self.exclude_srs)


class ModFiltered(Filtered, ModMinus):
    unfiltered_path = '/r/mod'
    filtername = 'mod'

    def __init__(self):
        ModMinus.__init__(self, self._get_filtered_subverbifys())


class ContribSR(ModContribSR):
    name  = "contrib"
    title = "communities you're approved on"
    query_param = "contributor"
    path = "/r/contrib"


class DomainSR(FakeSubverbify):
    @property
    def path(self):
        return '/domain/' + self.domain

    def __init__(self, domain):
        FakeSubverbify.__init__(self)
        domain = domain.lower()
        self.domain = domain
        self.name = domain
        self.title = _("%(domain)s on %(verbify.com)s") % {
            "domain": domain, "verbify.com": g.domain}
        try:
            idn = domain.decode('idna')
            if idn != domain:
                self.idn = idn
        except UnicodeError:
            # If we were given a bad domain name (e.g. xn--.com) we'll get an
            # error here. These domains are invalid to register so it should
            # be fine to ignore the error.
            pass

    def get_links(self, sort, time):
        from v1.lib.db import queries
        return queries.get_domain_links(self.domain, sort, time)

    @property
    def allow_silding(self):
        return False


class SearchResultSubverbify(Subverbify):
    _nodb = True

    @classmethod
    def add_props(cls, user, wrapped):
        from v1.controllers.verbify_base import UnloggedUser
        Subverbify.add_props(user, wrapped)
        for item in wrapped:
            url = UrlParser(item.path)
            url.update_query(ref="search_subverbifys")
            item.search_path = url.unparse()
            can_view = item.can_view(user)
            if isinstance(user, UnloggedUser):
                can_comment = item.type == "public"
            else:
                can_comment = item.can_comment(user)
            if not can_view:
                item.display_type = "private"
            elif item.type == "archived":
                item.display_type = "archived"
            elif not can_comment:
                item.display_type = "restricted"
            else:
                item.display_type = "public"
        Printable.add_props(user, wrapped)

Frontpage = DefaultSR()
Friends = FriendsSR()
Mod = ModSR()
Contrib = ContribSR()
All = AllSR()
Random = RandomVerbify()
RandomNSFW = RandomNSFWVerbify()
RandomSubscription = RandomSubscriptionVerbify()

# add to _specials so they can be retrieved with Subverbify._by_name, e.g.
# Subverbify._by_name("all")
Subverbify._specials.update({
    sr.name: sr for sr in (
        Friends,
        RandomNSFW,
        RandomSubscription,
        Random,
        Contrib,
        All,
        Frontpage,
    )
})

# some subverbifys have unfortunate names
Subverbify._specials['mod'] = Mod


SubverbifyUserRelations = collections.namedtuple(
    "SubverbifyUserRelations",
    ["subscriber", "moderator", "contributor", "banned", "muted"],
)


class SRMember(Relation(Subverbify, Account)):
    _defaults = dict(encoded_permissions=None)
    _permission_class = None
    _cache = g.srmembercache
    _rel_cache = g.srmembercache

    @classmethod
    def _cache_prefix(cls):
        return "srmember:"

    @classmethod
    def _rel_cache_prefix(cls):
        return "srmemberrel:"

    def has_permission(self, perm):
        """Returns whether this member has explicitly been granted a permission.
        """
        return self.get_permissions().get(perm, False)

    def get_permissions(self):
        """Returns permission set for this member (or None if N/A)."""
        if not self._permission_class:
            raise NotImplementedError
        return self._permission_class.loads(self.encoded_permissions)

    def update_permissions(self, **kwargs):
        """Grants or denies permissions to this member.

        Args are named parameters with bool or None values (use None to disable
        granting or denying the permission). After calling this method,
        the relation will be _dirty until _commit is called.
        """
        if not self._permission_class:
            raise NotImplementedError
        perm_set = self._permission_class.loads(self.encoded_permissions)
        if perm_set is None:
            perm_set = self._permission_class()
        for k, v in kwargs.iteritems():
            if v is None:
                if k in perm_set:
                    del perm_set[k]
            else:
                perm_set[k] = v
        self.encoded_permissions = perm_set.dumps()

    def set_permissions(self, perm_set):
        """Assigns a permission set to this relation."""
        self.encoded_permissions = perm_set.dumps()

    def is_superuser(self):
        return self.get_permissions().is_superuser()


class FakeSRMember:
    """All-permission granting stub for SRMember, used by FakeSubverbifys."""
    def __init__(self, permission_class):
        self.permission_class = permission_class

    def has_permission(self, perm):
        return True

    def get_permissions(self):
        return self.permission_class(all=True)

    def is_superuser(self):
        return True


Subverbify.__bases__ += (
    UserRel('moderator', SRMember,
            permission_class=ModeratorPermissionSet),
    UserRel('moderator_invite', SRMember,
            permission_class=ModeratorPermissionSet),
    UserRel('contributor', SRMember, disable_ids_fn=True),
    UserRel('banned', SRMember, disable_ids_fn=True),
    UserRel('muted', SRMember, disable_ids_fn=True),
    UserRel('wikibanned', SRMember),
    UserRel('wikicontributor', SRMember),
)


def add_legacy_subscriber(srs, user):
    srs = tup(srs)
    for sr in srs:
        rel = SRMember(sr, user, "subscriber")
        try:
            rel._commit()
        except CreationError:
            break


def remove_legacy_subscriber(sr, user):
    rels = SRMember._fast_query([sr], [user], "subscriber")
    rel = rels.get((sr, user, "subscriber"))
    if rel:
        rel._delete()


class SubverbifyTempBan(object):
    def __init__(self, sr, kind, victim, banner, duration):
        self.sr = sr._id36
        self._srname = sr.name
        self.who = victim._id36
        self._whoname = victim.name
        self.type = kind
        self.banner = banner._id36
        self.duration = duration

    @classmethod
    def schedule(cls, sr, kind, victim, banner, duration):
        info = {
            'sr': sr._id36,
            'who': victim._id36,
            'type': kind,
            'banner': banner._id36,
        }
        result = TryLaterBySubject.schedule(
            cls.cancel_rowkey(sr.name, kind),
            cls.cancel_colkey(victim.name),
            json.dumps(info),
            duration,
            trylater_rowkey=cls.schedule_rowkey(),
        )
        return {victim.name: result.keys()[0]}

    @classmethod
    def cancel_colkey(cls, name):
        return name

    @classmethod
    def cancel_rowkey(cls, name, type):
        return "srunban:%s:%s" % (name, type)

    @classmethod
    def schedule_rowkey(cls):
        return "srunban"

    @classmethod
    def search(cls, srname, bantype, subjects):
        results = TryLaterBySubject.search(cls.cancel_rowkey(srname, bantype),
                                           subjects)

        def convert_uuid_to_datetime(uu):
            return datetime.datetime.fromtimestamp(convert_uuid_to_time(uu),
                                                   g.tz)
        return {
            name: convert_uuid_to_datetime(uu)
                for name, uu in results.iteritems()
        }

    @classmethod
    def unschedule(cls, srname, victim_name, bantype):
        TryLaterBySubject.unschedule(
            cls.cancel_rowkey(srname, bantype),
            cls.cancel_colkey(victim_name),
            cls.schedule_rowkey(),
        )


@trylater_hooks.on('trylater.srunban')
def on_subverbify_unban(data):
    from v1.models.modaction import ModAction
    for blob in data.itervalues():
        baninfo = json.loads(blob)
        container = Subverbify._byID36(baninfo['sr'], data=True)
        victim = Account._byID36(baninfo['who'], data=True)
        banner = Account._byID36(baninfo['banner'], data=True)
        kind = baninfo['type']
        remove_function = getattr(container, 'remove_' + kind)
        new = remove_function(victim)
        g.log.info("Unbanned %s from %s", victim.name, container.name)

        if new:
            action = dict(
                banned='unbanuser',
                wikibanned='wikiunbanned',
            ).get(kind, None)
            ModAction.create(container, banner, action, target=victim,
                             description="was temporary")


class MutedAccountsBySubverbify(object):
    @classmethod
    def mute(cls, sr, user, muter, parent_message=None):
        NUM_HOURS = 72

        from v1.lib.db import queries
        from v1.models import Message, ModAction
        info = {
            'sr': sr._id36,
            'who': user._id36,
            'muter': muter._id36,
        }

        result = TryLaterBySubject.schedule(
            cls.cancel_rowkey(sr),
            cls.cancel_colkey(user),
            json.dumps(info),
            datetime.timedelta(hours=NUM_HOURS),
            trylater_rowkey=cls.schedule_rowkey(),
        )

        #if the user has interacted with the subverbify before, message them
        if user.has_interacted_with(sr):
            subject = "You have been muted from r/%(subverbifyname)s"
            subject %= dict(subverbifyname=sr.name)
            message = ("You have been [temporarily muted](%(muting_link)s) "
                "from r/%(subverbifyname)s. You will not be able to message "
                "the moderators of r/%(subverbifyname)s for %(num_hours)s hours.")
            message %= dict(
                muting_link="https://verbify.zendesk.com/hc/en-us/articles/205269739",
                subverbifyname=sr.name,
                num_hours=NUM_HOURS,
            )
            if parent_message:
                subject = parent_message.subject
                re = "re: "
                if not subject.startswith(re):
                    subject = re + subject

            item, inbox_rel = Message._new(muter, user, subject, message,
                request.ip, parent=parent_message, sr=sr, from_sr=True)
            queries.new_message(item, inbox_rel, update_modmail=True)

        return {user.name: result.keys()[0]}

    @classmethod
    def cancel_colkey(cls, user):
        return user.name

    @classmethod
    def cancel_rowkey(cls, subverbify):
        return "srmute:%s" % subverbify.name

    @classmethod
    def schedule_rowkey(cls):
        return "srmute"

    @classmethod
    def search(cls, subverbify, subjects):
        results = TryLaterBySubject.search(cls.cancel_rowkey(subverbify),
                                           subjects)

        return {
            name: datetime.datetime.fromtimestamp(convert_uuid_to_time(uu),
                    g.tz)
                for name, uu in results.iteritems()
        }

    @classmethod
    def unmute(cls, sr, user, automatic=False):
        from v1.models import ModAction

        TryLaterBySubject.unschedule(
            cls.cancel_rowkey(sr),
            cls.cancel_colkey(user),
            cls.schedule_rowkey(),
        )

        if automatic:
            unmuter = Account.system_user()
            ModAction.create(sr, unmuter, 'unmuteuser', target=user)


@trylater_hooks.on('trylater.srmute')
def unmute_hook(data):
    for blob in data.itervalues():
        muteinfo = json.loads(blob)
        subverbify = Subverbify._byID36(muteinfo['sr'], data=True)
        user = Account._byID36(muteinfo['who'], data=True)

        subverbify.remove_muted(user)
        MutedAccountsBySubverbify.unmute(subverbify, user, automatic=True)


class SubverbifysActiveForFrontPage(tdb_cassandra.View):
    """Tracks which subverbifys currently have valid frontpage posts.

    The front page's "hot" page only includes posts that are newer than
    g.HOT_PAGE_AGE, so there's no point including subverbifys in it if they
    haven't had a post inside that period. Since we pick random subsets of
    users' subscriptions when they subscribe to more subverbifys than we
    build the page from, this means that inactive subverbifys can effectively
    "waste" some of these slots, since they may not have any posts that can
    possibly be added to the page.

    This CF will get an entry inserted for each subverbify whenever a new
    post is made in that subverbify, with a TTL equal to g.HOT_PAGE_AGE. We
    will then be able to query it to determine which subverbifys don't have
    any posts recent enough to contribute to the front page, and exclude
    them from consideration for a user's front page set.
    """

    _use_db = True
    _connection_pool = "main"
    _ttl = datetime.timedelta(days=g.HOT_PAGE_AGE)
    _extra_schema_creation_args = {
        "key_validation_class": ASCII_TYPE,
    }
    _read_consistency_level = tdb_cassandra.CL.ONE
    _write_consistency_level = tdb_cassandra.CL.QUORUM

    ROWKEY = "1"

    @classmethod
    def mark_new_post(cls, subverbify):
        cls._set_values(cls.ROWKEY, {subverbify._id36: ""})

    @classmethod
    def filter_inactive_ids(cls, subverbify_ids):
        sr_id36s = [to36(sr_id) for sr_id in subverbify_ids]
        try:
            results = cls._cf.get(cls.ROWKEY, columns=sr_id36s)
        except tdb_cassandra.NotFoundException:
            results = {}

        num_filtered = len(subverbify_ids) - len(results)
        g.stats.simple_event("frontpage.filter_inactive", delta=num_filtered)

        return [int(sr_id36, 36) for sr_id36 in results.keys()]
