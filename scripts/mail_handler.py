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
                flaskr.functions.send_transactional_email(email_data)

    except Exception as e:
        print(e)

    finally:
        r.close()
    
        
