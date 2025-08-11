# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import sys
import flask
import dotenv
import configparser
import json
import flaskr.functions
import time
import uuid
import re

dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


bp = flask.Blueprint('order', __name__, url_prefix=config['ENDPOINTS']['order'])


@bp.route(f'{config['ENDPOINTS']['to_checkout']}/<draft_order_uuid>/<shipping_method_uuid>', methods=['GET'])
def order_checkout(draft_order_uuid, shipping_method_uuid):
    shipping_data_uuid = flask.request.args.get('ssauuid', None)

    try:
        flask.g.cursor.execute('SELECT * FROM draftOrders WHERE uuid = %s', (draft_order_uuid,))
        draft_order = flask.g.cursor.fetchone()
        if not draft_order:
            return flask.abort(404)

        shipping_method = json.loads(draft_order['shippingMethods'])[shipping_method_uuid]
        if not shipping_method:
            return flask.abort(404)
    except:
        return flask.abort(404)
    
    order_products = json.loads(draft_order['products'])

    products_data = []
    for product in order_products:
        flask.g.cursor.execute('SELECT * from products WHERE id = %s', (product['productId'],))
        product_data = flask.g.cursor.fetchone()
        products_data.append(product_data)

    logged_data = {}
    if flask.session.get('logged', False):
        flask.g.cursor.execute('SELECT * FROM shippingAddresses WHERE userId = %s', (flask.session.get('user_id', None),))
        logged_data['shipping_addresses'] = flask.g.cursor.fetchall()
        try:
            logged_data['main_shipping_address'] = logged_data['shipping_addresses'][0]
        except:
            logged_data['main_shipping_address'] = {}

        if shipping_data_uuid != None:
            for address in logged_data['shipping_addresses']:
                if address['uuid'] == shipping_data_uuid:
                    logged_data['main_shipping_address'] = address

        flask.g.cursor.execute('SELECT * FROM billingData WHERE userId = %s LIMIT 1', (flask.session.get('user_id', None),))
        logged_data['main_billing_data'] = flask.g.cursor.fetchall()[0]

        flask.g.cursor.execute('SELECT * FROM users WHERE id = %s', (flask.session.get('user_id', None),))
        logged_data['user_data'] = flask.g.cursor.fetchall()[0]
        
    return flask.render_template('order/checkout.html', order_products=order_products, products_data=products_data, shipping_method=shipping_method, draft_order_uuid=draft_order_uuid, shipping_method_uuid=shipping_method_uuid, logged_data=logged_data)


@bp.route(f'{config['ENDPOINTS']['finalize_order']}', methods=['POST'])
def finalize_order():
    rq_data = json.loads(flask.request.data)
    
    #get draft order data
    flask.g.cursor.execute('SELECT * FROM draftOrders WHERE uuid = %s', (rq_data['douuid'],))
    draft_order_data = flask.g.cursor.fetchone()

    errors = validate_finalize_order_shipping_data(rq_data)
    if len(errors) > 0:
        return {'errors': errors}, 400
    
    errors = validate_finalize_order_billing_data(rq_data)
    if len(errors) > 0:
        return {'errors': errors}, 400
    
    print(rq_data)

    return 'ok', 200


@bp.route(config['ENDPOINTS']['calculate_shipping'], methods=['POST'])
def calculate_shipping_cost():
    
    ### SOME LOGIC HERE TO CALCULATE SHIPPING COST LATER ON ###
    ### BELOW IS EXAMPLE OF JSON RESPONSE AND OTHER NECESSARY STUFF ###

    return_json = {
        'shipping_methods': {
            str(uuid.uuid4()): {
                'id': 1,
                'cost': 100,
                'currency': 'PLN',
                'name': 'Name of the method'
            },
            str(uuid.uuid4()): {
                'id': 2,
                'cost': 200,
                'currency': 'PLN',
                'name': 'Name of the method 2'
            }
        }
    }

    draft_order_uuid = create_draft_order(return_json['shipping_methods'])
    if not draft_order_uuid:
        return flask.jsonify({'errors': flaskr.static_cache.ERROR_MESSAGES['order']['failed_to_calculate_shipping']}), 500
    return_json.update({'douuid': draft_order_uuid})

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
            flask.g.cursor.execute('SELECT * from products WHERE id = %s', (product['productId'],))
            product_data = flask.g.cursor.fetchone()
            product.update({'priceNet': product_data['priceNet'], 'vatRate': product_data['vatRate']})
            sum_products += round(product_data['priceNet'] * product['amount'], 2)

        draft_order_uuid = str(uuid.uuid4())
        flask.g.cursor.execute('INSERT INTO draftOrders (cartId, uuid, products, productsSumNet, shippingMethods, timestamp) VALUES (%s, %s, %s, %s, %s, %s)', (cart_id, draft_order_uuid, json.dumps(cart_products), sum_products, json.dumps(shipping_methods), int(time.time())))
        flask.g.conn.commit()

        return draft_order_uuid

    except Exception as e:
        print(e)
        return False
    

def validate_finalize_order_shipping_data(data):
    errors = []
    if (data['ship-fn'] == '') or (len(data['ship-fn']) > 45):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_first_name'])
    if (data['ship-ln'] == '') or (len(data['ship-ln']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_last_name'])
    if (len(data['ship-cn']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_company_name'])
    if (data['ship-st'] == '') or (len(data['ship-st']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_street_name'])
    if not re.search(r'[0-9]', data['ship-pc']) or (len(data['ship-pc']) > 20):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_postcode'])
    if (data['ship-ct'] == '') or (len(data['ship-ct']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_city_name'])
    if 'ship-ctr-code' in data:
        if not re.search(r'[A-Z]', data['ship-ctr-code']):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_country'])
    else:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_country'])
    if not re.search(r'[0-9]', data['ship-ph']) or (len(data['ship-ph']) > 20):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_phone'])
    if 'ship-em' in data:
        if ('@' not in data['ship-em']) or ('.' not in data['ship-em']):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_email'])

    return errors


def validate_finalize_order_billing_data(data):
    errors = []
    if ('checkbox-bill' in data) and (data['checkbox-bill'] == True):
        if (data['bill-nm'] == '') or (len(data['bill-nm']) > 255):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_billing_name'])
        if (data['bill-st'] == '') or (len(data['bill-st']) > 255):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_street_name'])
        if (data['bill-ct'] == '') or (len(data['bill-ct']) > 255):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_city_name'])
        if not re.search(r'[0-9]', data['bill-pc']) or (len(data['bill-pc']) > 20):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_postcode'])
        if 'bill-ctr-code' in data:
            if not re.search(r'[A-Z]', data['bill-ctr-code']):
                errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_country'])
        else:
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_country'])
        if ('@' not in data['bill-em']) or ('.' not in data['bill-em']):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_email'])
        if not re.search(r'[0-9]', data['bill-vat']) or (len(data['bill-vat']) > 45):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_tax_number'])
    
    return errors