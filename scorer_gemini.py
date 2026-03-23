import json, re, datetime, os, subprocess, urllib.request, urllib.parse, time, sys

HTML_FILE = "sensor-live.html"
MAX_HISTORY = 48
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries

SYSTEM_PROMPT = """You are a geopolitical analyst specializing in Middle East conflicts.
Your task is to assess the current temperature of the Iran-USA-Israel war that began on February 28, 2026.

TEMPERATURE SCALE:
0-20   = Active diplomacy / ceasefire negotiations
21-50  = Proxy conflict / indirect confrontation
51-80  = Open warfare / direct military engagement
81-100 = Total war / strategic strikes on capitals
101+   = Nuclear threat / NATO direct involvement

You must respond ONLY with valid JSON, no backticks, no extra text, no markdown."""

def build_prompt():
    now = datetime.datetime.now()
    day = max(1, (now - datetime.datetime(2026, 2, 28)).days + 1)
    date_str = now.strftime("%B %d, %Y at %H:%M UTC")
    
    return f"""Assess the Iran-USA-Israel war status for Day {day} of the conflict ({date_str}).

Consider ALL of the following factors when calculating temperature:
- IDF air operations over Iran, Lebanon, Syria
- Iranian missile and drone retaliation campaigns  
- Strait of Hormuz status (open/partial/closed) and oil price impact
- Hezbollah northern front activity (Lebanon)
- Kurdish front dynamics (Iraq/Syria)
- US CENTCOM force posture (carrier groups, troops deployed)
- Nuclear posture signals from Iran, Israel, USA
- Diplomatic channels (Qatar, Oman, Turkey mediation)
- Russian and Chinese positioning
- Saudi Arabia / UAE alignment
- Civilian casualties and humanitarian situation
- Energy markets (WTI crude, LNG prices)
- Cyber warfare activity
- Intelligence operations (CIA/Mossad)

Respond ONLY with this exact JSON structure:
{{
  "temperatura": <float between 0 and 130>,
  "trend": "rising|stable|falling",
  "title": "<max 80 chars, dramatic headline in English>",
  "summary": "<max 200 chars summary in Italian>",
  "hot_actors": ["actor1", "actor2", "actor3"],
  "key_event": "<single most important event, max 65 chars>",
  "nuclear_risk": <integer 0-10>,
  "hormuz_strait": "open|partial|closed",
  "us_forces": "<brief status of US military posture>",
  "oil_price_impact": "<brief oil market assessment>",
  "diplomatic_channel": "<active diplomacy if any, or none>",
  "tickers": [
    "<news item 1, max 120 chars>",
    "<news item 2, max 120 chars>",
    "<news item 3, max 120 chars>",
    "<news item 4, max 120 chars>",
    "<news item 5, max 120 chars>"
  ]
}}"""

def ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fetch_with_retry():
    """Call Claude API with retry logic on failure."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[{ts()}] API call attempt {attempt}/{MAX_RETRIES}...")
            result = fetch()
            return result
        except Exception as e:
            last_error = e
            print(f"[{ts()}] Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"[{ts()}] Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")

def fetch():
    """Call Claude Haiku API and return parsed scoring data."""
    prompt = build_prompt()
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1200,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.loads(r.read().decode("utf-8"))
    
    text = raw["content"][0]["text"].strip()
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    s = text.find("{")
    e = text.rfind("}") + 1
    if s >= 0 and e > s:
        text = text[s:e]
    
    data = json.loads(text)
    
    required = ["temperatura", "trend", "title", "summary", "tickers"]
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    data["temperatura"] = max(0.0, min(130.0, float(data["temperatura"])))
    
    print(f"[{ts()}] SUCCESS: {data['temperatura']}C | {data['trend']} | {data['title'][:50]}")
    print(f"[{ts()}] Nuclear risk: {data.get('nuclear_risk','N/A')}/10 | Hormuz: {data.get('hormuz_strait','N/A')}")
    return data

def load_html():
    path = os.path.join(REPO_DIR, HTML_FILE)
    if not os.path.exists(path):
        raise FileNotFoundError(f"HTML file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def save_html(content):
    with open(os.path.join(REPO_DIR, HTML_FILE), "w", encoding="utf-8") as f:
        f.write(content)

def load_history(html):
    try:
        m = re.search(r'const history = \[([^\]]*)\]', html)
        if m:
            vals = [v.strip() for v in m.group(1).split(",") if v.strip()]
            return [float(v) for v in vals]
    except Exception as e:
        print(f"[{ts()}] Warning: could not load history: {e}")
    return []

def get_status_label(temp):
    if temp <= 20:  return "DIPLOMACY"
    if temp <= 50:  return "PROXY WAR"
    if temp <= 80:  return "OPEN WAR"
    if temp <= 100: return "TOTAL WAR"
    return "NUCLEAR RISK"

def update_html(html, scoring, history):
    temp = round(float(scoring["temperatura"]), 1)
    day = max(1, (datetime.datetime.now() - datetime.datetime(2026, 2, 28)).days + 1)
    time_str = datetime.datetime.now().strftime("TIME %H:%M")
    arrow = {"rising": "↑", "falling": "↓", "stable": "→"}.get(scoring.get("trend", "stable"), "→")
    key_event = scoring.get("key_event", "")[:65]
    status = get_status_label(temp)
    hist_str = ", ".join(str(v) for v in history)

    html = re.sub(r'const history = \[[^\]]*\]', f'const history = [{hist_str}]', html)
    html = re.sub(r'let currentTemp = [\d.]+;', f'let currentTemp = {temp};', html)
    html = re.sub(r'id="svg-temp-disp">[^<]*°C', f'id="svg-temp-disp">{temp}°C', html)
    html = re.sub(r'LIVE · GIORNO \d+ · ORE \d+:\d+', f'LIVE · DAY {day} · {time_str}', html)
    html = re.sub(r'OUTPUT: [\d.]+\s*°C\s*[↑↓→][^\n<]*', f'OUTPUT: {temp} °C {arrow} {key_event}', html)
    html = re.sub(r'(STABILE|SALITA|DISCESA|STABLE|RISING|FALLING|DIPLOMACY|PROXY WAR|OPEN WAR|TOTAL WAR|NUCLEAR RISK)', status, html, count=1)

    new_tickers = scoring.get("tickers", [])
    if len(new_tickers) >= 3:
        ticker_js = "const TICKERS = [\n" + "".join(
            f"  {json.dumps(t, ensure_ascii=False)},\n" for t in new_tickers
        ) + "];"
        html = re.sub(r'const TICKERS = \[[\s\S]*?\];', ticker_js, html)

    extended = {
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nuclear_risk": scoring.get("nuclear_risk", 0),
        "hormuz": scoring.get("hormuz_strait", "unknown"),
        "us_forces": scoring.get("us_forces", ""),
        "oil_impact": scoring.get("oil_price_impact", ""),
        "diplomacy": scoring.get("diplomatic_channel", "none")
    }
    extended_comment = f"<!-- SENSOR_DATA:{json.dumps(extended)} -->"
    html = re.sub(r'<!-- SENSOR_DATA:[^>]* -->', '', html)
    html = html.replace('</body>', f'{extended_comment}\n</body>')

    return html

def git_push():
    print(f"[{ts()}] Pushing to GitHub...")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cmds = [
        ["git", "-C", REPO_DIR, "add", HTML_FILE],
        ["git", "-C", REPO_DIR, "commit", "-m", f"auto-update: {timestamp}"],
        ["git", "-C", REPO_DIR, "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            if "nothing to commit" in result.stdout + result.stderr:
                print(f"[{ts()}] Nothing to commit — HTML unchanged.")
                return
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{result.stderr}")
    print(f"[{ts()}] GitHub Pages updated successfully.")

if __name__ == "__main__":
    print(f"[{ts()}] === Iran Geopolitical Sensor — One-Shot Scorer ===")
    
    if not ANTHROPIC_API_KEY:
        print(f"[{ts()}] ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    html = load_html()
    history = load_history(html)
    print(f"[{ts()}] History loaded: {len(history)} data points")
    
    scoring = fetch_with_retry()
    
    history.append(round(float(scoring["temperatura"]), 1))
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    print(f"[{ts()}] History updated: {len(history)} data points")
    
    updated_html = update_html(html, scoring, history)
    save_html(updated_html)
    print(f"[{ts()}] HTML saved.")
    
    git_push()
    
    print(f"[{ts()}] === Done. Temperature: {scoring['temperatura']}C | {scoring['trend'].upper()} ===")
