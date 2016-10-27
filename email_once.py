from time import time
from datetime import date
import calendar
import argparse

import update


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    parsed_args = update.parse_update_optional_args(parser)
    parsed_args.fn = "Person.email_new_badge"

    update.run_update(parsed_args)


