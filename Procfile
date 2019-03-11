web: gunicorn views:app -w 2 --reload
refresh: python update.py Person.refresh --limit=10000000000 --chunk=1