from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
import datetime
import shortuuid
from util import safe_commit

def save_openness_log(my_person):
    # make a new log
    new_openness_log = LogOpenness()
    new_openness_log.set_openness_columns(my_person)

    # see if we already have a log the same as this.  if so, nothing to do, return.
    q = LogOpenness.query.filter_by(orcid_id=my_person.orcid_id).order_by(LogOpenness.created.desc())
    most_recent_log = q.first()
    if most_recent_log:
        if new_openness_log.has_same_openness(most_recent_log):
            print u"no new openness to log for {}".format(my_person.orcid_id)
            return

    # nope!  is worth logging.  finish adding attributes and store in db
    new_openness_log.id = shortuuid.uuid()[0:10]
    new_openness_log.created = datetime.datetime.utcnow().isoformat()
    new_openness_log.orcid_id = my_person.orcid_id
    db.session.add(new_openness_log)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on new_openness_log {}".format(new_openness_log.orcid_id)
    print u"logged new openness for {}".format(my_person.orcid_id)
    return


openness_columns = [
    "num_products",
    "num_fulltext",
    "num_any_oa",
    "num_cc_by",
    "num_cc_restricted",
    "num_cc0_pd"
]

class LogOpenness(db.Model):
    id = db.Column(db.Text, primary_key=True)
    orcid_id = db.Column(db.Text)
    created = db.Column(db.DateTime)

    num_products = db.Column(db.Integer)
    num_fulltext = db.Column(db.Integer)
    num_any_oa = db.Column(db.Integer)
    num_cc_by = db.Column(db.Integer)
    num_cc_restricted = db.Column(db.Integer)
    num_cc0_pd = db.Column(db.Integer)

    def set_openness_columns(self, person):
        for k in openness_columns:
            self.__setattr__(k, getattr(person, k))

    def has_same_openness(self, new_log_openness):
        for k in openness_columns:
            if getattr(self, k) != getattr(new_log_openness, k):
                return False
        return True

