# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import jinja2
import smtplib
import ast
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mysql.connector
import redis
import dotenv
import configparser
import base64
import flask
import datetime
import uuid
import time


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


def connect_db():
    conn = mysql.connector.connect(host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'), auth_plugin=os.getenv('DB_AUTH_PLUGIN'))
    return conn


def connect_redis():
    redis_client = redis.Redis(host=config['REDIS']['host'], port=config['REDIS']['port'], db=config['REDIS']['db'])
    return redis_client


def send_transactional_email(data):
    sender = os.getenv('TRANSACTIONAL_EMAIL_USERNAME')
    p = os.getenv('TRANSACTIONAL_EMAIL_PASSWORD')
    receiver = data['email']
    cc = data.get('cc', [])

    em = MIMEMultipart()
    em['From'] = config['TRANSACTIONAL_EMAIL']['from']
    em['To'] = receiver
    em['Reply-To'] = config['TRANSACTIONAL_EMAIL']['reply_to']
    em['Subject'] = data['subject']
    em['Importance'] = 'High'
    em['User-Agent'] = config['TRANSACTIONAL_EMAIL']['user-agent']
    em['X-Mailer'] = config['TRANSACTIONAL_EMAIL']['x-mailer']
    
    if cc:
        cc = ast.literal_eval(cc)
        em['Cc'] = ', '.join(cc)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader('/'))
    template = env.get_template(f"{working_dir}{data['template']}")
    rendered_html = template.render(config=config, data=data, working_dir=working_dir)
    em.attach(MIMEText(rendered_html, 'html'))
    recipients = [receiver] + cc
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(os.getenv('TRANSACTIONAL_EMAIL_SERVER'), os.getenv('TRANSACTIONAL_EMAIL_PORT'), context=context) as smtp:
        smtp.login(sender, p)
        smtp.sendmail(sender, recipients, em.as_string())


def build_category_tree(flat_categories):
    category_dict = {str(cat["id"]): {**cat, "children": []} for cat in flat_categories}
    root_categories = []

    for cat in category_dict.values():
        if cat["parentId"]:
            parent = category_dict.get(str(cat["parentId"]))
            if parent:
                parent["children"].append(cat)
        else:
            root_categories.append(cat)

    return root_categories


def get_config_cookie(request):
    try:
        config_cookie = base64.b64decode(request.cookies.get(config['COOKIE_NAMES']['user_preferences'])).decode('utf-8').split(',')
        user_config = [int(config_cookie[0]), config_cookie[1]]
        if not user_config[0] in flask.g.products_visibility_per_page:
            raise Exception('Invalid config cookie data')
        if not user_config[1] in flask.g.sorting_option_values:
            raise Exception('Invalid config cookie data')
    except Exception as e:
        user_config = [int(config['PRODUCTS']['default_visibility_per_page']), config['PRODUCTS']['default_sorting_option']]

    return_dict = {
        'config_cookie': ','.join(str(x) for x in user_config),
        'expires': datetime.datetime.now() + datetime.timedelta(days=365*10),
        'products_visibility_per_page': user_config[0],
        'sorting_option': user_config[1]
    }

    return_dict['config_cookie'] = base64.b64encode(return_dict['config_cookie'].encode('utf-8')).decode('utf-8')

    return return_dict


def init_cart():
    if flask.request.cookies.get(config['COOKIE_NAMES']['cart']) and flask.session.get('logged'):
        print('merge carts')
    elif (not flask.request.cookies.get(config['COOKIE_NAMES']['cart'])) and (not flask.session.get('logged')):
        print('create new cart')

    
    