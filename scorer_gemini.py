import json,re,datetime,os,subprocess,urllib.request

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
        "model":"claude-haiku-4-5-20251001",
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
    with urllib.request.urlopen(req,timeout=40) as r:
        raw=json.loads(r.read().decode("utf-8"))
    text=raw["content"][0]["text"].strip().strip("`").lstrip("json").strip()
    s=text.find("{"); e=text.rfind("}")+1
    if s>=0 and e>s: text=text[s:e]
    data=json.loads(text)
    print(f"[{ts()}] OK  {data['temperatura']}C  {data['trend']}  {data['titolo'][:50]}")
    return data

def load_html():
    with open(os.path.join(REPO_DIR,HTML_FILE),"r",encoding="utf-8") as f: return f.read()

def save_html(c):
    with open(os.path.join(REPO_DIR,HTML_FILE),"w",encoding="utf-8") as f: f.write(c)

def load_history(html):
    try:
        m=re.search(r'const history = \[([^\]]*)\]',html)
        if m: return [float(v.strip()) for v in m.group(1).split(",") if v.strip()]
    except: pass
    return []

def update_html(html,scoring,history):
    temp=round(float(scoring["temperatura"]),1)
    giorno=max(1,(datetime.datetime.now()-datetime.datetime(2026,2,28)).days+1)
    ora=datetime.datetime.now().strftime("ORE %H:%M")
    arrow={"salita":"↑","discesa":"↓","stabile":"→"}.get(scoring.get("trend","stabile"),"→")
    evento=scoring.get("evento_chiave","")[:65]
    hist_str=", ".join(str(v) for v in history)
    html=re.sub(r'const history = \[[^\]]*\]',f'const history = [{hist_str}]',html)
    html=re.sub(r'let currentTemp = [\d.]+;',f'let currentTemp = {temp};',html)
    html=re.sub(r'id="svg-temp-disp">[^<]*°C',f'id="svg-temp-disp">{temp}°C',html)
    html=re.sub(r'LIVE · GIORNO \d+ · ORE \d+:\d+',f'LIVE · GIORNO {giorno} · {ora}',html)
    html=re.sub(r'OUTPUT: [\d.]+\s*°C\s*[↑↓→][^\n<]*',f'OUTPUT: {temp} °C {arrow} {evento}',html)
    new_tickers=scoring.get("tickers",[])
    if len(new_tickers)>=3:
        tj="const TICKERS = [\n"+"".join(f"  {json.dumps(t,ensure_ascii=False)},\n" for t in new_tickers)+"];"
        html=re.sub(r'const TICKERS = \[[\s\S]*?\];',tj,html)
    return html

def git_push():
    print(f"[{ts()}] Git push...")
    ora=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git","-C",REPO_DIR,"add",HTML_FILE],check=True)
    subprocess.run(["git","-C",REPO_DIR,"commit","-m",f"auto: {ora}"],check=True)
    subprocess.run(["git","-C",REPO_DIR,"push"],check=True)
    print(f"[{ts()}] OK  GitHub Pages aggiornato")

if __name__=="__main__":
    if not ANTHROPIC_API_KEY:
        print("ERRORE: ANTHROPIC_API_KEY non impostata")
        exit(1)
    print(f"[{ts()}] Avvio one-shot scorer")
    html=load_html()
    history=load_history(html)
    print(f"[{ts()}] Storico: {len(history)} punti")
    scoring=fetch()
    history.append(round(float(scoring["temperatura"]),1))
    if len(history)>MAX_HISTORY: history=history[-MAX_HISTORY:]
    save_html(update_html(html,scoring,history))
    git_push()
    print(f"[{ts()}] Done.")
