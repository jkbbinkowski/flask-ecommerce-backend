# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import dotenv
import configparser
import json
import flaskr.functions
import time


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


bp = flask.Blueprint('order', __name__, url_prefix=config['ENDPOINTS']['calculate_shipping_cost'])