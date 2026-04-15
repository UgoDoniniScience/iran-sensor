import json,time,re,datetime,os,subprocess,urllib.request

INTERVAL_MINUTES=120
HTML_FILE="sensor-live.html"
MAX_HISTORY=48
REPO_DIR=os.path.dirname(os.path.abspath(__file__))
ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY","")
API_URL="https://api.anthropic.com/v1/messages"

PROMPT="""Sei un analista geopolitico. Analizza la guerra Iran-USA-Israele iniziata il 28 febbraio 2026.
Rispondi SOLO con JSON valido senza backtick e senza testo aggiuntivo:
{"temperatura":<float>,"trend":"salita|stabile|discesa","titolo":"<max80car>","sommario":"<max200car in italiano>","attori_caldi":["a1","a2","a3"],"evento_chiave":"<evento principale>","rischio_nucleare":<0-10>,"stretto_hormuz":"aperto|parziale|chiuso","tickers":["<notizia1 max120car>","<notizia2>","<notizia3>","<notizia4>","<notizia5>"]}

SCALA TEMPERATURA:
0-20 diplomazia | 21-50 proxy | 51-80 guerra aperta | 81-100 guerra totale | 101+ nucleare/NATO"""

def ts(): return datetime.datetime.now().strftime("%H:%M:%S")
def nxt(m): return (datetime.datetime.now()+datetime.timedelta(minutes=m)).strftime("%H:%M")

def fetch():
    print(f"[{ts()}] Claude API call...")
    giorno=max(1,(datetime.datetime.now()-datetime.datetime(2026,2,28)).days+1)
    q=(f"Guerra Iran-USA-Israele, giorno {giorno} del conflitto. "
       f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}. "
       f"Aggiorna la temperatura del conflitto considerando la progressione logica degli eventi: "
       f"raid IDF su Iran e Libano, risposta missilistica iraniana, Stretto di Hormuz, "
       f"fronti attivi (Libano/Hezbollah, curdi, Golfo), diplomazia in corso. "
       f"Rispondi SOLO con il JSON.")
    payload={
        "model":"claude-haiku-4-5",
        "max_tokens":1000,
        "messages":[{"role":"user","content":PROMPT+"\n\n"+q}]
    }
    body=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(
        API_URL, data=body,
        headers={
            "Content-Type":"application/json",
            "x-api-key":ANTHROPIC_API_KEY,
            "anthropic-version":"2023-06-01"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req,timeout=40) as r:
            raw=json.loads(r.read().decode("utf-8"))
        text=raw["content"][0]["text"].strip().strip("`").lstrip("json").strip()
        s=text.find("{"); e=text.rfind("}")+1
        if s>=0 and e>s: text=text[s:e]
        data=json.loads(text)
        print(f"[{ts()}] OK  {data['temperatura']}C  {data['trend']}  {data['titolo'][:50]}")
        return data
    except Exception as ex:
        print(f"[{ts()}] ERR {ex.__class__.__name__}: {ex.read().decode() if hasattr(ex, chr(114)+chr(101)+chr(97)+chr(100)) else ex}")
        return None

def load_html():
    with open(os.path.join(REPO_DIR,HTML_FILE),"r",encoding="utf-8") as f: return f.read()

def save_html(c):
    with open(os.path.join(REPO_DIR,HTML_FILE),"w",encoding="utf-8") as f: f.write(c)

def load_history():
    try:
        m=re.search(r'const history = \[([\s\S]*?)\];',load_html())
        if m: return [float(v.strip()) for v in m.group(1).split(",") if v.strip()]
    except: pass
    return []

def update_html(html,scoring,history):
    temp=round(float(scoring["temperatura"]),1)
    giorno=max(1,(datetime.datetime.now()-datetime.datetime(2026,2,28)).days+1)
    ora=datetime.datetime.now().strftime("ORE %H:%M")
    arrow={"salita":"â†'","discesa":"â†"","stabile":"â†'"}.get(scoring.get("trend","stabile"),"â†'")
    evento=scoring.get("evento_chiave","")[:65]
    hist_str=", ".join(str(v) for v in history)
    html=re.sub(r'const history = \[[\s\S]*?\];',f'const history = [\n  {hist_str}\n];',html)
    html=re.sub(r'let currentTemp = [\d.]+;',f'let currentTemp = {temp};',html)
    html=re.sub(r'id="svg-temp-disp">[^<]*Â°C',f'id="svg-temp-disp">{temp}Â°C',html)
    html=re.sub(r'LIVE Â· GIORNO \d+ Â· ORE \d+:\d+',f'LIVE Â· GIORNO {giorno} Â· {ora}',html)
    html=re.sub(r'OUTPUT: [\d.]+\s*Â°C\s*[â†'â†"â†'][^\n<]*',f'OUTPUT: {temp} Â°C {arrow} {evento}',html)
    new_tickers=scoring.get("tickers",[])
    if len(new_tickers)>=3:
        tj="const TICKERS = [\n"+"".join(f"  {json.dumps(t,ensure_ascii=False)},\n" for t in new_tickers)+"];"
        html=re.sub(r'const TICKERS = \[[\s\S]*?\];',tj,html)
    return html

def git_push():
    print(f"[{ts()}] Git push...")
    try:
        ora=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git","-C",REPO_DIR,"add",HTML_FILE],check=True,capture_output=True)
        subprocess.run(["git","-C",REPO_DIR,"commit","-m",f"auto: {ora}"],check=True,capture_output=True)
        subprocess.run(["git","-C",REPO_DIR,"push"],check=True,capture_output=True)
        print(f"[{ts()}] OK  GitHub Pages aggiornato")
    except subprocess.CalledProcessError as e:
        msg=e.stderr.decode() if e.stderr else str(e)
        if "nothing to commit" in msg: print(f"[{ts()}] --  nessuna modifica")
        else: print(f"[{ts()}] ERR git: {msg[:150]}")
    except FileNotFoundError:
        print(f"[{ts()}] ERR Git non installato")

def main():
    if not ANTHROPIC_API_KEY:
        print("\n"+"="*55)
        print("  CHIAVE ANTHROPIC MANCANTE")
        print()
        print("  Windows PowerShell:")
        print("  $env:ANTHROPIC_API_KEY='sk-ant-...'")
        print("  python scorer_gemini.py")
        print("="*55+"\n")
        return
    print("="*55)
    print("  GEOPOLITICAL SCORER  Â·  Claude Haiku + Git Push")
    print(f"  Repo:    {REPO_DIR}")
    print(f"  Ciclo:   ogni {INTERVAL_MINUTES} min")
    print("="*55)
    history=load_history()
    print(f"[{ts()}] Storico: {len(history)} punti")
    scoring=fetch()
    if scoring:
        history.append(round(float(scoring["temperatura"]),1))
        if len(history)>MAX_HISTORY: history=history[-MAX_HISTORY:]
        save_html(update_html(load_html(),scoring,history))
        git_push()
    while True:
        print(f"[{ts()}] Pausa {INTERVAL_MINUTES} min â€" prossimo: {nxt(INTERVAL_MINUTES)}")
        time.sleep(INTERVAL_MINUTES*60)
        scoring=fetch()
        if scoring:
            history.append(round(float(scoring["temperatura"]),1))
            if len(history)>MAX_HISTORY: history=history[-MAX_HISTORY:]
            save_html(update_html(load_html(),scoring,history))
            git_push()

if __name__=="__main__": main()

