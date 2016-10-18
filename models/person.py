from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import deferred
from sqlalchemy import orm
from sqlalchemy import text
from sqlalchemy import func

from app import db

from models import product  # needed for sqla i think
from models import badge  # needed for sqla i think
from models.product import make_product
from models.product import distinct_product_list
from models.orcid import OrcidProfile
from models.orcid import clean_orcid
from models.orcid import NoOrcidException
from models.orcid import OrcidDoesNotExist
from models.orcid import make_and_populate_orcid_profile
from models.source import sources_metadata
from models.source import Source
from models.refset import Refset
from models.emailer import send
from models.log_email import save_email
from models.log_openness import save_openness_log
from util import elapsed
from util import chunks
from util import date_as_iso_utc
from util import days_ago
from util import safe_commit
from util import calculate_percentile
from util import as_proportion

from time import time
from time import sleep
from copy import deepcopy
import jwt
import os
import shortuuid
import requests
import json
import re
import datetime
import logging
import operator
import threading
import hashlib
import math
from nameparser import HumanName
from collections import defaultdict
from requests_oauthlib import OAuth1Session
from util import update_recursive_sum


class PersonExistsException(Exception):
    pass

def get_random_people(n, refset_only=False):
    # this simpler way didn't work: func.setseed(0.42)
    # below way is from https://github.com/khanduri/khanduri.github.io/blob/master/_posts/2016-02-26-fetch-rows-in-random-order-with-seed-support.md
    sql = text('select setseed({0});'.format(0.42))
    db.engine.execute(sql)

    q = Person.query
    if refset_only:
        q = q.filter(Person.campaign == "2015_with_urls")

    q = q.order_by(func.random())
    q = q.limit(n)
    people = q.all()
    return people


def delete_person(orcid_id):
    # also need delete all the badges, products
    product.Product.query.filter_by(orcid_id=orcid_id).delete()
    badge.Badge.query.filter_by(orcid_id=orcid_id).delete()

    # and now delete the person.  have to do this after deleting the stuff above.
    Person.query.filter_by(orcid_id=orcid_id).delete()

    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(orcid_id)

def set_person_email(orcid_id, email, high_priority=False):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    my_person.email = email
    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(orcid_id)


def update_person(my_person, properties_to_change):
    for k, v in properties_to_change.iteritems():
        setattr(my_person, k, v)

    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.orcid_id)
    return my_person



def set_person_claimed_at(my_person):
    my_person.claimed_at = datetime.datetime.utcnow().isoformat()
    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.orcid_id)

def get_full_twitter_profile(twitter_creds):
    oauth = OAuth1Session(
        os.getenv('TWITTER_CONSUMER_KEY'),
        client_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
        resource_owner_key=twitter_creds["oauth_token"],
        resource_owner_secret=twitter_creds["oauth_token_secret"]
    )
    url = "https://api.twitter.com/1.1/account/verify_credentials.json?include_email=true"

    r = oauth.get(url)
    full_twitter_profile = r.json()
    return full_twitter_profile


def make_temporary_person_from_orcid(orcid_id):
    my_person = Person()

    my_person.id = "u_is{}".format(shortuuid.uuid()[0:5])
    my_person.created = datetime.datetime.utcnow()
    print u"starting make_temporary_person_from_orcid: made new person for {}".format(my_person)

    my_person.orcid_id = orcid_id
    my_person.refresh()

    print u"finished make_temporary_person_from_orcid: made new person for {}".format(my_person)
    return my_person


def make_person(twitter_creds, high_priority=False, landing_page=None):
    if Person.query.filter_by(twitter=twitter_creds["screen_name"]).first():
        raise PersonExistsException

    my_person = Person()

    my_person.id = "u_is{}".format(shortuuid.uuid()[0:5])
    my_person.created = datetime.datetime.utcnow()
    my_person.claimed_at = datetime.datetime.utcnow().isoformat()
    my_person.landing_page = landing_page
    print u"\nin make_person: made new person for {}".format(my_person)

    return connect_twitter(my_person, twitter_creds, set_everything_possible=True)


def connect_orcid(my_person, orcid_id):
    print u"adding a brand new orcid_id for {}: {}".format(my_person.full_name, orcid_id)
    my_person.orcid_id = orcid_id
    return refresh_orcid_info_and_save(my_person)


def disconnect_twitter(my_person):
    my_person.twitter_creds = None
    my_person.twitter = None
    print u"\nDisconnected Twitter from: {}".format(my_person)

    db.session.add(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.id)

    return my_person

def connect_twitter(my_person, twitter_creds, set_everything_possible=False):

    full_twitter_profile = get_full_twitter_profile(twitter_creds)
    full_twitter_profile.update(twitter_creds)
    my_person.twitter_creds = full_twitter_profile
    my_person.twitter = full_twitter_profile["screen_name"]

    if set_everything_possible:
        my_person.email = full_twitter_profile["email"]
        twitter_full_name = full_twitter_profile["name"]

        try:
            parsed_name = HumanName(twitter_full_name)
            my_person.family_name = parsed_name["last"]
            my_person.given_names = parsed_name["first"]
            if my_person.given_names and len(my_person.given_names) <= 2 and parsed_name["middle"]:
                my_person.given_names = parsed_name["middle"]
        except KeyError:
            my_person.first_name = twitter_full_name

    print u"\nAdded Twitter info to person: {}".format(my_person)

    db.session.add(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.id)

    return my_person





def refresh_orcid_info_and_save(my_person):
    print u"refreshing all orcid info for {}".format(my_person.orcid_id)
    my_person.refresh_orcid_info()

    print u"storing refreshed person in db"
    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.orcid_id)
    return my_person


# this should be refactored with refresh_profile().  doing it this way is dumb.
def refresh_person(my_person, high_priority=False):
    print u"refreshing {}".format(my_person.orcid_id)

    # for testing on jason's local, so it doesn't have to do a real refresh
    # sleep(5)
    # return my_person

    my_person.refresh(high_priority=high_priority)
    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.orcid_id)
    return my_person


def refresh_profile(orcid_id, high_priority=False):
    print u"refreshing {}".format(orcid_id)
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()

    # for testing on jason's local, so it doesn't have to do a real refresh
    # sleep(5)
    # return my_person

    my_person.refresh(high_priority=high_priority)
    db.session.merge(my_person)

    commit_success = safe_commit(db)
    if commit_success:
        print u"committed {}".format(orcid_id)
    else:
        print u"COMMIT fail on {}".format(orcid_id)

    return my_person



class Person(db.Model):
    id = db.Column(db.Text, primary_key=True)
    orcid_id = db.Column(db.Text, unique=True)

    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)
    claimed_at = db.Column(db.DateTime)

    orcid_api_raw_json = deferred(db.Column(JSONB))
    fresh_orcid = db.Column(db.Boolean)
    invalid_orcid = db.Column(db.Boolean)

    email = db.Column(db.Text)
    twitter = db.Column(db.Text)
    twitter_creds = db.Column(MutableDict.as_mutable(JSONB))
    campaign = db.Column(db.Text)
    landing_page = db.Column(db.Text)
    depsy_id = db.Column(db.Text)
    depsy_percentile = db.Column(db.Float)
    affiliation_name = db.Column(db.Text)
    affiliation_role_title = db.Column(db.Text)

    post_counts = db.Column(MutableDict.as_mutable(JSONB))
    mendeley_sums = db.Column(MutableDict.as_mutable(JSONB)) # not deferred for now
    num_products = db.Column(db.Integer)
    num_posts = db.Column(db.Integer)
    num_mentions = db.Column(db.Integer)
    num_badges = db.Column(db.Integer)

    openness = db.Column(db.Float)

    events_emailed = db.Column(MutableDict.as_mutable(JSONB))
    weekly_event_count = db.Column(db.Float)
    monthly_event_count = db.Column(db.Float)
    tweeted_quickly = db.Column(db.Boolean)
    finished_wizard = db.Column(db.Boolean)
    saw_opencon_landing_page = db.Column(db.Boolean)

    num_fulltext = db.Column(db.Integer)
    num_any_oa = db.Column(db.Integer)
    num_cc_by = db.Column(db.Integer)
    num_cc_restricted = db.Column(db.Integer)
    num_cc0_pd = db.Column(db.Integer)

    coauthors = db.Column(MutableDict.as_mutable(JSONB))

    error = db.Column(db.Text)

    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("person", lazy="subquery"),
        foreign_keys="Product.orcid_id"
    )

    badges = db.relationship(
        'Badge',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("person", lazy="subquery"),
        foreign_keys="Badge.orcid_id"
    )


    def __init__(self):
        self.invalid_orcid = False




    @property
    def impactstory_url(self):
        if self.orcid_id:
            return u"https://impactstory.org/u/{}".format(self.orcid_id)
        else:
            return None

    # doesn't have error handling; called by refresh when you want it to be robust
    def call_apis(self, high_priority=False, overwrite_orcid=True, overwrite_metrics=True):
        print u"** calling set_api_raw_from_orcid"
        if overwrite_orcid or not self.orcid_api_raw_json:
            self.set_api_raw_from_orcid()
        else:
            print u"not calling orcid because no overwrite"

        # parse orcid so we now what to gather
        self.set_from_orcid()

        products_without_dois = [p for p in self.products if not p.doi]
        if products_without_dois:
            print u"** calling set_data_for_all_products for crossref doi lookup"
            # do this first, so have doi for everything else
            self.set_data_for_all_products("set_doi_from_crossref_biblio_lookup", high_priority)
        else:
            print u"** all products have dois data, so not calling crossref to look for dois"

        products_without_altmetric = [p for p in self.products if not p.altmetric_api_raw]
        if overwrite_metrics or products_without_altmetric:
            print u"** calling set_data_for_all_products for altmetric"
            self.set_data_for_all_products("set_data_from_altmetric", high_priority)
        else:
            print u"** all products have altmetric data and no overwrite, so not calling altmetric"

        products_without_mendeley = [p for p in self.products if not p.mendeley_api_raw]
        if overwrite_metrics or products_without_mendeley:
            print u"** calling set_data_for_all_products for mendeley"
            self.set_data_for_all_products("set_data_from_mendeley", high_priority)
        else:
            print u"** all products have mendeley data and no overwrite, so not calling mendeley"


    # doesn't have error handling; called by refresh when you want it to be robust
    def refresh_from_db(self):
        print u"* refresh_from_db {}".format(self.orcid_id)
        self.error = None
        start_time = time()
        try:
            print u"** calling call_apis with overwrites false"
            self.call_apis(overwrite_orcid=False, overwrite_metrics=False)

            print u"** calling calculate"
            self.calculate()
        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            print u"got a requests timeout"
            self.error = "requests timeout"
        except OrcidDoesNotExist:
            self.invalid_orcid = True
            self.error = "invalid orcid"
            print u"error: invalid orcid: {}".format(self.orcid_id)
        except Exception:
            logging.exception("refresh error")
            self.error = "refresh error"
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()
        finally:
            self.updated = datetime.datetime.utcnow().isoformat()
            if self.error:
                print u"ERROR refreshing person {}: {}".format(self.id, self.error)


    # doesn't throw errors; sets error column if error
    def refresh(self, high_priority=False):
        print u"* refreshing {} ({})".format(self.orcid_id, self.full_name)
        self.error = None
        start_time = time()
        try:
            print u"** calling call_apis"
            self.call_apis(high_priority=high_priority)

            print u"** calling calculate"
            self.calculate()

            print u"** finished refreshing all {num} products for {orcid_id} ({name}) in {sec}s".format(
                orcid_id=self.orcid_id,
                name=self.full_name,
                num=len(self.all_products),
                sec=elapsed(start_time)
            )

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            print u"got a requests timeout"
            self.error = "requests timeout"
        except OrcidDoesNotExist:
            self.invalid_orcid = True
            self.error = "invalid orcid"
            print u"error: invalid orcid: {}".format(self.orcid_id)
        except Exception:
            logging.exception("refresh error")
            self.error = "refresh error"
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()
        finally:
            self.updated = datetime.datetime.utcnow().isoformat()
            if self.error:
                print u"ERROR refreshing person {}: {}".format(self.id, self.error)


    def set_mendeley(self, high_priority=False):
        self.set_data_for_all_products("set_data_from_mendeley", high_priority)

    def set_mendeley_sums(self):
        self.mendeley_sums = None
        products_with_mendeley = [p for p in self.all_products if p.mendeley_api_raw]
        if products_with_mendeley:
            self.mendeley_sums = {
            "readers": self.mendeley_readers,
            "country": self.mendeley_countries,
            "country_percent": as_proportion(self.mendeley_countries),
            "subdiscipline": self.mendeley_disciplines,
            "subdiscipline_percent": as_proportion(self.mendeley_disciplines),
            "academic_status": self.mendeley_job_titles,
            "academic_status_percent": as_proportion(self.mendeley_job_titles),
            "h_index": self._mendeley_h_index,
            "percent_of_products": self.mendeley_percent_of_products
            }
        else:
            print "no mendeley"
        return self.mendeley_sums


    def set_products(self, products_to_add):
        updated_products = []

        for product_to_add in products_to_add:
            needs_to_be_added = True
            for my_existing_product in self.products:
                if my_existing_product.orcid_put_code == product_to_add.orcid_put_code:

                    # update the product biblio from the most recent orcid api response
                    my_existing_product.orcid_api_raw_json = product_to_add.orcid_api_raw_json
                    my_existing_product.set_biblio_from_orcid()

                    updated_products.append(my_existing_product)
                    needs_to_be_added = False
            if needs_to_be_added:
                updated_products.append(product_to_add)
        self.products = updated_products


    def recalculate_openness(self):
        self.set_openness()
        self.set_num_oa_licenses()
        self.assign_badges(limit_to_badges=["percent_fulltext"])
        self.set_badge_percentiles(limit_to_badges=["percent_fulltext"])

    def set_num_oa_licenses(self):
        self.num_fulltext = 0
        self.num_any_oa = 0
        self.num_cc_by = 0
        self.num_cc_restricted = 0
        self.num_cc0_pd = 0

        for p in self.all_products:
            if p.fulltext_url:
                self.num_fulltext += 1

            if p.fulltext_url and p.license:
                if p.license != "unknown":
                    self.num_any_oa += 1

                if p.license == "cc-by":
                    self.num_cc_by += 1
                elif p.license == "cc0" or p.license == "pd":
                    self.num_cc0_pd += 1
                elif "cc-" in p.license:
                    self.num_cc_restricted += 1


    def email_new_stuff(self):
        if not self.claimed_at:
            return
        if not self.email:
            return

        # fake it for now
        # DATE_NOTIFICATION_EMAILS_STARTED = "2015-07-05"
        # self.events_emailed = {"emailed": []}

        DATE_NOTIFICATION_EMAILS_STARTED = "2016-07-01"

        if not self.events_emailed:
            self.events_emailed = {"emailed": []}

        print u"looking for new stuff to email for {}".format(self.email)
        posts = self.get_posts()
        posts_to_email = []
        for post in posts:
            post_date_iso = post["posted_on"]
            if post_date_iso > date_as_iso_utc(self.created):
                if post_date_iso > DATE_NOTIFICATION_EMAILS_STARTED:
                    if post["url"] not in self.events_emailed["emailed"]:
                        posts_to_email.append(post)

        if not posts_to_email:
            print u"nothing to email."
            return

        print u"have things to email!"
        post_urls = [post["url"] for post in posts_to_email]
        self.events_emailed["emailed"] += post_urls

        post_count_by_source = {}
        for post in posts_to_email:
            source = post["source"]
            try:
                post_count_by_source[source] += 1
            except KeyError:
                post_count_by_source[source] = 1

        new_event_counts = post_count_by_source.items()
        details_dict = self.to_dict()
        details_dict["post_count_to_email"] = new_event_counts

        send(self.email, "Your research is getting new attention online", "notification", {"profile": details_dict}, for_real=True)
        # send(self.email, "Your research is getting new attention online", "notification", {"profile": details_dict}, for_real=False)
        save_email(self.orcid_id, new_event_counts)


    def run_log_openness(self):
        save_openness_log(self)


    ## used to fix people's pictures if they have updated them on twitter
    ## called from command line, ie python update.py Person.update_twitter_profile_data --id=0000-0003-3904-7546
    def update_twitter_profile_data(self):
        if not self.twitter or not self.twitter_creds:
            print u"Can't update twitter, doesn't have twitter username or twitter_creds"
            return None

        oauth = OAuth1Session(
            os.getenv('TWITTER_CONSUMER_KEY'),
            client_secret=os.getenv('TWITTER_CONSUMER_SECRET')
        )
        url = "https://api.twitter.com/1.1/users/lookup.json?screen_name={}".format(self.twitter)
        r = oauth.get(url)
        response_data = r.json()
        first_profile = response_data[0]

        keys_to_update = ["profile_image_url", "profile_image_url_https"]
        for k in keys_to_update:
            self.twitter_creds[k] = first_profile[k]

        print u"Updated twitter creds for @{}".format(self.twitter)

        return self.twitter_creds

    def refresh_orcid_info(self):
        self.set_api_raw_from_orcid()
        self.set_from_orcid()
        self.set_num_products()


    def calculate(self):
        # things with api calls in them, or things needed to make those calls
        start_time = time()
        self.set_fulltext_urls()  # do after set publisher, which gets issns
        self.set_depsy()
        print u"finished api calling part of {method_name} on {num} products in {sec}s".format(
            method_name="calculate".upper(),
            num = len(self.products),
            sec = elapsed(start_time, 2)
        )

        # everything else
        start_time = time()
        self.set_post_counts() # do this first
        self.set_mendeley_sums()
        self.set_num_posts()
        self.set_num_mentions()
        self.set_num_products()
        self.set_openness()  # do after set_fulltext_urls
        self.set_num_oa_licenses() # do after set_fulltext_urls
        self.set_event_counts()
        self.set_coauthors()  # do this last, uses scores
        print u"finished calculating part of {method_name} on {num} products in {sec}s".format(
            method_name="calculate".upper(),
            num = len(self.products),
            sec = elapsed(start_time, 2)
        )

        start_time = time()
        self.assign_badges()
        self.set_badge_percentiles()

        print u"finished badges part of {method_name} on {num} products in {sec}s".format(
            method_name="calculate".upper(),
            num = len(self.products),
            sec = elapsed(start_time, 2)
        )

    def mini_calculate(self):
        self.set_num_posts()
        self.set_num_mentions()
        self.set_num_products()

    # convenience method to call base again as a batch job,
    # for example after adding license-storing code
    def call_base_on_base1s(self):
        products_with_base1 = [p for p in self.all_products if p.open_step == "base 1"]
        self.call_base(products_with_base1)


    # convenience method to call sherlock again as a batch job,
    # for example after adding license-storing code
    def call_sherlock_on_license_unknowns(self):
        products_for_sherlock = []
        for p in self.all_products:
            if p.fulltext_url and not p.license:
                products_for_sherlock += [p]
        self.call_sherlock(products_for_sherlock)



    def set_depsy(self):
        if self.email:
            headers = {'Accept': 'application/json'}
            # example http://depsy.org/api/search/person?email=ethan@weecology.org
            url = "http://depsy.org/api/search/person?email={}".format(self.email)
            # might throw requests.Timeout
            try:
                r = requests.get(url, headers=headers, timeout=10)
            except requests.Timeout:
                print u"timeout in set_depsy"
                return

            response_dict = r.json()
            if response_dict["count"] > 0:
                self.depsy_id = response_dict["list"][0]["id"]
                self.depsy_percentile = response_dict["list"][0]["impact_percentile"]
                print u"got a depsy id for {}: {}".format(self.id, self.depsy_id)


    @property
    def first_name(self):
        first_name = self.given_names
        try:
            parsed_name = HumanName(self.full_name)
            first_name = parsed_name["first"]
            if first_name and len(first_name) <= 2 and parsed_name["middle"]:
                first_name = parsed_name["middle"]
        except KeyError:
            pass
        # print u"set first name {} as first name for {}".format(self.first_name, self.full_name)
        return first_name


    def set_api_raw_from_orcid(self):
        start_time = time()

        # look up profile in orcid
        try:
            orcid_data = make_and_populate_orcid_profile(self.orcid_id)
            self.orcid_api_raw_json = orcid_data.api_raw_profile
        except requests.Timeout:
            self.error = "timeout from requests when getting orcid"

        print u"finished {method_name} in {sec}s".format(
            method_name="set_api_raw_from_orcid".upper(),
            sec = elapsed(start_time, 2)
        )

    def set_fresh_orcid(self):
        orcid_created_date_timestamp = self.orcid_api_raw_json["orcid-history"]["submission-date"]["value"]
        orcid_created_date = datetime.datetime.fromtimestamp(orcid_created_date_timestamp/1000)
        profile_created_date = self.created
        if not profile_created_date:
            # because just made and not set yet
            profile_created_date = datetime.datetime.utcnow()
        self.fresh_orcid = (profile_created_date - orcid_created_date).total_seconds() < (60*60)  # 1 hour

    def set_from_orcid(self):
        total_start_time = time()

        if not self.orcid_api_raw_json:
            print u"no orcid data in db for {}".format(self.orcid_id)
            return

        orcid_data = OrcidProfile(self.orcid_id)
        orcid_data.api_raw_profile = self.orcid_api_raw_json

        self.given_names = orcid_data.given_names
        self.family_name = orcid_data.family_name
        self.set_fresh_orcid()
        if orcid_data.best_affiliation:
            self.affiliation_name = orcid_data.best_affiliation["name"]
            self.affiliation_role_title = orcid_data.best_affiliation["role_title"]
        else:
            self.affiliation_name = None
            self.affiliation_role_title = None

        # now walk through all the orcid works and save the most recent ones in our db, deduped.
        products_to_add = []
        for work in orcid_data.works:
            new_product = make_product(work)
            products_to_add = distinct_product_list(new_product, products_to_add)

        products_to_add.sort(key=operator.attrgetter('year_int'), reverse=True)

        # keep only most recent products
        products_to_add = products_to_add[:100]

        self.set_products(products_to_add)



    def set_fulltext_urls(self):
        # handle this in impactstory
        # ### first: user supplied a url?  it is open!
        # print u"first making user_supplied_fulltext_url products open"
        for p in self.all_products:
            if p.user_supplied_fulltext_url:
                p.set_oa_from_user_supplied_fulltext_url(p.user_supplied_fulltext_url)

        # then call sherlock on the rest!
        self.call_sherlock()



    def call_sherlock(self, call_even_if_already_open=False):
        print u"calling sherlock!"
        start_time = time()

        products_for_sherlock = {}

        for p in self.products:
            if call_even_if_already_open:
                products_for_sherlock[p.id] = p
            else:
                if not p.has_fulltext_url or not p.license:
                    products_for_sherlock[p.id] = p

        if not products_for_sherlock:
            return

        biblios_for_sherlock = [p.biblio_for_sherlock() for p in products_for_sherlock.values()]
        # print biblios_for_sherlock
        url = u"http://api.sherlockoa.org/v1/publications"
        # url = u"http://localhost:5000/v1/publications"

        # print u"calling sherlock with", biblios_for_sherlock
        post_body = {"biblios": biblios_for_sherlock}
        # print "\n\n"
        # print json.dumps(post_body)
        # print "\n\n"
        r = requests.post(url, json=post_body)
        if r and r.status_code==200:
            results = r.json()["results"]
            for response_dict in results:
                if response_dict["free_fulltext_url"]:
                    product_id = response_dict["product_id"]
                    products_for_sherlock[product_id].fulltext_url = response_dict["free_fulltext_url"]
                    products_for_sherlock[product_id].license = response_dict["license"]

        open_products = [p for p in products_for_sherlock.values() if p.has_fulltext_url]
        print u"number of open_products is {}".format(len(open_products))

        print u"finished {method_name} on {num} products in {sec}s".format(
            method_name="call_sherlock".upper(),
            num = len(products_for_sherlock),
            sec = elapsed(start_time, 2)
        )

    def set_data_for_all_products(self, method_name, high_priority=False, include_products=None):
        start_time = time()
        threads = []

        # use all products unless passed a specific set
        if not include_products:
            include_products = self.all_products

        # start a thread for each product
        for work in include_products:
            method = getattr(work, method_name)
            process = threading.Thread(target=method, args=[high_priority])
            process.start()
            threads.append(process)

        # wait till all work is done
        for process in threads:
            process.join()

        # now go see if any of them had errors
        # need to do it this way because can't catch thread failures; have to check
        # object afterwards instead to see if they logged failures
        for work in include_products:
            if work.error:
                # don't print out doi here because that could cause another bug
                # print u"setting person error; {} for product {}".format(work.error, work.id)
                self.error = work.error

        print u"finished {method_name} on {num} products in {sec}s".format(
            method_name=method_name.upper(),
            num = len(include_products),
            sec = elapsed(start_time, 2)
        )



    @property
    def picture(self):
        try:
            url = self.twitter_creds["profile_image_url"].replace("_normal", "").replace("http:", "https:")
        except TypeError:
            # no twitter. let's try gravatar

            try:
                email_hash = hashlib.md5(self.email).hexdigest()
            except TypeError:
                # bummer, no email either. that's ok, gravatar will return a blank face for
                # an email they don't have
                email_hash = ""

            url = u"https://www.gravatar.com/avatar/{}?s=110&d=mm".format(email_hash)

        return url


    @property
    def wikipedia_urls(self):
        articles = set()
        for my_product in self.products_with_dois:
            if my_product.post_counts_by_source("wikipedia"):
                articles.update(my_product.wikipedia_urls)
        return articles

    @property
    def distinct_fans_count(self):
        fans = set()
        for my_product in self.products_with_dois:
            for fan_name in my_product.twitter_posters_with_followers:
                fans.add(fan_name)
        return len(fans)

    @property
    def countries_using_mendeley(self):
        countries = set()
        for my_product in self.all_products:
            for my_country in my_product.countries_using_mendeley:
                if my_country:
                    countries.add(my_country)
        return sorted(countries)


    @property
    def countries(self):
        countries = set()
        for my_product in self.products:
            for my_country in my_product.countries:
                if my_country:
                    countries.add(my_country)
        return sorted(countries)


    @property
    def subscores(self):
        resp = []
        subscore_names = ["buzz", "engagement", "openness", "fun"]
        for subscore_name in subscore_names:
            resp.append({
                "name": subscore_name,
                "display_name": subscore_name
            })
        return resp

    @property
    def sources(self):
        sources = []
        for source_name in sources_metadata:
            source = Source(source_name, self.products)
            if source.posts_count > 0:
                sources.append(source)
        return sources


    # convenience so can have all of these set for one profile
    def set_post_details(self):
        for my_product in self.products_with_dois:
            my_product.set_post_details()


    def set_coauthors(self):
        # comment out the commit.  this means coauthors made during this commit session don't show up on this refresh
        # but doing it because is so much faster
        # safe_commit(db)

        # now go for it
        # print u"running coauthors for {}".format(self.orcid_id)
        coauthor_orcid_id_query = u"""select distinct orcid_id
                    from product
                    where doi in
                      (select doi from product where orcid_id='{}')""".format(self.orcid_id)
        rows = db.engine.execute(text(coauthor_orcid_id_query))

        # remove own orcid_id
        orcid_ids = [row[0] for row in rows if row[0] if row[0] != self.id]
        if not orcid_ids:
            return

        # don't load products or badges
        coauthors = Person.query.filter(Person.orcid_id.in_(orcid_ids)).options(orm.noload('*')).all()

        resp = {}
        for coauthor in coauthors:
            resp[coauthor.orcid_id] = {
                "name": coauthor.full_name,
                "id": coauthor.id,
                "orcid_id": coauthor.orcid_id,
                "num_posts": coauthor.num_posts,
            }
        self.coauthors = resp


    def get_event_dates(self):
        event_dates = []

        for product in self.products_with_dois:
            if product.event_dates:
                for source, dates_list in product.event_dates.iteritems():
                    event_dates += dates_list
        # now sort them all
        event_dates.sort(reverse=False)
        return event_dates

    def set_event_counts(self):
        self.monthly_event_count = 0
        self.weekly_event_count = 0

        event_dates = self.get_event_dates()
        if not event_dates:
            return

        for event_date in event_dates:
            event_days_ago = days_ago(event_date)
            if event_days_ago <= 7:
                self.weekly_event_count += 1
            if event_days_ago <= 30:
                self.monthly_event_count += 1


    def get_tweeter_names(self, most_recent=None):
        twitter_posts = self.get_twitter_posts(most_recent)
        names = [post["attribution"] for post in twitter_posts if "attribution" in post]
        return names

    def get_twitter_posts(self, most_recent=None):
        twitter_posts = [post for post in self.get_posts() if post["source"]=="twitter"]
        if most_recent:
            twitter_posts = twitter_posts[0:most_recent]
        return twitter_posts

    def get_posts(self):
        posts = []
        for my_product in self.products_with_dois:
            posts += my_product.posts
        return posts

    @property
    def percent_open_license(self):
        if not self.all_products:
            return None

        if self.num_products >= 1:
            response = round(self.num_cc_by+self.num_cc0_pd/float(self.num_products)), 3)
        else:
            response = None

        return response


    @property
    def percent_fulltext(self):
        if not self.all_products:
            return None

        num_open_products = len([p for p in self.all_products if p.has_fulltext_url])

        # only defined if three or more products
        if self.num_products >= 1:
            response = round((num_open_products / float(self.num_products)), 3)
        else:
            response = None

        return response


    def set_openness(self):
        self.openness = self.percent_fulltext
        return self.openness


    def post_counts_by_source(self, source_name):
        if self.post_counts and source_name in self.post_counts:
            return self.post_counts[source_name]
        return 0

    def set_post_counts(self):
        self.post_counts = {}

        for p in self.products_with_dois:
            if p.post_counts:
                for metric, count in p.post_counts.iteritems():
                    try:
                        self.post_counts[metric] += int(count)
                    except KeyError:
                        self.post_counts[metric] = int(count)

        # print u"setting post_counts", self.post_counts


    def set_num_posts(self):
        self.num_posts = 0
        if self.post_counts:
            self.num_posts = sum(self.post_counts.values())

    def set_num_mentions(self):
        self.num_mentions = sum([p.num_mentions for p in self.all_products])

    def set_num_products(self):
        self.num_products = len(self.all_products)

    def get_token(self):
        # print u"in get_token with ", self
        payload = {
            'id': self.id,
            'email': self.email,
            'num_products': self.num_products,
            'finished_wizard': self.finished_wizard,
            'orcid_id': self.orcid_id,
            'twitter_screen_name': self.twitter,
            'first_name': self.first_name,
            'claimed_at': date_as_iso_utc(self.claimed_at),
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=999),
        }

        # for testing
        # payload["orcid_id"] = None
        # payload["num_products"] = 0



        token = jwt.encode(payload, os.getenv("JWT_KEY"))
        return token.decode('unicode_escape')

    @property
    def badges_to_show_in_ui(self):
        return [b for b in self.badges_for_api if b.my_badge_type.show_in_ui]

    @property
    def overview_badges(self):
        overview_possibilities = self.badges_to_show_in_ui

        if len(overview_possibilities) <= 3:
            return overview_possibilities

        already_have_groups = []
        badges_to_return = []

        for my_badge in overview_possibilities:
            if my_badge.group not in already_have_groups and my_badge.group != "fun":
                badges_to_return.append(my_badge)
                already_have_groups.append(my_badge.group)

        if len(badges_to_return) < 3:
            for my_badge in overview_possibilities:
                if my_badge.group != "fun" and (my_badge.name not in [b.name for b in badges_to_return]):
                    badges_to_return.append(my_badge)

        return badges_to_return[0:3]

    @property
    def badges_for_api(self):
        badges = []
        for my_badge in self.badges:
            if my_badge.value and my_badge.my_badge_type.valid_badge:
                # custom exclusions specific to badge type
                badges.append(my_badge)

        badges.sort(key=lambda x: x.sort_score, reverse=True)


        # custom exclusions specific to badge type
        if len(badges) > 1:
            badges = [b for b in badges if b.name != "first_steps"]

        return badges

    def get_badge(self, badge_name):
        for my_badge in self.badges:
            if my_badge.name == badge_name:
                return my_badge
        return None

    def assign_badges(self, limit_to_badges=[]):

        for badge_assigner_class in badge.all_badge_assigners():

            badge_assigner = badge_assigner_class()
            if limit_to_badges:
                if badge_assigner.name not in limit_to_badges:
                    # isn't a badge we want to assign right now, so skip
                    continue

            candidate_badge = badge_assigner.get_badge_or_None(self)
            already_assigned_badge = self.get_badge(badge_assigner.name)

            if candidate_badge:
                if already_assigned_badge:
                    already_assigned_badge.value = candidate_badge.value
                    already_assigned_badge.products = candidate_badge.products
                    already_assigned_badge.support = candidate_badge.support
                    print u"{} already had badge, now updated {}".format(
                        self.id, already_assigned_badge)
                else:
                    print u"{} first time got badge {}".format(self.id, candidate_badge)
                    self.badges.append(candidate_badge)

                    if candidate_badge.name == 'babel':
                        print u"BABEL support: {}".format(candidate_badge.support)

            else:
                # print u"nope, {} doesn't get badge {}".format(self.id, badge_assigner.name)
                if already_assigned_badge:
                    print u"{} doesn't get badge {}, but had it before, so removing".format(self.id, badge_assigner.name)

                    if already_assigned_badge.name == 'babel':
                        print u"first, here was its BABEL support: {}".format(already_assigned_badge.support)
                        print u"used to have babel support on dois: {}".format(already_assigned_badge.dois)

                    badge.Badge.query.filter_by(id=already_assigned_badge.id).delete()

        self.num_badges = len(self.badges_to_show_in_ui)



    def set_badge_percentiles(self, limit_to_badges=[]):
        badge_names = [my_badge.name for my_badge in self.badges]
        refsets = Refset.query.filter(Refset.name.in_(badge_names)).all()

        for my_badge in self.badges:
            if limit_to_badges:
                if my_badge.name not in limit_to_badges:
                    # isn't a badge we want to assign right now, so skip
                    continue

            if my_badge.name in badge.all_badge_assigner_names():
                # from http://stackoverflow.com/a/7125547/596939
                matching_refset = next((ref for ref in refsets if ref.name==my_badge.name), None)

                if matching_refset:
                    my_badge.set_percentile(matching_refset.cutoffs)


    @property
    def parsed_name(self):
        return u"{} {}".format(self.given_names, self.family_name)


    @property
    def full_name(self):
        return u"{} {}".format(self.given_names, self.family_name)


    @property
    def num_twitter_followers(self):
        try:
            return self.twitter_creds["followers_count"]
        except TypeError:
            return None

    @property
    def display_coauthors(self):
        if not self.coauthors:
            return None
        else:
            ret = []
            for coauthor in self.coauthors.values():
                coauthor["sort_score"] = coauthor.get("num_posts", 0)
                ret.append(coauthor)
            return ret

    # convenience method
    def all_products_set_biblio_from_orcid(self):
        for p in self.all_products:
            p.set_biblio_from_orcid()

    @property
    def sorted_products(self):
        return sorted([p for p in self.products],
                key=lambda k: k.altmetric_score,
                reverse=True)

    @property
    def products_with_dois(self):
        ret = [p for p in self.all_products if p.doi]
        return ret

    @property
    def products_no_dois(self):
        ret = [p for p in self.all_products if not p.doi]
        return ret

    @property
    def products_with_mentions(self):
        ret = [p for p in self.all_products if p.has_mentions]
        return ret

    @property
    def all_products(self):
        ret = self.sorted_products
        return ret


    @property
    def mendeley_readers(self):
        total = 0
        for p in self.all_products:
            if p.mendeley_api_raw and "reader_count" in p.mendeley_api_raw:
                total += p.mendeley_api_raw["reader_count"]
        return total

    @property
    def mendeley_percent_of_products(self):
        if not self.all_products:
            return None

        count = 0
        for p in self.all_products:
            if p.mendeley_api_raw and "reader_count" in p.mendeley_api_raw:
                if p.mendeley_api_raw["reader_count"] >= 1:
                    count += 1
        return float(count) / len(self.all_products)

    @property
    def mendeley_countries(self):
        resp = {}
        for p in self.all_products:
            try:
                resp = update_recursive_sum(resp, p.mendeley_api_raw["reader_count_by_country"])
            except (AttributeError, TypeError):
                pass
        return resp

    @property
    def mendeley_disciplines(self):
        resp = {}
        for p in self.all_products:
            try:
                resp = update_recursive_sum(resp, p.mendeley_disciplines)
            except (AttributeError, TypeError):
                pass
        return resp

    @property
    def mendeley_job_titles(self):
        resp = {}
        for p in self.all_products:
            try:
                resp = update_recursive_sum(resp, p.mendeley_job_titles)
            except (AttributeError, TypeError):
                pass
        return resp

    @property
    def _mendeley_h_index(self):
        reader_counts = []
        for p in self.all_products:
            try:
                reader_counts.append(p.mendeley_api_raw["reader_count"])
            except (KeyError, TypeError):
                reader_counts.append(0)

        t_index = h_index(reader_counts)
        return t_index

    def __repr__(self):
        return u'<Person ({id}, @{twitter}, {orcid_id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            twitter=self.twitter,
            orcid_id=self.orcid_id,
            given_names=self.given_names,
            family_name=self.family_name
        )


    def to_dict(self):
        ret = {
            "_id": self.id,  # do this too, so it is on top
            "_full_name": self.full_name,
            "id": self.id,
            "orcid_id": self.orcid_id,
            "email": self.email,
            "first_name": self.first_name,
            "given_names": self.given_names,
            "family_name": self.family_name,
            "created": date_as_iso_utc(self.created),
            "updated": date_as_iso_utc(self.updated),
            "claimed_at": date_as_iso_utc(self.claimed_at),
            "picture": self.picture,
            "affiliation_name": self.affiliation_name,
            "affiliation_role_title": self.affiliation_role_title,
            "twitter": self.twitter,
            "depsy_id": self.depsy_id,
            "campaign": self.campaign,
            "percent_fulltext": self.percent_fulltext,
            "percent_open_license": self.percent_open_license,
            "fresh_orcid": self.fresh_orcid,
            "num_posts": self.num_posts,
            "num_mentions": self.num_mentions,
            "num_orcid_products": len(self.all_products),
            "mendeley": {
                "country_percent": as_proportion(self.mendeley_countries),
                "subdiscipline_percent": as_proportion(self.mendeley_disciplines),
                "job_title_percent": as_proportion(self.mendeley_job_titles),
                "mendeley_url": None,
                "readers": self.mendeley_readers,
                "percent_of_products": self.mendeley_percent_of_products
            },
            "sources": [s.to_dict() for s in self.sources],
            "overview_badges": [b.to_dict() for b in self.overview_badges],
            "badges": [b.to_dict() for b in self.badges_for_api],
            "coauthors": self.display_coauthors,
            "subscores": self.subscores,
            "products": [p.to_dict() for p in self.all_products],
            "num_twitter_followers": self.num_twitter_followers
        }


        # for testing! no products for jason.
        # if self.orcid_id == "0000-0001-6187-6610":
        #     ret["products"] = []

        return ret


def h_index(citations):
    # from http://www.rainatian.com/2015/09/05/leetcode-python-h-index/

    citations.sort(reverse=True)

    i=0
    while (i<len(citations) and i+1 <= citations[i]):
        i += 1

    return i



