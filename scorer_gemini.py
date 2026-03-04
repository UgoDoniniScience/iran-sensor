#!/usr/bin/env python3
"""
GEOPOLITICAL TEMPERATURE SCORER — versione GRATUITA
Usa Google Gemini 1.5 Flash (gratis, 1500 req/giorno)
Aggiornamento ogni 120 minuti — costo: €0
"""

import json, time, datetime, os, urllib.request, urllib.error

# ─── CONFIGURAZIONE ────────────────────────────────────────────
INTERVAL_MINUTES = 120
OUTPUT_FILE      = "temp.json"
MAX_HISTORY      = 48

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key={key}"
)

# ─── PROMPT ────────────────────────────────────────────────────
SYSTEM_INSTRUCTION = """Sei un analista geopolitico specializzato nel conflitto Iran 2026.
Analizza le ultime notizie e assegna una TEMPERATURA DI CONFLITTO su scala APERTA (non limitata a 100).

SCALA:
0-20   Tensione diplomatica, sanzioni
21-50  Attacchi proxy, escalation limitata
51-80  Guerra aperta, raid aerei, scambio missilistico
81-100 Guerra totale attiva (stato attuale circa 87)
101-150 Escalation nucleare o NATO diretto
150+   Conflitto globale

Rispondi SOLO con JSON valido senza testo aggiuntivo e senza backtick:
{"temperatura":<float>,"trend":"salita|stabile|discesa","titolo":"<max 80 car>","sommario":"<max 200 car in italiano>","attori_caldi":["att1","att2","att3"],"evento_chiave":"<evento principale>","rischio_nucleare":<0-10>,"stretto_hormuz":"aperto|parziale|chiuso"}"""

def user_prompt():
    return (
        "Cerca e analizza le ultimissime notizie sulla guerra Iran-USA-Israele. "
        "Considera: attacchi in corso, vittime, escalation, dichiarazioni ufficiali, "
        "movimenti militari, Stretto di Hormuz, coinvolgimento di nuovi attori. "
        "Data: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M") + ". "
        "Rispondi SOLO con il JSON."
    )

# ─── GEMINI CALL ───────────────────────────────────────────────
def fetch_temperature():
    print(f"[{now()}] Chiamata Gemini API con Google Search grounding...")

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"parts": [{"text": user_prompt()}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800
        }
    }

    url  = GEMINI_URL.format(key=GEMINI_API_KEY)
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Pulizia: rimuovi eventuali backtick residui
        text = text.strip("`").lstrip("json").strip()
        # Estrai solo il blocco JSON se c'è testo prima/dopo
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        data = json.loads(text)
        t = data.get("temperatura", "?")
        print(f"[{now()}] Temperatura: {t}C  "
              f"trend={data.get('trend','?')}  "
              f"hormuz={data.get('stretto_hormuz','?')}")
        return data

    except urllib.error.HTTPError as e:
        print(f"[{now()}] HTTP {e.code}: {e.read().decode('utf-8','ignore')[:300]}")
    except (KeyError, json.JSONDecodeError) as e:
        print(f"[{now()}] Parsing fallito: {e}")
    except Exception as e:
        print(f"[{now()}] Errore: {e}")
    return None

# ─── FILE I/O ──────────────────────────────────────────────────
def load_existing():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "temperatura": 87.4, "trend": "salita",
        "titolo": "In attesa del primo aggiornamento...",
        "sommario": "Avvia scorer_gemini.py per iniziare.",
        "attori_caldi": ["USA", "IRAN", "ISRAELE"],
        "evento_chiave": "Sistema avviato",
        "rischio_nucleare": 4, "stretto_hormuz": "chiuso",
        "ultimo_aggiornamento": now_iso(),
        "prossimo_aggiornamento": next_upd_iso(INTERVAL_MINUTES),
        "storico": [], "giorno_conflitto": 5
    }

def save_output(existing, history, scoring):
    start  = datetime.datetime(2026, 2, 28)
    giorno = max(1, (datetime.datetime.now() - start).days + 1)

    history.append({"ts": now_iso(), "t": scoring.get("temperatura", 87.4)})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    out = {
        "temperatura":            scoring.get("temperatura", existing.get("temperatura")),
        "trend":                  scoring.get("trend", "stabile"),
        "titolo":                 scoring.get("titolo", ""),
        "sommario":               scoring.get("sommario", ""),
        "attori_caldi":           scoring.get("attori_caldi", []),
        "evento_chiave":          scoring.get("evento_chiave", ""),
        "rischio_nucleare":       scoring.get("rischio_nucleare", 0),
        "stretto_hormuz":         scoring.get("stretto_hormuz", "parziale"),
        "ultimo_aggiornamento":   now_iso(),
        "prossimo_aggiornamento": next_upd_iso(INTERVAL_MINUTES),
        "storico":                history,
        "giorno_conflitto":       giorno
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[{now()}] Salvato {OUTPUT_FILE}  T={out['temperatura']}C")
    return out, history

# ─── HELPERS ───────────────────────────────────────────────────
def now():          return datetime.datetime.now().strftime("%H:%M:%S")
def now_iso():      return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
def next_upd_iso(m):
    return (datetime.datetime.now() + datetime.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S")
def fmt_t(s):
    try:    return datetime.datetime.fromisoformat(s).strftime("%H:%M")
    except: return "--:--"

# ─── MAIN ──────────────────────────────────────────────────────
def main():
    if not GEMINI_API_KEY:
        print("\n" + "="*60)
        print("  CHIAVE GEMINI NON TROVATA!")
        print("  Mac/Linux:  export GEMINI_API_KEY='AIza...'")
        print("  Windows:    $env:GEMINI_API_KEY='AIza...'")
        print("  Vedi SETUP_GRATUITO.md per ottenere la chiave gratis")
        print("="*60 + "\n")
        return

    print("="*60)
    print("  GEOPOLITICAL SCORER — versione GRATUITA")
    print(f"  Motore: Google Gemini 1.5 Flash  |  Costo: 0 euro")
    print(f"  Intervallo: {INTERVAL_MINUTES} min  |  Output: {OUTPUT_FILE}")
    print("="*60)

    existing = load_existing()
    history  = existing.get("storico", [])

    # Prima lettura immediata all'avvio
    scoring = fetch_temperature()
    if scoring:
        existing, history = save_output(existing, history, scoring)
    else:
        print(f"[{now()}] Prima lettura fallita, riprovo tra {INTERVAL_MINUTES} min")
        existing["prossimo_aggiornamento"] = next_upd_iso(INTERVAL_MINUTES)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    # Loop principale ogni 120 minuti
    while True:
        prossimo = fmt_t(next_upd_iso(INTERVAL_MINUTES))
        print(f"[{now()}] Pausa {INTERVAL_MINUTES} min — prossimo aggiornamento ore {prossimo}")
        time.sleep(INTERVAL_MINUTES * 60)

        scoring = fetch_temperature()
        if scoring:
            existing, history = save_output(existing, history, scoring)
        else:
            print(f"[{now()}] Lettura fallita, riprovo al prossimo ciclo")

if __name__ == "__main__":
    main()
