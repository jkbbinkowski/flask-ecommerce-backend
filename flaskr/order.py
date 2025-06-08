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
import uuid


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


bp = flask.Blueprint('order', __name__, url_prefix=config['ENDPOINTS']['order'])


@bp.route(config['ENDPOINTS']['calculate_shipping'], methods=['POST'])
def calculate_shipping_cost():
    
    ### SOME LOGIC HERE TO CALCULATE SHIPPING COST LATER ON ###
    ### BELOW IS EXAMPLE OF RETURNING JSON RESPONSE AND OTHER NECESSARY STUFF ###

    return_json = {
        'shipping_methods': {
            str(uuid.uuid4()): {
                'cost': 100,
                'currency': 'PLN',
                'name': 'Name of the method'
            },
            str(uuid.uuid4()): {
                'cost': 200,
                'currency': 'PLN',
                'name': 'Name of the method 2'
            }
        }
    }

    if create_draft_order(return_json['shipping_methods']) != True:
        return flask.jsonify({'errors': flaskr.static_cache.ERROR_MESSAGES['order']['failed_to_calculate_shipping']}), 500
    flask.session['order_shipping_methods'] = return_json['shipping_methods']

    return flask.jsonify(return_json)


def create_draft_order(shipping_methods):
    try:
        if flask.session.get('logged'):
            user_id = flask.session['user_id']
        else:
            user_id = None

        if user_id is not None:
            flask.g.cursor.execute('SELECT id FROM carts WHERE userId = %s', (user_id,))
            cart_id = flask.g.cursor.fetchone()['id']
        else:
            flask.g.cursor.execute('SELECT id FROM carts WHERE uuid = %s', (flask.request.cookies.get(config['COOKIE_NAMES']['cart']),))
            cart_id = flask.g.cursor.fetchone()['id']

        flask.g.cursor.execute('SELECT * FROM cartProducts WHERE cartId = %s', (cart_id,))
        cart_products = flask.g.cursor.fetchall()

        sum_products = 0
        for product in cart_products:
            flask.g.cursor.execute('SELECT priceNet from products WHERE id = %s', (product['productId'],))
            sum_products += round(flask.g.cursor.fetchone()['priceNet'] * product['amount'], 2)

        draft_order_uuid = str(uuid.uuid4())
        flask.session['draft_order_uuid'] = draft_order_uuid
        flask.g.cursor.execute('INSERT INTO draftOrders (uuid, products, productsSumNet, shippingMethods, timestamp) VALUES (%s, %s, %s, %s, %s)', (draft_order_uuid, json.dumps(cart_products), sum_products, json.dumps(shipping_methods), int(time.time())))
        flask.g.conn.commit()

        return True

    except Exception as e:
        print(e)
        return False