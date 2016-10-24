from app import app
from app import db

from models.orcid import get_orcid_id_from_oauth
from models.person import Person
from models.person import PersonExistsException
from models.person import make_person
from models.person import refresh_orcid_info_and_save
from models.person import connect_orcid
from models.person import connect_twitter
from models.person import disconnect_twitter
from models.person import refresh_profile
from models.person import refresh_person
from models.person import delete_person
from models.person import update_person
from models.person import make_temporary_person_from_orcid
from models.log_temp_profile import add_new_log_temp_profile
from models.person import get_random_people
from models.product import get_all_products
from models.refset import num_people_in_db
from models.badge import badge_configs
from models.search import autocomplete
from models.url_slugs_to_redirect import url_slugs_to_redirect
from models.twitter import get_twitter_creds
from util import safe_commit
from util import elapsed

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
import sys
import json
import logging
from operator import attrgetter
from urlparse import parse_qs, parse_qsl
from time import sleep
from time import time

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


def abort_json(status_code, msg, **kwargs):
    body_dict = {
        "message": msg
    }
    body_dict.update(kwargs)

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
        if not request.args.get("source"):
            if request.headers.getlist("X-Forwarded-For"):
                ip = request.headers.getlist("X-Forwarded-For")[0]
                if ip == "54.210.209.20":
                    abort_json(429, """We've noticed you are making many requests.
                                    Please add ?source=YOUREMAILADDRESS to your API calls,
                                    or email us at team@impactstory.org for more details on
                                    our API. Thanks!""")

        print u"making temporary person for {orcid_id}, referred by {referrer} using url {url}, ip {ip}".format(
            orcid_id=orcid_id,
            referrer=request.referrer,
            url=request.url,
            ip=request.remote_addr)
        my_person = make_temporary_person_from_orcid(orcid_id)
        print u"saving log_temp_profile for {}".format(my_person)
        temp_profile_log = add_new_log_temp_profile(my_person, request)

    return json_resp(my_person.to_dict())




@app.route("/api/person/twitter_screen_name/<screen_name>")
@app.route("/api/person/twitter_screen_name/<screen_name>.json")
def profile_endpoint_twitter(screen_name):
    res = db.session.query(Person.orcid_id).filter_by(twitter=screen_name).first()
    if not res:
        abort_json(404, "We don't have anyone with that twitter screen name")

    return json_resp({"id": res[0]})


# need to call it with https for it to work
@app.route("/api/person/<orcid_id>", methods=["POST"])
@app.route("/api/person/<orcid_id>.json", methods=["POST"])
def modify_profile_endpoint(orcid_id):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()

    product_id = request.json["product"]["id"]
    my_product = next(my_product for my_product in my_person.products if my_product.id==product_id)
    url = request.json["product"]["fulltext_url"]
    my_product.set_oa_from_user_supplied_fulltext_url(url)

    my_person.recalculate_openness()

    safe_commit(db)

    return json_resp(my_person.to_dict())



@app.route("/api/person/<orcid_id>/refresh", methods=["POST"])
@app.route("/api/person/<orcid_id>/refresh.json", methods=["POST"])
def refresh_profile_endpoint(orcid_id):
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



def parse_token(req):
    token = req.headers.get('Authorization').split()[1]
    return jwt.decode(token, os.getenv("JWT_KEY"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.headers.get('Authorization'):
            response = jsonify(message='Missing authorization header')
            print u"in login_required with error, Missing authorization header"
            response.status_code = 401
            return response

        try:
            payload = parse_token(request)
        except DecodeError:
            response = jsonify(message='Token is invalid')
            response.status_code = 401
            print u"in login_required with error, got DecodeError"
            return response
        except ExpiredSignature:
            response = jsonify(message='Token has expired')
            response.status_code = 401
            print u"in login_required with error, got DecodeError"
            return response

        print u"in login_required. payload: {}: ".format(payload)

        g.my_person = None
        if "id" in payload:
            # this uses the current token format
            g.my_person = Person.query.filter_by(id=payload["id"]).first()
        if not g.my_person and "orcid_id" in payload:
            # fallback because some tokens don't have id?
            g.my_person = Person.query.filter_by(orcid_id=payload["orcid_id"]).first()
        if not g.my_person and "sub" in payload:
            # fallback for old token format
            g.my_person = Person.query.filter_by(orcid_id=payload["sub"]).first()
        if not g.my_person:
            print u"in login_required with error, no known keys in token payload: {}".format(payload)

        print u"in login_required success, got a person {}".format(g.my_person)
        return f(*args, **kwargs)

    return decorated_function


@app.route('/api/me', methods=["GET", "DELETE", "POST"])
@login_required
def me():
    if request.method == "GET":
        return jsonify({"token":g.my_person.get_token()})

    elif request.method == "POST":
        updated_person = update_person(g.my_person, request.json)
        return jsonify({"token": updated_person.get_token()})

    elif request.method == "DELETE":
        delete_person(orcid_id=g.my_person.orcid_id)
        return jsonify({"msg": "Alas, poor Yorick! I knew him, Horatio"})


@app.route("/api/me/refresh", methods=["POST"])
@login_required
def refresh_me():
    refresh_person(g.my_person)
    return jsonify({"token":  g.my_person.get_token()})


@app.route("/api/me/orcid/login", methods=["POST"])
def orcid_login():
    print u"in orcid_login with request.json {}".format(request.json)
    my_orcid_id = get_orcid_id_from_oauth(
        request.json['code'],
        request.json['redirectUri']
    )
    if not my_orcid_id:
        print u"in orcid_login with error, no my_orcid_id"
        abort_json(401, "Bad ORCID response; the auth code you sent is probably expired.")

    my_person = Person.query.filter_by(orcid_id=my_orcid_id).first()
    if not my_person:
        print u"in orcid_login with error, no my_person"
        abort_json(
            404,
            "We don't have that ORCID in the db.",
            identity_provider_id=my_orcid_id
        )

    return jsonify({"token":  my_person.get_token()})


@app.route("/api/me/orcid/connect", methods=["POST"])
@login_required
def orcid_connect():
   print u"in orcid_connect with request.json {}".format(request.json)

    orcid_id = get_orcid_id_from_oauth(
        request.json['code'],
        request.json['redirectUri']
    )
    if not orcid_id:
        print u"in orcid_login with error, no orcid_id"
        abort_json(500, "Invalid JSON return from ORCID during OAuth.")

    connect_orcid(g.my_person, orcid_id)
    return jsonify({"token":  g.my_person.get_token()})



@app.route("/api/me/orcid/refresh", methods=["POST"])
@login_required
def refresh_my_orcid():
    refresh_orcid_info_and_save(g.my_person)
    return jsonify({"token":  g.my_person.get_token()})



@app.route("/api/me/twitter/login", methods=["POST"])
def twitter_login():
    twitter_creds = get_twitter_creds(request.json.get('oauth_token'), request.json.get('oauth_verifier'))
    if not twitter_creds:
        print u"error in twitter_login, empty twitter creds"
        abort_json(422, "empty twitter creds")

    my_person = Person.query.filter_by(twitter=twitter_creds["screen_name"]).first()
    if not my_person:
        abort_json(
            404,
            "We don't have that Twitter in the db.",
            identity_provider_id=twitter_creds["screen_name"]
        )

    return jsonify({"token": my_person.get_token()})



@app.route("/api/me/twitter/register", methods=["POST"])
def twitter_register_but_login_if_they_are_already_registered():
    twitter_creds = get_twitter_creds(request.json.get('oauth_token'), request.json.get('oauth_verifier'))
    landing_page = request.json.get("customLandingPage", "default")
    if not twitter_creds:
        print u"error in twitter_register_but_login_if_they_are_already_registered, empty twitter creds"
        abort_json(422, "empty twitter creds")

    try:
        my_person = make_person(twitter_creds, landing_page=landing_page)
    except PersonExistsException:
        my_person = Person.query.filter_by(twitter=twitter_creds["screen_name"]).first()

    return jsonify({"token": my_person.get_token()})


# since new users now MUST have a twitter, this endpoint is only useful for legacy users,
# who signed up when you registered with ORCID and Twitter was optional
@app.route("/api/me/twitter/connect", methods=["POST"])
@login_required
def twitter_connect():
    twitter_creds = get_twitter_creds(
        request.json.get('oauth_token'),
        request.json.get('oauth_verifier')
    )

    connect_twitter(g.my_person, twitter_creds)
    return jsonify({"token": g.my_person.get_token()})



@app.route("/api/me/twitter/disconnect", methods=["POST"])
@login_required
def twitter_disconnect_endpoint():
    disconnect_twitter(g.my_person)
    return jsonify({"token": g.my_person.get_token()})



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


##########
# admin

@app.route("/admin/random/<n>", methods=["GET"])
def random_people(n):
    people = get_random_people(n)
    summary = [(p.impactstory_url, p.full_name) for p in people]
    response = {"people": summary}
    return jsonify(response)



@app.route("/admin/badge-test/<badge_name>", methods=["GET"])
def badge_test(badge_name):
    people = get_random_people(250, refset_only=True)
    people.sort(key=attrgetter(badge_name), reverse=False)

    refset = [getattr(p, badge_name) for p in people]

    percentiles = [0, .25, .5, .75, .9, .99]
    indexes = [int(i * len(refset)) for i in percentiles]
    people_summaries = [(p.impactstory_url, p.full_name, getattr(p, badge_name)) for p in people]
    people_at_percentiles = [people_summaries[i] for i in indexes]
    percentile_exemplars = zip(percentiles, people_at_percentiles)

    people_above_90th = people_summaries[int(0.9*len(refset)):]

    detailed_percentiles = [x * .01 for x in range(100)]
    detailed_indexes = [int(i * len(refset)) for i in detailed_percentiles]
    detailed_percentile_values = [refset[i] for i in detailed_indexes]
    refset_response = []
    for (percent, value) in zip(detailed_percentiles, detailed_percentile_values):
        refset_response += [u"{}: {:.2f}".format(int(100*percent), value)]

    response = {
        "_badge_name": badge_name,
        "_percentile_exemplars": percentile_exemplars,
        "people_above_90th": people_above_90th,
        "refset": refset_response
    }

    return jsonify(response)



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)

















