# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import dotenv
import configparser


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


bp = flask.Blueprint('index', __name__, url_prefix='/')


@bp.route('', methods=['GET'])
def main():
    return flask.render_template('index.html')


@bp.route(f'{config['ACTIONS']['download_invoice']}/<invoice_uuid>', methods=['GET'])
def download_invoice(invoice_uuid):
    
    ### logic here to download invoice

    return invoice_uuid, 200