# Test : modifier une séance précédente, effacer une séance. Lancer d'abord :
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8804 --base /tmp/t14.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8804}/api/"
def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, data=None if c is None else json.dumps(c).encode(), method=m,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(q) as x: return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
def ok(cond, msg):
    print(("OK   " if cond else "ÉCHEC ") + msg)
    assert cond, msg
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "Effacer"}, J)[1]["code"]
cfg = r("GET", f"classes/{code}/config", None, J)[1]
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou", "nouveau": True})[1]
for n, t in ((1, "Séance A"), (2, "Séance B"), (3, "Séance C")):
    cfg.update(seance=n, ouvertes=list(range(1, n + 1)), ouverte=True, tache=t)
    s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
    r("PUT", f"eleve/seance/{n}", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": f"idée {n}"}]}, e["jeton"])
ok({k: v["tache"] for k, v in cfg["archives"].items()} == {"1": "Séance A", "2": "Séance B", "3": "Séance C"}, "trois séances, chacune sa consigne")
# modifier la séance 1
arch = dict(cfg["archives"]); arch["1"] = {**arch["1"], "tache": "Séance A corrigée", "indices": ["Un indice"]}
s, cfg = r("PUT", f"classes/{code}/config", {**cfg, "archives": arch}, J)
ok(cfg["archives"]["1"]["tache"] == "Séance A corrigée" and cfg["tache"] == "Séance C", "modifier la séance 1 ne touche pas la plus récente")
s, m1 = r("GET", "eleve/moi?seance=1", None, e["jeton"])
ok(m1["config"]["tache"] == "Séance A corrigée" and m1["coupsDePouce"]["total"] == 1, "l'élève qui a commencé voit la consigne corrigée et le nouvel indice")
ok(m1["seances"]["1"]["ideesAvant"][0]["texte"] == "idée 1", "son travail est conservé")
# effacer la séance 2
s, d = r("DELETE", f"classes/{code}/seances/2", None, J)
ok(s == 200 and d["elevesConcernes"] == 1, "séance 2 effacée (1 élève concerné)")
c2 = d["config"]
ok(2 not in c2["ouvertes"] and "2" not in c2["archives"] and c2["supprimees"] == [2], "elle disparaît des séances ouvertes et des archives")
s, m = r("GET", "eleve/moi", None, e["jeton"])
ok([o["seance"] for o in m["ouvertes"]] == [1, 3] and sorted(m["seances"]) == ["1", "3"], "l'élève ne la voit plus ; ses séances 1 et 3 sont intactes")
ok(r("PUT", "eleve/seance/2", {"phase": "reflexion"}, e["jeton"])[0] == 409, "on ne peut plus y écrire")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
ok(sorted(tr[e["id"]]["seances"]) == ["1", "3"], "ses traces sont effacées côté enseignant")
ok(r("DELETE", f"classes/{code}/seances/2", None, J)[0] == 404, "effacer deux fois : séance inconnue")
# une nouvelle séance prend le numéro suivant
s, cfg = r("PUT", f"classes/{code}/config", {**c2, "seance": 4, "ouvertes": [1, 3, 4], "ouverte": True, "tache": "Séance D"}, J)
ok(cfg["ouvertes"] == [1, 3, 4] and cfg["archives"]["4"]["tache"] == "Séance D" and "2" not in cfg["archives"], "créer la séance 4 ne fait pas réapparaître la 2")
ok(r("DELETE", f"classes/{code}/seances/9", None, J)[0] == 404 and r("DELETE", f"classes/{code}/seances/1", None, e["jeton"])[0] == 401, "séance inexistante refusée ; un élève ne peut rien effacer")
# numéro affiché : rang parmi les séances qui existent encore (les identifiants 1, 3, 4 s'affichent 1, 2, 3)
r("PUT", "eleve/seance/4", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": "idée 4"}]}, e["jeton"])
s, m = r("GET", "eleve/moi?seance=4", None, e["jeton"])
ok([(o["seance"], o["numero"]) for o in m["ouvertes"]] == [(1, 1), (3, 2), (4, 3)] and m["config"]["numero"] == 3, "l'élève voit les séances 1, 2, 3 (identifiants 1, 3, 4)")
ok([p["numero"] for p in m["parcours"]] == [1, 2, 3], "son parcours est numéroté de même")
s, d = r("DELETE", f"classes/{code}/seances/1", None, J)
s, m = r("GET", "eleve/moi?seance=4", None, e["jeton"])
ok([o["numero"] for o in m["ouvertes"]] == [1, 2], "après l'effacement de la première séance, les suivantes deviennent 1 et 2")
txt = urllib.request.urlopen(urllib.request.Request(B + f"classes/{code}/export.csv", headers={"Authorization": "Bearer " + J})).read().decode("utf-8-sig")
ok(txt.splitlines()[0].startswith("pseudo;seance;numero;") and ";4;2;" in txt, "l'export garde l'identifiant et ajoute le numéro affiché")

