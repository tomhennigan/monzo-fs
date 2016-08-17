# coding=utf8

"""Utility functions and decorators used in mondo-fs."""

import datetime
import json


_singleton = {}


def singleton(key, value=None):
    """Gets or sets a singleton instance.

    :param key: the key used to identify this singleton.
    :param value: (optional) if set this is the value for the singleton.
    :return: singleton value for key.
    """
    global _singleton

    if value is not None:
        if key in _singleton:
            raise Exception('Singleton %s was already set.' % key)
        _singleton[key] = value

    if key not in _singleton:
        raise Exception('Singleton %s has not been set.' % key)

    return _singleton[key]


def cache(timedelta):
    """Returns a decorator that memoizes the wrapped function (based on
    JSON serialization of positional and keyword args).

    :param timedelta: A datetime.timedelta instance for cache lifetime.
    :returns: A callable that can be used as a decorator for a function.
    """

    cache = {}
    cache_expiry = {}

    if type(timedelta) is not datetime.timedelta:
        raise Exception('timedelta argument must have type datetime.timedelta')

    def _decorator(fn):
        def _cache(*args, **kwargs):
            key = json.dumps(args) + json.dumps(kwargs)
            expires = cache_expiry.get(key, None)

            if expires:
                if datetime.datetime.now() < expires:
                    return cache[key]
                else:
                    cache[key] = None
                    cache_expiry[key] = None

            cache[key] = fn(*args, **kwargs)
            cache_expiry[key] = datetime.datetime.now() + timedelta

            return cache[key]
        return _cache
    return _decorator


def appendnewline(fn):
    """Returns a function that calls the given function and appends an ascii
    newline byte to the result (if the result is not a list or dict). The
    result of the function is also interpreted as bytes.

    :param fn: A callable to be wrapped.
    :return: A callable that invokes fn and appends a newline byte.
    """
    def _decorator(*a, **k):
        r = fn(*a, **k)
        if type(r) not in (list, dict):
            r = bytes(r) + b'\n'
        return r
    return _decorator


def to_2dp(fn):
    """Converts pence (e.g. 1000) to 2dp (e.g. 10.00)."""
    return lambda *a, **k: '%.02f' % (float(fn(*a, **k)) / 100.0)
