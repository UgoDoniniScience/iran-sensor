#!/usr/bin/env python3
"""
GEOPOLITICAL TEMPERATURE SCORER — versione GRATUITA + AUTO-PUSH
─────────────────────────────────────────────────────────────────
Ogni 120 minuti:
  1. Chiama Google Gemini 1.5 Flash (gratis, 1.500 req/giorno)
  2. Riscrive sensor-live.html con i nuovi dati
  3. Push automatico su GitHub Pages → YouTube live si aggiorna
Costo totale: €0/mese
─────────────────────────────────────────────────────────────────
"""
import json, time, re, datetime, os, subprocess, urllib.request

INTERVAL_MINUTES = 120
HTML_FILE        = "sensor-live.html"
MAX_HISTORY      = 48
REPO_DIR         = os.path.dirname(os.path.abspath(__file__))
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL       = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key={key}"
)

SYSTEM_INSTRUCTION = """\
Sei un analista geopolitico specializzato nel conflitto Iran 2026.
Analizza le ultime notizie e assegna una TEMPERATURA DI CONFLITTO su scala aperta.

SCALA: 0-20 diplomazia | 21-50 proxy | 51-80 guerra aperta | 81-100 guerra totale | 101+ nucleare/NATO

Rispondi SOLO con JSON valido, zero testo aggiuntivo, zero backtick:
{"temperatura":<float>,"trend":"salita|stabile|discesa","titolo":"<max80car>","sommario":"<max200car>","attori_caldi":["a1","a2","a3"],"evento_chiave":"<evento principale>","rischio_nucleare":<0-10>,"stretto_hormuz":"aperto|parziale|chiuso","tickers":["<notizia1 max120car>","<notizia2>","<notizia3>","<notizia4>","<notizia5>"]}"""

def user_prompt():
    return (
        "Cerca le ultimissime notizie guerra Iran-USA-Israele. "
        "Considera: attacchi in corso, vittime, escalation, dichiarazioni, movimenti militari, Hormuz, nuovi attori. "
        "Data: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M") +
        ". Rispondi SOLO con il JSON."
    )

def fetch_temperature():
    print(f"[{ts()}] Gemini API call con Google Search grounding...")
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents":           [{"parts": [{"text": user_prompt()}]}],
        "tools":              [{"google_search": {}}],
        "generationConfig":   {"temperature": 0.2, "maxOutputTokens": 1000}
    }
    url  = GEMINI_URL.format(key=GEMINI_API_KEY)
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = text.strip("`").lstrip("json").strip()
        s = text.find("{"); e = text.rfind("}") + 1
        if s >= 0 and e > s: text = text[s:e]
        data = json.loads(text)
        print(f"[{ts()}] OK  {data['temperatura']}C  {data['trend']}  {data['titolo'][:55]}")
        return data
    except Exception as exc:
        print(f"[{ts()}] ERR {exc}")
        return None

def load_html():
    with open(os.path.join(REPO_DIR, HTML_FILE), "r", encoding="utf-8") as f:
        return f.read()

def save_html(c):
    with open(os.path.join(REPO_DIR, HTML_FILE), "w", encoding="utf-8") as f:
        f.write(c)

def update_html(html, scoring, history):
    temp   = round(float(scoring["temperatura"]), 1)
    giorno = max(1, (datetime.datetime.now() - datetime.datetime(2026, 2, 28)).days + 1)
    ora    = datetime.datetime.now().strftime("ORE %H:%M")
    arrow  = {"salita":"↑","discesa":"↓","stabile":"→"}.get(scoring.get("trend","stabile"),"→")
    evento = scoring.get("evento_chiave","")[:65]

    # storico
    hist_str = ", ".join(str(v) for v in history)
    html = re.sub(r'const history = \[[\s\S]*?\];', f'const history = [\n  {hist_str}\n];', html)

    # currentTemp
    html = re.sub(r'let currentTemp = [\d.]+;', f'let currentTemp = {temp};', html)

    # SVG display
    html = re.sub(r'id="svg-temp-disp">[^<]*°C', f'id="svg-temp-disp">{temp}°C', html)

    # header giorno/ora
    html = re.sub(r'LIVE · GIORNO \d+ · ORE \d+:\d+', f'LIVE · GIORNO {giorno} · {ora}', html)

    # formula box prima riga
    html = re.sub(r'OUTPUT: [\d.]+\s*°C\s*[↑↓→][^\n<]*', f'OUTPUT: {temp} °C {arrow} {evento}', html)

    # tickers
    new_tickers = scoring.get("tickers", [])
    if len(new_tickers) >= 3:
        tj = "const TICKERS = [\n"
        for t in new_tickers:
            tj += f"  {json.dumps(t, ensure_ascii=False)},\n"
        tj += "];"
        html = re.sub(r'const TICKERS = \[[\s\S]*?\];', tj, html)

    return html

def load_history():
    try:
        m = re.search(r'const history = \[([\s\S]*?)\];', load_html())
        if m:
            return [float(v.strip()) for v in m.group(1).split(",") if v.strip()]
    except: pass
    return []

def git_push():
    print(f"[{ts()}] Git push...")
    try:
        ora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git","-C",REPO_DIR,"add",HTML_FILE],  check=True, capture_output=True)
        subprocess.run(["git","-C",REPO_DIR,"commit","-m",f"auto: {ora}"], check=True, capture_output=True)
        subprocess.run(["git","-C",REPO_DIR,"push"],           check=True, capture_output=True)
        print(f"[{ts()}] OK  GitHub Pages aggiornato")
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode() if e.stderr else str(e)
        if "nothing to commit" in msg:
            print(f"[{ts()}] --  nessuna modifica")
        else:
            print(f"[{ts()}] ERR git push: {msg[:150]}")
    except FileNotFoundError:
        print(f"[{ts()}] ERR Git non installato — vai su git-scm.com")

def ts():   return datetime.datetime.now().strftime("%H:%M:%S")
def nxt(m): return (datetime.datetime.now()+datetime.timedelta(minutes=m)).strftime("%H:%M")

def main():
    if not GEMINI_API_KEY:
        print("\n" + "="*58)
        print("  CHIAVE GEMINI MANCANTE")
        print()
        print("  1. Vai su: https://aistudio.google.com/apikey")
        print("  2. Crea una chiave (gratis, nessuna carta)")
        print("  3. Esporta la variabile:")
        print()
        print("     Mac/Linux:  export GEMINI_API_KEY='AIza...'")
        print("     Windows:    $env:GEMINI_API_KEY='AIza...'")
        print()
        print("  4. Riesegui: python3 scorer_gemini.py")
        print("="*58 + "\n")
        return

    print("="*58)
    print("  GEOPOLITICAL SCORER  ·  Gemini Flash + Auto Git Push")
    print(f"  Repo:     {REPO_DIR}")
    print(f"  Display:  {HTML_FILE}")
    print(f"  Ciclo:    ogni {INTERVAL_MINUTES} min  |  Costo: 0 euro/mese")
    print("="*58)

    history = load_history()
    print(f"[{ts()}] Storico: {len(history)} punti caricati dall'HTML")

    scoring = fetch_temperature()
    if scoring:
        history.append(round(float(scoring["temperatura"]),1))
        if len(history) > MAX_HISTORY: history = history[-MAX_HISTORY:]
        html = update_html(load_html(), scoring, history)
        save_html(html)
        git_push()

    while True:
        print(f"[{ts()}] Pausa {INTERVAL_MINUTES} min — prossimo: {nxt(INTERVAL_MINUTES)}")
        time.sleep(INTERVAL_MINUTES * 60)
        scoring = fetch_temperature()
        if scoring:
            history.append(round(float(scoring["temperatura"]),1))
            if len(history) > MAX_HISTORY: history = history[-MAX_HISTORY:]
            html = update_html(load_html(), scoring, history)
            save_html(html)
            git_push()

if __name__ == "__main__":
    main()
