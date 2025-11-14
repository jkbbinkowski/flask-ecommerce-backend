# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import json
import re
import uuid
import time
import werkzeug.security
from flaskr.decorators import logout_required
import dotenv
import configparser
import flaskr.functions
import flaskr.static_cache
import logging


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')

logger = logging.getLogger(__name__)


bp = flask.Blueprint('auth', __name__, url_prefix='/')


@bp.route(config['ENDPOINTS']['login'], methods=['GET', 'POST'])
@logout_required
def login():
    if flask.request.method == 'GET':
        args = flask.request.args
        return flask.render_template('auth/login.html', args=args)

    elif flask.request.method == 'POST':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_login_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 404

        flask.g.cursor.execute('SELECT * FROM users WHERE email = %s', (data['log-email'],))
        auth_data_db = flask.g.cursor.fetchall()

        if len(auth_data_db) == 0 or (not werkzeug.security.check_password_hash(auth_data_db[0]['passHash'], data['log-pass'])):
            return {'errors': flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_email_or_password']}, 404

        flask.session['logged'] = True
        flask.session['user_id'] = auth_data_db[0]['id']
        flask.session['name'] = f"{auth_data_db[0]['firstName']} {auth_data_db[0]['lastName']}"
        flask.session['email'] = auth_data_db[0]['email']
        flaskr.functions.migrate_cart('cookie->user')

        return flaskr.static_cache.SUCCESS_MESSAGES['auth']['logged-in'], 200


@bp.route(config['ENDPOINTS']['register'], methods=['GET', 'POST'])
@logout_required
def register():
    if flask.request.method == 'GET':
        return flask.render_template('auth/register.html')

    elif flask.request.method == 'POST':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_register_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 400

        flask.g.cursor.execute('SELECT email FROM users WHERE email = %s', (data['reg-email'],))
        emails = flask.g.cursor.fetchall()

        if len(emails) != 0:
            return {'errors': flaskr.static_cache.ERROR_MESSAGES['auth']['email_already_exists']}, 400

        pass_hash = werkzeug.security.generate_password_hash(data['reg-pass'], config['AUTH']['hash_method'])
        flask.g.cursor.execute('INSERT INTO users (uuid, firstName, lastName, email, phone, passHash) VALUES (%s, %s, %s, %s, %s, %s)', (str(uuid.uuid4()), data['reg-fn'], data['reg-ln'], data['reg-email'], data['reg-ph'], pass_hash))
        flask.g.conn.commit()
        user_id = flask.g.cursor.lastrowid
        flaskr.functions.init_new_user(user_id)

        queue_data = {'template': config['EMAIL_PATHS']['register'], 'subject': config['EMAIL_SUBJECTS']['register'], 'email': data['reg-email'], 'name': data['reg-fn'], 'bcc': config['TRANSACTIONAL_EMAIL']['bcc']}
        flask.g.redis_client.lpush(config['REDIS_QUEUES']['email_queue'], json.dumps(queue_data))

        return flaskr.static_cache.SUCCESS_MESSAGES['auth']['registered'], 201
    

@bp.route(config['ENDPOINTS']['forgot_password'], methods=['GET', 'POST'])
@logout_required
def forgot_password():
    if flask.request.method == 'GET':
        return flask.render_template('auth/forgot_pass.html')
    
    elif flask.request.method == 'POST':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_forgot_password_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 400
        
        token_generated = False
        try:
            flask.g.cursor.execute('SELECT * FROM users WHERE email = %s', (data['forgot-pass-email'],))
            user_data = flask.g.cursor.fetchone()
            if user_data is not None:
                token = str(uuid.uuid4())
                flask.g.cursor.execute('INSERT INTO forgotPassTokens (userID, token, creationTime) VALUES (%s, %s, %s)', (user_data['id'], token, int(time.time())))
                flask.g.conn.commit()
                token_generated = True
        except:
            return {'errors': flaskr.static_cache.ERROR_MESSAGES['auth']['forgot-pass-token-already-generated']}, 409

        email_sent = False
        try:
            if token_generated:
                email_data = {'template': config['EMAIL_PATHS']['forgot_pass'], 'subject': config['EMAIL_SUBJECTS']['forgot_pass'], 'email': user_data['email'], 'name': user_data['firstName'], 'token': token, 'expiration_time_min': int((int(config['AUTH']['forgot_pass_token_expiration_time'])/60))}
                flaskr.functions.send_transactional_email(email_data)
                email_sent = True
        except Exception as e:
            flask.g.cursor.execute('DELETE FROM forgotPassTokens WHERE userID = %s', (user_data['id'],))
            flask.g.conn.commit()
            return '', 500

        if not email_sent:
            time.sleep(int(config['ADVANCED']['simulate_forgot_pass_email_send_time']))
            
        return flaskr.static_cache.SUCCESS_MESSAGES['auth']['forgot-pass-token-generated'], 200
    

@bp.route(f"{config['ENDPOINTS']['forgot_password']}{config['ENDPOINTS']['new_password']}/<token>", methods=['GET'])
@bp.route(f"{config['ENDPOINTS']['forgot_password']}{config['ENDPOINTS']['new_password']}", methods=['POST'], defaults={'token': None})
@logout_required
def new_forgot_password(token):
    if flask.request.method == 'GET':
        flask.g.cursor.execute('SELECT * FROM forgotPassTokens WHERE token = %s', (token,))
        token_db = flask.g.cursor.fetchone()
        if token_db is None:
            return flask.abort(404)
        
        elif int(token_db['creationTime'])+int(config['AUTH']['forgot_pass_token_expiration_time']) < int(time.time()):
            flask.g.cursor.execute('DELETE FROM forgotPassTokens WHERE token = %s', (token,))
            flask.g.conn.commit()
            return flask.render_template('auth/forgot_pass_token_expired.html', expired=True)
        
        return flask.render_template('auth/new_pass.html', token=token)
    
    elif flask.request.method == 'POST':
        data = json.loads(flask.request.get_data().decode())

        errors = validate_new_password_data(data)
        if len(errors) > 0:
            return {'errors': errors}, 400
        
        flask.g.cursor.execute('SELECT * FROM forgotPassTokens WHERE token = %s', (data['new-pass-token'],))
        user_id = flask.g.cursor.fetchone()['userID']
        flask.g.cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user_data = flask.g.cursor.fetchone()
        flask.g.cursor.execute('UPDATE users SET passHash = %s WHERE id = %s', (werkzeug.security.generate_password_hash(data['new-pass'], config['AUTH']['hash_method']), user_data['id']))
        flask.g.cursor.execute('DELETE FROM forgotPassTokens WHERE token = %s', (data['new-pass-token'],))
        flask.g.conn.commit()
        queue_data = {'template': config['EMAIL_PATHS']['new_pass'], 'subject': config['EMAIL_SUBJECTS']['new_pass'], 'email': user_data['email'], 'name': user_data['firstName']}
        flask.g.redis_client.lpush(config['REDIS_QUEUES']['email_queue'], json.dumps(queue_data))

        return flaskr.static_cache.SUCCESS_MESSAGES['auth']['new-password-set'], 200
        

@bp.route(config['ENDPOINTS']['logout'], methods=['GET'])
def logout():
    if flask.session.get('user_id'):
        flaskr.functions.migrate_cart('user->cookie')
        flask.session.clear()
        return flask.render_template('auth/logged_out.html')
    else:
        return flask.redirect('/')


def validate_login_data(data):
    errors = []
    if ('@' not in data['log-email']) or ('.' not in data['log-email']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_email'])

    return errors


def validate_register_data(data):
    errors = []
    if (data['reg-fn'] == '') or (len(data['reg-fn']) > 45):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_name'])
    if (data['reg-ln'] == '') or (len(data['reg-ln']) > 255):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_last_name'])
    if ('@' not in data['reg-email']) or ('.' not in data['reg-email']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_email'])
    if not re.search(r'[a-z]', data['reg-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_lower_case'])
    if not re.search(r'[A-Z]', data['reg-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_upper_case'])
    if not re.search(r'[0-9]', data['reg-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_digit'])
    if not re.search(r'[0-9]', data['reg-ph']) or (len(data['reg-ph']) > 20):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_phone'])
    if len(data['reg-pass']) < int(config['AUTH']['min_password_length']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_length'])
    if data['reg-pass'] != data['reg-pass-confirm']:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_confirm'])
    if data['reg-reg-checkbox'] != True:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_reg_checkbox'])

    return errors


def validate_forgot_password_data(data):
    errors = []
    if ('@' not in data['forgot-pass-email']) or ('.' not in data['forgot-pass-email']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_email'])

    return errors


def validate_new_password_data(data):
    errors = []
    if not re.search(r'[a-z]', data['new-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_lower_case'])
    if not re.search(r'[A-Z]', data['new-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_upper_case'])
    if not re.search(r'[0-9]', data['new-pass']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_digit'])
    if len(data['new-pass']) < int(config['AUTH']['min_password_length']):
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_length'])
    if data['new-pass'] != data['new-pass-confirm']:
        errors.append(flaskr.static_cache.ERROR_MESSAGES['auth']['invalid_pass_confirm'])

    return errors