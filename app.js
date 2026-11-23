/* RDV en terrain numérique — interactivité.
   Le contenu est déjà écrit dans le HTML (généré chaque jour depuis Airtable par scripts/render.py).
   Ici : compte à rebours, bouton agenda (.ics), recherche et « voir plus » dans l'historique. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };

  // Compte à rebours dans le bandeau du prochain RDV
  var k = $("kicker");
  if (k && k.dataset.date) {
    var p = k.dataset.date.split("-"), t = new Date(); t.setHours(0, 0, 0, 0);
    var j = Math.round((new Date(+p[0], +p[1] - 1, +p[2]) - t) / 864e5);
    var when = j === 0 ? "c'est ce soir" : j === 1 ? "demain" : j > 1 ? "dans " + j + " jours" : "";
    if (when) k.textContent = k.textContent.replace("Prochain rendez-vous", "Prochain rendez-vous · " + when);
  }

  // Ajout à l'agenda
  var b = $("btn-ics");
  if (b && b.dataset.ics) {
    b.addEventListener("click", function () {
      var n = JSON.parse(b.dataset.ics), ymd = n.date.replace(/-/g, "");
      var clean = function (s) { return String(s || "").replace(/[,;\\]/g, " ").replace(/\n/g, " "); };
      var insc = (document.querySelector(".hero .btn-yellow") || {}).href || "";
      var desc = "Programme :\\n" + n.programme.map(function (x) { return "- " + clean(x); }).join("\\n") + "\\nInscription : " + insc;
      var body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//RDV en terrain numerique//FR", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", "UID:rtn-" + ymd + "@rdventerrainnumerique.fr",
        "DTSTAMP:" + new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, ""),
        "DTSTART;TZID=Europe/Paris:" + ymd + "T183000", "DTEND;TZID=Europe/Paris:" + ymd + "T210000",
        "SUMMARY:RDV en terrain numérique", "LOCATION:" + clean(n.lieu + (n.adresse ? " - " + n.adresse : "")),
        "DESCRIPTION:" + desc, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([body], { type: "text/calendar;charset=utf-8" }));
      a.download = "rdv-terrain-numerique-" + n.date + ".ics";
      document.body.appendChild(a); a.click(); a.remove();
    });
  }

  // Historique : 6 soirées visibles, recherche plein texte
  var evs = [].slice.call(document.querySelectorAll("#events .ev")), LIMIT = 6, all = false;
  var q = $("q"), more = $("more"), empty = $("empty");
  function apply() {
    var s = (q && q.value || "").trim().toLowerCase(), shown = 0, match = 0;
    evs.forEach(function (e) {
      var ok = !s || e.dataset.search.indexOf(s) >= 0;
      if (ok) match++;
      var vis = ok && (s || all || shown < LIMIT);
      if (vis) shown++;
      e.hidden = !vis;
    });
    if (more) { more.hidden = !!s || all || evs.length <= LIMIT; more.textContent = "Voir les " + (evs.length - LIMIT) + " soirées précédentes"; }
    if (empty) empty.hidden = match > 0;
  }
  if (q) q.addEventListener("input", apply);
  if (more) more.addEventListener("click", function () { all = true; apply(); });
  apply();
})();
