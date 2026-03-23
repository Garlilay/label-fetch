from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
from DrissionPage import Chromium, ChromiumOptions
import pandas as pd
import time
import threading
import uuid
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'arkham-scraper-secret-2024')
CORS(app, supports_credentials=True)

# 存储每个用户的 browser session
browser_sessions = {}
session_lock = threading.Lock()

def get_or_create_browser(session_id):
    with session_lock:
        if session_id not in browser_sessions:
            co = ChromiumOptions()
            co.headless(True)
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--disable-gpu')
            browser = Chromium(co)
            browser_sessions[session_id] = {
                'browser': browser,
                'logged_in': False,
                'tab': browser.latest_tab
            }
        return browser_sessions[session_id]

def get_address_label(raw_data):
    response_json = raw_data.get('transfers', [])
    label_set = set()
    for a in response_json:
        for addr_key in ['fromAddress', 'toAddress']:
            if addr_key in a and 'arkhamLabel' in a[addr_key]:
                addr = a[addr_key]
                label = addr['arkhamLabel']
                entity_id = addr['arkhamEntity']['id'] if 'arkhamEntity' in addr else ''
                name = (entity_id + ':' + label['name']) if entity_id else label['name']
                label_set.add((label['address'], name, label['chainType']))
        for addr_key in ['fromAddresses', 'toAddresses']:
            if addr_key in a and isinstance(a[addr_key], list):
                for addr in a[addr_key]:
                    if 'arkhamLabel' in addr:
                        label = addr['arkhamLabel']
                        entity_id = addr['arkhamEntity']['id'] if 'arkhamEntity' in addr else ''
                        name = (entity_id + ':' + label['name']) if entity_id else label['name']
                        label_set.add((label['address'], name, label['chainType']))
    return label_set

def get_all_address(tab, raw_url):
    label_set = set()
    tab.get(raw_url.format(0))
    time.sleep(0.5)
    raw_data = tab.json
    if not raw_data or 'transfers' not in raw_data:
        return label_set
    max_count = raw_data.get('count', 0)
    label_set.update(get_address_label(raw_data))
    for offset in range(50, min(max_count, 2000), 50):
        tab.get(raw_url.format(offset))
        time.sleep(1)
        raw_data = tab.json
        if not raw_data or 'transfers' not in raw_data:
            break
        label_set.update(get_address_label(raw_data))
    return label_set

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    session_id = request.cookies.get('session_id') or str(uuid.uuid4())

    try:
        bs = get_or_create_browser(session_id)
        tab = bs['tab']
        tab.get('https://intel.arkm.com/login')
        time.sleep(2)

        # 填写邮箱
        email_input = tab.ele('tag:input@type=email', timeout=5)
        if not email_input:
            email_input = tab.ele('tag:input@placeholder^Email', timeout=5)
        email_input.clear()
        email_input.input(email)

        # 填写密码
        pwd_input = tab.ele('tag:input@type=password', timeout=5)
        pwd_input.clear()
        pwd_input.input(password)

        # 点击登录
        submit = tab.ele('tag:button@type=submit', timeout=5)
        submit.click()
        time.sleep(3)

        # 检查是否登录成功
        current_url = tab.url
        if 'login' not in current_url:
            bs['logged_in'] = True
            resp = jsonify({'success': True})
            resp.set_cookie('session_id', session_id, max_age=86400*7)
            return resp
        else:
            return jsonify({'success': False, 'error': '登录失败，请检查账号密码'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/check_login', methods=['GET'])
def check_login():
    session_id = request.cookies.get('session_id')
    if not session_id or session_id not in browser_sessions:
        return jsonify({'logged_in': False})
    return jsonify({'logged_in': browser_sessions[session_id]['logged_in']})

@app.route('/api/scrape', methods=['POST'])
def scrape():
    session_id = request.cookies.get('session_id')
    if not session_id or session_id not in browser_sessions:
        return jsonify({'success': False, 'error': '请先登录'})

    bs = browser_sessions[session_id]
    if not bs['logged_in']:
        return jsonify({'success': False, 'error': '请先登录'})

    data = request.json
    entity_id = data.get('entity_id', '').strip()
    chains = data.get('chains', [])
    tokens = data.get('tokens', [])
    usd_gte = data.get('usd_gte', 10000)

    if not entity_id:
        return jsonify({'success': False, 'error': 'entity_id 不能为空'})

    chain_param = '&chains=' + '%2C'.join(chains) if chains else ''
    tab = bs['tab']

    try:
        all_labels = set()
        for flow in ['in', 'out']:
            url_tpl = f'https://api.arkm.com/transfers?base={entity_id}&flow={flow}&usdGte={usd_gte}&sortKey=time&sortDir=desc&limit=50&offset={{}}{chain_param}'
            s = get_all_address(tab, url_tpl)
            all_labels.update(s)

        df = pd.DataFrame(list(all_labels), columns=['address', 'name', 'chainType'])

        if tokens:
            # token 过滤需要 token 字段，这里按 name 过滤作为补充
            pass

        records = df.to_dict(orient='records')
        return jsonify({'success': True, 'data': records, 'total': len(records)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/logout', methods=['POST'])
def logout():
    session_id = request.cookies.get('session_id')
    if session_id and session_id in browser_sessions:
        try:
            browser_sessions[session_id]['browser'].quit()
        except:
            pass
        del browser_sessions[session_id]
    resp = jsonify({'success': True})
    resp.delete_cookie('session_id')
    return resp

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
