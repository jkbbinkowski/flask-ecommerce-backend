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
import random
import string
import werkzeug
import datetime
import logging
import math


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')

logger = logging.getLogger(__name__)


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

    flask.g.cursor.execute('SELECT * FROM paymentMethods')
    payment_methods = flask.g.cursor.fetchall()

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
        
    return flask.render_template('order/checkout.html', order_products=order_products, products_data=products_data, shipping_method=shipping_method, draft_order_uuid=draft_order_uuid, shipping_method_uuid=shipping_method_uuid, logged_data=logged_data, payment_methods=payment_methods)


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
    
    errors = validate_finalize_order_data(rq_data)
    if len(errors) > 0:
        return {'errors': errors}, 400
    
    flask.g.cursor.execute('SELECT * FROM paymentMethods WHERE uuid = %s', (rq_data['order-pm'],))
    payment_method_name = flask.g.cursor.fetchone()['name']
    if not payment_method_name:
        raise RuntimeError("Invalid payment method uuid")
    
    #check if user is logged in
    if 'uuuid' in rq_data:
        flask.g.cursor.execute('SELECT * FROM users WHERE uuid = %s', (rq_data['uuuid'],))
        user_data = flask.g.cursor.fetchone()
        order_email = user_data['email']
        order_user_id = user_data['id']
    elif ('checkbox-create-acc' in rq_data) and (rq_data['checkbox-create-acc'] == True):
        user_data = order_create_account(rq_data)
        if not user_data:
            return {'errors': flaskr.static_cache.ERROR_MESSAGES['order']['account_already_exists']}, 400
        order_email = user_data[0]
        order_user_id = user_data[1]
    else:
        order_email = rq_data['ship-em']
        order_user_id = None

    #calculate total to pay
    total_to_pay = 0
    total_to_pay += json.loads(draft_order_data['shippingMethods'])[rq_data['smuuid']]['cost']
    for product in json.loads(draft_order_data['products']):
        total_to_pay += ((product['priceNet']*(1+(product['vatRate']/100))) * product['amount'])
    total_to_pay = round(total_to_pay, 2)

    #create order number and uuid
    order_number = create_and_validate_order_number()
    order_uuid = str(uuid.uuid4())
    timestamp = int(time.time())
    
    #insert order to database
    flask.g.cursor.execute('''
                            INSERT INTO orders 
                            (timestamp, email, userId, uuid, orderNumber, orderStatus, products, shippingMethod, paymentMethod, totalToPay, currency, shippingFirstName, shippingLastName, shippingCompanyName, shippingPhone, shippingStreet, shippingPostcode, shippingCity, shippingCountryCode, shippingCountry, additionalInfo)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ''', 
                            (timestamp, order_email, order_user_id, order_uuid, order_number, config['ORDERS']['new_order_status'], draft_order_data['products'], json.dumps(json.loads(draft_order_data['shippingMethods'])[rq_data['smuuid']]), rq_data['order-pm'], total_to_pay, config['GLOBAL']['currency'], rq_data['ship-fn'], rq_data['ship-ln'], rq_data['ship-cn'], rq_data['ship-ph'], rq_data['ship-st'], rq_data['ship-pc'], rq_data['ship-ct'], rq_data['ship-ctr-code'], rq_data['ship-ctr'], rq_data['order-ai']))
    flask.g.conn.commit()                       
    order_db_id = flask.g.cursor.lastrowid

    #delete draft order from db
    flask.g.cursor.execute('DELETE FROM draftOrders WHERE uuid = %s', (rq_data['douuid'],))
    flask.g.conn.commit()

    #add order status history
    flask.g.cursor.execute('INSERT INTO orderStatusesHistory (orderId, status, timestamp) VALUES (%s, %s, %s)', (order_db_id, config['ORDERS']['new_order_status'], timestamp))
    flask.g.conn.commit()

    #add invoice data
    if ('checkbox-bill' in rq_data) and (rq_data['checkbox-bill'] == True):
        flask.g.cursor.execute('''
                               INSERT INTO orderInvoices 
                               (orderId, invoiceNeeded, name, street, postcode, city, countryCode, country, email, taxId)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                               ''',
                               (order_db_id, True, rq_data['bill-nm'], rq_data['bill-st'], rq_data['bill-pc'], rq_data['bill-ct'], rq_data['bill-ctr-code'], rq_data['bill-ctr'], rq_data['bill-em'], rq_data['bill-vat']))
    else:
        flask.g.cursor.execute('''
                               INSERT INTO orderInvoices 
                               (orderId, invoiceNeeded, name, street, postcode, city, countryCode, country, email)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                               ''',
                               (order_db_id, False, f'{rq_data['ship-fn']} {rq_data['ship-ln']}', rq_data['ship-st'], rq_data['ship-pc'], rq_data['ship-ct'], rq_data['ship-ctr-code'], rq_data['ship-ctr'], order_email))
    flask.g.conn.commit()

    #add transational email to queue
    order_data = {
        'order_number': order_number,
        'order_uuid': order_uuid,
        'order_products': json.loads(draft_order_data['products']),
        'rq_data': rq_data,
        'order_status': config['ORDERS']['new_order_status'],
        'payment_method_name': payment_method_name,
        'shipping_method_name': json.loads(draft_order_data['shippingMethods'])[rq_data['smuuid']]['name'],
        'shipping_method_cost': json.loads(draft_order_data['shippingMethods'])[rq_data['smuuid']]['cost'],
        'order_date': datetime.datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M'),
        'products': json.loads(draft_order_data['products']),
        'total_to_pay': str(total_to_pay)
    }
    email_data = { 'template': config['EMAIL_PATHS']['new_order'], 'subject': config['EMAIL_SUBJECTS']['new_order'].replace('{order_number}', order_number), 'email': order_email, 'bcc': config['TRANSACTIONAL_EMAIL']['bcc'], 'order_data': order_data}
    flask.g.redis_client.lpush(config['REDIS_QUEUES']['email_queue'], json.dumps(email_data))

    #truncate cart on successfull checkout
    if flask.session.get('logged'):
        flask.g.cursor.execute('SELECT id FROM carts WHERE userId = %s', (flask.session['user_id'],))
        cart_id = flask.g.cursor.fetchone()['id']
    else:
        flask.g.cursor.execute('SELECT id FROM carts WHERE uuid = %s', (flask.request.cookies.get(config['COOKIE_NAMES']['cart']),))
        cart_id = flask.g.cursor.fetchone()['id']
    flask.g.cursor.execute('UPDATE carts SET lastModTime = %s WHERE id = %s', (int(time.time()), cart_id))
    flask.g.cursor.execute('DELETE FROM cartProducts WHERE cartId = %s', (cart_id,))
    flask.g.conn.commit()

    resp = {
        'ouuid': order_uuid
    }

    return flask.jsonify(resp), 201


@bp.route(config['ENDPOINTS']['calculate_shipping'], methods=['POST'])
def calculate_shipping_cost():
    return_json = {'shipping_methods': {}}
    shipping_methods_dict = {}
    cart_total_price_gross = 0

    cart_products = flask.g.cart_products
    
    for product in cart_products:
        cart_total_price_gross += round(product['price'] * (1 + product['vatRate'] / 100) * product['amount'], 2)
        flask.g.cursor.execute('''
        SELECT DISTINCT sm.*, sa.maxPerPackage, %s AS amountPerPackage, sa.id AS shippingAgregatorId FROM shippingMethods sm
            INNER JOIN shippingAgregator_shippingMethods sa_sm ON sa_sm.shippingMethodId = sm.id
            INNER JOIN shippingAgregator sa ON sa.id = sa_sm.shippingAgregatorId
            INNER JOIN products p ON p.shippingAgregatorInternalName = sa.InternalName
            WHERE p.id = %s;
        ''', (product['amount'], product['id']))
        shipping_methods = flask.g.cursor.fetchall()
        for shipping_method in shipping_methods:
            shipping_agregator_id = shipping_method['shippingAgregatorId']
            shipping_method_uuid = shipping_method['uuid']
            if not shipping_agregator_id in shipping_methods_dict:
                shipping_methods_dict[shipping_agregator_id] = {}
            if not shipping_method_uuid in shipping_methods_dict[shipping_agregator_id]:
                shipping_methods_dict[shipping_agregator_id].update({shipping_method_uuid: shipping_method})
            else:
                shipping_methods_dict[shipping_agregator_id][shipping_method_uuid]['amountPerPackage'] += shipping_method['amountPerPackage']
            dict_remover = ['uuid', 'shippingAgregatorId', 'id']
            for el in dict_remover:
                if el in shipping_methods_dict[shipping_agregator_id][shipping_method_uuid]:
                    del shipping_methods_dict[shipping_agregator_id][shipping_method_uuid][el]

    print(cart_total_price_gross)
    print(shipping_methods_dict)

    return_json = {
        'shipping_methods': {}
    }

    draft_order_uuid = create_draft_order(return_json['shipping_methods'])
    if not draft_order_uuid:
        return flask.jsonify({'errors': flaskr.static_cache.ERROR_MESSAGES['order']['failed_to_calculate_shipping']}), 500
    return_json.update({'douuid': draft_order_uuid})

    return flask.jsonify(return_json)


@bp.route(f'{config['ENDPOINTS']['details']}/<order_uuid>', methods=['GET'])
def order_details(order_uuid):
    #get order data
    flask.g.cursor.execute('SELECT * FROM orders WHERE uuid = %s', (order_uuid,))
    order = flask.g.cursor.fetchone()
    if not order:
        return flask.abort(404)
    
    #get order invoice data
    flask.g.cursor.execute('SELECT * FROM orderInvoices WHERE orderId = %s', (order['id'],))
    order_invoice = flask.g.cursor.fetchone()

    #get order payment method data
    flask.g.cursor.execute('SELECT * FROM paymentMethods WHERE uuid = %s', (order['paymentMethod'],))
    order['orderPaymentMethod'] = flask.g.cursor.fetchone()['name']

    #get order products data
    order['products'] = json.loads(order['products'])
    for product in order['products']:
        flask.g.cursor.execute('SELECT * FROM products WHERE id = %s', (product['productId'],))
        product_data = flask.g.cursor.fetchone()
        product.update({'priceNet': product_data['priceNet'], 'vatRate': product_data['vatRate'], 'name': product_data['name'], 'productId': product_data['id'], 'productEan': product_data['ean']})

    #get order date
    order['orderDate'] = datetime.datetime.fromtimestamp(order['timestamp']).strftime('%d.%m.%Y %H:%M')

    #get order tracking numbers data
    flask.g.cursor.execute('SELECT * FROM trackingNumbers WHERE orderId = %s', (order['id'],))
    tracking_numbers = flask.g.cursor.fetchall()

    #get order tracking numbers carrier data
    for tracking_number in tracking_numbers:
        flask.g.cursor.execute('SELECT * FROM carriers WHERE id = %s', (tracking_number['carrierId'],))
        carrier = flask.g.cursor.fetchone()
        tracking_number['carrierName'] = carrier['name']
        tracking_number['trackingLink'] = carrier['trackingLink'].replace('XXXXXX', tracking_number['trackingNumber'])

    #get order payments data
    flask.g.cursor.execute('SELECT * FROM payments WHERE orderId = %s', (order['id'],))
    payments = flask.g.cursor.fetchall()
    order['paymentStatus'] = config['PAYMENTS']['pending_payment_status']
    #get order payment status
    for payment in payments:
        if payment['success']:
            order['paymentStatus'] = config['PAYMENTS']['paid_payment_status']
            break

    #get order status history
    flask.g.cursor.execute('SELECT * FROM orderStatusesHistory WHERE orderId = %s ORDER BY timestamp DESC', (order['id'],))
    order_status_history = flask.g.cursor.fetchall()

    return flask.render_template('order/details.html', order=order, order_invoice=order_invoice, tracking_numbers=tracking_numbers, order_status_history=order_status_history)


@bp.route(f'{config['ENDPOINTS']['validate_order_data']}', methods=['POST'])
def validate_order_data():
    rq_data = json.loads(flask.request.data)

    errors = validate_finalize_order_shipping_data(rq_data)
    if len(errors) > 0:
        return {'errors': errors}, 400
    
    errors = validate_finalize_order_billing_data(rq_data)
    if len(errors) > 0:
        return {'errors': errors}, 400
    
    errors = validate_finalize_order_data(rq_data)
    if len(errors) > 0:
        return {'errors': errors}, 400

    return '', 200


@bp.route(f'{config['ACTIONS']['download_invoice']}/<invoice_uuid>', methods=['GET'])
def download_invoice(invoice_uuid):
    
    ### logic here to download invoice

    return invoice_uuid, 200
    

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

        for product in cart_products:
            flask.g.cursor.execute('SELECT * from products WHERE id = %s', (product['productId'],))
            product_data = flask.g.cursor.fetchone()
            product.update({'priceNet': product_data['priceNet'], 'vatRate': product_data['vatRate'], 'name': product_data['name'], 'productId': product_data['id']})
            del product['id']

        draft_order_uuid = str(uuid.uuid4())
        flask.g.cursor.execute('INSERT INTO draftOrders (cartId, uuid, products, shippingMethods, timestamp) VALUES (%s, %s, %s, %s, %s)', (cart_id, draft_order_uuid, json.dumps(cart_products), json.dumps(shipping_methods), int(time.time())))
        flask.g.conn.commit()

        return draft_order_uuid

    except Exception as e:
        print(e)
        return False
    

def order_create_account(data):
    flask.g.cursor.execute('SELECT email FROM users WHERE email = %s', (data['ship-em'],))
    emails = flask.g.cursor.fetchall()

    if len(emails) != 0:
        return False
    
    random_pass = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(int(config['AUTH']['order_auto_pass_length'])))
    pass_hash = werkzeug.security.generate_password_hash(random_pass, config['AUTH']['hash_method'])

    flask.g.cursor.execute('INSERT INTO users (uuid, firstName, lastName, email, phone, passHash) VALUES (%s, %s, %s, %s, %s, %s)', (str(uuid.uuid4()), data['ship-fn'], data['ship-ln'], data['ship-em'], data['ship-ph'], pass_hash))
    flask.g.conn.commit()
    user_id = flask.g.cursor.lastrowid
    flaskr.functions.init_new_user(user_id)

    queue_data = {'template': config['EMAIL_PATHS']['order_new_account'], 'subject': config['EMAIL_SUBJECTS']['register'], 'email': data['ship-em'], 'name': data['ship-fn'], 'pass': random_pass, 'bcc': config['TRANSACTIONAL_EMAIL']['bcc']}
    flask.g.redis_client.lpush(config['REDIS_QUEUES']['email_queue'], json.dumps(queue_data))

    return [data['ship-em'], user_id]


def create_and_validate_order_number():
    order_number = str(int(time.time()))+''.join([chr(65 + random.randint(0, 25)) for _ in range(int(config['ORDERS']['chars_in_order_number']))])
    flask.g.cursor.execute('SELECT orderNumber FROM orders WHERE orderNumber = %s', (order_number,))
    while len(flask.g.cursor.fetchall()) > 0:
        order_number = str(int(time.time()))+''.join([chr(65 + random.randint(0, 25)) for _ in range(3)])
        flask.g.cursor.execute('SELECT orderNumber FROM orders WHERE orderNumber = %s', (order_number,))
    
    return order_number


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
        if (data['bill-vat']) != '':
            if not re.search(r'[0-9]', data['bill-vat']) or (len(data['bill-vat']) > 45):
                errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_tax_number'])
    
    return errors


def validate_finalize_order_data(data):
    errors = []
    if data['checkbox-reg'] != True:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['invalid_reg_checkbox'])
    if len(data['order-ai']) > 1000:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['order']['too_long_additional_info'])
    
    return errors