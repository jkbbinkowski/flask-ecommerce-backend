# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import dotenv
import configparser
import flaskr.jinja_filters
import datetime
import base64
import json
import uuid
import flaskr.functions


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


bp = flask.Blueprint('cart', __name__, url_prefix=config['ENDPOINTS']['cart'])


@bp.route(config['ACTIONS']['init'])
def check_cart():
    if not (flaskr.functions.get_cart_cookie(flask.request) and (flask.session.get('logged'))):
        cart_uuid = str(uuid.uuid4())
        resp = flask.make_response()
        resp.set_cookie(config['COOKIE_NAMES']['cart'], cart_uuid, expires=datetime.datetime.now()+datetime.timedelta(days=365*10), path='/')
        return resp
    else:
        return '', 200