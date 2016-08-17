# coding=utf8

"""A wrapper for the current iteration of the Mondo API.

Handles tasks such as prompting the user to go through the web oauth flow,
capturing the code from Mondo with a built in web server, exchanging the code
for an oauth token and re-issuing it as and when required.

  Typical usage example:

  api = MondoAPI(client_id, client_secret)
  api.initialize()
  print api.list_accounts()
"""

import BaseHTTPServer
import datetime
import os
import pickle
import urllib
import urlparse

import iso8601
import requests
import rfc3339


class MondoAPI:
    """Wraps authenticating, calling and de-marshaling Mondo API calls."""

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = 'http://localhost:1234/'
        self.config_file = os.path.join(os.path.expanduser('~'), '.mondofs')
        self.oauth = None

    def initialize(self):
        """Attempt to initialize this instance. We attempt to read an oauth
        token from a config file on disk. If that token exists but is expired
        we attempt to refresh it. If the token is still not valid or present we
        take the user back through the oauth flow to get a new token.
        """

        if os.path.exists(self.config_file):
            # Attempt to reload config from the given config file.
            with open(self.config_file, 'r') as fp:
                self.oauth = pickle.load(fp)

        if self.oauth and self._oauth_expired():
            # If the token was read from the file then lets try and refresh it.
            self._refresh_oauth_token()

        if not self.oauth or self._oauth_expired():
            # If that didn't work we need to ask the user to re-authorize the
            # app.
            self._authorize()

    def _authorize(self):
        """Perform the initial oauth dance by redirecting the user to mondo. To
        get an auth code that we can exchange for an oauth token.
        """

        # This should be good enough.. We fetch 40 random bytes and map them to
        # characters in the range a-z.
        # TODO(tomhennigan) It's unclear from the docs how secure this token
        # should actually be. Should clarify this and harden if required.
        az = map(chr, range(ord('a'), ord('z') + 1))
        expected_state = ''.join(map(lambda d: az[ord(d) % len(az)],
                                     os.urandom(40)))

        url = 'https://auth.getmondo.co.uk/?'
        url += urllib.urlencode({
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'state': expected_state,
            'response_type': 'code',
        })
        print 'Please go to the URL below to authorize this app.'
        print
        print '\033[93m' + url + '\033[00m'
        print
        print 'You\'ll need to give Mondo your email, and they\'ll send you a'
        print 'confirmation email that you can use to sign in to this app.'

        # Start an HTTP server to wait for the callback from Mondo. Once the
        # user has done the dance of filling in their email address, finding
        # the verification email and clicking "Authorize" in that we'll get a
        # callback.
        httpd = BaseHTTPServer.HTTPServer(('localhost', 1234), HTTPServer)
        httpd.handle_request()
        code = HTTPServer.params.get('code', [None])[0]
        state_back = HTTPServer.params.get('state', [None])[0]

        if not code or not state_back:
            raise Exception('Invalid response from callback.')

        if expected_state != state_back:
            raise Exception('State token %s was not OK %s.' % (state_back,
                                                               expected_state))

        # We need to convert the auth code we're given to an oauth token that
        # we can use to authenticate API requests.
        self._fetch_oauth_token(code=code,
                                redirect_uri=self.redirect_uri,
                                grant_type='authorization_code')

    def _oauth_expired(self):
        """Tests whether the oauth token has expired."""
        return datetime.datetime.now() > self.oauth['_expires']

    def _fetch_oauth_token(self, **params):
        """Fetches an oauth token. Requests should set keyword arguments for
        additional POST parameters to the /oauth2/token endpoint.
        """

        # Exchange the code from the callback for an oauth token.
        params['client_id'] = self.client_id
        params['client_secret'] = self.client_secret
        r = requests.post('https://api.getmondo.co.uk/oauth2/token',
                          data=params)

        self.oauth = r.json()
        now = datetime.datetime.now()
        expires = self.oauth.get('expires_in', -1)
        self.oauth['_expires'] = now + datetime.timedelta(milliseconds=expires)

        with open(self.config_file, 'w') as fp:
            pickle.dump(self.oauth, fp)

    def _refresh_oauth_token(self):
        """Forces a refresh of the oauth token."""
        self._fetch_oauth_token(grant_type='refresh_token',
                                refresh_token=self.oauth['refresh_token'])

    def _get_access_token(self):
        """Gets a valid and non-expired oauth token."""
        if self._oauth_expired():
            self._refresh_oauth_token()

        return self.oauth.get('access_token', None)

    def _get(self, path, params=None):
        """Executes a GET request to the mondo API.

        :param params: An optional dictionary of parameters.
        :returns: The de-marshaled response from the API (e.g. a dict).
        """
        url = 'https://api.getmondo.co.uk/' + path
        if params:
            url += ('?' + urllib.urlencode(params))
        headers = {
            'Authorization': 'Bearer ' + self._get_access_token(),
        }
        return requests.get(url, headers=headers).json()

    def get_accounts(self):
        """https://getmondo.co.uk/docs/#accounts"""
        return self._get('accounts').get('accounts', [])

    def get_balance(self, account_id):
        """https://getmondo.co.uk/docs/#balance"""
        return self._get('balance', params={'account_id': account_id})

    def list_transactions(self, account_id, date_from, date_to):
        """https://getmondo.co.uk/docs/#list-transactions"""
        return list(self._list_transactions(account_id, date_from, date_to))

    def _list_transactions(self, account_id, date_from, date_to):
        """Fetch all transactions within the given date ranges. Handles
        pagination.

        :returns: A generator that yields all transactions within the range.
        """
        start = date_from
        limit = 100
        while True:
            since = rfc3339.rfc3339(start,
                                    use_system_timezone=False,
                                    utc=True)
            before = rfc3339.rfc3339(date_to,
                                     use_system_timezone=False,
                                     utc=True)
            params = {
                'account_id': account_id,
                'limit': limit,
                'since': since,
                'before': before,
            }
            response = self._get('transactions', params=params)
            transactions = response.get('transactions', [])

            last_created = None
            for transaction in transactions:
                created = iso8601.parse_date(transaction['created'])
                if last_created is None or created > last_created:
                    last_created = created
                yield transaction

            if len(transactions) < limit:
                # No need to paginate.
                return

            start = last_created

    def get_transaction(self, transaction_id, merchant):
        """https://getmondo.co.uk/docs/#retrieve-transaction"""
        params = {}
        if merchant:
            params['expand[]'] = 'merchant'
        result = self._get('transactions/' + transaction_id, params=params)
        return result.get('transaction', {})


class HTTPServer(BaseHTTPServer.BaseHTTPRequestHandler):
    """An HTTP server capable of handling a GET request."""

    def do_GET(self):
        if self.path.startswith('/?'):
            HTTPServer.params = urlparse.parse_qs(self.path[2:])
        else:
            HTTPServer.params = {}

        self.send_response(302)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        w = self.wfile.write
        w('<!DOCTYPE html>')
        w('<html>')
        w('  <head>')
        w('    <title>mondo-fs succesfully setup</title>')
        w('    <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">')
        w('    <link rel="stylesheet" href="https://code.getmdl.io/1.2.0/material.indigo-pink.min.css">')
        w('    <script defer src="https://code.getmdl.io/1.2.0/material.min.js"></script>')
        w('    <style>')
        w('      html, body {')
        w('      }')
        w('      body {')
        w('      display: flex;')
        w('      align-items: center;')
        w('      justify-content: center;')
        w('      }')
        w('      .mondo-card {')
        w('      flex: 0 0 300px;')
        w('      height: 300px;')
        w('      }')
        w('      .mondo-card > .mdl-card__title {')
        w('      color: #111;')
        w('      height: 176px;')
        w('      background: #f0f0f0 url(\'http://i.imgur.com/e0rv3HQ.png\') center center no-repeat;')
        w('      }')
        w('    </style>')
        w('  </head>')
        w('  <body>')
        w('    <div class="mondo-card mdl-card mdl-shadow--2dp">')
        w('      <div class="mdl-card__title">')
        w('        <h2 class="mdl-card__title-text">Success!</h2>')
        w('      </div>')
        w('      <div class="mdl-card__supporting-text">')
        w('        You\'ve successfully setup mondo-fs. Please navigate to the mount point in your favorite file browser to try it out!')
        w('      </div>')
        w('      <div class="mdl-card__actions mdl-card--border">')
        w('        <a href="https://github.com/tomhennigan/mondo-fs" class="mdl-button mdl-button--colored mdl-js-button mdl-js-ripple-effect" data-upgraded=",MaterialButton,MaterialRipple">')
        w('        Learn More')
        w('        <span class="mdl-button__ripple-container"><span class="mdl-ripple"></span></span></a>')
        w('      </div>')
        w('    </div>')
        w('  </body>')
        w('</html>')
