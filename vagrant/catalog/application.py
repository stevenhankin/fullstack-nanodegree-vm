from flask import Flask, render_template, request, redirect, url_for, g, abort
from sqlalchemy import asc, desc, text
from sqlalchemy.orm.exc import NoResultFound
from database_setup import Base, User, Category, Item, session
from flask import session as login_session

import hashlib

import config
import pycurl
import urllib
import json
import StringIO

import random, string

app = Flask(__name__)
app.secret_key = "\xc7\xc7\xf7\x80\x9b\xbb'\xd7\xa7\xe4\xa8\xd9\x7f\x03z)u&Z2c\xde\xf0\xd8"
app.config['SESSION_TYPE'] = 'filesystem'


@app.route('/')
def show_homepage():
    """
    Shows all the available categories and items
    :return:
    """
    print "** LOGIN_SESSION is"
    print login_session

    max_items = 5
    all_categories = session.query(Category).order_by(asc(Category.name)).all()
    # if 'username' not in login_session:
    #     return render_template('public_categories.html', categories=categories)
    # else:
    s = "select item.name as item_name, category.name as category_name, " \
        " category.id as category_id " \
        " from item" \
        " join category on (item.category_id = category.id)" \
        " order by item.time_created DESC" \
        " limit " + str(max_items)
    latest_items = session.execute(s).fetchall()
    return render_template('categories_latest.html',
                           all_categories=all_categories,
                           latest_items=latest_items,
                           max_items=max_items,
                           login_session=login_session)


# For specified category, display all items
@app.route('/categories/<int:category_id>/items')
def show_category_items(category_id):
    """
    Displays all the items for the selected category
    :param category_id:
    :return:
    """
    print "category_id " + str(category_id)
    all_categories = session.query(Category).order_by(asc(Category.name)).all()
    category = session.query(Category).filter(Category.id == category_id).first()
    items = session.query(Item).filter(Item.category_id == category_id)
    item_count = items.count()
    return render_template('category_items.html',
                           all_categories=all_categories,
                           category=category,
                           items=items,
                           item_count=item_count,
                           login_session=login_session)


@app.route('/categories/<int:category_id>/items/<int:item_id>')
def show_item_details(category_id, item_id):
    """
    Displays full description of an item
    :param category_id:
    :param item_id:
    :return:
    """
    print "** ITEM LOGIN_SESSION is"
    print login_session
    print "item_id " + str(item_id)
    # all_categories = session.query(Category).order_by(asc(Category.name)).all()
    # category = session.query(Category).filter(Category.id == category_id).first()
    item = session.query(Item, User).join(User).filter(Item.id == item_id).one()
    # item_count = items.count()
    print item.Item.description
    return render_template('item_details.html', item=item, login_session=login_session)


@app.route('/items/<int:item_id>/edit', methods=['POST', 'GET'])
def edit_item_details(item_id):
    """
    Edit item details IF user originally created the item
    :param item_id:
    :return:
    """

    print "Login session is..."
    print login_session

    # User must be logged in for GET and POST
    if not login_session.has_key('userid'):
        abort(403)

    item = session.query(Item, User).join(User).filter(Item.id == item_id).one()

    print "item creator "+str(item.Item.user_id)+", current user "+str(login_session['userid'])
    # User must be item creator
    if item.Item.user_id != login_session['userid']:
        abort(403)

    categories = session.query(Category).order_by(asc(Category.name)).all()

    if request.method == 'GET':
        return render_template('item_details_edit.html', item=item, categories=categories, login_session=login_session)
    if request.method == 'POST':
        return 'Ok!!'


def redirect_dest(fallback):
    dest = request.args.get('next')
    try:
        dest_url = url_for(dest)
    except:
        return redirect(fallback)
    return redirect(dest_url)


@app.route('/logout')
def logout():
    login_session.clear()
    nextRedirect = request.args.get('next')
    print "next is " + nextRedirect
    return redirect(nextRedirect)


@app.route('/login')
def login_redirect():
    """
    Redirect from Amazon Login with an auth token
    :return:
    """
    nextRedirect = request.args.get('next')
    access_token = request.args.get('access_token')
    print "access token is " + access_token
    d = amazon_authorization(access_token)
    # # State token to prevent CSRF
    # state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    # login_session['state'] = state
    # Find user in database by email or create new record
    user = session.query(User).filter(User.email == d['email']).first()
    print user
    if user is None:
        m = hashlib.md5()
        m.update(d['email'])
        gravatar = 'https://secure.gravatar.com/avatar/' + m.hexdigest() + '?size=35'
        user = User(name=d['name'], email=d['email'], picture=gravatar)
        session.add(user)
        session.commit()

    login_session['userid'] = user.id
    login_session['picture'] = user.picture
    login_session['name'] = user.name

    return redirect_dest(nextRedirect)


def amazon_authorization(access_token):
    """
    Encapsulates the SDK code from Amazon
    :param access_token: Access token provided by Amazon callback
    :return: Object containing user credentials if authenticated
    """
    b = StringIO.StringIO()
    # verify that the access token belongs to us
    c = pycurl.Curl()
    c.setopt(pycurl.URL, "https://api.amazon.com/auth/o2/tokeninfo?access_token=" + urllib.quote_plus(access_token))
    c.setopt(pycurl.SSL_VERIFYPEER, 1)
    c.setopt(pycurl.WRITEFUNCTION, b.write)
    c.perform()
    d = json.loads(b.getvalue())
    if d['aud'] != config.YOUR_CLIENT_ID:
        # the access token does not belong to us
        raise BaseException("Invalid Token")

    # exchange the access token for user profile
    b = StringIO.StringIO()
    c = pycurl.Curl()
    c.setopt(pycurl.URL, "https://api.amazon.com/user/profile")
    c.setopt(pycurl.HTTPHEADER, ["Authorization: bearer " + access_token])
    c.setopt(pycurl.SSL_VERIFYPEER, 1)
    c.setopt(pycurl.WRITEFUNCTION, b.write)
    c.perform()
    d = json.loads(b.getvalue())
    print "%s %s %s" % (d['name'], d['email'], d['user_id'])
    return d
