import logging
import random
import string
import httplib2
import json
import os
from flask_dance.contrib.google import make_google_blueprint, google
from sqlalchemy import create_engine
from models import Base, Item, User
from flask import Flask, redirect, jsonify, request
from flask import abort, render_template, make_response
from flask import session as login_session, url_for
from sqlalchemy.orm import sessionmaker
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

# print('loading1')

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


APPLICATION_NAME = "Udacity Catalog App"
app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
blueprint = make_google_blueprint(
    client_id=json.loads(open('/var/www/html/catalog/web/client_secrets.json',
                         'r').read())['web']['client_id'],
    client_secret=json.loads(open('/var/www/html/catalog/web/client_secrets.json',
                             'r').read())['web']['client_secret'],
    scope=["profile", "email"]
)
app.register_blueprint(blueprint, url_prefix="/login")

# alternate logging system

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

engine = create_engine('postgresql://catalog:catalog@localhost:5432/catalog')
Base.metadata.bind = engine


DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/')
def splash():
    if (login_session.get('state')):
        return showLogin()
    else:
        return preLogin()


@app.route("/login")
def preLogin():
    # print('loginattempt')
    return render_template('login.html')


@app.route("/googlelogin", methods=['GET', 'POST'])
def showLogin():
    state = ''.join(
        random.choice(
            string.ascii_uppercase + string.digits) for x in range(32))
    if (not login_session.get('state') or (not login_session.get(
        'access_token'))):
        login_session['state'] = state
        login_session['access_token'] = login_session['state']
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    # print(resp.json())
    login_session['google'] = resp.json()
    login_session['username'] = resp.json()['name']
    login_session['email'] = resp.json()['email']
    if not (getUserID(login_session['email'])):
        login_session['user_id'] = createUser(login_session)
    else:
        login_session['user_id'] = getUserID(login_session['email'])
    assert resp.ok, resp.text
    return redirect(url_for('userCP') + "?state=" + login_session['state'])


@app.route("/usercp")
def userCP():
    infirst = 'a'
    try:
        stategiven = request.args['state']
        infirst += request.args['state']
    except:
        logging.info('no state token')
        return redirect('/login')
    logging.info(login_session)
    lsu = ""
    if request.args['state'] == login_session['state'] \
            and login_session.get('username') is not None:
        lsu = login_session['username']
    return render_template('usercp.html', STATE=request.args['state'], LSU=lsu)

@app.route('/gdisconnect')
def gdisconnect():
    failed = False
    # Only disconnect a connected user.

    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    try:
        del login_session['access_token']
    except:
        failed = True

    try:
        del login_session['username']
    except:
        failed = True

    try:
        del login_session['state']
    except:
        failed = True

    try:
        del login_session['user_id']
    except:
        failed = True

    try:
        del login_session['email']
    except:
        failed = True

    if failed is True:
        print('unable to remove all credentials')

    if result['status'] == '200':
        logging.info(login_session)
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return preLogin()
    else:
        return preLogin()


@app.route("/new", methods=['GET', 'POST'])
def newItem():
    """Add new item to catalog"""
    infirst = 'a'
    try:
        stategiven = request.args['state']
        infirst += request.args['state']
    except:
        logging.info('no state token')
        return redirect('/login')


    if 'username' not in login_session:
        return redirect('/login')

    if request.method == 'GET':

        lsu = ""
        if request.args['state'] == login_session['state'] \
                and login_session['username'] is not None:
            lsu = login_session['username']

        return render_template('newItemForm.html', STATE=stategiven, LSU=lsu)

    elif request.method == 'POST':
        print('IN POST')
        # check for authorization based on state token
        if request.args.get('state') != login_session['state']:
            response = make_response(
                json.dumps('Invalid state parameter.'), 401)
            response.headers['Content-Type'] = 'application/json'
            return response

        request.get_data()
        code = request.data.decode('utf-8')

        def itemDecoder(raw_item):
            arr = raw_item.split('&')
            d = {}
            for i in arr:
                key, value = i.split('=')
                d[key] = value
            return d


        decoded_item = itemDecoder(code)
        print('V4 itemsV')
        print(decoded_item['name'])
        print(decoded_item['description'])
        print(decoded_item['category'])
        print(login_session['user_id'])
        print('^4^')


        makeANewItem(
            name=decoded_item['name'],
            description=decoded_item['description'],
            category=decoded_item['category'],
            user_id=login_session['user_id'])

        return redirect('/api/items?state=' + stategiven)


@app.route("/api/items")
def allItemsFunction():
    """Retreives all items in database"""
    return getAllItems()


@app.route('/single_item')
def oneItemForm():
    """Retreives data for single item in database"""

    lsu = ""

    if request.args['state'] == login_session['state'] and \
            login_session['username'] is not None:
        lsu = login_session['username']

    try:
        if request.args['id'] is not None:
            itemID = request.args['id']
            item = getItem(itemID)
            return render_template(
                'view_item.html',
                STATE=request.args['state'],
                ID=request.args['id'],
                ITEM=item,
                LSU=lsu)
    except:
        return render_template(
            'item_request.html',
            STATE=request.args['state'],
            LSU=lsu
            )


@app.route("/api/item/<int:id>")
def oneItemFunction(id):
    """Get information for an item with a given id"""
    return jsonify(getItem(id).serialize)


@app.route("/item", methods=['GET', 'POST', 'PUT', 'DELETE'])
def itemrt():
    """Renders edit item template"""
    if request.method == 'GET':

        if request.args['state'] != login_session['state']:
            return redirect('/login')

        lsu = ""
        if request.args['state'] == login_session['state'] and \
                login_session['username'] is not None:
            lsu = login_session['username']

        return render_template(
            'editItem.html',
            LSU=lsu,
            STATE=request.args['state'])

    return redirect('/login')


@app.route("/item/<int:id>/modify", methods=['GET', 'PUT', 'DELETE'])
def itemMod(id):
    """Modifies item in database with a given id"""

    # retreive item from database
    try:
        myItem = getItem(id)
    except:
        logging.info('item not found')
        response = make_response(
            json.dumps("Item Not found, check for proper item ID number"), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    if request.method == 'GET':
        lsu = ""
        if request.args['state'] == login_session['state'] and \
                login_session['username'] is not None:
            lsu = login_session['username']
        return render_template(
            'editItem.html',
            LSU=lsu,
            id=id,
            STATE=request.args['state'])

    if myItem.user_id != login_session['user_id']:
        logging.info("unable to verify item user id with logged in user id")
        response = make_response(
            json.dumps('Unauthorized user', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

    if request.method == 'PUT':
        stategiven = request.args['state']
        if stategiven != login_session['state']:
            logging.info('not matching')
            return redirect('/login')

        request.get_data()
        code = request.data.decode('utf-8')

        def itemDecoder(raw_item):
            arr = raw_item.split('&')
            d = {}
            for i in arr:
                key, value = i.split('=')
                d[key] = value
            return d

        decoded_item = itemDecoder(code)

        if not decoded_item['name']:
            logging.info('no name given')
        myItem.name = decoded_item['name']
        if not decoded_item['description']:
            logging.info('no desc given')
        myItem.description = decoded_item['description']
        if not decoded_item['category']:
            logging.info('no category given')
        myItem.category = decoded_item['category']
        session.add(myItem)
        session.commit()
        #todo: return redirect to view that item
        return jsonify(item=myItem.serialize)

    else:
        return deleteItem(id)


@app.route("/users", methods=['POST'])
def new_user():
    """Creates new user"""
    username = request.json.get('username')
    password = request.json.get('password')
    if username is None or password is None:
        abort(400)

    try:
        if session.query(User).filter_by(
                username=username).first() is not None:
            user = session.query(User).filter_by(username=username).first()
            return jsonify({'message': 'user already exists'}), 200
    except:
        user = None

    user = User(username=username)
    user.hash_password(password)
    session.add(user)
    session.commit()
    return jsonify({'username': user.username}), 201


@app.route('/api/users')
def get_users():
    """Gets data for all users"""
    try:
        users = session.query(User).all()
    except:
        return ('no users')
    return jsonify(users=[user.serialize for user in users])


def getAllItems():
    try:
        items = session.query(Item).all()
    except:
        return ('no items')
    return jsonify(Items=[i.serialize for i in items])


def getItem(id):
    return session.query(Item).filter_by(id=id).one()


def makeANewItem(name, description, category, user_id):
    item = Item(
        name=name,
        description=description,
        category=category,
        user_id=user_id)

    session.add(item)
    session.commit()
    return jsonify(Item=item.serialize)


def deleteItem(id):
    item = getItem(id)
    session.delete(item)
    session.commit()
    return "Item Deleted"


def createUser(login_session):
    # print('creating new user...')
    username = login_session['username']
    if not login_session['username']:
        username = login_session['email'].split('@')[0]
    newUser = User(name=username, email=login_session[
                   'email'])
    session.add(newUser)
    session.commit()

    user = session.query(User).filter_by(email=login_session['email']).one()

    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def deleteUser(id):
    user = getUserInfo(id)
    session.delete(user)
    session.commit()
    return "user deleted"

def sayhi():
    return "hi"


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

if __name__ == '__main__':
        # app.secret_key = json.loads(
        #     open('/var/www/html/catalog/web/client_secrets.json', 'r').read())['web']['client_secret']
        app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
        # app.config['SESSION_TYPE'] = 'filesystem'
        app.debug = True
        # app.run(host='127.0.0.1', port=9000)
        app.run(host='0.0.0.0', port=80)
