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


bp = flask.Blueprint('footer', __name__, url_prefix='/')


@bp.route(config['ENDPOINTS']['about'], methods=['GET'])
def about_us():
    return flask.render_template('footer/about_us.html')


@bp.route(config['ENDPOINTS']['contact'], methods=['GET'])
def contact():
    return flask.render_template('footer/contact.html')


@bp.route(config['ENDPOINTS']['payments'], methods=['GET'])
def payments():
    return flask.render_template('footer/payments.html')


@bp.route(config['ENDPOINTS']['shipping'], methods=['GET'])
def shipping():
    return flask.render_template('footer/shipping.html')


@bp.route(config['ENDPOINTS']['dropshipping'], methods=['GET'])
def dropshipping():
    return flask.render_template('footer/dropshipping.html')


@bp.route(config['ENDPOINTS']['faq'], methods=['GET'])
def faq():
    return flask.render_template('footer/faq.html')


@bp.route(config['ENDPOINTS']['regulations'], methods=['GET'])
def regulations():
    return flask.render_template('footer/regulations.html')


@bp.route(config['ENDPOINTS']['privacy_policy'], methods=['GET'])
def privacy_policy():
    return flask.render_template('footer/privacy_policy.html')


@bp.route(config['ENDPOINTS']['returns'], methods=['GET'])
def returns():
    return flask.render_template('footer/returns.html')


@bp.route(config['ENDPOINTS']['complaints'], methods=['GET'])
def complaints():
    return flask.render_template('footer/complaints.html')


@bp.route(config['ENDPOINTS']['purchase_safety'], methods=['GET'])
def purchase_safety():
    return flask.render_template('footer/purchase_safety.html')


@bp.route(config['ENDPOINTS']['cooperation'], methods=['GET'])
def cooperation():
    return flask.render_template('footer/cooperation.html')


@bp.route(config['ENDPOINTS']['forms']+'/<form>', methods=['GET'])
def forms(form):
    try:
        return flask.send_file(f'{working_dir}flaskr/static/pdf/{form}')
    except:
        return flask.abort(404)
