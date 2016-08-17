# coding=utf8

"""Defines the various functions to support the mondo fuse filesystem."""

import calendar
import datetime
import json

import diazed
from mondofs.decorators import cache, singleton, appendnewline, to_2dp
from mondofs.diazed import readdir, readlink, mixed
from mondofs.mondo import MondoAPI


def transaction_list_cache():
    """Caches the result from listing all transactions in a given month. This
    transaction object only contains partial info (e.g. no merchant details).

    :returns: a singleton dict instance that can be used as a cache.
    """
    try:
        return singleton('transaction-list-cache')
    except:
        return singleton('transaction-list-cache', {})


@cache(datetime.timedelta(minutes=5))
def _get_transaction(transaction_id, merchant):
    """Return a transaction dict for the transaction with the given id.
    Optionally with merchant details.

    :param transaction_id: The transaction id to fetch.
    :param merchant: Whether to fetch merchant details.
    :returns: A transaction object optionally with merchant details.
    """
    # If we're not getting merchant details and we've seen this in the list
    # cache then we can fetch it from there :)
    cache = transaction_list_cache()
    if not merchant and transaction_id in cache:
        return cache[transaction_id]

    return singleton(MondoAPI).get_transaction(transaction_id, merchant)


@readdir('/')
@cache(datetime.timedelta(days=1))
def list_accounts():
    """List out all the account IDs for the current user."""
    return [a['id'] for a in singleton(MondoAPI).get_accounts()]


@readdir('/<account>')
@cache(datetime.timedelta(days=1))
def list_account(account_id):
    """For a specific account list the subfolders that are available."""
    return ['transactions', 'balance']


@readdir('/<account>/transactions')
def transactions(account_id):
    """List out the years for which we could have transaction data."""
    return [str(y) for y in xrange(2015, datetime.datetime.now().year + 1)]


@readdir('/<account>/transactions/<year>')
def months_in_year(account_id, year):
    """List out the months for which transaction data could be avaialble."""
    today = datetime.datetime.now()
    if int(year) != today.year:
        return ['%02d' % m for m in xrange(1, 13)]
    else:
        return ['%02d' % m for m in xrange(1, today.month + 1)]


@readdir('/<account>/transactions/<year>/<month>')
@cache(datetime.timedelta(minutes=1))
def transactions_in_year_month(account_id, year, month):
    """List the transaction ids that occurred in the given year/month."""
    year = int(year)
    month = int(month)
    date_from = datetime.datetime(year=year, month=month, day=1)
    date_to = datetime.datetime(year=year,
                                month=month,
                                day=calendar.monthrange(year, month)[1])
    transactions = singleton(MondoAPI).list_transactions(account_id,
                                                         date_from,
                                                         date_to)
    # Cache the result of listing the transactions so we can re-use it.
    cache = transaction_list_cache()
    for transaction in transactions:
        transaction['merchant'] = {}
        cache[transaction['id']] = transaction

    # Just return the ids which act as folders.
    return [t['id'] for t in transactions]


@readdir('/<account>/transactions/<year>/<month>/<txn>')
def transaction_fields(account_id, year, month, transaction_id):
    """List the fields available in the transaction."""
    return _get_transaction(transaction_id, False).keys() + ['json']


@readlink('/<account>/transactions/<year>/<month>/<txn>/json')
def transaction_as_json(account_id, year, month, transaction_id):
    """A special file to print the given transaction as JSON."""
    return json.dumps(_get_transaction(transaction_id, True))


@mixed(
    operations=[
        'readlink',
        'readdir'
    ],
    paths=[
        '/<account>/transactions/<year>/<month>/<txn>/<f1>',
        '/<account>/transactions/<year>/<month>/<txn>/<f1>/<f2>',
        '/<account>/transactions/<year>/<month>/<txn>/<f1>/<f2>/<f3>'
    ]
)
@appendnewline
def field_from_transaction(account_id, year, month, transaction_id,
                           field, subfield=None, subsubfield=None):
    merchant = (field == 'merchant')
    txn = _get_transaction(transaction_id, merchant)
    if not merchant:
        txn['merchant'] = {}

    ret = txn.get(field, '')
    if subfield:
        ret = ret.get(subfield, '')
    if subsubfield:
        ret = ret.get(subsubfield, '')
    if type(ret) is dict:
        ret = ret.keys()

    if field in ('amount', 'local_amount', 'account_balance'):
        return '%.02f' % (float(ret) / 100.0)

    return ret


@cache(datetime.timedelta(seconds=30))
def _get_balance(account_id):
    return singleton(MondoAPI).get_balance(account_id)


@readdir('/<account>/balance')
def list_balance(account_id):
    return ['balance', 'currency', 'spend_today']


@readlink('/<account>/balance/balance')
@appendnewline
@to_2dp
def balance_balance(account_id):
    return _get_balance(account_id).get('balance', '')


@readlink('/<account>/balance/currency')
@appendnewline
def balance_currency(account_id):
    return _get_balance(account_id).get('currency', '')


@readlink('/<account>/balance/spend_today')
@appendnewline
@to_2dp
def balance_spend_today(account_id):
    return _get_balance(account_id).get('spend_today', '')
