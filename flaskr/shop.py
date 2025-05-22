# Copyright (c) 2025 Jakub Binkowski
# Licensed under the Jakub Binkowski License (modified MIT-style)
# For license terms, see: https://github.com/jkbbinkowski/flask-ecommerce-backend/blob/master/LICENSE

import os
import flask
import dotenv
import configparser
import flaskr.jinja_filters
import datetime
import base64
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
    child_category_ids = get_child_category_ids(active_categories)

    #pagination
    if child_category_ids == '()':
        flask.g.cursor.execute('SELECT COUNT(*) as total FROM products')
    else:
        flask.g.cursor.execute(f'SELECT COUNT(*) as total FROM products WHERE categoryId IN {child_category_ids}')
    total_products = flask.g.cursor.fetchone()['total']
    total_pages = (total_products + user_config['products_visibility_per_page'] - 1)//user_config['products_visibility_per_page']
    if page < 1 or ((page > total_pages) and (total_pages != 0)):
        flask.abort(404)
    offset = (page - 1)*user_config['products_visibility_per_page']

    #get products
    if child_category_ids == '()':
        flask.g.cursor.execute(f'SELECT * FROM products {json.loads(config['PRODUCTS']['sorting_option_queries'])[user_config["sorting_option"]]} LIMIT {user_config["products_visibility_per_page"]} OFFSET {offset}')
    else:
        flask.g.cursor.execute(f'SELECT * FROM products WHERE categoryId IN {child_category_ids} {json.loads(config['PRODUCTS']['sorting_option_queries'])[user_config["sorting_option"]]} LIMIT {user_config["products_visibility_per_page"]} OFFSET {offset}')
    products = flask.g.cursor.fetchall()

    #render template
    resp = flask.make_response(flask.render_template('shop/products.html', 
        current_path = flask.request.path,
        products=products, 
        current_products_limit=user_config['products_visibility_per_page'],
        current_sorting_option=user_config['sorting_option'],
        current_page=page,
        total_pages=total_pages,
        total_products=total_products,
        active_categories=active_categories
    ))
    resp.set_cookie(config['COOKIE_NAMES']['user_preferences'], user_config['config_cookie'], expires=user_config['expires'], path='/')
    return resp


@bp.route(f'/{config["ENDPOINTS"]["product"]}/<product_slug>', methods=['GET'])
def product(product_slug):
    #read product id from slug
    product_id = product_slug.split('-')
    product_id = product_id[len(product_id)-1]
    
    #get product details
    flask.g.cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = flask.g.cursor.fetchone()

    #check if id is valid for given slug
    try:
        if f"{flaskr.jinja_filters.slugify(product['name'])}-{product['id']}" != product_slug:
            flask.abort(404)
    except:
        flask.abort(404)

    return flask.render_template('shop/product_details.html', product=product)


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


def get_child_category_ids(active_categories):
    child_ids = []
    if len(active_categories) == 1:
        child_ids.append(active_categories[0]['id'])
        flask.g.cursor.execute(f"SELECT id FROM categories WHERE parentId = {active_categories[0]['id']}")
        for id in flask.g.cursor.fetchall():
            child_ids.append(id['id'])
        flask.g.cursor.execute(f"SELECT id FROM categories WHERE parentId IN {str(tuple(child_ids))}")
        for id in flask.g.cursor.fetchall():
            child_ids.append(id['id'])
    elif len(active_categories) == 2:
        child_ids.append(active_categories[1]['id'])
        flask.g.cursor.execute(f"SELECT id FROM categories WHERE parentId = {active_categories[1]['id']}")
        for id in flask.g.cursor.fetchall():
            child_ids.append(id['id'])
    elif len(active_categories) == 3:
        child_ids.append(active_categories[2]['id'])

    return str(tuple(child_ids)).replace(',)', ')')