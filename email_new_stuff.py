from time import time
from datetime import date
import calendar
import argparse

import update

# to test just one: python email_new_stuff.py --now --orcid=0000-0003-1613-5981

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


