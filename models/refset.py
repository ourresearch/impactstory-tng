from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import deferred
from sqlalchemy.orm import Load
from sqlalchemy import orm
from sqlalchemy import text
from sqlalchemy import func
import datetime
from collections import defaultdict

from app import db

from models.badge import Badge
from models.badge import get_badge_assigner
from util import safe_commit
from util import chunk_into_n_sublists

def base_count_people_query():
    from models.person import Person
    # speed optimizations are from https://gist.github.com/hest/8798884
    count_q = db.session.query(Person)
    return count_q

# make this standalone function so everywhere uses the same query for this
def refine_refset_query(base_query):
    from models.person import Person
    q = base_query.filter(Person.campaign == "2015_with_urls")
    return q

def num_people_in_db():
    count_q = base_count_people_query()
    count_q = count_q.statement.with_only_columns([func.count()]).order_by(None)
    count = db.session.execute(count_q).scalar()
    print u"db person count", count
    return count

def num_people_in_refset():
    count_q = base_count_people_query()
    count_q = refine_refset_query(count_q)
    count_q = count_q.statement.with_only_columns([func.count()]).order_by(None)
    count = db.session.execute(count_q).scalar()
    print u"refsize count", count
    return count

def update_refsets():
    from models.person import Person

    print u"getting the badge percentile refsets...."

    q = db.session.query(Person).options(
             Load(Person).load_only("campaign", "orcid_id"))
    q = q.options(orm.noload('*'))
    q = q.options(orm.subqueryload("badges"))

    # q = refine_refset_query(q)
    rows = q.all()

    print u"query finished, now set the values in the lists"
    print "\n\n\n"
    refset_list_dict = defaultdict(list)
    for person in rows:
        for badge in person.badges:
            # print "BADGE", badge
            if badge.value != None:
                refset_list_dict[badge.name].append(badge.value)

    num_in_refset = num_people_in_refset()

    for name, unsorted_values in refset_list_dict.iteritems():
        print u"refreshing refset {}".format(name)

        assigner = get_badge_assigner(name)
        if assigner.pad_percentiles_with_zeros:
            # pad with zeros for all the people who didn't get the badge
            unsorted_values.extend([0] * (num_in_refset - len(unsorted_values)))

        # now sort
        # for testing!!!
        refset_list_dict[name] = sorted(unsorted_values)
        # refset_list_dict[name] = sorted(unsorted_values[0:200])

        # now pick out the cutoffs, minimum value at each of 100
        cutoffs = []
        for sublist in chunk_into_n_sublists(refset_list_dict[name], 100):
            sublist_values = sublist
            if sublist_values:
                cutoffs.append(min(sublist_values))

        this_badge_refset = Refset(name=name, cutoffs=cutoffs)
        print u"saving refset {} with cutoffs {}".format(name, cutoffs)

        db.session.merge(this_badge_refset)


    # and finally save it all

    safe_commit(db)




class Refset(db.Model):
    name = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    cutoffs = db.Column(JSONB)

    def __init__(self, name, cutoffs):
        self.name = name
        self.cutoffs = cutoffs
        self.updated = datetime.datetime.utcnow().isoformat()

    def __repr__(self):
        return u'<Refset ({name}) >'.format(
            name=self.name
        )


