#!/usr/bin/python

# zkillboard = https://github.com/zKillboard/zKillboard/wiki/API-(Statistics)
# eve api = https://esi.tech.ccp.is/latest/
# plh = https://github.com/rischwa/eve-plh
# DataTables = https://datatables.net/
# my id = 92942102,94358635

from flask import Flask, render_template, request, redirect, url_for
from datetime import date, datetime, timedelta, tzinfo
import pytz
import requests
import json
from functools import wraps
from flask_caching import Cache
import logging
import config
from esipy import App
from esipy import EsiClient
from collections import Counter

application = Flask(__name__)
application.config.from_object(config)

application.logger.info('Starting server')

cache = Cache(
    application,
    with_jinja2_ext=False,
    config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 60*60}
)

zkill_request_headers = {
    'user-agent': config.ESI_USER_AGENT
}

# map of name to nickname, easter egg
nicknames = {
    'Mynxee': 'Space Mom',
    'Portia Tigana': 'Tiggs'
}

# create the app
while True:
    try:
        esiapp = App.create(config.ESI_SWAGGER_JSON)
        break
    except Exception as inst:
        application.logger.error(inst)

# init the client
esiclient = EsiClient(
    security=None,
    cache=None,
    headers={'User-Agent': config.ESI_USER_AGENT},
    retry_requests=True
)


# This class will create the standard retry decorator.
# It only retries on a 500 status code.
class Retry:
    # By default, retry up to this many times.
    MAX_TRIES = 3

    # This method holds the validation check.
    def is_valid(self, resp):
        # By default, only retry if a status code is 500.
        return resp.status_code == 500

    def __call__(self, func):
        def retried_func(*args, **kwargs):
            tries = 0
            while True:
                resp = func(*args, **kwargs)
                if self.is_valid(resp) or tries >= self.MAX_TRIES:
                    break
                tries += 1
            return resp
        return retried_func


# This will retry on 4xx failures only.
class RetryOnAuthFailure(Retry):
    def is_valid(self, resp):
        return not (resp.status_code >= 400 and resp.status_code < 500)


# This will retry on *any* 5xx error, and do so up to 5 times.
class RetryOnServerError(Retry):
    MAX_TRIES = 5

    def is_valid(self, resp):
        return resp.status_code < 500


# Now we create the decorator "functions" (callables, really).
retry_on_500 = Retry()
retry_on_auth_failure = RetryOnAuthFailure()
retry_on_server_error = RetryOnServerError()


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


def name2id_op(name):
    op = esiapp.op['get_search'](
        categories='character',
        datasource=config.ESI_DATASOURCE,
        language='en-us',
        search=name,
        strict=True
    )
    return op


def id2record_op(character_id):
    op = esiapp.op['get_characters_character_id'](
        character_id=character_id,
        datasource=config.ESI_DATASOURCE
    )
    return op


@cache.memoize(timeout=24*60*60)
def lookup_corp(corporation_id):
    op = esiapp.op['get_corporations_names'](
        corporation_ids=[corporation_id],
        datasource=config.ESI_DATASOURCE
    )
    response = esiclient.request(op)
    return response.data[0].get('corporation_name', '')


def lookup_corp_startdate(character_id):
    op = esiapp.op['get_characters_character_id_corporationhistory'](
        character_id=character_id,
        datasource=config.ESI_DATASOURCE
    )
    response = esiclient.request(op)
    data = json.loads(response.raw)
    return response.data[0].get('start_date', '')


@cache.memoize(timeout=24*60*60)
def lookup_alliance(alliance_id):
    if alliance_id == 0:
        return ''
    op = esiapp.op['get_alliances_names'](
        alliance_ids=[alliance_id],
        datasource=config.ESI_DATASOURCE
    )
    response = esiclient.request(op)
    return response.data[0].get('alliance_name', '')


@retry_on_server_error
def fetch_zkill_data(endpoint):
    req = '{0}/{1}'.format(config.ZKILL_API, endpoint)
    return requests.get(req, headers=zkill_request_headers)


def lookup_zkill_character(character_id):
    r = fetch_zkill_data('stats/characterID/{0}/'.format(character_id))
    return json.loads(r.text)


@cache.memoize()
def lookup_corp_danger(corporation_id):
    r = fetch_zkill_data('stats/corporationID/{0}/'.format(corporation_id))
    d = json.loads(r.text)
    return d.get('dangerRatio', 0)


def fetch_last_kill(character_id):
    r = fetch_zkill_data('api/characterID/{0}/limit/1/'.format(character_id))
    d = json.loads(r.text)[0]
    when = d['killmail_time'].split('T')[0]
    victim = d['victim']
    who = victim.get('character_id', 0)
    return when, who


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


@cache.memoize()
def fetch_zkill_list(character_id):
    r = fetch_zkill_data('api/kills/characterID/{0}/'.format(character_id))
    return json.loads(r.text)


@cache.memoize()
def fetch_zkill_list_recent(character_id, seconds):
    r = fetch_zkill_data('api/kills/characterID/{0}/pastSeconds/{1}/'.format(character_id, seconds))
    return json.loads(r.text)


@cache.memoize()
def get_kill_history(character_id, kills):
    """ returns explorer_kills, total_kills, last_kill_time, kills_last_week """
    EXPLORERS = ['29248', '11188', '11192', '605', '11172', '607', '11182', '586', '33468', '33470']

    if kills == 0:
        return 0, 0, '', 0

    kill_list = fetch_zkill_list(character_id)
    ships = Counter(['{0}'.format(k['victim'].get('ship_type_id', 0)) for k in kill_list])
    kill_total = sum(ships.values())
    exp_total = sum([v for k, v in ships.iteritems() if k in EXPLORERS])
    last_kill_time = kill_list[-1].get('killmail_time', '').split('T')[0]

    kill_list = fetch_zkill_list_recent(character_id, 60*60*24*7)
    kills_last_week = len(kill_list)

    return exp_total, kill_total, last_kill_time, kills_last_week


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
        return fmt.format(days, months, years)


def seconds2days(total_seconds):
    s = int(total_seconds)
    return s // 86400


def age2seconds(a_date):
    today = datetime.now(tz=pytz.utc)
    td = today - a_date.v
    return td.total_seconds()


def get_character_id(name, character_ids):
    character_id = None
    record = {}
    if len(character_ids) == 0:
        character_id = None
    elif len(character_ids) == 1:
        character_id = character_ids[0]
    else:
        records = get_ccp_records(character_ids)
        for record in records:
            data = record[1]
            if data['name'] == name:
                character_id = record[0]
                break
    return character_id


def record2info(character_id, ccp_info, zkill_info):
    name = ccp_info.get('name', '')
    if name in nicknames:
        name = nicknames[name]
    corp_id = ccp_info.get('corporation_id', 0)
    alliance_id = ccp_info.get('alliance_id', 0)
    corp_start = lookup_corp_startdate(character_id)

    if zkill_info is None:
        zkill_info = []

    kills = zkill_info.get('shipsDestroyed', 0)
    losses = zkill_info.get('shipsLost', 0)
    has_killboard = (kills != 0) or (losses != 0)

    recent_explorer_total, recent_kill_total, last_kill_time, kills_last_week = get_kill_history(character_id, kills)

    char_info = {
        'name': name,
        'character_id': character_id,
        'security': ccp_info.get('security_status', 0),
        'age': seconds2time(age2seconds(ccp_info['birthday'])),
        'danger': zkill_info.get('dangerRatio', 0),
        'gang': zkill_info.get('gangRatio', 0),
        'kills': kills,
        'losses': losses,
        'has_killboard': has_killboard,
        'last_kill': last_kill_activity(character_id, has_killboard),
        'corp_name': lookup_corp(corp_id),
        'corp_id': corp_id,
        'corp_age': seconds2days(age2seconds(corp_start)),
        'is_npc_corp': corp_id < 2000000,
        'corp_danger': lookup_corp_danger(corp_id),
        'alliance_name': lookup_alliance(alliance_id),
        'recent_explorer_total': recent_explorer_total,
        'recent_kill_total': recent_kill_total,
        'last_kill_time': last_kill_time,
        'kills_last_week': kills_last_week
    }
    return char_info


def get_ccp_records(id_list):
    records = []
    operations = []
    ids = []
    for id in id_list:
        rv = cache.get(id)
        if rv is None:
            ids.append(id)
            operations.append(id2record_op(id))
        else:
            records.append((id, rv))
    if len(operations) > 0:
        results = esiclient.multi_request(operations)
        for idx, res in enumerate(results):
            data = res[1].data
            records.append((ids[idx], data))
            cache.set(id, data, timeout=60*60)
    return records


def multi_character_info_list(names):
    operations = []
    charlist = []
    names_to_lookup = []
    for name in names:
        rv = cache.get(name)
        if rv is None:
            names_to_lookup.append(name)
            operations.append(name2id_op(name))
        else:
            charlist.append(rv)
    if len(operations) > 0:
        results = esiclient.multi_request(operations)
        ids = []
        for idx, res in enumerate(results):
            if res[1].data is not None:
                rec_ids = res[1].data.get('character', [])
                ids.append(get_character_id(names_to_lookup[idx], rec_ids))
        records = get_ccp_records(ids)
        for idx2, record in enumerate(records):
            id = record[0]
            if id is not None:
                data = record2info(id, record[1], lookup_zkill_character(id))
                cache.set(names_to_lookup[idx2], data, timeout=60*60)
                charlist.append(data)
    return charlist


@application.route('/')
@templated('index.html')
def index():
    return dict(charlist=[], max_chars=config.MAX_CHARS)


@application.route('/local', methods=['POST', 'GET'])
@templated('index.html')
def local():
    names = []
    if request.method == 'POST':
        name_list = request.form['characters']
        names = name_list.splitlines()[:config.MAX_CHARS]
        application.logger.info('request for %d names', len(names))
    charlist = multi_character_info_list(names)
    return dict(charlist=charlist, max_chars=config.MAX_CHARS)


@application.route('/test')
@templated('index.html')
def test1():
    names = [
        'Albina Sobr', 'Allex Hotomanila', 'Altern Torren', 'Anatar Thandon',
        'Archiater', 'Art CooLSpoT', 'Azarkhy Alfik Thiesant',
        'Bitter Dystany', 'Cartelus', 'Chilik', 'Connor McCloud McMahon',
        'Dak Ad', 'Darkschnyder', 'Davidkaa Smith', 'Dig Cos', 'Dimka Tallinn',
        'Domenic Padre', 'Eudes Omaristos', 'FESSA13', 'Fineas ElMaestro',
        'Frack Taron', 'g0ldent0y', 'Gunner wortherspoon', 'gunofaugust',
        'Heior', 'Highshott', 'Irisfar Senpai', 'Jettero Prime',
        'Jocelyn Rotineque', 'Dar Mineret'
    ]
    return dict(charlist=multi_character_info_list(names), max_chars=config.MAX_CHARS)


@application.route('/favicon.ico')
def icon():
    return redirect(url_for('static', filename='favicon.ico'), code=302)


if __name__ == "__main__":
    application.run(port=config.PORT, host=config.HOST, debug=config.DEBUG)
