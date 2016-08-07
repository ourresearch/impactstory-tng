import requests
import os

from urlparse import parse_qs, parse_qsl
from requests_oauthlib import OAuth1

def get_twitter_creds(twitter_token, twitter_verifier):
    access_token_url = 'https://api.twitter.com/oauth/access_token'

    auth = OAuth1(os.getenv('TWITTER_CONSUMER_KEY'),
                  client_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
                  resource_owner_key=twitter_token,
                  verifier=twitter_verifier)

    r = requests.post(access_token_url, auth=auth)
    twitter_creds = dict(parse_qsl(r.text))
    print u"got back twitter_creds from twitter {}".format(twitter_creds)
    return twitter_creds