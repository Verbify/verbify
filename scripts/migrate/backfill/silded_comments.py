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
"""Fill in the silded comment listing.

This listing is stored in get_silded_comments and seen on /comments/silded.

"""

import datetime

from pylons import app_globals as g

from v1.lib.db.queries import get_silded_comments, get_all_silded_comments
from v1.lib.utils import Storage
from v1.models import SildingsByDay, Thing, Comment
from v1.models.query_cache import CachedQueryMutator


date = datetime.datetime.now(g.tz)
earliest_date = datetime.datetime(2012, 10, 01, tzinfo=g.tz)

already_seen = set()

with CachedQueryMutator() as m:
    while date > earliest_date:
        sildings = SildingsByDay.get_sildings(date)
        fullnames = [x["thing"] for x in sildings]
        things = Thing._by_fullname(fullnames, data=True, return_dict=False)
        comments = {t._fullname: t for t in things if isinstance(t, Comment)}

        for silding in sildings:
            fullname = silding["thing"]
            if fullname in comments and fullname not in already_seen:
                thing = silding["thing"] = comments[fullname]
                silding_object = Storage(silding)
                m.insert(get_silded_comments(thing.sr_id), [silding_object])
                m.insert(get_all_silded_comments(), [silding_object])
                already_seen.add(fullname)
        date -= datetime.timedelta(days=1)
