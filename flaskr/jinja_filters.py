# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import unicodedata
import re
import json

def slugify(value):
    value = str(unicodedata.normalize('NFKD', value).encode('ascii', 'ignore'), 'ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[\s_-]+', '-', value)

def jsonify(value):
    return json.loads(value)