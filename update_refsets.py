from time import time
from app import db
from util import elapsed
from util import safe_commit
import argparse

from models.refset import update_refsets

# needs to be imported so the definitions get loaded into the registry
import jobs_defs

if __name__ == "__main__":
    start = time()
    update_refsets()
    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))



