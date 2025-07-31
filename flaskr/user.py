# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import json
import re
import uuid
import sys
from flaskr.decorators import login_required
import dotenv
import configparser
import werkzeug.security
import flaskr.static_cache


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


bp = flask.Blueprint('user', __name__, url_prefix=config['ENDPOINTS']['user'])


@bp.route('/', methods=['GET'])
@login_required
def user_panel():
    return flask.render_template('user/panel.html')


@bp.route(config['ENDPOINTS']['account_data'], methods=['GET', 'PUT'])
@login_required
def account_data():
    if flask.request.method == 'GET':
        flask.g.cursor.execute('SELECT * FROM users WHERE id = %s', (flask.session['user_id'],))
        user_data_db = flask.g.cursor.fetchall()[0]

        return flask.render_template('user/account_data.html', user_data=user_data_db)

    elif flask.request.method == 'PUT':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_account_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 400

        flask.g.cursor.execute('UPDATE users SET firstName = %s, lastName = %s, phone = %s WHERE id = %s', (data['acc-fn'], data['acc-ln'], data['acc-ph'], flask.session['user_id']))
        flask.g.conn.commit()

        flask.session['name'] = f"{data['acc-fn']} {data['acc-ln']}"

        return flaskr.static_cache.SUCCESS_MESSAGES['user']['account-data-changed'], 200


@bp.route(config['ENDPOINTS']['billing_data'], methods=['GET', 'PUT'])
@login_required
def billing_data():
    if flask.request.method == 'GET':
        flask.g.cursor.execute('SELECT * FROM billingData WHERE userId = %s', (flask.session['user_id'],))
        billing_data_db = flask.g.cursor.fetchall()[0]
        billing_data_db = {k: (v if v is not None else '') for k, v in billing_data_db.items()}

        return flask.render_template('user/billing_data.html', billing_data=billing_data_db)

    elif flask.request.method == 'PUT':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_billing_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 400

        if data['bill-vat'] == '':
            bill_type = 'personal'
        else:
            bill_type = 'company'

        if not 'bill-ctr-code' in data:
            data['bill-ctr-code'] = ''

        if all(value == '' for key, value in data.items() if key not in ['bill-reg-checkbox', 'bill-vat']):
            bill_type = 'none'
        else:
            if any(value == '' for key, value in data.items() if key not in ['bill-reg-checkbox', 'bill-vat']):
                return {'errors': flaskr.static_cache.ERROR_MESSAGES['user']['missing_billing_data']}, 400

        flask.g.cursor.execute('UPDATE billingData SET type = %s, name = %s, street = %s, city = %s, postcode = %s, countryCode = %s, country = %s, taxId = %s, email = %s WHERE userId = %s', (bill_type, data['bill-nm'], data['bill-st'], data['bill-ct'], data['bill-pc'], data['bill-ctr-code'], data['bill-ctr'], data['bill-vat'], data['bill-email'], flask.session['user_id']))
        flask.g.conn.commit()

        return flaskr.static_cache.SUCCESS_MESSAGES['user']['billing-data-changed'], 200


@bp.route(config['ENDPOINTS']['shipping_data'], methods=['GET'], defaults={'own_uuid': None})
@bp.route(f"{config['ENDPOINTS']['shipping_data']}/<own_uuid>", methods=['DELETE'])
@login_required
def shipping_data(own_uuid):
    if flask.request.method == 'GET':
        flask.g.cursor.execute('SELECT * FROM shippingAddresses WHERE userId = %s', (flask.session['user_id'],))
        shipping_addresses_db = flask.g.cursor.fetchall()

        return flask.render_template('user/shipping_data/show.html', shipping_addresses=shipping_addresses_db)

    elif flask.request.method == 'DELETE':
        flask.g.cursor.execute('DELETE FROM shippingAddresses WHERE userId = %s AND uuid = %s', (flask.session['user_id'], own_uuid))
        flask.g.conn.commit()

        deleted_rows = flask.g.cursor.rowcount

        if deleted_rows == 1:
            return flaskr.static_cache.SUCCESS_MESSAGES['user']['shipping-address-deleted'], 202
        else:
            return {'errors': flaskr.static_cache.ERROR_MESSAGES['user']['shipping_address_not_found_or_not_accessible']}, 404


@bp.route(f"{config['ENDPOINTS']['shipping_data']}{config['ACTIONS']['add']}", methods=['GET', 'POST'])
@login_required
def shipping_data_add():
    if flask.request.method == 'GET':
        return flask.render_template('user/shipping_data/add.html')

    elif flask.request.method == 'POST':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_shipping_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 400

        own_uuid = str(uuid.uuid4())

        flask.g.cursor.execute('INSERT INTO shippingAddresses (uuid, userId, firstName, lastName, companyName, street, postcode, city, countryCode, country, phone) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', (own_uuid, flask.session['user_id'], data['ship-fn'], data['ship-ln'], data['ship-cn'], data['ship-st'], data['ship-pc'], data['ship-ct'], data['ship-ctr-code'], data['ship-ctr'], data['ship-ph']))
        flask.g.conn.commit()

        return flaskr.static_cache.SUCCESS_MESSAGES['user']['new-shipping-address-created'], 201          


@bp.route(f"{config['ENDPOINTS']['shipping_data']}{config['ACTIONS']['edit']}/<own_uuid>", methods=['GET', 'PUT'])
@login_required
def shipping_data_edit(own_uuid):
    if flask.request.method == 'GET':
        try:
            flask.g.cursor.execute('SELECT * FROM shippingAddresses WHERE uuid = %s AND userId = %s', (own_uuid, flask.session['user_id']))
            shipping_address_db = flask.g.cursor.fetchall()[0]
        except Exception as e:
            print(e, file=sys.stderr)
            return flask.abort(404)

        return flask.render_template('user/shipping_data/edit.html', shipping_address=shipping_address_db)

    elif flask.request.method == 'PUT':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_shipping_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 400

        flask.g.cursor.execute('UPDATE shippingAddresses SET firstName = %s, lastName = %s, companyName = %s, street = %s, postcode = %s, city = %s, countryCode = %s, country = %s, phone = %s WHERE uuid = %s AND userId = %s', (data['ship-fn'], data['ship-ln'], data['ship-cn'], data['ship-st'], data['ship-pc'], data['ship-ct'], data['ship-ctr-code'], data['ship-ctr'], data['ship-ph'], own_uuid, flask.session['user_id']))
        flask.g.conn.commit()

        return flaskr.static_cache.SUCCESS_MESSAGES['user']['address-updated-if-accessible'], 200  
    

@bp.route(config['ENDPOINTS']['change_password'], methods=['GET', 'POST'])
@login_required
def change_password():
    if flask.request.method == 'GET':
        return flask.render_template('user/change_password.html')
    
    elif flask.request.method == 'POST':
        data = json.loads(flask.request.get_data().decode())

        old_pass_hash = flask.g.cursor.execute('SELECT passHash FROM users WHERE id = %s', (flask.session['user_id'],))
        old_pass_hash = flask.g.cursor.fetchall()[0]['passHash']

        if not werkzeug.security.check_password_hash(old_pass_hash, data['old-pass']):
            return {'errors': flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_old_pass']}, 400

        errors = validate_password(data)
        if len(errors) > 0:
            return {'errors': errors}, 400
        
        flask.g.cursor.execute('SELECT * FROM users WHERE id = %s', (flask.session['user_id'],))
        user_data = flask.g.cursor.fetchall()[0]
        flask.g.cursor.execute('UPDATE users SET passHash = %s WHERE id = %s', (werkzeug.security.generate_password_hash(data['new-pass'], config['AUTH']['hash_method']), flask.session['user_id']))
        flask.g.conn.commit()

        if flask.session.get('user_id'):
            flask.session.clear()

        queue_data = {'template': config['EMAIL_PATHS']['new_pass'], 'subject': config['EMAIL_SUBJECTS']['new_pass'], 'email': user_data['email'], 'name': user_data['firstName']}
        flask.g.redis_client.lpush(config['REDIS_QUEUES']['email_queue'], json.dumps(queue_data))

        return flaskr.static_cache.SUCCESS_MESSAGES['user']['password-changed'], 200


def validate_billing_data(data):
    errors = []
    if (len(data['bill-nm']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['billing_name_too_long'])
    if (len(data['bill-st']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['street_name_too_long'])
    if (len(data['bill-ct']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['city_name_too_long'])
    if (data['bill-pc']) != '':
        if not re.search(r'[0-9]', data['bill-pc']) or (len(data['bill-pc']) > 20):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_postcode'])
    if 'bill-ctr-code' in data:
        if (data['bill-ctr-code']) != '':
            if not re.search(r'[A-Z]', data['bill-ctr-code']):
                errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_country'])
    else:
        if data['bill-ctr'] != '':
            errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_country'])
    if (data['bill-vat']) != '':
        if not re.search(r'[0-9]', data['bill-vat']) or (len(data['bill-vat']) > 45):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_tax_number'])
    if (data['bill-email']) != '':
        if ('@' not in data['bill-email']) or ('.' not in data['bill-email']):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_email'])
    if data['bill-reg-checkbox'] != True:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_reg_checkbox'])

    return errors


def validate_account_data(data):
    errors = []
    if (data['acc-fn'] == '') or (len(data['acc-fn']) > 45):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_first_name'])
    if (data['acc-ln'] == '') or (len(data['acc-ln']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_last_name'])
    if not re.search(r'[0-9]', data['acc-ph']) or (len(data['acc-ph']) > 20):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_phone'])
    if data['acc-reg-checkbox'] != True:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_reg_checkbox'])

    return errors


def validate_shipping_data(data):
    errors = []
    if (data['ship-fn'] == '') or (len(data['ship-fn']) > 45):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_first_name'])
    if (data['ship-ln'] == '') or (len(data['ship-ln']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_last_name'])
    if (len(data['ship-cn']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_company_name'])
    if (data['ship-st'] == '') or (len(data['ship-st']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['street_name_too_long'])
    if not re.search(r'[0-9]', data['ship-pc']) or (len(data['ship-pc']) > 20):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_postcode'])
    if (data['ship-ct'] == '') or (len(data['ship-ct']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['city_name_too_long'])
    if 'ship-ctr-code' in data:
        if not re.search(r'[A-Z]', data['ship-ctr-code']):
            errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_country'])
    else:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_country'])
    if not re.search(r'[0-9]', data['ship-ph']) or (len(data['ship-ph']) > 20):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['user']['invalid_phone'])

    return errors


def validate_password(data):
    errors = []
    if not re.search(r'[a-z]', data['new-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_new_pass_lower_case'])
    if not re.search(r'[A-Z]', data['new-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_new_pass_upper_case'])
    if not re.search(r'[0-9]', data['new-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_new_pass_digit'])
    if len(data['new-pass']) < int(config['AUTH']['min_password_length']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_new_pass_length'])
    if data['new-pass'] != data['new-pass-confirm']:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_confirm'])
    if data['pass-reg-checkbox'] != True:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_reg_checkbox'])

    return errors