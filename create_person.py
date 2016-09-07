from time import time
from app import db
from util import elapsed
from util import safe_commit
import argparse

from models.person import make_person
from models.orcid import clean_orcid
from models.orcid import NoOrcidException

# needs to be imported so the definitions get loaded into the registry
import jobs_defs


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def create_person(dirty_orcid, campaign=None, store_in_db=False):

    try:
        orcid_id = clean_orcid(dirty_orcid)
    except NoOrcidException:
        print u"\n\nWARNING: no valid orcid_id in {}; skipping\n\n".format(dirty_orcid)
        raise

    if store_in_db:
        print u"storing in db"
        my_person = make_person(orcid_id, store_in_db=True)
        if campaign:
            my_person.campaign = campaign
            db.session.add(my_person)
            success = safe_commit(db)
            if not success:
                print u"ERROR!  committing {}".format(my_person.orcid_id)
    else:
        print u"NOT storing in db"
        my_person = make_person(orcid_id, store_in_db=False)
        print my_person




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('orcid_id', type=str, help="ORCID ID to build")
    parser.add_argument('--campaign', type=str, help="name of campaign")
    parser.add_argument('--store', type=bool, help="store in the database?")
    parsed = parser.parse_args()

    start = time()
    create_person(parsed.orcid_id, parsed.campaign, parsed.store)

    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


