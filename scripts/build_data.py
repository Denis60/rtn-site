#!/usr/bin/env python3
"""Construit data.json pour le site RTN à partir de l'export Airtable servi par n8n.

Usage :
  python scripts/build_data.py --url "$RTN_DATA_URL"      # GitHub Action
  python scripts/build_data.py --file raw.json            # test local

Le workflow n8n « RTN - Données site web » renvoie les enregistrements bruts
(champs indexés par ID Airtable) des tables Soirées, Interventions,
personne - entreprise et Lieux. Ce script les met en forme pour le site,
télécharge les photos de synthèse (les liens Airtable expirent) et écrit data.json.
"""
import argparse, hashlib, json, os, re, sys, urllib.request
from datetime import datetime, date
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Champs Airtable (IDs stables, insensibles aux renommages) ---
S_DATE, S_LIEU, S_VILLE, S_SPONSOR = "fldAOkD91jmf1p5ep", "flddbdO1yxEPYIxw7", "fldpHadRnk1MaFJxa", "fldgLuNZzMZdUdCNj"
S_INTERV, S_ODJ, S_NB, S_PHOTO, S_RECAP = "fldCls5weFSPTJaQK", "flddmrPnxHXrSCEsU", "fldzEqW76gkJE5y5m", "fldd9cC91SF4JMLNS", "fldxWCgOOwO33uTn5"
I_QUI, I_SUJET, I_STATUT, I_SUPPORT = "fld1urtUxZPZqARNV", "fld7J5SXze89jxhKb", "fldeMfVBwduQFYHLB", "fldpTwVk7nEq8SPoK"
P_NAME, P_PERSONNE, P_ENTREPRISE, P_LOGO = "fldZU6B96H3TbtgzV", "fldbhpCjzkU7NkCcQ", "fldnaOTbVA3u3n945", "fldIo0DCT3ACGrSAK"
P_SITE = "fldH6bZqvD6RxQ1RH"
L_NOM, L_ADRESSE = "fldKAtGXesG09Ysv7", "fldrgfZUrOy3RzuxN"

INSCRIPTION = "https://docs.google.com/forms/d/e/1FAIpQLSdoK-db3MX8OSTDcKy6phXWfcXxs46Ox_xmTnMmXpevObmzaQ/viewform"
LINKEDIN = "https://www.linkedin.com/company/rdv-en-terrain-num%C3%A9rique-charente/"
GENERIC_RECAP = "linkedin.com/company/rdv-en-terrain"  # lien par défaut = pas un vrai récap


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def entreprise(raw):
    """Nom d'entreprise publiable : 1re ligne, sans notes internes."""
    if not raw:
        return ""
    line = clean(raw.splitlines()[0]).rstrip(" :")
    low = line.lower()
    if not line or "@" in line or "?" in line or "http" in low or len(line) > 40:
        return ""
    if any(w in low for w in ("avant ", "à partir", "suggestion", "indep")):
        return ""
    return line


def adresse(raw):
    lines = [clean(l) for l in (raw or "").splitlines()]
    lines = [l for l in lines if l and not re.match(r"^CS\s*\d+", l, re.I)]
    return ", ".join(lines)


def shrink(path):
    """Réduit logos (max 480x240) et photos (max 1600 px) si Pillow est présent."""
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        im = Image.open(path)
        box = (480, 240) if "/logos/" in path else (1600, 1600)
        if im.width <= box[0] and im.height <= box[1] and os.path.getsize(path) < 300_000:
            return
        im.thumbnail(box)
        if path.endswith(".jpg"):
            im.convert("RGB").save(path, "JPEG", quality=80, optimize=True, progressive=True)
        else:
            im.save(path, "PNG", optimize=True)
    except Exception as e:
        print(f"  ! réduction impossible {path} ({e})", file=sys.stderr)


def download(url, dest):
    if os.path.exists(dest):
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rtn-site-build"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if not (data[:8].startswith(b"\x89PNG") or data[:3] == b"\xff\xd8\xff" or data[:4] in (b"GIF8", b"RIFF") or b"<svg" in data[:300]):
            print(f"  ! pas une image (lien non public ?) : {url[:70]}", file=sys.stderr)
            return False
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        shrink(dest)
        return True
    except Exception as e:  # réseau indisponible : on garde ce qu'on a
        print(f"  ! téléchargement impossible {url[:60]}… ({e})", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--file")
    ap.add_argument("--out", default=os.path.join(ROOT, "data.json"))
    a = ap.parse_args()
    if a.url:
        with urllib.request.urlopen(a.url, timeout=120) as r:
            raw = json.load(r)
    else:
        raw = json.load(open(a.file, encoding="utf-8"))

    today = datetime.now(ZoneInfo("Europe/Paris")).date()
    pers = {p["id"]: p["fields"] for p in raw["personnes"]}
    lieux = {l["id"]: l["fields"] for l in raw["lieux"]}
    itv = {i["id"]: i["fields"] for i in raw["interventions"]}

    def person(pid):
        f = pers.get(pid, {})
        return {"nom": clean(f.get(P_PERSONNE) or f.get(P_NAME)), "entreprise": entreprise(f.get(P_ENTREPRISE))}

    def sponsor(pid):
        f = pers.get(pid, {})
        name = entreprise(f.get(P_ENTREPRISE)) or clean(f.get(P_NAME))
        logo = f.get(P_LOGO) or ""
        if logo:
            # nom de fichier lié à l'URL : changer « Logo URL » dans Airtable rafraîchit le logo
            local = f"assets/logos/{pid}-{hashlib.sha1(logo.encode()).hexdigest()[:8]}.png"
            legacy = f"assets/logos/{pid}.png"
            if download(logo, os.path.join(ROOT, local)):
                logo = local
            elif os.path.exists(os.path.join(ROOT, legacy)):
                logo = legacy
        site = (f.get(P_SITE) or "").strip()
        if site and not site.startswith("http"):
            site = "https://" + site
        return {"nom": name, "logo": logo, "site": site}

    def talks(ids, upcoming):
        out = []
        for iid in ids:
            f = itv.get(iid)
            if not f:
                continue
            statut = (f.get(I_STATUT) or "")
            if isinstance(statut, dict):
                statut = statut.get("name", "")
            if statut.lower().startswith("annul"):
                continue
            out.append({
                "sujet": clean(f.get(I_SUJET)) or "Sujet à venir",
                "intervenants": [person(p) for p in f.get(I_QUI, [])],
                "support": f.get(I_SUPPORT) or "",
                "aConfirmer": bool(upcoming and statut.lower().startswith("à confirmer")),
            })
        return out

    soirees = sorted([s for s in raw["soirees"] if s["fields"].get(S_DATE)], key=lambda s: s["fields"][S_DATE])
    events = []
    for n, s in enumerate(soirees, 1):
        f = s["fields"]
        d = date.fromisoformat(f[S_DATE])
        upcoming = d >= today
        lieu_id = (f.get(S_LIEU) or [None])[0]
        lf = lieux.get(lieu_id, {})
        ville = f.get(S_VILLE) or ""
        if isinstance(ville, dict):
            ville = ville.get("name", "")
        photo = ""
        att = (f.get(S_PHOTO) or [None])[0]
        if att and att.get("url"):
            local = f"assets/photos/soiree-{f[S_DATE]}.jpg"
            if download(att["url"], os.path.join(ROOT, local)) or os.path.exists(os.path.join(ROOT, local)):
                photo = local
        elif os.path.exists(os.path.join(ROOT, f"assets/photos/soiree-{f[S_DATE]}.jpg")):
            photo = f"assets/photos/soiree-{f[S_DATE]}.jpg"
        recap = f.get(S_RECAP) or ""
        if GENERIC_RECAP in recap and "/posts" in recap:
            recap = ""
        events.append({
            "edition": n,
            "date": f[S_DATE],
            "aVenir": upcoming,
            "programmePret": bool(f.get(S_ODJ)),
            "lieu": clean(lf.get(L_NOM)),
            "adresse": adresse(lf.get(L_ADRESSE)),
            "ville": ville,
            "sponsors": [sponsor(p) for p in f.get(S_SPONSOR, [])],
            "interventions": talks(f.get(S_INTERV, []), upcoming),
            "participants": f.get(S_NB),
            "photo": photo,
            "recap": recap,
        })

    past = [e for e in events if not e["aVenir"]]
    future = [e for e in events if e["aVenir"]]
    speakers = {i["nom"].lower() for e in past for t in e["interventions"] for i in t["intervenants"] if i["nom"]}
    data = {
        "generatedAt": datetime.now(ZoneInfo("Europe/Paris")).isoformat(timespec="minutes"),
        "inscription": INSCRIPTION,
        "linkedin": LINKEDIN,
        "stats": {
            "soirees": len(past),
            "presentations": sum(len(e["interventions"]) for e in past),
            "intervenants": len(speakers),
            "lieux": len({e["lieu"] for e in past if e["lieu"]}),
            "depuis": past[0]["date"] if past else None,
        },
        "prochaine": future[0] if future else None,
        "suivantes": [{"date": e["date"], "lieu": e["lieu"] if e["programmePret"] else ""} for e in future[1:]],
        "historique": list(reversed(past)),
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from render import render_all
    render_all(data, ROOT)
    print(f"data.json : {data['stats']} ; prochaine = {data['prochaine']['date'] if data['prochaine'] else '—'}")


if __name__ == "__main__":
    main()
