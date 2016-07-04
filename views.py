from app import app
from app import db

from models.person import Person
from models.person import make_person
from models.person import refresh_orcid_info
from models.person import connect_orcid
from models.person import set_person_claimed_at
from models.person import refresh_profile
from models.person import refresh_person
from models.person import delete_person
from models.product import get_all_products
from models.refset import num_people_in_db
from models.orcid import OrcidDoesNotExist
from models.orcid import NoOrcidException
from models.badge import badge_configs
from models.search import autocomplete
from models.url_slugs_to_redirect import url_slugs_to_redirect
from util import safe_commit

from flask import make_response
from flask import request
from flask import redirect
from flask import abort
from flask import jsonify
from flask import render_template
from flask import send_file
from flask import g

import jwt
from jwt import DecodeError
from jwt import ExpiredSignature
from functools import wraps
import requests
import stripe
from requests_oauthlib import OAuth1
import os
import time
import sys
import json
import logging
from urlparse import parse_qs, parse_qsl
from time import sleep

logger = logging.getLogger("views")


def json_dumper(obj):
    """
    if the obj has a to_dict() function we've implemented, uses it to get dict.
    from http://stackoverflow.com/a/28174796
    """
    try:
        return obj.to_dict()
    except AttributeError:
        return obj.__dict__


def json_resp(thing):
    # hide_keys = request.args.get("hide", "").split(",")
    # if hide_keys:
    #     for key_to_hide in hide_keys:
    #         try:
    #             del thing[key_to_hide]
    #         except KeyError:
    #             pass

    json_str = json.dumps(thing, sort_keys=True, default=json_dumper, indent=4)

    if request.path.endswith(".json") and (os.getenv("FLASK_DEBUG", False) == "True"):
        logger.info(u"rendering output through debug_api.html template")
        resp = make_response(render_template(
            'debug_api.html',
            data=json_str))
        resp.mimetype = "text/html"
    else:
        resp = make_response(json_str, 200)
        resp.mimetype = "application/json"
    return resp


def abort_json(status_code, msg):
    body_dict = {
        "HTTP_status_code": status_code,
        "message": msg,
        "error": True
    }
    resp_string = json.dumps(body_dict, sort_keys=True, indent=4)
    resp = make_response(resp_string, status_code)
    resp.mimetype = "application/json"
    abort(resp)


@app.route("/<path:page>")  # from http://stackoverflow.com/a/14023930/226013
@app.route("/")
def index_view(path="index", page=""):

    if page.lower() in url_slugs_to_redirect:
        return redirect(u"http://v1.impactstory.org/{}".format(page.strip()), code=302)

    return render_template(
        'index.html',
        is_local=os.getenv("IS_LOCAL", False),
        stripe_publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY")
    )


#support CORS
@app.after_request
def add_crossdomain_header(resp):
    resp.headers['Access-Control-Allow-Origin'] = "*"
    resp.headers['Access-Control-Allow-Methods'] = "POST, GET, OPTIONS, PUT, DELETE, PATCH, HEAD"
    resp.headers['Access-Control-Allow-Headers'] = "origin, content-type, accept, x-requested-with, authorization"

    # jason needs this to be able to see print() output in heroku local
    sys.stdout.flush()
    return resp

@app.before_request
def redirects():
    new_url = None

    try:
        if request.headers["X-Forwarded-Proto"] == "https":
            pass
        elif "http://" in request.url:
            new_url = request.url.replace("http://", "https://")
    except KeyError:
        #logger.debug(u"There's no X-Forwarded-Proto header; assuming localhost, serving http.")
        pass

    if request.url.startswith("https://www.impactstory.org"):
        new_url = request.url.replace(
            "https://www.impactstory.org",
            "https://impactstory.org"
        )
        logger.debug(u"URL starts with www; redirecting to " + new_url)

    if new_url:
        return redirect(new_url, 301)  # permanent


@app.route('/small-logo.png')
def logo_small():
    filename = "static/img/impactstory-logo.png"
    return send_file(filename, mimetype='image/png')


###########################################################################
# from satellizer.
# move to another file later
# this is copied from early GitHub-login version of Depsy. It's here:
# https://github.com/Impactstory/depsy/blob/ed80c0cb945a280e39089822c9b3cefd45f24274/views.py
###########################################################################




def parse_token(req):
    token = req.headers.get('Authorization').split()[1]
    return jwt.decode(token, os.getenv("JWT_KEY"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.headers.get('Authorization'):
            response = jsonify(message='Missing authorization header')
            response.status_code = 401
            return response

        try:
            payload = parse_token(request)
        except DecodeError:
            response = jsonify(message='Token is invalid')
            response.status_code = 401
            return response
        except ExpiredSignature:
            response = jsonify(message='Token has expired')
            response.status_code = 401
            return response

        g.my_orcid_id = payload['orcid_id']
        g.my_twitter_screen_name = payload['twitter_screen_name']
        g.my_id = payload["id"]

        return f(*args, **kwargs)

    return decorated_function











###########################################################################
# API
###########################################################################
@app.route("/api")
def api_test():
    return json_resp({"resp": "Impactstory: The Next Generation."})

@app.route("/api/test")
def test0():
    return jsonify({"test": True})



@app.route("/api/person/<orcid_id>/polling")
@app.route("/api/person/<orcid_id>/polling.json")
def profile_endpoint_polling(orcid_id):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()

    return json_resp(my_person.to_dict())


@app.route("/api/person/<orcid_id>")
@app.route("/api/person/<orcid_id>.json")
def profile_endpoint(orcid_id):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    if not my_person:
        print u"returning 404: orcid profile {} does not exist".format(orcid_id)
        abort_json(404, "That ORCID profile doesn't exist")
    return json_resp(my_person.to_dict())




@app.route("/api/person/twitter_screen_name/<screen_name>")
@app.route("/api/person/twitter_screen_name/<screen_name>.json")
def profile_endpoint_twitter(screen_name):
    res = db.session.query(Person.id).filter_by(twitter=screen_name).first()
    if not res:
        abort_json(404, "We don't have anyone with that twitter screen name")

    return json_resp({"id": res[0]})


# need to call it with https for it to work
@app.route("/api/person/<orcid_id>", methods=["POST"])
@app.route("/api/person/<orcid_id>.json", methods=["POST"])
def refresh_profile_endpoint(orcid_id):
    if request.json:
        my_person = Person.query.filter_by(orcid_id=orcid_id).first()

        product_id = request.json["product"]["id"]
        my_product = next(my_product for my_product in my_person.products if my_product.id==product_id)
        url = request.json["product"]["fulltext_url"]
        my_product.set_oa_from_user_supplied_fulltext_url(url)

        my_person.recalculate_openness()

        safe_commit(db)
    else:
        my_person = refresh_profile(orcid_id)
    return json_resp(my_person.to_dict())

@app.route("/api/person/<orcid_id>/fulltext", methods=["POST"])
@app.route("/api/person/<orcid_id>/fulltext.json", methods=["POST"])
def refresh_fulltext(orcid_id):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    my_person.recalculate_openness()
    safe_commit(db)
    return json_resp(my_person.to_dict())


@app.route("/api/person/<orcid_id>/tweeted-quickly", methods=["POST"])
def tweeted_quickly(orcid_id):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()

    if not my_person:
            print u"returning 404: orcid profile {} does not exist".format(orcid_id)
            abort_json(404, "That ORCID profile doesn't exist")

    my_person.tweeted_quickly = True
    success = safe_commit(db)
    return json_resp({"resp": "success"})


@app.route("/api/search/<search_str>")
def search(search_str):
    ret = autocomplete(search_str)
    return jsonify({"list": ret, "count": len(ret)})


@app.route("/api/products")
def all_products_endpoint():
    res = get_all_products()
    return jsonify({"list": res })

@app.route("/api/people")
def people_endpoint():
    count = num_people_in_db()
    return jsonify({"count": count})


@app.route("/api/badges")
def badges_about():
    return json_resp(badge_configs())



@app.route("/api/donation", methods=["POST"])
def donation_endpoint():
    stripe.api_key = os.getenv("STRIPE_API_KEY")
    metadata = {
        "full_name": request.json["fullName"],
        "orcid_id": request.json["orcidId"],
        "email": request.json["email"]
    }
    try:
        stripe.Charge.create(
            amount=request.json["cents"],
            currency="usd",
            source=request.json["tokenId"],
            description="Impactstory donation",
            metadata=metadata
        )
    except stripe.error.CardError, e:
        # The card has been declined
        abort_json(499, "Sorry, your credit card was declined.")

    return jsonify({"message": "well done!"})


# user management
##############################################################################


@app.route('/api/me', methods=["GET", "DELETE", "POST"])
@login_required
def me():
    my_person = Person.query.filter_by(id=g.my_id).first()

    if request.method == "GET":
        # @todo i'm pretty sure we don't use this anymore?
        return jsonify({"token": my_person.get_token()})

    elif request.method == "POST":
        refreshed_person = refresh_person(my_person)
        return jsonify({"token": refreshed_person.get_token()})

    elif request.method == "DELETE":
        delete_person(id=g.my_id)
        return jsonify({"msg": "Alas, poor Yorick! I knew him, Horatio"})



@app.route("/api/auth/orcid/login", methods=["POST"])
def orcid_login():
    pass


@app.route("/api/me/orcid", methods=["POST"])
@login_required
def manage_my_orcid():
    my_person = Person.query.filter_by(id=g.my_id).first()

    # this person already has an orcid id, so we're just going to refresh all their orcid info
    if my_person.orcid_id:
        modified_person = refresh_orcid_info(my_person)

    # they are trying to connect a brand new orcid id
    else:
        access_token_url = 'https://pub.orcid.org/oauth/token'
        payload = dict(client_id="APP-PF0PDMP7P297AU8S",
                       redirect_uri=request.json['redirectUri'],
                       client_secret=os.getenv('ORCID_CLIENT_SECRET'),
                       code=request.json['code'],
                       grant_type='authorization_code')

        # First we exchange authorization code for access token;
        # the access token has the ORCID ID, which is actually all we need here.
        r = requests.post(access_token_url, data=payload)
        try:
            modified_person = connect_orcid(my_person, r.json()["orcid"])
        except KeyError:
            print u"Aborting api/me/orcid; got no 'orcid' key back from ORCID! Got this: {}".format(r.json())
            abort_json(500, "Invalid JSON return from ORCID during OAuth.")

    token = modified_person.get_token()
    return jsonify({"token": token, "num_products": modified_person.num_products})





@app.route("/api/auth/twitter/login", methods=["POST"])
def login_twitter_user():
    pass

@app.route("/api/auth/twitter/register", methods=["POST"])
def register_twitter_user():
    access_token_url = 'https://api.twitter.com/oauth/access_token'

    auth = OAuth1(os.getenv('TWITTER_CONSUMER_KEY'),
                  client_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
                  resource_owner_key=request.json.get('token'),
                  verifier=request.json.get('verifier'))

    r = requests.post(access_token_url, auth=auth)

    twitter_creds = dict(parse_qsl(r.text))
    print u"got back twitter_creds from twitter {}".format(twitter_creds)

    my_person = Person.query.filter_by(twitter=twitter_creds["screen_name"]).first()
    if my_person is None:
        my_person = make_person(twitter_creds)

    token = my_person.get_token()
    return jsonify({"token": token})


# doesn't save anything in database, just proxy for calling twitter.com
@app.route("/api/auth/twitter/request-token")
def get_twitter_request_token():
    request_token_url = 'https://api.twitter.com/oauth/request_token'

    oauth = OAuth1(
        os.getenv('TWITTER_CONSUMER_KEY'),
        client_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
        callback_uri=request.args.get('redirectUri')
    )

    r = requests.post(request_token_url, auth=oauth)
    oauth_token_dict = dict(parse_qsl(r.text))
    return jsonify(oauth_token_dict)



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)

















