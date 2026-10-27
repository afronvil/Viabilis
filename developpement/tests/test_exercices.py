# Test de l'import GIFT / Moodle XML et du parcours d'exercices. Lancer d'abord :
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8791 --base /tmp/t2.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, sys, urllib.request, urllib.error
PORT = sys.argv[1] if len(sys.argv) > 1 else "8791"
B = f"http://127.0.0.1:{PORT}/api/"
def r(m, p, corps=None, j=None):
    req = urllib.request.Request(B + p, data=None if corps is None else json.dumps(corps).encode(), method=m,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(req) as x: return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
def ok(cond, msg):
    print(("OK   " if cond else "ÉCHEC ") + msg)
    assert cond, msg
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "Test"}, J)[1]["code"]
s, d = r("POST", f"classes/{code}/exercices/import", {"contenu": open(_os.path.join(SERVEUR, "exemples", "college", "maths", "fractions.gift"), encoding="utf-8").read()
             + "\n\n::Question ouverte::Expliquez à un camarade ce qu'est une fraction.{}\n", "niveau": 2, "source": "fractions.gift"}, J)
ok(d["importes"] == 8 and len(d["avertissements"]) == 1, f"import GIFT : {d['importes']} questions, {len(d['avertissements'])} avertissement")
s, d = r("POST", f"classes/{code}/exercices/import", {"contenu": open(_os.path.join(SERVEUR, "exemples", "ecole", "sciences", "sciences_moodle.xml"), encoding="utf-8").read(), "niveau": 3}, J)
ok(d["importes"] == 5, f"import Moodle XML : {d['importes']} questions")
s, liste = r("GET", f"classes/{code}/exercices", None, J)
ok(len(liste) == 13, f"{len(liste)} exercices listés")
xml_ids = [x["id"] for x in liste if x["niveau"] == 3]
cfg = r("GET", f"classes/{code}/config", None, J)[1]
cfg.update(tache="Inventez des problèmes avec des fractions", seance=1, ouverte=True, exercices={"actifs": True, "nombre": 3, "placement": "avant", "niveau": 3})
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
e1 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Ana"})[1]
s, exos = r("GET", "eleve/exercices", None, e1["jeton"])
ok(len(exos) == 3 and all(x["id"] in xml_ids for x in exos), "3 exercices tirés au niveau 3")
ok(not any("fraction" in json.dumps(x) or "reponses" in x for x in exos), "aucune réponse attendue envoyée à l'élève")
s, exos2 = r("GET", "eleve/exercices", None, e1["jeton"])
ok([x["id"] for x in exos] == [x["id"] for x in exos2], "tirage stable au rechargement")
x = exos[0]
mauvaise = {"choix_unique": -1, "vrai_faux": "vrai", "reponse_courte": "zzz", "numerique": "-5", "appariement": {}}.get(x["type"], None)
s, rep = r("POST", f"eleve/exercices/{x['id']}/reponse", {"reponse": mauvaise, "duree": 20}, e1["jeton"])
ok(rep["tentatives"] == 1 and not rep["fini"] and rep["attendu"] is None, "1re erreur : seconde chance, réponse non dévoilée")
s, rep = r("POST", f"eleve/exercices/{x['id']}/reponse", {"reponse": mauvaise, "duree": 15}, e1["jeton"])
ok(rep["fini"] and rep["attendu"], f"2e erreur : terminé, réponse attendue montrée ({rep['attendu'][:30]})")
s, rep = r("POST", f"eleve/exercices/{x['id']}/reponse", {"reponse": mauvaise}, e1["jeton"])
ok(s == 409, "3e tentative refusée")
ok(r("POST", f"eleve/exercices/{liste[0]['id']}/reponse", {"reponse": 0}, e1["jeton"])[0] == 404 if liste[0]["id"] not in [y["id"] for y in exos] else True, "exercice hors tirage refusé")
# niveau individuel
cfg["eleves"] = {"x": {"niveau": 9}}
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
ok(cfg["eleves"]["x"]["niveau"] == 5, "niveau individuel borné à 5")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
ex_tr = tr[e1["id"]]["seances"]["1"]["exercices"]
ok(len(ex_tr) == 1 and ex_tr[0]["tentatives"] == 2 and ex_tr[0]["score"] == 0 and ex_tr[0]["duree"] == 35, "résultats visibles côté enseignant (tentatives, score, durée)")
r("PUT", f"classes/{code}/exercices/{xml_ids[0]}", {"niveau": 4, "actif": False}, J)
liste = {x["id"]: x for x in r("GET", f"classes/{code}/exercices", None, J)[1]}
ok(liste[xml_ids[0]]["niveau"] == 4 and not liste[xml_ids[0]]["actif"], "niveau et activation modifiables")
ok(r("GET", f"classes/{code}/exercices", None, e1["jeton"])[0] == 401, "un élève ne peut pas lire la banque")
