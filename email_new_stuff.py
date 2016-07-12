from time import time
from datetime import date
import calendar
from util import elapsed
from util import safe_commit
import argparse

from models import emailer
from collections import defaultdict
import update


def email_everyone(filename):

    with open(filename, "r") as f:
        lines = f.read().split("\n")
        print "found {} lines".format(len(lines))

    total_start = time()
    row_num = 0
    people_to_email = defaultdict(dict)

    # skip header row
    for line in lines[1:]:
        row_num += 1

        try:
            (url_slug,orcid_id,twitter_id,email,stripe_id,is_advisor,given_name,surname,created,last_viewed_profile) = line.split(",")

            is_subscribed = len(stripe_id)>0 or is_advisor=="t"

            people_to_email[email] = {
                "orcid_id": orcid_id,
                "is_subscribed": is_subscribed,
                "given_name": given_name,
                "surname": surname,
                "refunded": False
            }
            print u"added person {} {} {}".format(row_num, email, people_to_email[email])
        except ValueError:
            print u"couldn't parse", line

    with open("data/impactstory_refunds.csv", "r") as f:
        lines = f.read().split("\r")
        print "found {} lines".format(len(lines))

    for line in lines[1:]:
        try:
            (stripe_created,full_name,email) = line.split(",")
            if email in people_to_email:
                people_to_email[email]["refunded"] = True
                print "added refunded true to dict for", email
            else:
                people_to_email[email] = {
                    "orcid_id": None,
                    "is_subscribed": False,
                    "refunded": True
                }
                print "added new emailee true to dict for", email
        except ValueError:
            print "couldn't parse"

    # email = "heather@impactstory.org"
    # send_tng_email("heather@impactstory.org", people_to_email[email])

    num_sending = 0
    num_not_sending = 0
    for email, addressee_dict in people_to_email.iteritems():
        if addressee_dict["is_subscribed"] or addressee_dict["refunded"]:
            if email in emails_sent:
                num_not_sending += 1
                print "not sending email to", email, "because already sent"
            else:
                print "WOULD send email to", email
                num_sending += 1

                #### COMMENTED OUT so don't accidentally send
                # send_tng_email(email, addressee_dict)

    print "num_not_sending", num_not_sending
    print "num_sending", num_sending


def send_tng_email(email, addressee_dict, now=None):
    pass

    # report_dict = {"profile": addressee_dict}
    #
    # msg = emailer.send(email, "The new Impactstory: Better. Freer.", "welcome", report_dict)
    #
    # print "SENT EMAIL to ", email





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    parser.add_argument('--now', action="store_true", default=False, help="send the emails now even if not specified day")
    parsed_args = update.parse_update_optional_args(parser)
    parsed_args.fn = "Person.email_new_stuff"

    run_now = False

    if parsed_args.now:
        print u"emailing because run_now override"
        run_now = True
    else:
        day_of_week_for_emails = "Tuesday"
        my_date = date.today()
        my_day_of_week = calendar.day_name[my_date.weekday()]
        run_now = (my_day_of_week == day_of_week_for_emails)

    if run_now:
        update.run_update(parsed_args)
    else:
        print u"not {} today so not emailing".format(day_of_week_for_emails)


