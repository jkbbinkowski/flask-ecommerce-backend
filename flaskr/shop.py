# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import dotenv
import configparser
import flaskr.jinja_filters
import urllib.parse
import json
import flaskr.functions


dotenv.load_dotenv()
working_dir = os.getenv('WORKING_DIR')
config = configparser.ConfigParser()
config.read(f'{working_dir}/config.ini')


bp = flask.Blueprint('shop', __name__, url_prefix=config['ENDPOINTS']['shop'])


@bp.route('', methods=['GET'], defaults={'category': None, 'sub_category': None, 'subsub_category': None})
@bp.route('<category>', methods=['GET'], defaults={'sub_category': None, 'subsub_category': None})
@bp.route('<category>/<sub_category>', methods=['GET'], defaults={'subsub_category': None})
@bp.route('<category>/<sub_category>/<subsub_category>', methods=['GET'])
def shop(category, sub_category, subsub_category):
    #get crucial cookies and parameters
    user_config = flaskr.functions.get_config_cookie(flask.request)
    page = flask.request.args.get('s', 1, type=int)

    #get categories names and ids of children
    active_categories = get_active_categories(category, sub_category, subsub_category)
    parent_categories_ids = get_parent_categories_ids(active_categories)

    #pagination
    if parent_categories_ids == '()':
        flask.g.cursor.execute('SELECT COUNT(*) as total FROM products')
    else:
        flask.g.cursor.execute(f'SELECT COUNT(*) as total FROM products WHERE categoryId IN {parent_categories_ids}')
    total_products = flask.g.cursor.fetchone()['total']
    total_pages = (total_products + user_config['products_visibility_per_page'] - 1)//user_config['products_visibility_per_page']
    if page < 1 or ((page > total_pages) and (total_pages != 0)):
        flask.abort(404)
    offset = (page - 1)*user_config['products_visibility_per_page']

    #availability
    if user_config['availability'] == 'available':
        availability_query = 'WHERE stock > 0'
    elif user_config['availability'] == 'not-available':
        availability_query = 'WHERE stock = 0'
    else:
        availability_query = 'WHERE stock >= 0'

    #price_filter
    try:
        if urllib.parse.unquote(flask.request.base_url) != urllib.parse.unquote(flask.request.referrer.split('?')[0]):
            user_config['price_filter'] = 'off'
    except:
        user_config['price_filter'] = 'off'

    if user_config['price_filter'] == 'on':
        price_filter_query = f'AND priceNet*(1+vatRate/100) >= {user_config["price_filter_values"].split("to")[0]} AND priceNet*(1+vatRate/100) <= {user_config["price_filter_values"].split("to")[1]}'
    else:
        price_filter_query = ''

    #get products
    if parent_categories_ids == '()':
        flask.g.cursor.execute(f'SELECT * FROM products {availability_query} {price_filter_query} {json.loads(config['USER_PREF_COOKIE']["sorting_option_queries"])[user_config["sorting_option"]]} LIMIT {user_config["products_visibility_per_page"]} OFFSET {offset}')
    else:
        flask.g.cursor.execute(f'SELECT * FROM products {availability_query} {price_filter_query} AND categoryId IN {parent_categories_ids} {json.loads(config['USER_PREF_COOKIE']["sorting_option_queries"])[user_config["sorting_option"]]} LIMIT {user_config["products_visibility_per_page"]} OFFSET {offset}')
    products = flask.g.cursor.fetchall()
    try:
        max_price_gross = max(product['priceNet']*(1+product['vatRate']/100) for product in products)
    except:
        max_price_gross = 0

    shop = {
        'sorting_option_names': flaskr.functions.get_config_list('str', config['USER_PREF_COOKIE']['sorting_option_names']),
        'sorting_option_values': flaskr.functions.get_config_list('str', config['USER_PREF_COOKIE']['sorting_option_values']),
        'products_visibility_per_page': flaskr.functions.get_config_list('int', config['USER_PREF_COOKIE']['visibility_per_page_options']),
        'products_availability_values': flaskr.functions.get_config_list('str', config['USER_PREF_COOKIE']['availability_values']),
        'default_list': [config['USER_PREF_COOKIE']['default_visibility_per_page'], config['USER_PREF_COOKIE']['default_sorting_option'], config['USER_PREF_COOKIE']['default_availability'], config['USER_PREF_COOKIE']['default_price_filter']]
    }

    #render template
    resp = flask.make_response(flask.render_template('shop/products.html', 
        current_path = flask.request.path,
        products=products, 
        current_products_limit=user_config['products_visibility_per_page'],
        current_sorting_option=user_config['sorting_option'],
        current_availability=user_config['availability'],
        current_page=page,
        total_pages=total_pages,
        total_products=total_products,
        active_categories=active_categories,
        max_price_gross=max_price_gross,
        current_price_filter=user_config['price_filter'],
        current_price_filter_min=user_config['price_filter_values'].split('to')[0],
        current_price_filter_max=user_config['price_filter_values'].split('to')[1],
        default_cookie = 1 if user_config['config_cookie'] == user_config['default_cookie'] else 0,
        shop = shop
    ))
    print(user_config['config_cookie'], user_config['default_cookie'])
    resp.set_cookie(config['COOKIE_NAMES']['user_preferences'], user_config['config_cookie'], path='/')
    return resp


@bp.route(f'/{config["ENDPOINTS"]["product"]}/<product_slug>', methods=['GET'])
def product(product_slug):
    #read product id from slug
    product_id = product_slug.split('-')
    product_id = product_id[len(product_id)-1]
    
    #get product details
    flask.g.cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = flask.g.cursor.fetchone()

    full_category_path = get_full_category_path(product['categoryId'])

    #check if id is valid for given slug
    try:
        if f"{flaskr.jinja_filters.slugify(product['name'])}-{product['id']}" != product_slug:
            flask.abort(404)
    except:
        flask.abort(404)

    return flask.render_template('shop/product_details.html', product=product, full_category_path=full_category_path)


def get_active_categories(category, sub_category, subsub_category):
    slugs = [category, sub_category, subsub_category]
    active_categories = []
    for idx, slug in enumerate(slugs):
        if idx == 0:
            if slug != None:
                flask.g.cursor.execute("SELECT * FROM categories WHERE slug = %s", (slug,))
                active_categories.append(flask.g.cursor.fetchone())
        else:
            if slug != None:
                flask.g.cursor.execute(f"SELECT * FROM categories WHERE slug = %s AND parentId = {active_categories[idx-1]['id']}", (slug,))
                active_categories.append(flask.g.cursor.fetchone())

    return active_categories


def get_parent_categories_ids(active_categories):
    parent_ids = []
    if len(active_categories) == 1:
        parent_ids.append(active_categories[0]['id'])
        flask.g.cursor.execute(f"SELECT id FROM categories WHERE parentId = {active_categories[0]['id']}")
        for id in flask.g.cursor.fetchall():
            parent_ids.append(id['id'])
        flask.g.cursor.execute(f"SELECT id FROM categories WHERE parentId IN {str(tuple(parent_ids))}")
        for id in flask.g.cursor.fetchall():
            parent_ids.append(id['id'])
    elif len(active_categories) == 2:
        parent_ids.append(active_categories[1]['id'])
        flask.g.cursor.execute(f"SELECT id FROM categories WHERE parentId = {active_categories[1]['id']}")
        for id in flask.g.cursor.fetchall():
            parent_ids.append(id['id'])
    elif len(active_categories) == 3:
        parent_ids.append(active_categories[2]['id'])

    return str(tuple(parent_ids)).replace(',)', ')')


def get_full_category_path(category_id):
    parent_categories = []

    while True:
        flask.g.cursor.execute(f"SELECT * FROM categories WHERE id = {category_id}")
        category = flask.g.cursor.fetchone()
        category_id = category['parentId']
        parent_categories.insert(0, category)
        if category_id == None:
            break

    return parent_categories