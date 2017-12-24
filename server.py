#!/usr/bin/python

# zkillboard api = https://github.com/zKillboard/zKillboard/wiki/API-(Statistics)
# eve api = https://esi.tech.ccp.is/latest/
# plh = https://github.com/rischwa/eve-plh
# my id = 92942102

from flask import Flask, render_template, request
from datetime import date, datetime, timedelta
import requests, json
from functools import wraps
from werkzeug.contrib.cache import SimpleCache
from urllib import quote

app = Flask(__name__)
cache = SimpleCache()

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

def cached(timeout=60 * 60, key='ccp'):
	def decorator(f):
		@wraps(f)
		def decorated_function(*args, **kwargs):
			cache_key = '{0}:{1}'.format(key, args[0])
			rv = cache.get(cache_key)
			if rv is not None:
				return rv
			rv = f(*args, **kwargs)
			cache.set(cache_key, rv, timeout=timeout)
			return rv
		return decorated_function
	return decorator

@cached()
def name2id(name):
	req = 'https://esi.tech.ccp.is/latest/search'
	payload = {'categories': 'character', 'datasource': 'tranquility', 'language': 'en-us', 'search': name, 'strict': 'false'}
	r = requests.get(req, params=payload)
	d = json.loads(r.text)
	chars = d.get('character', [])
	return chars

@cached()
def id2record(cid):
	req = 'https://esi.tech.ccp.is/latest/characters/{0}'.format(cid)
	payload = {'datasource': 'tranquility'}
	r = requests.get(req, params=payload)
	return json.loads(r.text)

@cached(key='zkill')
def lookup_zkill_character(cid):
	req = 'https://zkillboard.com/api/stats/characterID/{0}/'.format(cid)
	r = requests.get(req)
	return json.loads(r.text)

@cached(key='zkill')
def lookup_zkill_corp(cid):
	req = 'https://zkillboard.com/api/stats/corporationID/{0}/'.format(cid)
	r = requests.get(req)
	return json.loads(r.text)

def lookup_corp_danger(cid):
    rec = lookup_zkill_corp(cid)
    return rec.get('dangerRatio', 0)

@cached()
def lookup_corp(cid):
	req = 'https://esi.tech.ccp.is/latest/corporations/names/'
	payload = {'datasource': 'tranquility', 'corporation_ids': cid}
	r = requests.get(req, params=payload)
	d = json.loads(r.text)
	return d[0].get('corporation_name', '')

@cached()
def lookup_alliance(aid):
	if aid == 0:
		return ''
	req = 'https://esi.tech.ccp.is/latest/alliances/names/'
	payload = {'datasource': 'tranquility', 'alliance_ids': aid}
	r = requests.get(req, params=payload)
	d = json.loads(r.text)
	return d[0].get('alliance_name', '')
    
def seconds_to_time_left_string(total_seconds):
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

def calculate_age(bday):
    today = datetime.today()
    birthdate = datetime.strptime(bday, "%Y-%m-%dT%H:%M:%SZ")
    td = today - birthdate
    return seconds_to_time_left_string(td.total_seconds())

@cached(key='kill')
def fetch_last_kill(cid):
	req = 'https://zkillboard.com/api/stats/characterID/{0}/limit/1/'.format(cid)
	r = requests.get(req)
	d = json.loads(r.text)[0]
	victim = d['victim']
	who = victim.get('character_id', 0)
	return (d['killmail_time'].split("T")[0], who)

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

@cached(key='char')
def character_info(name):
    cids = name2id(name)
    cid = None
    record = {}
    if len(cids) == 0:
        cid = None
    elif len(cids) == 1:
        cid = cids[0]
    else:
        for nid in cids:         
            record = id2record(nid)
            print record['name']
            if record['name'] == name:
                print "break"
                cid = nid
                break
    if cid is None:
        return None
    record = id2record(cid)
    char = {}
    char['name'] = name
    char['cid'] = cid
    zkill = lookup_zkill_character(cid)
    char['danger'] = zkill.get('dangerRatio', 0)
    char['gang'] = zkill.get('gangRatio', 0)
    kills = char['kills'] = zkill.get('shipsDestroyed', 0)
    char['kills'] = kills
    losses = zkill.get('shipsLost', 0)
    char['losses'] = losses
    has_killboard = (kills != 0) or (losses != 0)
    char['has_killboard'] = has_killboard
    char['last_kill'] = last_kill_activity(cid, has_killboard)
    corp_id = record.get('corporation_id', 0)
    npc_corp = False
    if corp_id < 2000000:
        npc_corp = True
    char['npc_corp'] = npc_corp
    char['corp_name'] = lookup_corp(corp_id)
    char['corp_id'] = corp_id
    char['corp_danger'] = lookup_corp_danger(corp_id)
    aid = record.get('alliance_id', 0)
    char['alliance'] = lookup_alliance(aid)
    char['security'] = float('{0:1.2f}'.format(float(record.get('security_status', 0))))
    char['age'] = calculate_age(record['birthday'])
    return char

def character_info_list(names):
    charlist = []
    for name in names:
    	info = character_info(name)
    	if info is not None:
	        charlist.append(info)
    return charlist

@app.route('/')
@templated('index.html')
def lookup():
    return dict(charlist=[])

@app.route('/local', methods = ['POST', 'GET'])
@templated('index.html')
def local():
    names=[]
    if request.method == 'POST':
        name_list = request.form['characters']
        names = name_list.splitlines()
    return dict(charlist=character_info_list(names))

@app.route('/test1')
@templated('index.html')
def test1():
	names = ['Albina Sobr','Allex Hotomanila','Altern Torren','Anatar Thandon','Archiater','Art CooLSpoT',
			'Azarkhy Alfik Thiesant','Bitter Dystany','Cartelus','Chilik','Connor McCloud McMahon','Dak Ad',
			'Darkschnyder','Davidkaa Smith','Dig Cos','Dimka Tallinn','Domenic Padre','Eudes Omaristos',
			'FESSA13','Fineas ElMaestro','Frack Taron','g0ldent0y','Gunner wortherspoon','gunofaugust',
			'Heior','Highshott','Irisfar Senpai','Jettero Prime','Jocelyn Rotineque']
	return dict(charlist=character_info_list(names))

@app.route('/test2')
@templated('index.html')
def test2():
	names = ['Highshott','Portia Tigana']
	return dict(charlist=character_info_list(names))

if __name__ == "__main__":
#    app.run(host="10.60.42.51",debug=True)
    app.run(debug=True)
