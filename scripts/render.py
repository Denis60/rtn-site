"""Génère les pages HTML statiques du site RTN à partir des données mises en forme.

- index.html                 (depuis templates/index.html)
- soirees/AAAA-MM-JJ.html    (une page par soirée passée + la prochaine)
- sitemap.xml, robots.txt

Le contenu est écrit en dur dans le HTML (lisible par les moteurs de recherche
sans JavaScript) ; app.js n'ajoute que l'interactivité (recherche, agenda, compte à rebours).
"""
import json, os, re
from datetime import date, datetime
from html import escape as esc
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Paris")
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MOIS_C = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

FAQ = [
    ("Les soirées sont-elles payantes ?",
     "Non, elles sont gratuites. L'inscription est demandée pour prévoir la salle et le cocktail, offert par l'hôte ou le sponsor de la soirée."),
    ("Faut-il être un expert du numérique pour venir ?",
     "Pas du tout. Les intervenants parlent concret et chaque présentation se termine par les questions de la salle. Dirigeants, salariés, indépendants, étudiants : tout le monde est bienvenu."),
    ("Comment s'inscrire ?",
     "Via le formulaire d'inscription en haut de cette page. Vous recevez aussitôt une invitation à ajouter à votre agenda, puis les invitations des soirées suivantes par e-mail."),
    ("Où ont lieu les soirées ?",
     "Le lieu change à chaque fois : tiers-lieux, écoles, restaurants, entreprises… La plupart du temps à Angoulême et dans son agglomération, parfois ailleurs en Charente. L'adresse est indiquée dans l'invitation et sur ce site."),
    ("Comment proposer une intervention ?",
     "Écrivez-nous en décrivant votre retour d'expérience en quelques lignes. Le format : 15 à 20 minutes, du concret, puis les questions de la salle."),
    ("Qui organise et qui finance ?",
     "Un petit groupe de bénévoles, sans association ni cotisation. Les soirées vivent grâce aux hôtes qui prêtent leur salle et aux sponsors qui offrent le cocktail."),
]


def d(iso):
    return date.fromisoformat(iso)


def long_date(iso):
    x = d(iso)
    return f"{JOURS[x.weekday()].capitalize()} {x.day} {MOIS[x.month - 1]} {x.year}"


def short_date(iso):
    x = d(iso)
    return f"{x.day} {MOIS_C[x.month - 1]} {x.year}"


def iso_dt(iso, hh, mm):
    return datetime(*map(int, iso.split("-")), hh, mm, tzinfo=TZ).isoformat()


def lieu_nom(s):
    s = s or ""
    if s and s == s.lower():
        return " ".join(w[:1].upper() + w[1:] for w in s.split())
    return s


def people(lst, sep=", "):
    return sep.join(p["nom"] + (f" ({p['entreprise']})" if p["entreprise"] else "") for p in lst)


def logo_html(s, prefix=""):
    tag = "a" if s.get("site") else "span"
    attrs = f' href="{esc(s["site"])}" target="_blank" rel="noopener"' if s.get("site") else ""
    if s.get("logo"):
        src = s["logo"] if s["logo"].startswith("http") else prefix + s["logo"]
        return (f'<{tag}{attrs} class="logo-chip" title="{esc(s["nom"])}"><img src="{esc(src)}" alt="{esc(s["nom"])}" loading="lazy" '
                f'onerror="this.parentNode.classList.add(\'txt\');this.parentNode.textContent=this.alt"></{tag}>')
    return f'<{tag}{attrs} class="logo-chip txt">{esc(s["nom"])}</{tag}>'


def slug(e):
    return f"soirees/{e['date']}.html"


def event_jsonld(e, base, inscription, upcoming):
    loc = {"@type": "Place", "name": lieu_nom(e["lieu"]) or "Lieu communiqué aux inscrits"}
    loc["address"] = {"@type": "PostalAddress", "streetAddress": e["adresse"] or e["ville"] or "Charente",
                      "addressLocality": e["ville"] or "Angoulême", "addressRegion": "Charente", "addressCountry": "FR"}
    j = {
        "@context": "https://schema.org", "@type": "Event",
        "name": f"RDV en terrain numérique — {long_date(e['date'])}",
        "description": "Rencontre des professionnels du numérique de Charente : 3 retours d'expérience de 15-20 minutes, questions-réponses, cocktail."
                       + (" Au programme : " + " ; ".join(t["sujet"] for t in e["interventions"]) + "." if e["interventions"] else ""),
        "startDate": iso_dt(e["date"], 18, 30), "endDate": iso_dt(e["date"], 21, 0),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "isAccessibleForFree": True,
        "location": loc,
        "image": [f"{base}/{e['photo']}" if e.get("photo") else f"{base}/assets/ambiance/salle-1.jpg"],
        "url": f"{base}/{slug(e)}",
        "organizer": {"@type": "Organization", "name": "RDV en terrain numérique", "url": f"{base}/"},
    }
    perf = [{"@type": "Person", "name": p["nom"]} for t in e["interventions"] for p in t["intervenants"] if p["nom"]]
    if perf:
        j["performer"] = perf
    if e["sponsors"]:
        j["sponsor"] = [{"@type": "Organization", "name": s["nom"], **({"url": s["site"]} if s.get("site") else {})} for s in e["sponsors"]]
    if upcoming:
        j["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
                       "url": inscription, "validFrom": iso_dt(e["date"], 0, 0)[:10]}
    return j


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


# ---------- blocs de la page d'accueil ----------

def block_prochain(n, data):
    if not n:
        return ('      <p class="kicker"><span class="kicker-dot"></span> Prochain rendez-vous</p>\n'
                '      <h1><span class="h1-tag">Les rencontres des pros du numérique en Charente</span>'
                '<span class="hero-date">Date à venir</span></h1>\n'
                '      <p class="hero-meta">Le prochain RDV est en préparation. Inscrivez-vous pour être prévenu.</p>')
    x = d(n["date"])
    lieu = lieu_nom(n["lieu"])
    where = esc(lieu) + (f" ({esc(n['ville'])})" if n["ville"] and n["ville"] not in lieu else "")
    talks = n["interventions"] if n["programmePret"] else []
    if talks:
        cards = "".join(
            f'<article class="talk"><span class="talk-n">0{i + 1} / 0{len(talks)}</span>'
            + ('<span class="badge">À confirmer</span>' if t["aConfirmer"] else "")
            + f'<h3>{esc(t["sujet"])}</h3><div class="who">'
            + "".join(f'<div><b>{esc(p["nom"])}</b>' + (f' <span>· {esc(p["entreprise"])}</span>' if p["entreprise"] else "") + "</div>" for p in t["intervenants"])
            + "</div></article>" for i, t in enumerate(talks))
    else:
        cards = '<div class="programme-tbd">Le programme est en cours de finalisation : 3 sujets, 3 intervenants, annoncés très bientôt.</div>'
    spons = ""
    if n["sponsors"]:
        spons = '<span class="lbl">Soirée offerte par</span>' + "".join(logo_html(s) for s in n["sponsors"])
    place = ""
    if n["adresse"]:
        maps = "https://www.google.com/maps/search/?api=1&query=" + re.sub(r"\s+", "+", n["adresse"])
        place = f'📍 {esc(n["adresse"])} — <a href="{esc(maps)}" target="_blank" rel="noopener">itinéraire</a>'
    ics = esc(json.dumps({"date": n["date"], "lieu": lieu, "adresse": n["adresse"],
                          "programme": [t["sujet"] + " (" + ", ".join(p["nom"] for p in t["intervenants"]) + ")" for t in talks]},
                         ensure_ascii=False))
    return f'''      <p class="kicker"><span class="kicker-dot"></span> <span id="kicker" data-date="{n["date"]}">Prochain rendez-vous · édition n°{n["edition"]}</span></p>
      <h1><span class="h1-tag">Les rencontres des pros du numérique en Charente</span><span class="hero-date">{esc(JOURS[x.weekday()].capitalize())} {x.day} {MOIS[x.month - 1]} <span class="yr">{x.year}</span></span></h1>
      <p class="hero-meta"><b>18h30 – 21h00</b> · {where}<br>Trois retours d'expérience de 15 à 20 minutes, des questions sans filtre, un verre pour continuer. Gratuit, sur inscription.</p>
      <div class="hero-actions">
        <a class="btn btn-yellow" href="{esc(data["inscription"])}" target="_blank" rel="noopener">Je m'inscris — c'est gratuit</a>
        <button class="btn btn-ghost" id="btn-ics" type="button" data-ics="{ics}">Ajouter à mon agenda</button>
      </div>
      <div class="programme">{cards}</div>
      <div class="hero-foot">
        <div class="sponsor-slot">{spons}</div>
        <p class="hero-place">{place}</p>
      </div>'''


def block_stats(s):
    depuis = d(s["depuis"]) if s.get("depuis") else None
    dep = f"{MOIS[depuis.month - 1]} {depuis.year}" if depuis else ""
    return f'''  <section class="stats" aria-label="En chiffres">
    <div class="stat"><span class="stat-n">{s["soirees"]}</span><span class="stat-l">soirées depuis {dep}</span></div>
    <div class="stat"><span class="stat-n">{s["presentations"]}</span><span class="stat-l">retours d'expérience partagés</span></div>
    <div class="stat"><span class="stat-n">{s["intervenants"]}</span><span class="stat-l">intervenants</span></div>
    <div class="stat"><span class="stat-n">30–50</span><span class="stat-l">participants par soirée</span></div>
  </section>'''


def ev_card(e, prefix=""):
    x = d(e["date"])
    talks = "".join(
        f'<li><div class="s">{esc(t["sujet"])}</div><div class="w">{esc(people(t["intervenants"]))}</div>'
        + (f'<a class="sup" href="{esc(t["support"])}" target="_blank" rel="noopener">Voir le support ↗</a>' if t["support"] else "") + "</li>"
        for t in e["interventions"])
    side = ""
    if e["photo"]:
        side += f'<img class="photo" src="{prefix}{esc(e["photo"])}" width="1200" height="674" alt="Synthèse de la soirée RDV en terrain numérique du {short_date(e["date"])}" loading="lazy">'
    if e["sponsors"]:
        side += '<div class="spons">Avec ' + "".join(logo_html(s, prefix) for s in e["sponsors"]) + "</div>"
    if e["recap"]:
        side += f'<a class="recap" href="{esc(e["recap"])}" target="_blank" rel="noopener">Le récap de la soirée ↗</a>'
    hay = " ".join([e["lieu"], e["ville"], short_date(e["date"])] + [s["nom"] for s in e["sponsors"]]
                   + [t["sujet"] + " " + people(t["intervenants"]) for t in e["interventions"]]).lower()
    lieu = esc(lieu_nom(e["lieu"])) + (f" · {esc(e['ville'])}" if e["ville"] and e["ville"] != "Angoulême" else "")
    return (f'<article class="ev" data-search="{esc(hay)}"><div class="ev-date"><span class="d">{x.day}</span>'
            f'<span class="m">{MOIS[x.month - 1]} {x.year}</span><span class="ed">Édition n°{e["edition"]}</span>'
            f'<span class="where">{lieu}</span><a class="ev-link" href="{slug(e)}">Voir la soirée →</a></div>'
            f'<ul class="ev-talks">{talks}</ul><div class="ev-side">{side}</div></article>')


def block_suivantes(lst):
    if not lst:
        return ""
    return ('    <div class="upcoming"><span class="lbl">À noter dans l\'agenda :</span>'
            + "".join(f'<span class="chip">{short_date(s["date"])}</span>' for s in lst) + "</div>")


def block_faq():
    return "\n".join(f'      <details class="qa"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in FAQ)


def block_wall(data):
    seen, out = set(), []
    evs = ([data["prochaine"]] if data["prochaine"] else []) + data["historique"]
    for e in evs:
        for s in e["sponsors"]:
            k = s["nom"].lower()
            if k not in seen:
                seen.add(k)
                out.append(logo_html(s))
    return "\n".join("        " + o for o in out)


# ---------- page d'une soirée ----------

def soiree_page(e, data, base, prev_e, next_e, tpl):
    x = d(e["date"])
    lieu = lieu_nom(e["lieu"])
    subjects = [t["sujet"] for t in e["interventions"]]
    upcoming = e["aVenir"]
    title = f"RDV en terrain numérique du {x.day} {MOIS[x.month - 1]} {x.year}" + (f" — {lieu}" if lieu else "") + (f", {e['ville']}" if e["ville"] and e["ville"] not in lieu else "")
    desc = (("Prochaine soirée" if upcoming else "Soirée") + f" des pros du numérique en Charente, {short_date(e['date'])}"
            + (f" à {lieu}" if lieu else "") + ". " + ("Au programme : " + " ; ".join(subjects) if subjects else "Programme à venir."))
    desc = desc[:300]
    talks = "".join(
        f'<li><h3>{esc(t["sujet"])}</h3><p class="w">{esc(people(t["intervenants"]))}</p>'
        + (f'<a class="sup" href="{esc(t["support"])}" target="_blank" rel="noopener">Voir le support ↗</a>' if t["support"] else "") + "</li>"
        for t in e["interventions"]) or "<li><h3>Programme à venir</h3></li>"
    photo = (f'<img class="sp-photo" src="../{esc(e["photo"])}" width="1200" height="674" alt="Synthèse de la soirée du {short_date(e["date"])}">' if e["photo"] else "")
    spons = ('<div class="sp-spons"><p class="eyebrow">Merci à</p>' + "".join(logo_html(s, "../") for s in e["sponsors"]) + "</div>") if e["sponsors"] else ""
    recap = f'<p><a class="recap" href="{esc(e["recap"])}" target="_blank" rel="noopener">Lire le récap de la soirée ↗</a></p>' if e["recap"] else ""
    addr = f'<p class="sp-addr">📍 {esc(e["adresse"])}</p>' if e["adresse"] else ""
    nav = '<nav class="sp-nav">' + (f'<a href="{prev_e["date"]}.html">← {short_date(prev_e["date"])}</a>' if prev_e else "<span></span>") \
          + (f'<a href="{next_e["date"]}.html">{short_date(next_e["date"])} →</a>' if next_e else "<span></span>") + "</nav>"
    cta = (f'<a class="btn btn-yellow" href="{esc(data["inscription"])}" target="_blank" rel="noopener">Je m\'inscris — c\'est gratuit</a>' if upcoming
           else '<a class="btn btn-yellow" href="../#prochain">Voir le prochain rendez-vous</a>')
    body = f'''  <header class="sp-head">
    <p class="eyebrow">Édition n°{e["edition"]}{" · à venir" if upcoming else ""}</p>
    <h1>{esc(long_date(e["date"]))}</h1>
    <p class="sp-meta"><b>18h30 – 21h00</b>{" · " + esc(lieu) if lieu else ""}{" (" + esc(e["ville"]) + ")" if e["ville"] and e["ville"] not in lieu else ""}</p>
    {addr}
  </header>
  <div class="sp-grid">
    <section><h2>Au programme</h2><ul class="sp-talks">{talks}</ul>{recap}</section>
    <aside>{photo}{spons}</aside>
  </div>
  <div class="sp-cta">{cta}</div>
  {nav}'''
    jl = ld(event_jsonld(e, base, data["inscription"], upcoming)) + ld({
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{base}/"},
            {"@type": "ListItem", "position": 2, "name": "Les soirées", "item": f"{base}/#historique"},
            {"@type": "ListItem", "position": 3, "name": short_date(e["date"]), "item": f"{base}/{slug(e)}"}]})
    og = f"{base}/{e['photo']}" if e["photo"] else f"{base}/assets/ambiance/salle-1.jpg"
    out = tpl
    for k, v in {"TITLE": esc(title), "DESC": esc(desc), "URL": f"{base}/{slug(e)}", "OGIMAGE": og, "JSONLD": jl,
                 "INSCRIPTION": esc(data["inscription"]), "CRUMB": esc(short_date(e["date"])), "BODY": body}.items():
        out = out.replace(f"<!--@{k}-->", v)
    return out


# ---------- point d'entrée ----------

def bust(html, root, prefix=""):
    """Ajoute ?v=<empreinte> aux liens style.css / app.js pour forcer le rechargement après chaque modification."""
    import hashlib
    for f in ("style.css", "app.js"):
        h = hashlib.sha1(open(os.path.join(root, f), "rb").read()).hexdigest()[:8]
        html = re.sub(r'(["\'])' + re.escape(prefix + f) + r'(\?v=[0-9a-f]+)?(["\'])', r"\g<1>" + prefix + f + "?v=" + h + r"\g<3>", html)
    return html


def render_all(data, root):
    cfg = json.load(open(os.path.join(root, "site.json"), encoding="utf-8"))
    base = cfg["baseUrl"].rstrip("/")
    tpl_index = open(os.path.join(root, "templates/index.html"), encoding="utf-8").read()
    tpl_soiree = open(os.path.join(root, "templates/soiree.html"), encoding="utf-8").read()

    n = data["prochaine"]
    jl = [{
        "@context": "https://schema.org", "@type": "Organization", "name": "RDV en terrain numérique",
        "alternateName": "Rendez-vous en terrain numérique", "url": f"{base}/",
        "description": "Rencontres des professionnels du numérique de Charente : retours d'expérience, échanges et cocktail.",
        "areaServed": "Charente", "sameAs": [data["linkedin"]]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}]
    if n:
        jl.append(event_jsonld(n, base, data["inscription"], True))
    maj = datetime.fromisoformat(data["generatedAt"])
    blocks = {
        "BASE": base, "JSONLD": "\n".join(ld(j) for j in jl), "INSCRIPTION": esc(data["inscription"]),
        "LINKEDIN": esc(data["linkedin"]), "PROCHAIN": block_prochain(n, data), "STATS": block_stats(data["stats"]),
        "SUIVANTES": block_suivantes(data["suivantes"]),
        "HISTORIQUE": "\n".join("      " + ev_card(e) for e in data["historique"]),
        "FAQ": block_faq(), "WALL": block_wall(data),
        "MAJ": f"{maj.day} {MOIS[maj.month - 1]} {maj.year} à {maj.strftime('%H:%M')}",
    }
    out = tpl_index
    for k, v in blocks.items():
        out = out.replace(f"<!--@{k}-->", v)
    open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(bust(out, root))
    ml = os.path.join(root, "mentions-legales.html")
    if os.path.exists(ml):
        txt = bust(open(ml, encoding="utf-8").read(), root)
        open(ml, "w", encoding="utf-8").write(txt)

    # pages des soirées (chronologique pour la navigation précédent/suivant)
    chrono = list(reversed(data["historique"])) + ([n] if n else [])
    os.makedirs(os.path.join(root, "soirees"), exist_ok=True)
    keep = set()
    for i, e in enumerate(chrono):
        page = soiree_page(e, data, base, chrono[i - 1] if i > 0 else None, chrono[i + 1] if i + 1 < len(chrono) else None, tpl_soiree)
        open(os.path.join(root, slug(e)), "w", encoding="utf-8").write(bust(page, root, "../"))
        keep.add(os.path.basename(slug(e)))
    for f in os.listdir(os.path.join(root, "soirees")):  # soirée supprimée ou déplacée
        if f.endswith(".html") and f not in keep:
            os.remove(os.path.join(root, "soirees", f))

    today = datetime.now(TZ).date().isoformat()
    urls = [(f"{base}/", today, "daily", "1.0"), (f"{base}/mentions-legales.html", today, "yearly", "0.1")]
    urls += [(f"{base}/{slug(e)}", today if e["aVenir"] else e["date"], "weekly" if e["aVenir"] else "yearly", "0.8" if e["aVenir"] else "0.6") for e in chrono]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{u}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>" for u, m, c, p in urls]
    sm.append("</urlset>")
    open(os.path.join(root, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm) + "\n")
    open(os.path.join(root, "robots.txt"), "w", encoding="utf-8").write(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n")
    print(f"pages : index + {len(chrono)} soirées + sitemap ({len(urls)} URL)")
