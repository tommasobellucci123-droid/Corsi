#!/usr/bin/env python3
"""Raccoglie i corsi da Talentform e Challenge Network e scrive corsi.json.
Uso:  pip install requests beautifulsoup4   ->   python scrape.py
Rispetta robots.txt: i siti che vietano i bot (Umana Forma, Attal) vengono saltati.
"""
import json, re, time, hashlib, datetime as dt
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

UA = "CorsiFinderBot/1.0 (uso personale; contatto: tommasobellucci123@gmail.com)"   # <-- metti la tua email
PAUSA = 1.5  # secondi tra una richiesta e l'altra
MESI = {"gen":1,"feb":2,"mar":3,"apr":4,"mag":5,"giu":6,"lug":7,"ago":8,"set":9,"ott":10,"nov":11,"dic":12}
DATE = re.compile(r"(\d{1,2})\s+([A-Za-zàù]+)\s+(\d{4})\s*[–-]\s*(\d{1,2})\s+([A-Za-zàù]+)\s+(\d{4})")
_robots = {}

def consentito(url):
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in _robots:
        rp = RobotFileParser(host + "/robots.txt")
        try: rp.read()
        except Exception: rp = None
        _robots[host] = rp
    rp = _robots[host]
    return True if rp is None else rp.can_fetch(UA, url)

def scarica(url):
    if not consentito(url):
        print("  SALTATO (robots.txt lo vieta):", url); return None
    time.sleep(PAUSA)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def iso(g, m, a):
    return "%s-%02d-%02d" % (a, MESI[m.lower()[:3]], int(g))

def card_di(h3):
    """Risale dal titolo fino al contenitore che contiene solo quel corso."""
    n = h3
    while n.parent and len(n.parent.select("h3")) == 1:
        n = n.parent
    return n

def pulisci(t):
    t = re.sub(r"\s*\(corso.*$", "", t, flags=re.I)
    return re.sub(r",?\s*edizione del.*$", "", t, flags=re.I).strip()

def talentform():
    ente, base = "Talentform", "https://www.talentform.it/calendario-corsi-gratuiti/"
    print(ente)
    home = scarica(base)
    if not home: return []
    pagine = {base} | {urljoin(base, a["href"]) for a in home.select('a[href*="/calendario-corsi-gratuiti/corsi-gratuiti-"]')}
    out = []
    for url in sorted(pagine):
        soup = home if url == base else scarica(url)
        if not soup: continue
        for h3 in soup.select("h3"):
            a = h3.find("a", href=True)
            if not a or "/formazione-professionale/" not in a["href"]: continue
            card = card_di(h3)
            righe = [x for x in card.get_text("\n", strip=True).split("\n") if x]
            m = DATE.search(card.get_text(" ", strip=True))
            if not m: continue
            g1, m1, a1, g2, m2, a2 = m.groups()
            i = next((k for k, x in enumerate(righe) if DATE.search(x) or re.match(r"\d{1,2} \w{3} \d{4}", x)), None)
            luogo = righe[i + 2] if i is not None and len(righe) > i + 2 else ""
            area = righe[1] if len(righe) > 1 else ""
            out.append(dict(ente=ente, titolo=pulisci(h3.get_text(" ", strip=True)), area=area,
                            modalita=luogo or "Non indicata", inizio=iso(g1, m1, a1), fine=iso(g2, m2, a2),
                            link=urljoin(url, a["href"])))
    return out

def challenge():
    ente, url = "Challenge Network", "https://www.challengenetwork.it/proclass/formazione-professionale/"
    print(ente)
    soup = scarica(url)
    if not soup: return []
    out = []
    for h3 in soup.select("h3"):
        card = card_di(h3)
        m = DATE.search(card.get_text(" ", strip=True))
        a = card.find("a", href=True, string=re.compile("Scopri", re.I))
        if not (m and a): continue          # salta "Corsi avviati" e aree "in arrivo"
        h2 = h3.find_previous("h2")
        g1, m1, a1, g2, m2, a2 = m.groups()
        out.append(dict(ente=ente, titolo=h3.get_text(" ", strip=True),
                        area=h2.get_text(" ", strip=True) if h2 else "",
                        modalita="Aula virtuale" if "VIRTUALE" in card.get_text() else "In presenza",
                        inizio=iso(g1, m1, a1), fine=iso(g2, m2, a2), link=urljoin(url, a["href"])))
    return out

# Umana Forma e Attal Group: vietano i bot nel robots.txt. Aggiungi qui le funzioni solo
# se ottieni il permesso dagli enti (o un loro feed/export).
FONTI = [talentform, challenge]

if __name__ == "__main__":
    oggi = dt.date.today().isoformat()
    corsi = {}
    for f in FONTI:
        try:
            for c in f():
                if c["fine"] >= oggi:
                    c["id"] = hashlib.md5(c["link"].encode()).hexdigest()[:10]
                    corsi[c["id"]] = c
        except Exception as e:
            print("  ERRORE in", f.__name__, "->", e)
    lista = sorted(corsi.values(), key=lambda c: (c["inizio"], c["ente"], c["titolo"]))
    json.dump({"aggiornato": dt.date.today().strftime("%d/%m/%Y"), "corsi": lista},
              open("corsi.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Salvati", len(lista), "corsi in corsi.json")
