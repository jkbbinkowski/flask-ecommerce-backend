# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import json
import flask_compress
import flask_assets
import flask_wtf
from datetime import datetime
import dotenv
import configparser
import redis
import flaskr.functions
import flaskr.jinja_filters


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


app = flask.Flask(__name__, instance_relative_config=True)


# configure csrf
csrf = flask_wtf.csrf.CSRFProtect(app)


# ASSETS CONFIG
assets = flask_assets.Environment(app)
css = flask_assets.Bundle('css/bootstrap.min.css', 'css/main.css', 'css/LineIcons.3.0.css', 'css/tiny-slider.css', 'css/glightbox.min.css', output='min/packed.css', filters='cssmin')
assets.register('css_all', css)
js_all = flask_assets.Bundle('js/bootstrap.min.js', 'js/tiny-slider.js', 'js/glightbox.min.js', 'js/main.js', output='min/packed.js', filters='jsmin')
assets.register('js_all', js_all)
js_auth = flask_assets.Bundle('js/auth.js', output='min/apacked.js', filters='jsmin')
assets.register('js_auth', js_auth)
js_user = flask_assets.Bundle('js/user.js', output='min/upacked.js', filters='jsmin')
assets.register('js_user', js_user)


# configure gzip 
compress = flask_compress.Compress(app)


# jinja custom filters
app.jinja_env.filters['slugify'] = flaskr.jinja_filters.slugify


# app config
app.config['SERVER_NAME'] = config['APP']['server_name']
app.config['TESTING'] = int(config['APP']['testing'])
app.config['DEBUG'] = int(config['APP']['debug'])
app.config['FLASK_ENV'] = config['APP']['environment']
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.jinja_env.auto_reload = int(config['APP']['templates_auto_reload'])
if int(config['APP']['set_cookie_settings']) == 1:
    app.config['SESSION_COOKIE_SECURE'] = int(config['APP']['session_cookie_secure'])
    app.config['SESSION_COOKIE_SAMESITE'] = config['APP']['session_cookie_samesite']
    app.config['SESSION_COOKIE_HTTPONLY'] = int(config['APP']['session_cookie_httponly'])


# register blueprints
from . import index
app.register_blueprint(index.bp)
from . import auth
app.register_blueprint(auth.bp)
from . import user
app.register_blueprint(user.bp)
from . import footer
app.register_blueprint(footer.bp)
from . import blog
app.register_blueprint(blog.bp)
from . import shop
app.register_blueprint(shop.bp)


# load static data
CACHED_CATEGORIES = []
CACHED_ERROR_MESSAGES = {}
CACHED_SUCCESS_MESSAGES = {}
CACHED_PRODUCTS_VISIBILITY_PER_PAGE = []
CACHED_PRODUCTS_SORTING_OPTION_NAMES = []
CACHED_PRODUCTS_SORTING_OPTION_VALUES = []
with app.app_context():
    conn = flaskr.functions.connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM categories")
    CACHED_CATEGORIES = flaskr.functions.build_category_tree(cursor.fetchall())
    with open(f'{working_dir}flaskr/json/errors.json', 'r') as f:
        CACHED_ERROR_MESSAGES = json.load(f)
    with open(f'{working_dir}flaskr/json/successes.json', 'r') as f:
        CACHED_SUCCESS_MESSAGES = json.load(f)
    CACHED_PRODUCTS_VISIBILITY_PER_PAGE = [int(x.strip()) for x in config['PRODUCTS']['visibility_per_page_options'].split(',')]
    CACHED_PRODUCTS_SORTING_OPTION_NAMES = [x.strip() for x in config['PRODUCTS']['sorting_option_names'].split(',')]
    CACHED_PRODUCTS_SORTING_OPTION_VALUES = [x.strip() for x in config['PRODUCTS']['sorting_option_values'].split(',')]
    cursor.close()
    conn.close()


@app.before_request
def open_sql_before_request():
    try:
        flask.g.conn = flaskr.functions.connect_db()
        flask.g.cursor = flask.g.conn.cursor(dictionary=True)
        flask.g.redis_client = redis.Redis(host=config['REDIS']['host'], port=config['REDIS']['port'], db=config['REDIS']['db'])
        flask.g.errors = CACHED_ERROR_MESSAGES
        flask.g.successes = CACHED_SUCCESS_MESSAGES
        flask.g.products_visibility_per_page = CACHED_PRODUCTS_VISIBILITY_PER_PAGE
        flask.g.sorting_option_names = CACHED_PRODUCTS_SORTING_OPTION_NAMES
        flask.g.sorting_option_values = CACHED_PRODUCTS_SORTING_OPTION_VALUES
    except Exception as e:
        print(e)


@app.before_request
def check_host():
    if flask.request.host != config['APP']['server_name']:
        flask.abort(404)


@app.teardown_request
def teardown_request(exception):
    if hasattr(flask.g, 'cursor'):
        flask.g.cursor.close()
    if hasattr(flask.g, 'conn'):
       flask.g.conn.close()
    if hasattr(flask.g, 'redis_client'):
        flask.g.redis_client.close()


@app.context_processor
def inject_company_data():
    user = {
        'is_logged': flask.session.get('logged', False),
        'id': flask.session.get('user_id', None),
        'name': flask.session.get('name', None)
    }
    referrer = flask.request.referrer
    return dict(config=config, current_year=datetime.now().year, user=user, categories=CACHED_CATEGORIES, referrer=referrer)


@app.errorhandler(404)
def not_found(e):
    return flask.Response(flask.render_template('error_codes/404.html'), status=404)