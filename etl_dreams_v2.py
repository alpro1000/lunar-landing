#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETL v2: собирает современный корпус "сонника" из разрешённых источников
и синтезирует современную трактовку (оценочно), избегая классических сонников.

Файлы:
  - data/dreams_curated.json      (для фронта)
  - data/dreams_curated.jsonl     (для бэкапов/аналитики)

Запуск локально:
  python etl_dreams_v2.py --config sources.yml

Deps (минимум):
  pip install requests beautifulsoup4 html2text tqdm rapidfuzz pyyaml feedparser tldextract
Опционально:
  pip install praw             # reddit
  pip install datasets         # Hugging Face Datasets
  pip install openai           # если хотите LLM-парафраз

ENV:
  OPENAI_API_KEY=...           # если включите LLM-парафраз
  OWNER_APPROVED=1             # чтобы включить скрейп вашего домена (magickum_owner)
  REDDIT_CLIENT_ID=... REDDIT_SECRET=... REDDIT_USER_AGENT="appname/1.0"  # если включен reddit
"""
import os, re, sys, json, time, argparse, logging, csv
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests, yaml, feedparser, tldextract
from bs4 import BeautifulSoup
from html2text import html2text
from tqdm import tqdm
from rapidfuzz import process, fuzz

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
UA = {"User-Agent": "LunarDream-ETL/2.0 (contact: owner-approved)"}
RATE = 1.0
TIMEOUT = 25

# ---------------- helpers ----------------
def norm_text(html):
    txt = html2text(html or "", bodywidth=0)
    txt = re.sub(r'\n{3,}', '\n\n', txt).strip()
    return txt

def shorten(s, n=220):
    s = re.sub(r'\s+', ' ', s or '').strip()
    return s if len(s)<=n else s[:n-1]+"…"

def safe_get(url, params=None):
    time.sleep(RATE)
    r = requests.get(url, headers=UA, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r

def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False)+"\n")

def write_json(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(',',':'))

def pick_contexts(text, k=3):
    body = (text or '').lower()
    words = re.findall(r'[a-zа-яёіїґéèçàùöüßñ\-]{5,}', body, flags=re.IGNORECASE)
    freq = {}
    for w in words: freq[w] = freq.get(w,0)+1
    return [w for w,_ in sorted(freq.items(), key=lambda x: -x[1])[:k]]

# ---------------- collectors ----------------
def collect_dreambank(limit=50):
    base = "https://dreambank.net"
    rows = []
    try:
        idx = safe_get(base).text
        soup = BeautifulSoup(idx, "html.parser")
        links = []
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if not href: continue
            if not href.startswith("http"): href = urljoin(base, href)
            if urlparse(href).netloc.endswith("dreambank.net"):
                links.append(href)
        links = list(dict.fromkeys(links))[:int(limit)]
        for href in tqdm(links, desc="DreamBank", unit="pg"):
            try:
                html = safe_get(href).text
                s2 = BeautifulSoup(html,"html.parser")
                title = (s2.find("title") or s2.find("h1") or {}).get_text(strip=True) or "DreamBank page"
                main = s2.find("body") or s2
                text = norm_text(main.prettify())
                if len(text) < 400: continue
                rows.append({"source":"dreambank","id":href,"url":href,"title":title,"text":text,"date":TODAY,"tags":["dreambank"],"license":"public-website"})
            except Exception as e:
                logging.debug(f"DreamBank skip {href}: {e}")
    except Exception as e:
        logging.warning(f"DreamBank error: {e}")
    return rows

def collect_sddb_zenodo(record_id="11662064"):
    rows=[]
    try:
        j = safe_get(f"https://zenodo.org/api/records/{record_id}").json()
        for f in j.get("files", []):
            dl = f.get("links",{}).get("self"); name = (f.get("key") or "").lower()
            if not dl or not name.endswith((".json",".jsonl",".csv",".tsv",".txt")): continue
            txt = safe_get(dl).text
            if name.endswith((".json",".jsonl")):
                lines = txt.splitlines()
                # JSONL?
                parsed = False
                for line in lines:
                    try:
                        obj = json.loads(line)
                        t = obj.get("text") or obj.get("report") or ""
                        if len(t)>120:
                            rows.append({"source":"sddb","id":obj.get("id") or hash(t)%10**9,"url":"https://sleepanddreamdatabase.org/","title":shorten(obj.get("title") or "SDDb report",120),"text":t,"date":TODAY,"tags":["sddb"],"license":"as-provided"})
                        parsed=True
                    except Exception:
                        pass
                if not parsed:
                    try:
                        data = json.loads(txt)
                        seq = data if isinstance(data,list) else [data]
                        for obj in seq:
                            t = obj.get("text") or obj.get("report") or ""
                            if len(t)>120:
                                rows.append({"source":"sddb","id":obj.get("id") or hash(t)%10**9,"url":"https://sleepanddreamdatabase.org/","title":shorten(obj.get("title") or "SDDb report",120),"text":t,"date":TODAY,"tags":["sddb"],"license":"as-provided"})
                    except Exception:
                        pass
            else:
                # CSV/TSV
                lines = txt.splitlines()
                if not lines: return rows
                delim = ',' if ',' in lines[0] and lines[0].count(',')>=lines[0].count('\t') else '\t'
                reader = csv.reader(lines, delimiter=delim)
                hdr = [h.strip().lower() for h in next(reader, [])]
                idx = next((i for i,h in enumerate(hdr) if h in ("text","report","content","dream")), None)
                if idx is None: return rows
                for cols in reader:
                    if idx < len(cols):
                        t = cols[idx].strip()
                        if len(t)>120:
                            rows.append({"source":"sddb","id":hash(t)%10**9,"url":"https://sleepanddreamdatabase.org/","title":"SDDb report","text":t,"date":TODAY,"tags":["sddb"],"license":"as-provided"})
    except Exception as e:
        logging.warning(f"SDDb Zenodo error: {e}")
    return rows

def collect_dryad(doi="10.5061/dryad.qbzkh18fr"):
    rows=[]
    try:
        page = safe_get(f"https://datadryad.org/dataset/doi:{doi}").text
        soup = BeautifulSoup(page,"html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if not href: continue
            if not (href.endswith((".csv",".tsv",".json")) or "download" in href): 
                continue
            try:
                txt = safe_get(href).text
                if href.endswith((".csv",".tsv")):
                    lines = txt.splitlines()
                    if not lines: continue
                    delim = ',' if ',' in lines[0] and lines[0].count(',')>=lines[0].count('\t') else '\t'
                    reader = csv.reader(lines, delimiter=delim)
                    hdr = [h.strip().lower() for h in next(reader, [])]
                    idx = next((i for i,h in enumerate(hdr) if h in ("text","report","dream","content")), None)
                    if idx is None: continue
                    for cols in reader:
                        if idx < len(cols):
                            t = cols[idx].strip()
                            if len(t)>120:
                                rows.append({"source":"dryad","id":hash(t)%10**9,"url":href,"title":"Dryad dream report","text":t,"date":TODAY,"tags":["dryad"],"license":"as-provided"})
                elif href.endswith(".json"):
                    data = json.loads(txt)
                    seq = data if isinstance(data,list) else [data]
                    for obj in seq:
                        t = (obj.get("text") or obj.get("report") or "")
                        if len(t)>120:
                            rows.append({"source":"dryad","id":obj.get("id") or hash(t)%10**9,"url":href,"title":"Dryad dream report","text":t,"date":TODAY,"tags":["dryad"],"license":"as-provided"})
            except Exception:
                continue
    except Exception as e:
        logging.warning(f"Dryad error: {e}")
    return rows

def collect_donders(fig_id="21388722"):
    rows=[]
    try:
        meta = safe_get(f"https://api.figshare.com/v2/articles/{fig_id}").json()
        for f in meta.get("files",[]):
            link = f.get("download_url"); name=(f.get("name") or "").lower()
            if not link or not any(name.endswith(x) for x in (".csv",".tsv",".json",".txt")):
                continue
            txt = safe_get(link).text
            lines = txt.splitlines()
            if not lines:
                continue
            delim = ',' if ',' in lines[0] and lines[0].count(',')>=lines[0].count('\t') else '\t'
            try:
                reader = csv.reader(lines, delimiter=delim)
                hdr = [h.strip().lower() for h in next(reader, [])]
                idx = next((i for i,h in enumerate(hdr) if h in ("report","dream","text","transcript","content")), None)
                if idx is None:
                    # treat as plain text
                    txt2 = "\n".join(lines)
                    if len(txt2)>200:
                        rows.append({"source":"donders","id":hash(txt2)%10**9,"url":link,"title":"Donders dream-related","text":txt2,"date":TODAY,"tags":["donders"],"license":"as-provided"})
                else:
                    for cols in reader:
                        if idx < len(cols):
                            t = cols[idx].strip()
                            if len(t)>120:
                                rows.append({"source":"donders","id":hash(t)%10**9,"url":link,"title":"Donders dream-related","text":t,"date":TODAY,"tags":["donders"],"license":"as-provided"})
            except Exception:
                # plain text fallback
                if len(txt)>200:
                    rows.append({"source":"donders","id":hash(txt)%10**9,"url":link,"title":"Donders dream-related","text":txt,"date":TODAY,"tags":["donders"],"license":"as-provided"})
    except Exception as e:
        logging.warning(f"Donders error: {e}")
    return rows

def collect_rss(url, lic="unknown"):
    rows=[]
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:200]:
            text = (e.get('summary') or e.get('description') or e.get('content',[{'value':''}])[0].get('value') or '')
            text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
            if len(text)<160: continue
            rows.append({"source":"rss","id":e.get('id') or e.get('link'),"url":e.get('link'),"title":shorten(e.get('title','RSS post'),120),"text":text,"date":TODAY,"tags":["rss"],"license":lic})
    except Exception as e:
        logging.warning(f"RSS error {url}: {e}")
    return rows

def collect_google_sheet(csv_url, lic="by-owner"):
    rows=[]
    try:
        txt = safe_get(csv_url).text
        reader = csv.DictReader(txt.splitlines())
        # ожидаем колонки 'symbol','text' или 'report'
        for rec in reader:
            t = rec.get('text') or rec.get('report') or ''
            sym = rec.get('symbol') or ''
            if len(t)<60 and not sym: continue
            rows.append({"source":"gsheet","id":hash((sym+t))%10**9,"url":csv_url,"title":"Sheet row","text":t,"date":TODAY,"tags":["gsheet"],"license":lic})
    except Exception as e:
        logging.warning(f"GoogleSheet error: {e}")
    return rows

def collect_reddit(subs, limit=200, mode="hot"):
    rows=[]
    try:
        import praw
        cid=os.getenv("REDDIT_CLIENT_ID"); sec=os.getenv("REDDIT_SECRET"); ua=os.getenv("REDDIT_USER_AGENT","LunarDream/1.0")
        if not cid or not sec:
            logging.warning("Reddit disabled: no credentials"); return rows
        r = praw.Reddit(client_id=cid, client_secret=sec, user_agent=ua, read_only=True)
        for sub in subs:
            subreddit = r.subreddit(sub)
            stream = getattr(subreddit, mode)(limit=limit) if mode in ("hot","new","top") else subreddit.hot(limit=limit)
            for s in stream:
                text = (s.selftext or "").strip()
                if len(text)<160: continue
                # берём небольшой фрагмент (fair use/ограничение)
                sample = text[:1200]
                rows.append({"source":"reddit","id":s.id,"url":"https://www.reddit.com"+s.permalink,"title":shorten(s.title,120),"text":sample,"date":TODAY,"tags":["reddit",sub],"license":"reddit-terms"})
    except Exception as e:
        logging.warning(f"Reddit error: {e}")
    return rows

def collect_hf_datasets(names):
    rows=[]
    try:
        from datasets import load_dataset
        for name in names:
            try:
                ds = load_dataset(name)
                # пытаемся вытащить колонку 'text' или смежные
                for split in ds.keys():
                    for item in ds[split]:
                        t = item.get("text") or item.get("report") or item.get("content") or ""
                        if len(t)>120:
                            rows.append({"source":"hf", "id":hash(t)%10**9, "url":f"https://huggingface.co/datasets/{name}", "title":"HF dataset row","text":t,"date":TODAY,"tags":["hf",name],"license":"dataset-terms"})
            except Exception:
                logging.warning(f"HF dataset skip {name}")
    except Exception as e:
        logging.warning(f"HF not available: {e}")
    return rows

def collect_owner_site(start_url, domain):
    if os.getenv("OWNER_APPROVED","0") != "1":
        logging.warning("Owner-site disabled: set OWNER_APPROVED=1 to enable"); return []
    rows=[]
    seen=set()
    try:
        q=[start_url]
        base_host = tldextract.extract(domain).registered_domain
        for href in tqdm(q, desc=f"Owner:{domain}", unit="pg"):
            if href in seen: continue
            seen.add(href)
            try:
                html = safe_get(href).text
                s=BeautifulSoup(html,"html.parser")
                title=(s.find("h1") or s.find("title") or {}).get_text(strip=True) or domain
                # универсальные контейнеры контента
                main = s.find("article") or s.find("main") or s.find("div", class_=re.compile(r"(entry|post|content|article)"))
                main = main or s
                text = norm_text(main.prettify())
                if len(text)>300:
                    rows.append({"source":"owner", "id":href, "url":href, "title":shorten(title,120), "text":text, "date":TODAY, "tags":["owner",domain], "license":"by-owner"})
                # расширяем очередь по внутренним ссылкам
                for a in s.select("a[href]"):
                    u=a.get("href") or ""
                    if u.startswith("#"): continue
                    if not u.startswith("http"): u=urljoin(href,u)
                    host = tldextract.extract(urlparse(u).netloc).registered_domain
                    if base_host and host==base_host and u not in seen and "/magikum-sonnik" in u:
                        q.append(u)
            except Exception as e:
                logging.debug(f"owner skip {href}: {e}")
    except Exception as e:
        logging.warning(f"Owner site error: {e}")
    return rows

# ---------------- symbol synthesis ----------------
BASE_SYMBOLS = [
  "вода","огонь","падение","полёт","погоня","дверь","окно","лестница","машина","поезд","самолёт",
  "ребёнок","родители","дом","подвал","зеркало","собака","кошка","змея","рыба","птица","кровь","болезнь","кольцо","деньги"
]

def extract_symbol_candidates(text):
    best = process.extractOne(text, BASE_SYMBOLS, scorer=fuzz.partial_ratio)
    if not best: return []
    s, score = best[0], best[1]
    return [s] if score>=70 else []

def group_by_symbol(raw_rows):
    buckets = {}
    for r in raw_rows:
        for s in extract_symbol_candidates(r.get("text","")):
            buckets.setdefault(s, []).append(r)
    return buckets

def llm_paraphrase(symbol, examples):
    api_key = os.getenv("OPENAI_API_KEY")
    preview = " ".join(shorten(e.get("text",""),140) for e in examples[:3])
    if not api_key:
        ctx = ', '.join(pick_contexts(" ".join(e.get("text","") for e in examples),3))
        return (f"«{symbol}» (оценочно): чаще встречается вместе с темами {ctx}. "
                "Смотрите на эмоции при пробуждении, текущий контекст и повторяемость. "
                "Практика: дневник снов, короткая запись сразу после пробуждения, намерение перед сном."), 0.8
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
              {"role":"system","content":"Ты редактор современного сонника. Пиши кратко, мягко, без фатализма. Помечай 'оценочно'."},
              {"role":"user","content":f"Составь современную трактовку символа «{symbol}» на основе выдержек:\n{preview}\n2 абзаца + 2 практических совета. Без предсказаний."}
            ],
            temperature=0.4
        )
        return r.choices[0].message.content.strip(), 0.9
    except Exception as e:
        logging.warning(f"LLM error: {e}")
        return f"«{symbol}»: ориентир, а не прогноз. Фокус на эмоциях и контексте.", 0.6

# ---------------- main ----------------
def main(cfg_path, out_jsonl="data/dreams_curated.jsonl", out_json="data/dreams_curated.json"):
    with open(cfg_path,"r",encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    scfg = (cfg.get("sources") or {})

    raw=[]

    # DreamBank
    db = scfg.get("dreambank",{})
    if db.get("enabled",False):
        raw+=collect_dreambank(limit=db.get("limit",50))

    # SDDb via Zenodo
    sddb = scfg.get("sddb_zenodo",{})
    if sddb.get("enabled",False):
        raw+=collect_sddb_zenodo(record_id=str(sddb.get("record_id","11662064")))

    # Dryad list
    for item in scfg.get("dryad",[]) or []:
        doi=item.get("doi"); 
        if doi: raw+=collect_dryad(doi=doi)

    # Donders list
    for item in scfg.get("donders",[]) or []:
        fig=item.get("fig_id")
        if fig: raw+=collect_donders(fig_id=str(fig))

    # RSS feeds
    for item in scfg.get("rss",[]) or []:
        url=item.get("url"); lic=item.get("license","unknown")
        if url: raw+=collect_rss(url, lic)

    # Google Sheets
    for item in scfg.get("google_sheets",[]) or []:
        csv_url=item.get("csv_url"); lic=item.get("license","by-owner")
        if csv_url: raw+=collect_google_sheet(csv_url, lic)

    # Reddit (optional)
    rdcfg=scfg.get("reddit",{})
    if rdcfg.get("enabled",False):
        raw+=collect_reddit(rdcfg.get("subreddits",["Dreams"]), limit=int(rdcfg.get("limit",200)), mode=rdcfg.get("mode","hot"))

    # Hugging Face datasets (optional)
    hfcfg=scfg.get("hf_datasets",{})
    if hfcfg.get("enabled",False):
        raw+=collect_hf_datasets(hfcfg.get("names",[]))

    # Owner site (magickum) — only with OWNER_APPROVED=1
    ow=scfg.get("magickum_owner",{})
    if ow.get("enabled",False):
        raw+=collect_owner_site(ow.get("start_url"), ow.get("domain"))

    if not raw:
        logging.error("Нет сырых данных. Проверьте конфиг/интернет/разрешения.")
        sys.exit(2)

    # deduplicate by text hash
    dedup={}
    for r in raw:
        key = hash((r.get("source"), shorten(r.get("text",""),160)))
        if key not in dedup:
            dedup[key]=r
    raw = list(dedup.values())
    logging.info(f"RAW rows: {len(raw)}")

    # group by symbols and synthesize
    buckets = group_by_symbol(raw)
    curated=[]
    for symbol, reports in buckets.items():
        interp, conf = llm_paraphrase(symbol, reports)
        curated.append({
          "symbol": symbol,
          "contexts": pick_contexts(" ".join(r.get("text","") for r in reports), 3),
          "modern_interpretation": interp,
          "tone": "neutral",
          "lunar_links": [],
          "sources": [{
             "url": r.get("url"), "title": r.get("title"), "date": TODAY, "license": r.get("license","unknown")
          } for r in reports[:6]],
          "confidence": round(conf,2),
          "updated_at": datetime.now(timezone.utc).isoformat(),
          "notes": "Синтез на основе современных корпусов (оценочно). Классические сонники не использовались."
        })

    curated.sort(key=lambda x: x["symbol"])
    write_jsonl(out_jsonl, curated)
    write_json(out_json, curated)
    logging.info(f"✔ Символов: {len(curated)} → {out_jsonl} / {out_json}")

if __name__=="__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="sources.yml", help="путь к конфигу источников")
    ap.add_argument("--outl", default="data/dreams_curated.jsonl")
    ap.add_argument("--out",  default="data/dreams_curated.json")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main(args.config, out_jsonl=args.outl, out_json=args.out)
