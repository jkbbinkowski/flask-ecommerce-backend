# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
from functools import wraps
import dotenv
import configparser


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not flask.session.get('logged'):
            return flask.Response(flask.render_template('error_codes/401.html'), status=401)
        return f(*args, **kwargs)
    return decorated_function


def logout_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if flask.session.get('logged'):
            return flask.redirect(config['ENDPOINTS']['user'])
        return f(*args, **kwargs)
    return decorated_function