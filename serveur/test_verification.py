# Test de la vérification des idées. Lancer d'abord :
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8795 --base /tmp/t5.sqlite3
import json, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8795}/api/"
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
code = r("POST", "classes", {"nom": "Vérif"}, J)[1]["code"]
cfg = r("GET", f"classes/{code}/config", None, J)[1]
cfg.update(tache="Payer 10 € avec des pièces de 1 €, 2 € et 5 €", seance=1, ouverte=True, ordre="reflexion", minIdees=1,
           verification={"mode": "calcul", "cible": "10", "nombres": "1, 2, 5", "attendu": 10, "maximum": 2})
s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
ok(cfg["verification"]["nombres"] == "1 ; 2 ; 5" and cfg["verification"]["cible"] == 10.0, f"réglages validés : {cfg['verification']}")
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou"})[1]
ok(r("POST", "eleve/verifier", {}, e["jeton"])[0] == 409, "pas de vérification sans idées")
idees = ["5 + 5", "2+2+2+2+2", "5 + 2 + 2", "5 + 3 + 2", "5+5", "deux pièces"]
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": t} for t in idees], "ideesApres": []}, e["jeton"])
s, v = r("POST", "eleve/verifier", {}, e["jeton"])
ok([x["statut"] for x in v["retours"]] == ["juste", "juste", "a_revoir", "a_revoir", "doublon", "a_revoir"], f"statuts : {[x['statut'] for x in v['retours']]}")
ok(v["justes"] == 2 and "Il en existe d'autres" in v["bilan"] and v["restantes"] == 1, f"bilan : {v['bilan']}")
import re as _re
sys.path.insert(0, ".")
import verification as _V
donnees = [m for x in v["retours"] for m in _re.findall(r"\d[\d +×*-]*\d", x["retour"])]
ok(not any((_V.evaluer(m) or (None,))[0] == 10 and "+" in m for m in donnees), "aucune solution donnée à l'élève dans les retours")
s, moi = r("GET", "eleve/moi", None, e["jeton"])
ok(moi["derniereVerification"]["justes"] == 2, "dernière vérification retrouvée au rechargement")
r("POST", "eleve/verifier", {}, e["jeton"])
ok(r("POST", "eleve/verifier", {}, e["jeton"])[0] == 429, "maximum de vérifications respecté")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
vt = tr[e["id"]]["seances"]["1"]["verification"]
ok(vt["nombre"] == 2 and vt["justes"] == 2, "vérification visible côté enseignant")
cfg["verification"] = {"mode": "ia", "criteres": "Le problème contient une fraction.", "maximum": 3}
r("PUT", f"classes/{code}/config", cfg, J)
e2 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Max"})[1]
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": "Un gâteau coupé en 4"}], "ideesApres": []}, e2["jeton"])
s, v2 = r("POST", "eleve/verifier", {}, e2["jeton"])
ok(s == 200 and len(v2["retours"]) == 1, "mode IA (IA factice) : un retour par idée")
