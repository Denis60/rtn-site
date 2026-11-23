/* RDV en terrain numérique — rendu du site à partir de data.json
   data.json est régénéré chaque jour depuis Airtable (GitHub Action + n8n). */
(function () {
  "use strict";
  var MOIS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"];
  var MOIS_C = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  var JOURS = ["dimanche","lundi","mardi","mercredi","jeudi","vendredi","samedi"];
  var $ = function (id) { return document.getElementById(id); };

  function d(iso) { var p = iso.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function lieuNom(s) { return s && s === s.toLowerCase() ? s.replace(/\b\p{L}/gu, function (c) { return c.toUpperCase(); }) : (s || ""); }
  function longDate(iso) { var x = d(iso); return cap(JOURS[x.getDay()]) + " " + x.getDate() + " " + MOIS[x.getMonth()] + " " + x.getFullYear(); }
  function shortDate(iso) { var x = d(iso); return x.getDate() + " " + MOIS_C[x.getMonth()] + " " + x.getFullYear(); }
  function daysTo(iso) { var t = new Date(); t.setHours(0, 0, 0, 0); return Math.round((d(iso) - t) / 864e5); }
  function who(list) {
    return list.map(function (p) { return "<div><b>" + esc(p.nom) + "</b>" + (p.entreprise ? " <span>· " + esc(p.entreprise) + "</span>" : "") + "</div>"; }).join("");
  }
  function logo(s, cls) {
    if (s.logo) return '<span class="logo-chip ' + (cls || "") + '" title="' + esc(s.nom) + '"><img src="' + esc(s.logo) + '" alt="' + esc(s.nom) + '" loading="lazy" onerror="this.parentNode.classList.add(\'txt\');this.parentNode.textContent=this.alt"></span>';
    return '<span class="logo-chip txt ' + (cls || "") + '">' + esc(s.nom) + "</span>";
  }
  function maps(addr) { return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(addr); }

  function renderNext(data) {
    var n = data.prochaine;
    if (!n) {
      $("kicker").textContent = "Prochain rendez-vous";
      $("hero-date").textContent = "Date à venir";
      $("hero-meta").textContent = "Le prochain RDV est en préparation. Inscrivez-vous pour être prévenu.";
      $("btn-ics").hidden = true;
      return;
    }
    var j = daysTo(n.date);
    $("kicker").textContent = "Prochain rendez-vous · " + (j === 0 ? "c'est ce soir" : j === 1 ? "demain" : "dans " + j + " jours") + " · édition n°" + n.edition;
    var x = d(n.date);
    $("hero-date").innerHTML = esc(cap(JOURS[x.getDay()])) + " " + x.getDate() + " " + esc(MOIS[x.getMonth()]) + ' <span class="yr">' + x.getFullYear() + "</span>";
    var lieu = lieuNom(n.lieu);
    $("hero-meta").innerHTML = "<b>18h30 – 21h00</b>" + (lieu ? " · " + esc(lieu) : "") + (n.ville && lieu.indexOf(n.ville) < 0 ? " (" + esc(n.ville) + ")" : "") + "<br>3 retours d'expérience, des questions, un cocktail. Gratuit, sur inscription.";

    var talks = n.programmePret ? n.interventions : [];
    if (talks.length) {
      $("programme").innerHTML = talks.map(function (t, i) {
        return '<article class="talk"><span class="talk-n">0' + (i + 1) + " / 0" + talks.length + "</span>" +
          (t.aConfirmer ? '<span class="badge">À confirmer</span>' : "") +
          "<h3>" + esc(t.sujet) + '</h3><div class="who">' + who(t.intervenants) + "</div></article>";
      }).join("");
    } else {
      $("programme").innerHTML = '<div class="programme-tbd">Le programme est en cours de finalisation : 3 sujets, 3 intervenants, annoncés très bientôt.</div>';
    }
    if (n.sponsors && n.sponsors.length) {
      $("hero-sponsors").innerHTML = '<span class="lbl">Soirée offerte par</span>' + n.sponsors.map(function (s) { return logo(s); }).join("");
    }
    if (n.adresse) $("hero-place").innerHTML = "📍 " + esc(n.adresse) + ' — <a href="' + maps(n.adresse) + '" target="_blank" rel="noopener">itinéraire</a>';

    $("btn-ics").addEventListener("click", function () { ics(n); });
  }

  function ics(n) {
    var ymd = n.date.replace(/-/g, "");
    var desc = "Programme :\\n" + (n.interventions || []).map(function (t) {
      return "- " + t.sujet.replace(/[,;]/g, " ") + " (" + t.intervenants.map(function (p) { return p.nom; }).join(", ") + ")";
    }).join("\\n") + "\\nInscription : " + window.RTN.inscription;
    var body = [
      "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//RDV en terrain numerique//FR", "CALSCALE:GREGORIAN",
      "BEGIN:VEVENT", "UID:rtn-" + ymd + "@rdventerrainnumerique.fr",
      "DTSTAMP:" + new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, ""),
      "DTSTART;TZID=Europe/Paris:" + ymd + "T183000", "DTEND;TZID=Europe/Paris:" + ymd + "T210000",
      "SUMMARY:RDV en terrain numérique", "LOCATION:" + (lieuNom(n.lieu) + (n.adresse ? " - " + n.adresse : "")).replace(/[,;]/g, " "),
      "DESCRIPTION:" + desc, "END:VEVENT", "END:VCALENDAR"
    ].join("\r\n");
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([body], { type: "text/calendar;charset=utf-8" }));
    a.download = "rdv-terrain-numerique-" + n.date + ".ics";
    document.body.appendChild(a); a.click(); a.remove();
  }

  function renderStats(s) {
    $("st-soirees").textContent = s.soirees;
    $("st-pres").textContent = s.presentations;
    $("st-int").textContent = s.intervenants;
    if (s.depuis) { var x = d(s.depuis); $("st-depuis").textContent = MOIS[x.getMonth()] + " " + x.getFullYear(); }
  }

  var LIMIT = 6, showAll = false;
  function renderHistory(data) {
    var q = ($("q").value || "").trim().toLowerCase();
    var list = data.historique.filter(function (e) {
      if (!q) return true;
      var hay = [e.lieu, e.ville, shortDate(e.date)].concat(e.sponsors.map(function (s) { return s.nom; }));
      e.interventions.forEach(function (t) { hay.push(t.sujet); t.intervenants.forEach(function (p) { hay.push(p.nom, p.entreprise); }); });
      return hay.join(" ").toLowerCase().indexOf(q) >= 0;
    });
    var shown = q || showAll ? list : list.slice(0, LIMIT);
    $("events").innerHTML = shown.map(function (e) {
      var x = d(e.date);
      var talks = e.interventions.map(function (t) {
        return '<li><div class="s">' + esc(t.sujet) + '</div><div class="w">' +
          t.intervenants.map(function (p) { return esc(p.nom) + (p.entreprise ? " (" + esc(p.entreprise) + ")" : ""); }).join(", ") + "</div>" +
          (t.support ? '<a class="sup" href="' + esc(t.support) + '" target="_blank" rel="noopener">Voir le support ↗</a>' : "") + "</li>";
      }).join("");
      var side = "";
      if (e.photo) side += '<img class="photo" src="' + esc(e.photo) + '" alt="Synthèse de la soirée du ' + shortDate(e.date) + '" loading="lazy">';
      if (e.sponsors.length) side += '<div class="spons">Avec ' + e.sponsors.map(function (s) { return logo(s); }).join("") + "</div>";
      if (e.recap) side += '<a class="recap" href="' + esc(e.recap) + '" target="_blank" rel="noopener">Le récap de la soirée ↗</a>';
      return '<article class="ev"><div class="ev-date"><span class="d">' + x.getDate() + '</span><span class="m">' + MOIS[x.getMonth()] + " " + x.getFullYear() +
        '</span><span class="ed">Édition n°' + e.edition + '</span><span class="where">' + esc(lieuNom(e.lieu)) + (e.ville && e.ville !== "Angoulême" ? " · " + esc(e.ville) : "") + "</span></div>" +
        '<ul class="ev-talks">' + talks + '</ul><div class="ev-side">' + side + "</div></article>";
    }).join("") + (!q && !showAll && list.length > LIMIT ? '<button class="more" id="more" type="button">Voir les ' + (list.length - LIMIT) + " soirées précédentes</button>" : "");
    $("empty").hidden = list.length > 0;
    var m = $("more"); if (m) m.addEventListener("click", function () { showAll = true; renderHistory(data); });
  }

  function renderUpcoming(data) {
    if (!data.suivantes || !data.suivantes.length) return;
    $("upcoming").innerHTML = '<span class="lbl">À noter dans l\'agenda :</span>' + data.suivantes.map(function (s) {
      return '<span class="chip">' + shortDate(s.date) + "</span>";
    }).join("");
  }

  function renderWall(data) {
    var seen = {}, all = [];
    var evs = data.historique.slice();
    if (data.prochaine) evs.unshift(data.prochaine);
    evs.forEach(function (e) { e.sponsors.forEach(function (s) { var k = s.nom.toLowerCase(); if (!seen[k]) { seen[k] = 1; all.push(s); } }); });
    $("wall").innerHTML = all.map(function (s) { return logo(s); }).join("");
  }

  function wireLinks(data) {
    document.querySelectorAll(".js-inscription").forEach(function (a) { a.href = data.inscription; });
    document.querySelectorAll(".js-linkedin").forEach(function (a) { a.href = data.linkedin; });
  }

  fetch("data.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (data) {
    window.RTN = data;
    wireLinks(data);
    renderNext(data);
    renderStats(data.stats);
    renderUpcoming(data);
    renderHistory(data);
    renderWall(data);
    $("q").addEventListener("input", function () { renderHistory(data); });
    if (data.generatedAt) { var g = new Date(data.generatedAt); $("maj").textContent = "le " + g.toLocaleDateString("fr-FR") + " à " + g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }); }
  }).catch(function (e) { console.error("data.json", e); });
})();
