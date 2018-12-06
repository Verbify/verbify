from collections import defaultdict
from datetime import datetime

from pylons import app_globals as g

from v1.lib.db.operators import desc
from v1.lib.utils import fetch_things2
from v1.models import (
    calculate_server_seconds,
    Comment,
    Link,
    Subverbify,
)

LINK_SILDING_START = datetime(2014, 2, 1, 0, 0, tzinfo=g.tz)
COMMENT_SILDING_START = datetime(2012, 10, 1, 0, 0, tzinfo=g.tz)

queries = [
    Link._query(
        Link.c.sildings != 0, Link.c._date > LINK_SILDING_START, data=True,
        sort=desc('_date'),
    ),
    Comment._query(
        Comment.c.sildings != 0, Comment.c._date > COMMENT_SILDING_START,
        data=True, sort=desc('_date'),
    ),
]

seconds_by_srid = defaultdict(int)
silding_price = g.sodium_month_price.pennies

for q in queries:
    for things in fetch_things2(q, chunks=True, chunk_size=100):
        print things[0]._fullname

        for thing in things:
            seconds_per_silding = calculate_server_seconds(silding_price, thing._date)
            seconds_by_srid[thing.sr_id] += int(thing.sildings * seconds_per_silding)

for sr_id, seconds in seconds_by_srid:
    sr = Subverbify._byID(sr_id, data=True)
    print "%s: %s seconds" % (sr.name, seconds)
    sr._incr("silding_server_seconds", seconds)
