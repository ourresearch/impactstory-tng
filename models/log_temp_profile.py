from sqlalchemy.dialects.postgresql import JSONB
import datetime
import urlparse

from app import db
from util import safe_commit

def add_new_log(my_temp_person, request=None):
    if LogTempProfile.query.get(my_temp_person.orcid_id):
        return

    new_log = LogTempProfile(my_temp_person, request)
    db.session.add(new_log)
    safe_commit(db)

class LogTempProfile(db.Model):
    orcid_id = db.Column(db.Text, primary_key=True)
    source = db.Column(db.Text)
    ip = db.Column(db.Text)
    created = db.Column(db.DateTime)
    num_products = db.Column(db.Integer)
    num_posts = db.Column(db.Integer)
    num_badges = db.Column(db.Integer)
    percent_fulltext = db.Column(db.Float)
    error = db.Column(db.Text)

    details = db.Column(JSONB)

    def __init__(self, my_temp_person, request=None):
        self.orcid_id = my_temp_person.orcid_id
        self.num_products = my_temp_person.num_products
        self.num_posts = my_temp_person.num_posts
        self.num_badges = my_temp_person.num_badges
        self.percent_fulltext = my_temp_person.percent_fulltext
        self.error = my_temp_person.error

        self.created = datetime.datetime.utcnow()

        if request:
            self.ip = request.remote_addr
            if request.referrer:
                referrer_parsed = urlparse.urlparse(request.referrer)
                source = urlparse.parse_qs(referrer_parsed.query).get("source", None)
                if source:
                    self.source = source[0]
                elif "datacite" in request.referrer:
                    self.source = "datacite"
                else:
                    self.source = request.referrer

    def __repr__(self):
        return u'<LogTempProfile ({orcid_id}, {source}) >'.format(
            orcid_id=self.orcid_id,
            source=self.source
        )


