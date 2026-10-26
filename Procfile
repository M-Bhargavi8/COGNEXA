release: flask --app wsgi db upgrade
web: waitress-serve --listen=0.0.0.0:$PORT --threads=${WAITRESS_THREADS:-8} --ident=cognexa wsgi:app
