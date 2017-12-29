#!/usr/bin/python

# zkillboard api = https://github.com/zKillboard/zKillboard/wiki/API-(Statistics)
# eve api = https://esi.tech.ccp.is/latest/
# plh = https://github.com/rischwa/eve-plh
# my id = 92942102

from flask import Flask, render_template, request
from datetime import date, datetime, timedelta
import requests, json
from functools import wraps
from flask_caching import Cache
import logging
import config

logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(formatter)
logger.addHandler(console)

application = Flask(__name__)
application.config.from_object(config)

cache = Cache(application, with_jinja2_ext=False, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 60*60})

request_headers = {
    'user-agent': 'kat1248@gmail.com Signal Cartel Little Helper'
}

# map of name to nickname, easter egg
nicknames = {
    'Mynxee': 'Space Mom',
    'Portia Tigana': 'Tiggs'
}

# maximum number of characters to fetch (for speed)
max_chars = config.MAX_CHARS

def templated(template=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            template_name = template
            if template_name is None:
                template_name = request.endpoint.replace('.', '/') + '.html'
            ctx = f(*args, **kwargs)
            if ctx is None:
                ctx = {}
            elif not isinstance(ctx, dict):
                return ctx
            return render_template(template_name, **ctx)
        return decorated_function
    return decorator

# CCP ESI Api calls
@cache.memoize(timeout=24*60*60)
def name2id(name):
    req = 'https://esi.tech.ccp.is/latest/search'
    payload = {'categories': 'character', 'datasource': 'tranquility', 'language': 'en-us', 'search': name, 'strict': 'false'}
    r = requests.get(req, params=payload, headers=request_headers)
    d = json.loads(r.text)
    chars = d.get('character', [])
    return chars

@cache.memoize()
def id2record(character_id):
    req = 'https://esi.tech.ccp.is/latest/characters/{0}'.format(character_id)
    payload = {'datasource': 'tranquility'}
    r = requests.get(req, params=payload, headers=request_headers)
    return json.loads(r.text)

@cache.memoize(timeout=24*60*60)
def lookup_corp(corporation_id):
    req = 'https://esi.tech.ccp.is/latest/corporations/names/'
    payload = {'datasource': 'tranquility', 'corporation_ids': corporation_id}
    r = requests.get(req, params=payload, headers=request_headers)
    d = json.loads(r.text)
    return d[0].get('corporation_name', '')

@cache.memoize()
def lookup_corp_startdate(character_id):
    req = 'https://esi.tech.ccp.is/latest/characters/{0}/corporationhistory'.format(character_id)
    r = requests.get(req, headers=request_headers)
    d = json.loads(r.text)
    return d[0].get('start_date', '')

@cache.memoize(timeout=24*60*60)
def lookup_alliance(alliance_id):
    if alliance_id == 0:
        return ''
    req = 'https://esi.tech.ccp.is/latest/alliances/names/'
    payload = {'datasource': 'tranquility', 'alliance_ids': alliance_id}
    r = requests.get(req, params=payload, headers=request_headers)
    d = json.loads(r.text)
    return d[0].get('alliance_name', '')

# ZKillboard Api calls
@cache.memoize()
def lookup_zkill_character(character_id):
    req = 'https://zkillboard.com/api/stats/characterID/{0}/'.format(character_id)
    r = requests.get(req, headers=request_headers)
    return json.loads(r.text)

@cache.memoize()
def lookup_corp_danger(corporation_id):
    req = 'https://zkillboard.com/api/stats/corporationID/{0}/'.format(corporation_id)
    r = requests.get(req, headers=request_headers)
    d = json.loads(r.text)
    return d.get('dangerRatio', 0)

@cache.memoize()
def fetch_last_kill(cid):
    req = 'https://zkillboard.com/api/stats/characterID/{0}/limit/1/'.format(cid)
    r = requests.get(req, headers=request_headers)
    d = json.loads(r.text)[0]
    when = d['killmail_time'].split("T")[0]
    victim = d['victim']
    who = victim.get('character_id', 0)
    return (when, who)

def last_kill_activity(cid, has_killboard):
    if has_killboard:
        when, who = fetch_last_kill(cid)
        if who == cid:
            return 'died {0}'.format(when)
        elif who == 0:
            return 'struct {0}'.format(when)
        else:
            return 'kill {0}'.format(when)
    else:
        return ''

def seconds2time(total_seconds):
    s = int(total_seconds)
    years = s // 31104000
    s = s - (years * 31104000)
    months = s // 2592000
    s = s - (months * 2592000)
    days = s // 86400
    fmt = ''
    if years > 0:
        fmt += '{2}y'
    if months > 0:
        fmt += '{1}m'
    if days > 0:
        fmt += '{0}d'
    if fmt == '':
        return 'today'
    else:
        return fmt.format(days,months,years)

def seconds2days(total_seconds):
    s = int(total_seconds)
    return s // 86400

def age2seconds(a_date):
    today = datetime.today()
    birthdate = datetime.strptime(a_date, "%Y-%m-%dT%H:%M:%SZ")
    td = today - birthdate
    return td.total_seconds()

@cache.memoize()
def get_character_id(name):
    character_ids = name2id(name)
    character_id = None
    record = {}
    if len(character_ids) == 0:
        character_id = None
    elif len(character_ids) == 1:
        character_id = character_ids[0]
    else:
        for next_id in character_ids:
            record = id2record(next_id)
            if record['name'] == name:
                character_id = next_id
                break
    return character_id

@cache.memoize()
def character_info(name):
    character_id = get_character_id(name)
    if character_id is None:
        return None

    record = id2record(character_id)
    corp_id = record.get('corporation_id', 0)
    alliance_id = record.get('alliance_id', 0)

    zkill = lookup_zkill_character(character_id)
    kills = zkill.get('shipsDestroyed', 0)
    losses = zkill.get('shipsLost', 0)
    has_killboard = (kills != 0) or (losses != 0)

    if name in nicknames:
        name = nicknames[name]

    char_info = {
        'name': name, 
        'character_id': character_id,
        'security': float('{0:1.2f}'.format(float(record.get('security_status', 0)))),
        'age': seconds2time(age2seconds(record['birthday'])), 
        'danger': zkill.get('dangerRatio', 0),
        'gang': zkill.get('gangRatio', 0), 
        'kills': kills, 
        'losses': losses,
        'has_killboard': has_killboard, 
        'last_kill': last_kill_activity(character_id, has_killboard),
        'corp_name': lookup_corp(corp_id), 
        'corp_id': corp_id,
        'corp_age': seconds2days(age2seconds(lookup_corp_startdate(character_id))),
        'is_npc_corp': corp_id < 2000000, 
        'corp_danger': lookup_corp_danger(corp_id), 
        'alliance_name': lookup_alliance(alliance_id)
    }
    return char_info

def character_info_list(names):
    charlist = []
    for name in names:
        info = character_info(name)
        if info is not None:
            charlist.append(info)
    return charlist

@application.route('/')
@templated('index.html')
def lookup():
    return dict(charlist=[], max_chars=max_chars)

@application.route('/local', methods = ['POST', 'GET'])
@templated('index.html')
def local():
    names=[]
    if request.method == 'POST':
        name_list = request.form['characters']
        names = name_list.splitlines()[:max_chars]
    return dict(charlist=character_info_list(names), max_chars=max_chars)

@application.route('/test')
@templated('index.html')
def test1():
    names = [
        'Albina Sobr','Allex Hotomanila','Altern Torren','Anatar Thandon','Archiater','Art CooLSpoT',
        'Azarkhy Alfik Thiesant','Bitter Dystany','Cartelus','Chilik','Connor McCloud McMahon','Dak Ad',
        'Darkschnyder','Davidkaa Smith','Dig Cos','Dimka Tallinn','Domenic Padre','Eudes Omaristos',
        'FESSA13','Fineas ElMaestro','Frack Taron','g0ldent0y','Gunner wortherspoon','gunofaugust',
        'Heior','Highshott','Irisfar Senpai','Jettero Prime','Jocelyn Rotineque'
    ]
    return dict(charlist=character_info_list(names), max_chars=max_chars)

if __name__ == "__main__":
    application.run(port=config.PORT, host=config.HOST, debug=config.DEBUG)
