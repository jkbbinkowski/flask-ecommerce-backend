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


bp = flask.Blueprint('cart', __name__, url_prefix=config['ENDPOINTS']['cart'])


@bp.route(config['ACTIONS']['add'], methods=['POST'])
def add_to_cart():
    data = json.loads(flask.request.get_data().decode())
    flask.g.cursor.execute('SELECT * FROM products WHERE id = %s', (data['productId'],))
    product = flask.g.cursor.fetchone()
    if product == None:
        return {"errors": flaskr.static_cache.ERROR_MESSAGES['cart']['product_not_found']}, 404
    elif data['amount'] < 1:
        return {"errors": flaskr.static_cache.ERROR_MESSAGES['cart']['amount_too_low']}, 400

    if flask.session.get('logged'):
        flask.g.cursor.execute('SELECT id FROM carts WHERE userId = %s', (flask.session['user_id'],))
        cart_id = flask.g.cursor.fetchone()['id']
    else:
        flask.g.cursor.execute('SELECT id FROM carts WHERE uuid = %s', (flask.request.cookies.get(config['COOKIE_NAMES']['cart']),))
        cart_id = flask.g.cursor.fetchone()['id']

    flask.g.cursor.execute('SELECT * FROM cartProducts WHERE productId = %s and cartId = %s', (data['productId'], cart_id))
    cart_product = flask.g.cursor.fetchone()

    if cart_product:
        if (cart_product['amount'] + data['amount']) > product['stock']:
            return {"errors": flaskr.static_cache.ERROR_MESSAGES['cart']['not_enough_in_stock']}, 400
        flask.g.cursor.execute('UPDATE cartProducts SET amount = amount + %s WHERE productId = %s and cartId = %s', (data['amount'], data['productId'], cart_id))
        flask.g.conn.commit()
    else:
        if data['amount'] > product['stock']:
            return {"errors": flaskr.static_cache.ERROR_MESSAGES['cart']['not_enough_in_stock']}, 400
        flask.g.cursor.execute('INSERT INTO cartProducts (productId, amount, cartId) VALUES (%s, %s, %s)', (data['productId'], data['amount'], cart_id))
        flask.g.conn.commit()
    flask.g.cursor.execute('UPDATE carts SET lastModTime = %s WHERE id = %s', (int(time.time()), cart_id))

    return flaskr.static_cache.SUCCESS_MESSAGES['cart']['product_added'], 202


@bp.route(config['ACTIONS']['remove']+'/<productId>', methods=['GET'])
def remove_from_cart(productId):
    cart_id = None
    if flask.session.get('logged'):
        flask.g.cursor.execute('SELECT id FROM carts WHERE userId = %s', (flask.session['user_id'],))
        cart_id = flask.g.cursor.fetchone()['id']
    else:
        flask.g.cursor.execute('SELECT id FROM carts WHERE uuid = %s', (flask.request.cookies.get(config['COOKIE_NAMES']['cart']),))
        cart_id = flask.g.cursor.fetchone()['id']

    flask.g.cursor.execute('UPDATE carts SET lastModTime = %s WHERE id = %s', (int(time.time()), cart_id))
    flask.g.cursor.execute('DELETE FROM cartProducts WHERE productId = %s and cartId = %s', (productId, cart_id))
    flask.g.conn.commit()

    return flask.redirect(flask.request.referrer or '/')


@bp.route(config['ACTIONS']['edit']+'/<productId>', methods=['PUT'])
def edit_cart_product(productId):
    data = json.loads(flask.request.get_data().decode())
    flask.g.cursor.execute('SELECT * FROM products WHERE id = %s', (data['productId'],))
    product = flask.g.cursor.fetchone()
    if product == None:
        return {"errors": flaskr.static_cache.ERROR_MESSAGES['cart']['product_not_found']}, 404
    elif data['amount'] < 1:
        return {"errors": flaskr.static_cache.ERROR_MESSAGES['cart']['amount_too_low']}, 400
    elif (data['amount']) > product['stock']:
        return {"errors": flaskr.static_cache.ERROR_MESSAGES['cart']['not_enough_in_stock']}, 400
    
    cart_id = None
    if flask.session.get('logged'):
        flask.g.cursor.execute('SELECT id FROM carts WHERE userId = %s', (flask.session['user_id'],))
        cart_id = flask.g.cursor.fetchone()['id']
    else:
        flask.g.cursor.execute('SELECT id FROM carts WHERE uuid = %s', (flask.request.cookies.get(config['COOKIE_NAMES']['cart']),))
        cart_id = flask.g.cursor.fetchone()['id']

    flask.g.cursor.execute('UPDATE carts SET lastModTime = %s WHERE id = %s', (int(time.time()), cart_id))
    flask.g.cursor.execute('UPDATE cartProducts SET amount = %s WHERE productId = %s and cartId = %s', (data['amount'], productId, cart_id))
    flask.g.conn.commit()

    return flaskr.static_cache.SUCCESS_MESSAGES['cart']['product_edited'], 202


@bp.route('', methods=['GET'])
def cart():
    return flask.render_template('order/cart.html')



