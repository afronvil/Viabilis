# Propositions de séances suivantes : la séance garde son modèle d'origine ; données de démonstration pour l'interface.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8810 --base /tmp/t16.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, os, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8810}/api/"
n_ok = 0
def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None, headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        return json.load(urllib.request.urlopen(q))
    except urllib.error.HTTPError as e:
        return {"statut": e.code}
def ok(cond, msg):
    global n_ok
    assert cond, msg
    n_ok += 1
    print("OK  ", msg)
M = {m["id"]: m for m in json.load(open(os.path.join(SERVEUR, "web", "commun", "modeles.json")))["modeles"]}
for m in M.values():
    ok(all(x is None or x in M for x in m["suites"].values()), f"{m['id']} : suites connues")
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", "classes", {"nom": "CM1 suites"}, J)["code"]
cfg = r("GET", f"classes/{code}/config", j=J)
m = M["maths-pieces-10"]
cfg = r("PUT", f"classes/{code}/config", {**cfg, "modele": m["id"], "tache": m["tache"], "indices": m["indices"], "seance": 1, "ouvertes": [1], "ouverte": True,
        "verification": {**cfg["verification"], **m["verification"], "attendu": 10, "maximum": 3}}, J)
ok(cfg["modele"] == "maths-pieces-10" and cfg["archives"]["1"]["modele"] == "maths-pieces-10", "la séance garde son modèle d'origine")
ok(r("PUT", f"classes/{code}/config", {**cfg, "modele": "<script>"}, J)["modele"] == "", "identifiant de modèle invalide refusé")
# des élèves aux résultats contrastés
eleves = {"Lou": (2, ["5+5", "5+2+2+1", "2+2+2+2+2", "5+1+1+1+1+1", "2+2+2+2+1+1"], 3, True),     # à l'aise
          "Sami": (3, ["5+5", "5+2+2+1", "5+2+1+1+1"], 2, True),                                  # attendu
          "Noa": (5, ["5+4", "3+3+3", "5+5"], 1, True),                                           # en difficulté
          "Ema": (4, ["2+2+2+2", "5+2"], 1, False)}                                              # en difficulté, pas fini
for pseudo, (charge, idees, compris, fini) in eleves.items():
    e = r("POST", "eleve/connexion", {"code": code, "pseudo": pseudo})
    corps = {"phase": "reflexion", "chargeDebut": charge, "ideesAvant": [{"texte": t} for t in idees], "ideesApres": []}
    r("PUT", "eleve/seance/1", corps, e["jeton"]); r("POST", "eleve/verifier?seance=1", {}, e["jeton"])
    if fini:
        r("PUT", "eleve/seance/1", {**corps, "phase": "envoye", "chargeFin": charge, "compris": compris}, e["jeton"])
tr = r("GET", f"classes/{code}/traces", None, J)
ok(len(tr) == 4 and all("verification" in d["seances"]["1"] for d in tr.values()), "traces et vérifications disponibles pour les propositions")
cfg = r("PUT", f"classes/{code}/config", {**cfg, "modele": "", "tache": "Ma consigne libre"}, J)
ok(cfg["archives"]["1"]["modele"] == "" , "consigne libre : pas de modèle")
cfg = r("PUT", f"classes/{code}/config", {**cfg, "modele": m["id"], "tache": m["tache"]}, J)
print(f"test_suites : {n_ok} vérifications réussies ; classe de démonstration {code}")
