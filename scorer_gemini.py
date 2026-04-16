import json, re, datetime, os, subprocess, urllib.request, time, sys

HTML_FILE = 'sensor-live.html'
MAX_HISTORY = 48
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
API_URL = 'https://api.anthropic.com/v1/messages'
MAX_RETRIES = 3
RETRY_DELAY = 10

SYSTEM_PROMPT = (
    'You are a geopolitical analyst specializing in Middle East conflicts. '
    'Assess the Iran-USA-Israel war that began on February 28, 2026. '
    'TEMPERATURE SCALE: 0-20=diplomacy, 21-50=proxy, 51-80=open war, '
    '81-100=total war, 101+=nuclear. '
    'Respond ONLY with valid JSON, no backticks, no extra text.'
)

def build_prompt():
    now = datetime.datetime.now()
    day = max(1, (now - datetime.datetime(2026, 2, 28)).days + 1)
    date_str = now.strftime('%B %d, %Y at %H:%M UTC')
    return (
        'Assess Iran-USA-Israel war, Day ' + str(day) + ' (' + date_str + '). '
        'Consider: IDF strikes, Iranian missiles/drones, Strait of Hormuz, Hezbollah, '
        'US CENTCOM, nuclear signals, diplomacy, Russia, China, Saudi Arabia, oil markets. '
        'Respond ONLY with JSON: '
        '{"temperatura":<float 0-130>,"trend":"rising|stable|falling",'
        '"title":"<80 chars>","summary":"<200 chars Italian>",'
        '"hot_actors":["a1","a2","a3"],'
        '"key_event":"<65 chars>","nuclear_risk":<0-10>,'
        '"hormuz_strait":"open|partial|closed",'
        '"us_forces":"<brief>","oil_price_impact":"<brief>",'
        '"diplomatic_channel":"<brief>",'
        '"tickers":["<news1>","<news2>","<news3>","<news4>","<news5>"]}'
    )

def ts():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def fetch():
    payload = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 1200,
        'system': SYSTEM_PROMPT,
        'messages': [{'role': 'user', 'content': build_prompt()}]
    }
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        API_URL, data=body,
        headers={
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.loads(r.read().decode('utf-8'))
    text = raw['content'][0]['text'].strip()
    text = re.sub(r'```[a-z]*\s*', '', text).strip()
    s = text.find('{')
    e = text.rfind('}') + 1
    if s >= 0 and e > s:
        text = text[s:e]
    data = json.loads(text)
    for field in ['temperatura', 'trend', 'title', 'summary', 'tickers']:
        if field not in data:
            raise ValueError('Missing field: ' + field)
    data['temperatura'] = max(0.0, min(130.0, float(data['temperatura'])))
    print('[' + ts() + '] OK ' + str(data['temperatura']) + 'C | ' + data['trend'])
    return data

def fetch_with_retry():
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print('[' + ts() + '] Attempt ' + str(attempt) + '/' + str(MAX_RETRIES))
            return fetch()
        except Exception as e:
            last_error = e
            print('[' + ts() + '] Failed: ' + str(e))
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise RuntimeError('All attempts failed: ' + str(last_error))

def load_html():
    with open(os.path.join(REPO_DIR, HTML_FILE), 'r', encoding='utf-8') as f:
        return f.read()

def save_html(content):
    with open(os.path.join(REPO_DIR, HTML_FILE), 'w', encoding='utf-8') as f:
        f.write(content)

def load_history(html):
    try:
        m = re.search(r'const history = \[([^\]]*)\]', html)
        if m:
            return [float(v.strip()) for v in m.group(1).split(',') if v.strip()]
    except Exception:
        pass
    return []

def update_html(html, scoring, history):
    temp = round(float(scoring['temperatura']), 1)
    day = max(1, (datetime.datetime.now() - datetime.datetime(2026, 2, 28)).days + 1)
    time_str = datetime.datetime.now().strftime('TIME %H:%M')
    hist_str = ', '.join(str(v) for v in history)

    html = re.sub(r'const history = \[[^\]]*\]', 'const history = [' + hist_str + ']', html)
    html = re.sub(r'let currentTemp = [\d.]+;', 'let currentTemp = ' + str(temp) + ';', html)
    html = re.sub(r'id="svg-temp-disp">[^<]*', 'id="svg-temp-disp">' + str(temp) + '\u00b0C', html)
    html = html.replace('LIVE · DAY -- · TIME --:--', 'LIVE · DAY ' + str(day) + ' · ' + time_str)
    html = re.sub(r'LIVE .{1,5} DAY \d+ .{1,5} TIME \d+:\d+', 'LIVE · DAY ' + str(day) + ' · ' + time_str, html)

    tickers = scoring.get('tickers', [])
    if len(tickers) >= 3:
        tj = 'const TICKERS = [\n' + ''.join(
            '  ' + json.dumps(t, ensure_ascii=False) + ',\n' for t in tickers
        ) + '];'
        html = re.sub(r'const TICKERS = \[[\s\S]*?\];', tj, html)

    extended = {
        'temperatura': temp,
        'trend': scoring.get('trend', 'stable'),
        'last_update': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'nuclear_risk': scoring.get('nuclear_risk', 0),
        'hormuz': scoring.get('hormuz_strait', 'unknown'),
        'us_forces': scoring.get('us_forces', ''),
        'oil_impact': scoring.get('oil_price_impact', ''),
        'diplomacy': scoring.get('diplomatic_channel', 'none')
    }
    sensor_json = json.dumps(extended, ensure_ascii=True)
    comment = '<!-- SENSOR_DATA:' + sensor_json + ' -->'
    html = re.sub(r'<!-- SENSOR_DATA:[^>]* -->', '', html)
    html = html.replace('</body>', comment + '\n</body>')
    return html

def git_push():
    print('[' + ts() + '] Git push...')
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for cmd in [
        ['git', '-C', REPO_DIR, 'add', HTML_FILE],
        ['git', '-C', REPO_DIR, 'commit', '-m', 'auto-update: ' + timestamp],
        ['git', '-C', REPO_DIR, 'push'],
    ]:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            if 'nothing to commit' in result.stdout + result.stderr:
                print('[' + ts() + '] Nothing to commit.')
                return
            raise RuntimeError('Git failed: ' + result.stderr)
    print('[' + ts() + '] GitHub Pages updated.')

if __name__ == '__main__':
    print('[' + ts() + '] === Iran Geopolitical Sensor ===')
    if not ANTHROPIC_API_KEY:
        print('ERROR: ANTHROPIC_API_KEY not set')
        sys.exit(1)
    html = load_html()
    history = load_history(html)
    print('[' + ts() + '] History: ' + str(len(history)) + ' points')
    scoring = fetch_with_retry()
    history.append(round(float(scoring['temperatura']), 1))
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    save_html(update_html(html, scoring, history))
    git_push()
    print('[' + ts() + '] Done. Temp: ' + str(scoring['temperatura']) + 'C | ' + scoring['trend'].upper())
