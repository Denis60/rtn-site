# Site « RDV en terrain numérique »

Site statique (GitHub Pages) des soirées des professionnels du numérique de Charente.
Domaine : https://rdventerrainnumerique.fr

## Comment ça marche
- `index.html`, `style.css`, `app.js` : la page. Elle lit `data.json`.
- `data.json` est **régénéré chaque jour** par la GitHub Action `maj-donnees.yml` :
  1. appel du webhook n8n « RTN - Données site web » (workflow `trRHOXKsj22y9mTb`), qui lit Airtable (4 appels API) ;
  2. `scripts/build_data.py` met en forme, télécharge les photos de synthèse (les liens Airtable expirent) et les logos ;
  3. commit si quelque chose a changé → GitHub Pages republie.
- Secret GitHub requis : `RTN_DATA_URL` = URL du webhook n8n.
- Forcer une mise à jour : onglet **Actions** → « Mise à jour des données » → **Run workflow**.

## Ce qui pilote le contenu (Airtable, base RTN)
- **Prochain RDV** = 1re soirée datée d'aujourd'hui ou plus tard. Programme affiché si « ODJ prêt » est coché.
- **Interventions** : statut « Annulé » masqué ; champ **Support** (URL) = lien affiché dans l'historique.
- **Sponsors** : champ Sponsor de la soirée ; logo = « Logo URL » de la fiche personne - entreprise.
- **Photo** : « Photo synthèse » de la soirée ; **Récap** : « Lien récap ».
