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

from v1.lib.db.tdb_sql import make_metadata, index_str, create_table

import json
import pytz
import uuid

from pycassa import NotFoundException
from pycassa.system_manager import ASCII_TYPE, INT_TYPE, TIME_UUID_TYPE, UTF8_TYPE
from pycassa.util import convert_uuid_to_time
from pylons import tmpl_context as c
from pylons import app_globals as g
from pylons.i18n import _, ungettext
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.functions import sum as sa_sum

from v1.lib.utils import SodiumPrice, randstr, to_date
import re
from random import choice
from time import time

from v1.lib.db import tdb_cassandra
from v1.lib.db.tdb_cassandra import NotFound, view_of
from v1.models import Account
from v1.models.subverbify import Frontpage
from v1.models.wiki import WikiPage, WikiPageIniItem
from v1.lib.memoize import memoize

import stripe

sodium_bonus_cutoff = datetime(2010,7,27,0,0,0,0,g.tz)
sodium_static_goal_cutoff = datetime(2013, 11, 7, tzinfo=g.display_tz)

NON_REVENUE_STATUSES = ("declined", "chargeback", "fudge", "invalid",
                        "refunded", "reversed")

ENGINE_NAME = 'authorize'

ENGINE = g.dbm.get_engine(ENGINE_NAME)
METADATA = make_metadata(ENGINE)
TIMEZONE = pytz.timezone("America/Los_Angeles")

Session = scoped_session(sessionmaker(bind=ENGINE))
Base = declarative_base(bind=ENGINE)

sodium_table = sa.Table('verbify_sodium', METADATA,
                      sa.Column('trans_id', sa.String, nullable = False,
                                primary_key = True),
                      # status can be: invalid, unclaimed, claimed
                      sa.Column('status', sa.String, nullable = False),
                      sa.Column('date', sa.DateTime(timezone=True),
                                nullable = False,
                                default = sa.func.now()),
                      sa.Column('payer_email', sa.String, nullable = False),
                      sa.Column('paying_id', sa.String, nullable = False),
                      sa.Column('pennies', sa.Integer, nullable = False),
                      sa.Column('secret', sa.String, nullable = True),
                      sa.Column('account_id', sa.String, nullable = True),
                      sa.Column('days', sa.Integer, nullable = True),
                      sa.Column('subscr_id', sa.String, nullable = True),
                      sa.Column('silding_type', sa.String, nullable = True))

indices = [index_str(sodium_table, 'status', 'status'),
           index_str(sodium_table, 'date', 'date'),
           index_str(sodium_table, 'account_id', 'account_id'),
           index_str(sodium_table, 'secret', 'secret'),
           index_str(sodium_table, 'payer_email', 'payer_email'),
           index_str(sodium_table, 'subscr_id', 'subscr_id')]
create_table(sodium_table, indices)


class SodiumRevenueGoalByDate(object):
    __metaclass__ = tdb_cassandra.ThingMeta

    _use_db = True
    _cf_name = "SodiumRevenueGoalByDate"
    _read_consistency_level = tdb_cassandra.CL.ONE
    _write_consistency_level = tdb_cassandra.CL.ALL
    _extra_schema_creation_args = {
        "column_name_class": UTF8_TYPE,
        "default_validation_class": INT_TYPE,
    }
    _compare_with = UTF8_TYPE
    _type_prefix = None

    ROWKEY = '1'

    @staticmethod
    def _colkey(date):
        return date.strftime("%Y-%m-%d")

    @classmethod
    def set(cls, date, goal):
        cls._cf.insert(cls.ROWKEY, {cls._colkey(date): int(goal)})

    @classmethod
    def get(cls, date):
        """Gets the goal for a date, or the nearest previous goal."""
        try:
            colkey = cls._colkey(date)
            col = cls._cf.get(
                cls.ROWKEY,
                column_reversed=True,
                column_start=colkey,
                column_count=1,
            )
            return col.values()[0]
        except NotFoundException:
            return None


class SildedCommentsByAccount(tdb_cassandra.DenormalizedRelation):
    _use_db = True
    _last_modified_name = 'Silding'
    _views = []

    @classmethod
    def value_for(cls, thing1, thing2):
        return ''

    @classmethod
    def sild(cls, user, thing):
        cls.create(user, [thing])


class SildedLinksByAccount(tdb_cassandra.DenormalizedRelation):
    _use_db = True
    _last_modified_name = 'Silding'
    _views = []

    @classmethod
    def value_for(cls, thing1, thing2):
        return ''

    @classmethod
    def sild(cls, user, thing):
        cls.create(user, [thing])


@view_of(SildedCommentsByAccount)
@view_of(SildedLinksByAccount)
class SildingsByThing(tdb_cassandra.View):
    _use_db = True
    _extra_schema_creation_args = {
        "key_validation_class": UTF8_TYPE,
        "column_name_class": UTF8_TYPE,
    }

    @classmethod
    def get_silder_ids(cls, thing):
        columns = cls.get_time_sorted_columns(thing._fullname)
        return [int(account_id, 36) for account_id in columns.iterkeys()]

    @classmethod
    def create(cls, user, things):
        for thing in things:
            cls._set_values(thing._fullname, {user._id36: ""})

    @classmethod
    def delete(cls, user, things):
        # sildings cannot be undone
        raise NotImplementedError()


@view_of(SildedCommentsByAccount)
@view_of(SildedLinksByAccount)
class SildingsByDay(tdb_cassandra.View):
    _use_db = True
    _compare_with = TIME_UUID_TYPE
    _extra_schema_creation_args = {
        "key_validation_class": ASCII_TYPE,
        "column_name_class": TIME_UUID_TYPE,
        "default_validation_class": UTF8_TYPE,
    }

    @staticmethod
    def _rowkey(date):
        return date.strftime("%Y-%m-%d")

    @classmethod
    def get_sildings(cls, date):
        key = cls._rowkey(date)
        columns = cls.get_time_sorted_columns(key)
        sildings = []
        for name, json_blob in columns.iteritems():
            timestamp = convert_uuid_to_time(name)
            date = datetime.utcfromtimestamp(timestamp).replace(tzinfo=g.tz)

            silding = json.loads(json_blob)
            silding["date"] = date
            silding["user"] = int(silding["user"], 36)
            sildings.append(silding)
        return sildings

    @classmethod
    def create(cls, user, things):
        key = cls._rowkey(datetime.now(g.tz))

        columns = {}
        for thing in things:
            columns[uuid.uuid1()] = json.dumps({
                "user": user._id36,
                "thing": thing._fullname,
            })
        cls._set_values(key, columns)

    @classmethod
    def delete(cls, user, things):
        # sildings cannot be undone
        raise NotImplementedError()


def create_unclaimed_sodium (trans_id, payer_email, paying_id,
                           pennies, days, secret, date,
                           subscr_id = None):

    try:
        sodium_table.insert().execute(trans_id=str(trans_id),
                                    subscr_id=subscr_id,
                                    status="unclaimed",
                                    payer_email=payer_email,
                                    paying_id=paying_id,
                                    pennies=pennies,
                                    days=days,
                                    secret=str(secret),
                                    date=date
                                    )
    except IntegrityError:
        rp = sodium_table.update(
            sa.and_(sodium_table.c.status == 'uncharged',
                    sodium_table.c.trans_id == str(trans_id)),
            values = {
                sodium_table.c.status: "unclaimed",
                sodium_table.c.payer_email: payer_email,
                sodium_table.c.paying_id: paying_id,
                sodium_table.c.pennies: pennies,
                sodium_table.c.days: days,
                sodium_table.c.secret:secret,
                sodium_table.c.subscr_id : subscr_id
                },
            ).execute()


def create_claimed_sodium (trans_id, payer_email, paying_id,
                         pennies, days, secret, account_id, date,
                         subscr_id = None, status="claimed"):
    sodium_table.insert().execute(trans_id=trans_id,
                                subscr_id=subscr_id,
                                status=status,
                                payer_email=payer_email,
                                paying_id=paying_id,
                                pennies=pennies,
                                days=days,
                                secret=secret,
                                account_id=account_id,
                                date=date)


def create_gift_sodium(giver_id, recipient_id, days, date,
            signed, note=None, silding_type=None):
    trans_id = "X%d%s-%s" % (int(time()), randstr(2), 'S' if signed else 'A')
    sodium_table.insert().execute(
        trans_id=trans_id,
        status="gift",
        paying_id=giver_id,
        payer_email='',
        pennies=0,
        days=days,
        account_id=recipient_id,
        date=date,
        secret=note,
        silding_type=silding_type,
    )


def create_sodium_code(trans_id, payer_email, paying_id, pennies, days, date):
    if not trans_id:
        trans_id = "GC%d%s" % (int(time()), randstr(2))

    valid_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    # keep picking new codes until we find an unused one
    while True:
        code = randstr(10, alphabet=valid_chars)

        s = sa.select([sodium_table],
                      sa.and_(sodium_table.c.secret == code.lower(),
                              sodium_table.c.status == 'unclaimed'))
        res = s.execute().fetchall()
        if not res:
            sodium_table.insert().execute(
                trans_id=trans_id,
                status='unclaimed',
                payer_email=payer_email,
                paying_id=paying_id,
                pennies=pennies,
                days=days,
                secret=code.lower(),
                date=date)
            return code


def account_by_payingid(paying_id):
    s = sa.select([sa.distinct(sodium_table.c.account_id)],
                  sodium_table.c.paying_id == paying_id)
    res = s.execute().fetchall()

    if len(res) != 1:
        return None

    return int(res[0][0])

# returns None if the ID was never valid
# returns "already claimed" if it's already been claimed
# Otherwise, it's valid and the function claims it, returning a tuple with:
#   * the number of days
#   * the subscr_id, if any
def claim_sodium(secret, account_id):
    if not secret:
        return None

    # The donation email has the code at the end of the sentence,
    # so they might get sloppy and catch the period or some whitespace.
    secret = secret.strip(". ")
    secret = secret.replace("-", "").lower()

    rp = sodium_table.update(sa.and_(sodium_table.c.status == 'unclaimed',
                                   sodium_table.c.secret == secret),
                           values = {
                                      sodium_table.c.status: 'claimed',
                                      sodium_table.c.account_id: account_id,
                                    },
                           ).execute()
    if rp.rowcount == 0:
        just_claimed = False
    elif rp.rowcount == 1:
        just_claimed = True
    else:
        raise ValueError("rowcount == %d?" % rp.rowcount)

    s = sa.select([sodium_table.c.days, sodium_table.c.subscr_id],
                  sodium_table.c.secret == secret,
                  limit = 1)
    rows = s.execute().fetchall()

    if not rows:
        return None
    elif just_claimed:
        return (rows[0].days, rows[0].subscr_id)
    else:
        return "already claimed"

def check_by_email(email):
    s = sa.select([sodium_table.c.status,
                           sodium_table.c.secret,
                           sodium_table.c.days,
                           sodium_table.c.account_id],
                          sodium_table.c.payer_email == email)
    return s.execute().fetchall()


def has_prev_subscr_payments(subscr_id):
    s = sa.select([sodium_table], sodium_table.c.subscr_id == subscr_id)
    return bool(s.execute().fetchall())


def retrieve_sodium_transaction(transaction_id):
    s = sa.select([sodium_table], sodium_table.c.trans_id == transaction_id)
    res = s.execute().fetchall()
    if res:
        return res[0]   # single row per transaction_id


def update_sodium_transaction(transaction_id, status):
    rp = sodium_table.update(sodium_table.c.trans_id == str(transaction_id),
                           values={sodium_table.c.status: status}).execute()


def transactions_by_user(user):
    s = sa.select([sodium_table], sodium_table.c.account_id == str(user._id))
    res = s.execute().fetchall()
    return res


def sodium_payments_by_user(user):
    transactions = transactions_by_user(user)

    # filter out received gifts
    transactions = [trans for trans in transactions
                          if not trans.trans_id.startswith(('X', 'M'))]

    return transactions


def sodium_received_by_user(user):
    transactions = transactions_by_user(user)
    transactions = [trans for trans in transactions
                          if trans.trans_id.startswith('X')]
    return transactions


def days_to_pennies(days):
    if days < 366:
        months = days / 31
        return months * g.sodium_month_price.pennies
    else:
        years = days / 366
        return years * g.sodium_year_price.pennies


def append_random_bottlecap_phrase(message):
    """Appends a random "bottlecap" phrase from the wiki page.

    The wiki page should be an unordered list with each item a separate
    bottlecap.
    """

    bottlecap = None
    try:
        wp = WikiPage.get(Frontpage, g.wiki_page_sodium_bottlecaps)

        split_list = re.split('^[*-] ', wp.content, flags=re.MULTILINE)
        choices = [item.strip() for item in split_list if item.strip()]
        if len(choices):
            bottlecap = choice(choices)
    except NotFound:
        pass

    if bottlecap:
        message += '\n\n> ' + bottlecap
    return message


def sodium_revenue_multi(dates):
    date_expr = sa.func.date_trunc('day',
                    sa.func.timezone(TIMEZONE.zone, sodium_table.c.date))
    query = (select([date_expr, sa_sum(sodium_table.c.pennies)])
                .where(~ sodium_table.c.status.in_(NON_REVENUE_STATUSES))
                .where(date_expr.in_(dates))
                .group_by(date_expr)
            )
    return {truncated_time.date(): pennies
                for truncated_time, pennies in ENGINE.execute(query)}


@memoize("sodium-revenue-volatile", time=600, stale=True)
def sodium_revenue_volatile(date):
    return sodium_revenue_multi([date]).get(date, 0)


@memoize("sodium-revenue-steady", stale=True)
def sodium_revenue_steady(date):
    return sodium_revenue_multi([date]).get(date, 0)


@memoize("sodium-goal", stale=True)
def sodium_goal_on(date):
    """Returns the sodium revenue goal (in pennies) for a given date."""
    goal = SodiumRevenueGoalByDate.get(date)

    if not goal:
        return 0

    return float(goal)


def account_from_stripe_customer_id(stripe_customer_id):
    q = Account._query(Account.c.sodium_subscr_id == stripe_customer_id,
                       Account.c._spam == (True, False), data=True)
    return next(iter(q), None)


@memoize("subscription-details", time=60)
def _get_subscription_details(stripe_customer_id):
    stripe.api_key = g.secrets['stripe_secret_key']
    customer = stripe.Customer.retrieve(stripe_customer_id)

    if getattr(customer, 'deleted', False):
        return {}

    subscription = customer.subscription
    card = customer.active_card
    end = datetime.fromtimestamp(subscription.current_period_end).date()
    last4 = card.last4
    pennies = subscription.plan.amount

    return {
        'next_charge_date': end,
        'credit_card_last4': last4,
        'pennies': pennies,
    }


def get_subscription_details(user):
    if not getattr(user, 'sodium_subscr_id', None):
        return

    return _get_subscription_details(user.sodium_subscr_id)


def paypal_subscription_url():
    return "https://www.paypal.com/cgi-bin/webscr?cmd=_subscr-find&alias=%s" % g.sodiumpayment_email


def get_discounted_price(sodium_price):
    discount = float(getattr(g, 'BTC_DISCOUNT', '0'))
    price = (sodium_price.pennies * (1 - discount)) / 100.
    return SodiumPrice("%.2f" % price)


def make_sodium_message(thing, user_silded):
    from v1.models import Comment

    if thing.sildings == 0 or thing._spam or thing._deleted:
        return None

    author = Account._byID(thing.author_id, data=True)
    if not author._deleted:
        author_name = author.name
    else:
        author_name = _("[deleted]")

    if c.user_is_loggedin and thing.author_id == c.user._id:
        if isinstance(thing, Comment):
            silded_message = ungettext(
                "a verbifyor gifted you a month of verbify sodium for this "
                "comment.",
                "verbifyors have gifted you %(months)d months of verbify sodium "
                "for this comment.",
                thing.sildings
            )
        else:
            silded_message = ungettext(
                "a verbifyor gifted you a month of verbify sodium for this "
                "submission.",
                "verbifyors have gifted you %(months)d months of verbify sodium "
                "for this submission.",
                thing.sildings
            )
    elif user_silded:
        if isinstance(thing, Comment):
            silded_message = ungettext(
                "you have gifted verbify sodium to %(recipient)s for this "
                "comment.",
                "you and other verbifyors have gifted %(months)d months of "
                "verbify sodium to %(recipient)s for this comment.",
                thing.sildings
            )
        else:
            silded_message = ungettext(
                "you have gifted verbify sodium to %(recipient)s for this "
                "submission.",
                "you and other verbifyors have gifted %(months)d months of "
                "verbify sodium to %(recipient)s for this submission.",
                thing.sildings
            )
    else:
        if isinstance(thing, Comment):
            silded_message = ungettext(
                "a verbifyor has gifted verbify sodium to %(recipient)s for this "
                "comment.",
                "verbifyors have gifted %(months)d months of verbify sodium to "
                "%(recipient)s for this comment.",
                thing.sildings
            )
        else:
            silded_message = ungettext(
                "a verbifyor has gifted verbify sodium to %(recipient)s for this "
                "submission.",
                "verbifyors have gifted %(months)d months of verbify sodium to "
                "%(recipient)s for this submission.",
                thing.sildings
            )

    return silded_message % dict(
        recipient=author_name,
        months=thing.sildings,
    )


def cverbifys_lock(user):
    return g.make_lock("sodium_cverbifys", "cverbifys_%s" % user._id)


PENNIES_PER_SERVER_SECOND = {
    datetime.strptime(datestr, "%Y/%m/%d").date(): v
    for datestr, v in g.live_config['pennies_per_server_second'].iteritems()
}


def calculate_server_seconds(pennies, date):
    cutoff_dates = sorted(PENNIES_PER_SERVER_SECOND.keys())
    date = to_date(date)
    key = max(filter(lambda cutoff_date: date >= cutoff_date, cutoff_dates))
    rate = PENNIES_PER_SERVER_SECOND[key]

    # for simplicity all payment processor fees are $0.30 + 2.9%
    net_pennies = pennies * (1 - 0.029) - 30

    return net_pennies / rate


def get_current_value_of_month():
    price = g.sodium_month_price.pennies
    now = datetime.now(g.display_tz)
    seconds = calculate_server_seconds(price, now)
    return seconds


class StylesheetsEverywhere(WikiPageIniItem):
    @classmethod
    def _get_wiki_config(cls):
        return Frontpage, g.wiki_page_stylesheets_everywhere

    def __init__(self, id, tagline, thumbnail_url, preview_url, is_enabled=True):
        self.id = id
        self.tagline = tagline
        self.thumbnail_url = thumbnail_url
        self.preview_url = preview_url
        self.is_enabled = is_enabled
        self.checked = False
