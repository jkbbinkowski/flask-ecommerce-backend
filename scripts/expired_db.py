# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE


import configparser
import dotenv
import os
import sys
import time


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')

sys.path.append(working_dir)
import flaskr.functions


def delete_expired_forgot_pass_tokens(mydb, cursor):
    # delete forgot password tokens that are expired
    deletion_threshold = int(time.time()) - int(config['AUTH']['forgot_pass_token_expiration_time'])
    cursor.execute('DELETE FROM forgotPassTokens WHERE creationTime <= %s', (deletion_threshold,))
    mydb.commit()
    
    # delete carts that are expired
    deletion_threshold = int(time.time()) - int(config['GLOBAL']['cart_expiration_time'])
    cursor.execute('SELECT * FROM carts WHERE lastModTime < %s', (deletion_threshold,))

if __name__ == '__main__':
    mydb = flaskr.functions.connect_db()
    cursor = mydb.cursor()

    delete_expired_forgot_pass_tokens(mydb, cursor)

    cursor.close()
    mydb.close()


