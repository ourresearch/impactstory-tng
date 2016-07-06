from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
import datetime
import shortuuid
from util import safe_commit

def save_email(orcid_id, contents):
    email = Email()
    email.id = shortuuid.uuid()[0:10]
    email.sent = datetime.datetime.utcnow().isoformat()
    email.orcid_id = orcid_id
    email.contents = dict(contents)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on email {}".format(email.orcid_id)

class Email(db.Model):
    id = db.Column(db.Text, primary_key=True)
    orcid_id = db.Column(db.Text)
    sent = db.Column(db.DateTime)
    contents = db.Column(MutableDict.as_mutable(JSONB))
