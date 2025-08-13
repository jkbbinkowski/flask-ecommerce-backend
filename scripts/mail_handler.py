# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import sys
import json
import dotenv
import configparser


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')

sys.path.append(working_dir)
import flaskr.functions


if __name__ == '__main__':
    try:
        r = flaskr.functions.connect_redis()
        while True:
            task = r.brpop(config['REDIS_QUEUES']['email_queue'], timeout=config['REDIS']['timeout'])
            if task:
                email_data = json.loads(task[1])
                print(email_data)
                flaskr.functions.send_transactional_email(email_data)

    except Exception as e:
        print(e)

    finally:
        r.close()


# Example of data for transactional emails
# {
#     'template': config['EMAIL_PATHS']['new_pass'],  # path to template file
#     'subject': config['EMAIL_SUBJECTS']['new_pass'],  # subject of email
#     'email': user_data['email'],  # recipient email
#     'cc': [] # optional, list of emails to cc
#     'bcc': [] # optional, list of emails to bcc
# }

# # # Also you can parse another data that thats used by jinja2 during template rendering (template specific)
    
        