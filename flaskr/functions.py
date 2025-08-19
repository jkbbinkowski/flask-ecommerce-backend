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
import traceback
import hashlib
import flaskr.jinja_filters

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
    bcc = data.get('bcc', [])

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

    if bcc:
        bcc = ast.literal_eval(bcc)
        em['Bcc'] = ', '.join(bcc)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader('/'))
    env.filters['slugify'] = flaskr.jinja_filters.slugify
    template = env.get_template(f"{working_dir}{data['template']}")
    rendered_html = template.render(config=config, data=data, working_dir=working_dir)
    em.attach(MIMEText(rendered_html, 'html'))
    recipients = [receiver] + cc + bcc
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
    default_cookie = [int(config['USER_PREF_COOKIE']['default_visibility_per_page']), config['USER_PREF_COOKIE']['default_sorting_option'], config['USER_PREF_COOKIE']['default_availability'], config['USER_PREF_COOKIE']['default_price_filter'], config['USER_PREF_COOKIE']['default_price_filter_values']]

    try:
        config_cookie = base64.b64decode(request.cookies.get(config['COOKIE_NAMES']['user_preferences'])).decode('utf-8').split(',')
        user_config = [int(config_cookie[0]), config_cookie[1], config_cookie[2], config_cookie[3], config_cookie[4]]
        if not user_config[0] in get_config_list('int', config['USER_PREF_COOKIE']['visibility_per_page_options']):
            raise Exception('Invalid config cookie data')
        if not user_config[1] in get_config_list('str', config['USER_PREF_COOKIE']['sorting_option_values']):
            raise Exception('Invalid config cookie data')
        if not user_config[2] in get_config_list('str', config['USER_PREF_COOKIE']['availability_values']):
            raise Exception('Invalid config cookie data')
        if not user_config[3] in get_config_list('str', config['USER_PREF_COOKIE']['price_filter_values']):
            raise Exception('Invalid config cookie data')
        if ('to' not in user_config[4]):
            splitted = user_config[4].split('to')
            try:
                int(splitted[0])
                int(splitted[1])
                if (int(splitted[0]) < 0) or (int(splitted[1]) < 0):
                    raise Exception('Invalid config cookie data')
            except:
                raise Exception('Invalid config cookie data')
            user_config[4] = splitted
    except Exception as e:
        user_config = default_cookie

    return_dict = {
        'config_cookie': ','.join(str(x) for x in user_config),
        'products_visibility_per_page': user_config[0],
        'sorting_option': user_config[1],
        'availability': user_config[2],
        'price_filter': user_config[3],
        'price_filter_values': user_config[4],
        'default_cookie': ','.join(str(x) for x in default_cookie)
    }
    return_dict['config_cookie'] = base64.b64encode(return_dict['config_cookie'].encode('utf-8')).decode('utf-8')
    return_dict['default_cookie'] = base64.b64encode(return_dict['default_cookie'].encode('utf-8')).decode('utf-8')

    return return_dict


def init_cart(response):
    #check if redis_client is available
    redis_client = getattr(flask.g, "redis_client", None)
    if redis_client is None:
        return response

    #prevent duplicates of uuid carts for concurrent requests withing the same session
    raw_id = f"{flask.request.remote_addr}:{flask.request.headers.get('User-Agent')}"
    hashed_id = hashlib.sha256(raw_id.encode()).hexdigest()
    lock_key = f"{ config['REDIS_QUEUES']['init_cart_lock_queue'] }:{ hashed_id }"
    if (not flask.g.redis_client.set(lock_key, '1', nx=True, ex=int(config['ADVANCED']['cart_init_lock_time']))) or ('static' in flask.request.url):
        return response
    
    cart_cookie = flask.request.cookies.get(config['COOKIE_NAMES']['cart'])

    # if user is logged in, check if there is only one cart for user and if not, delete the old one/s and create a new one
    if flask.session.get('logged'):
        flask.g.cursor.execute('SELECT COUNT(*) FROM carts WHERE userId = %s', (flask.session['user_id'],))
        if flask.g.cursor.fetchone()['COUNT(*)'] != 1:
            flask.g.cursor.execute('DELETE FROM carts WHERE userId = %s', (flask.session['user_id'],))
            flask.g.conn.commit()
            flask.g.cursor.execute('INSERT INTO carts (userId, lastModTime) VALUES (%s, %s)', (flask.session['user_id'], int(time.time())))
            flask.g.conn.commit()

    # create new uuid cart if there is NO cart cookie
    elif (not cart_cookie):
        cart_uuid = str(uuid.uuid4())
        flask.g.cursor.execute('INSERT INTO carts (uuid, userId, lastModTime) VALUES (%s, %s, %s)', (cart_uuid, None, int(time.time())))
        flask.g.conn.commit()
        response.set_cookie(config['COOKIE_NAMES']['cart'], cart_uuid, expires=datetime.datetime.now() + datetime.timedelta(days=365*10), path='/')

    # if there is a cart cookie, check if it is valid and if not, create a new one
    else:
        flask.g.cursor.execute('SELECT COUNT(*) FROM carts WHERE uuid = %s', (cart_cookie,))
        if not flask.g.cursor.fetchone()['COUNT(*)']:
            cart_uuid = str(uuid.uuid4())
            flask.g.cursor.execute('INSERT INTO carts (uuid, userId, lastModTime) VALUES (%s, %s, %s)', (cart_uuid, None, int(time.time())))
            flask.g.conn.commit()
            response.set_cookie(config['COOKIE_NAMES']['cart'], cart_uuid, expires=datetime.datetime.now() + datetime.timedelta(days=365*10), path='/')
        

def get_cart_products():
    cart_products = []
    if flask.session.get('logged'):
        flask.g.cursor.execute('SELECT * FROM carts WHERE userId = %s', (flask.session['user_id'],))
        user_cart_id = flask.g.cursor.fetchone()['id']
        flask.g.cursor.execute('SELECT * FROM cartProducts WHERE cartId = %s', (user_cart_id,))
        cart_products = flask.g.cursor.fetchall()
    else:
        try:
            cart_uuid = flask.request.cookies.get(config['COOKIE_NAMES']['cart'])
            flask.g.cursor.execute('SELECT * FROM carts WHERE uuid = %s', (cart_uuid,))
            cookie_cart_id = flask.g.cursor.fetchone()['id']
            flask.g.cursor.execute('SELECT * FROM cartProducts WHERE cartId = %s', (cookie_cart_id,))
            cart_products = flask.g.cursor.fetchall()
        except Exception as e:
            cart_products = []

    db_cart_products = []
    for cart_product in cart_products:
        flask.g.cursor.execute('SELECT * FROM products WHERE id = %s', (cart_product['productId'],))
        product = flask.g.cursor.fetchone()
        db_cart_products.append({
            'id': cart_product['productId'],
            'amount': cart_product['amount'],
            'name': product['name'],
            'price': product['priceNet'],
            'vatRate': product['vatRate'],
            'EAN': product['ean'],
            'stock': product['stock']
        })
    
    flask.g.cart_products = db_cart_products


def migrate_cart(migration_type):
    try:
        cookie_cart_uuid = flask.request.cookies.get(config['COOKIE_NAMES']['cart'])
        flask.g.cursor.execute('SELECT id FROM carts WHERE uuid = %s', (cookie_cart_uuid,))
        cookie_cart_id = flask.g.cursor.fetchone()['id']
        flask.g.cursor.execute('SELECT id FROM carts WHERE userId = %s', (flask.session['user_id'],))
        user_cart_id = flask.g.cursor.fetchone()['id']

        if migration_type == 'cookie->user':
            delete_cart_id = user_cart_id
            direction_tuple = (user_cart_id, cookie_cart_id)
            flask.g.cursor.execute('SELECT COUNT(*) FROM cartProducts WHERE cartId = %s', (cookie_cart_id,))
            if not flask.g.cursor.fetchone()['COUNT(*)']:
                return
        elif migration_type == 'user->cookie':
            delete_cart_id = cookie_cart_id
            direction_tuple = (cookie_cart_id, user_cart_id)

        flask.g.cursor.execute('DELETE FROM cartProducts WHERE cartId = %s', (delete_cart_id,))
        flask.g.conn.commit()
        flask.g.cursor.execute('INSERT INTO cartProducts (cartId, productId, amount) SELECT %s, productId, amount FROM cartProducts WHERE cartId = %s', direction_tuple)
        flask.g.conn.commit()

    except Exception as e:
        print(traceback.format_exc())
        print(e)
        pass


def get_config_list(type, config_list):
    if type == 'int':
        return [int(x.strip()) for x in config_list.split(',')]
    elif type == 'str':
        return [x.strip() for x in config_list.split(',')]
    

def init_new_user(user_id):
    flask.g.cursor.execute('INSERT INTO billingData (userId) VALUES (%s)', (user_id,))
    flask.g.conn.commit()
    flask.g.cursor.execute('INSERT INTO carts (uuid, userId, lastModTime) VALUES (%s, %s, %s)', (None, user_id, int(time.time())))
    flask.g.conn.commit()