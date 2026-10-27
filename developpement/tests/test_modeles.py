# Modèles de séances : chaque modèle donne une configuration valide, et une séance créée depuis un modèle garde sa consigne et sa langue de lecture.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8807 --base /tmp/t15.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, os, sys, urllib.request
from verification import verifier_calcul
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8807}/api/"
ok = 0
def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None, headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    return json.load(urllib.request.urlopen(q))
def verif(cond, msg):
    global ok
    assert cond, msg
    ok += 1
M = json.load(open(os.path.join(SERVEUR, "web", "commun", "modeles.json")))["modeles"]
verif(len(M) >= 10 and len({m["id"] for m in M}) == len(M), "identifiants uniques")
for m in M:
    v = m["verification"]
    verif(m["tache"] and len(m["indices"]) == 3 and v["mode"] in ("calcul", "ia"), m["id"])
    if v["mode"] == "ia":
        verif(40 < len(v["criteres"]) <= 2000, m["id"] + " critères (le serveur les coupe au-delà de 2000 caractères)")
    verif(len(m["tache"]) <= 2000 and all(len(m["variantes"][x]["consigne"]) <= 2000 for x in ("accessible", "exigeante")), m["id"] + " consignes de 2000 caractères au plus")
    ex = m.get("exercices", "").split(" ")[0]
    chemin = ex                                                    # niveau/matière/banque.gift
    verif(not ex or os.path.exists(os.path.join(SERVEUR, "exemples", *chemin.split("/"))), m["id"] + " banque " + ex)
    verif(m.get("public", "ecole") in ("ecole", "college", "lycee", "superieur"), m["id"] + " public connu")
# solutions de référence acceptées par le vérificateur, et nombre attendu cohérent
pieces = ["5+5", "5+2+2+1", "5+2+1+1+1", "5+1+1+1+1+1", "2+2+2+2+2", "2+2+2+2+1+1", "2+2+2+1+1+1+1", "2+2+1+1+1+1+1+1", "2+1+1+1+1+1+1+1+1", "1+1+1+1+1+1+1+1+1+1"]
res = verifier_calcul(pieces, 10, [1, 2, 5], 10)
verif(res["justes"] == 10 and "complet" in res["bilan"], "10 € : 10 solutions")
res = verifier_calcul(["2*(5+7)", "3*5+2+7", "(5-2)*7+3", "3*7+5-2"], 24, [2, 3, 5, 7], 4, True)
verif(res["justes"] == 4 and "complet" in res["bilan"], "compte 24 : 4 solutions")
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", "classes", {"nom": "Modèles"}, J)["code"]
cfg = r("GET", f"classes/{code}/config", j=J)
def depuis(m, cfg):          # même correspondance que reglagesDuModele (enseignant/app.js)
    va = lambda n: {k: m["variantes"][n].get(k) for k in ("consigne", "indices", "cible", "attendu")}
    return {"tache": m["tache"], "indices": m["indices"], "niveauTache": m["niveauTache"],
            "verification": {**cfg["verification"], **m["verification"], "attendu": m["verification"].get("attendu") or 0, "cible": m["verification"].get("cible") or cfg["verification"]["cible"]},
            "variantes": {"actives": True, "accessible": va("accessible"), "exigeante": va("exigeante")},
            "lecture": {"active": True, "langue": m.get("lecture", "fr-FR")}}
ang = next(m for m in M if m.get("lecture") == "en-GB")
suite = [ang] + sorted((x for x in M if x is not ang), key=lambda x: x.get("lecture", "fr-FR") == "fr-FR")   # la dernière séance en français
for k, m in enumerate(suite, 1):
    cfg = r("PUT", f"classes/{code}/config", {**cfg, **depuis(m, cfg), "seance": k, "ouvertes": cfg["ouvertes"] + [k], "ouverte": True}, J)
    verif(cfg["seance"] == k and cfg["tache"] == m["tache"] and cfg["verification"]["mode"] == m["verification"]["mode"], m["id"] + " enregistré")
verif(cfg["archives"]["1"]["tache"] == ang["tache"] and cfg["archives"]["1"]["lecture"]["langue"] == "en-GB", "séance 1 garde sa consigne et sa lecture anglaise")
verif(cfg["lecture"]["langue"] == "fr-FR", "dernière séance en français")
el = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou"})
moi = r("GET", "eleve/moi?seance=1", j=el["jeton"])
verif(moi["lecture"]["langue"] == "en-GB" and moi["config"]["tache"] == ang["tache"], "l'élève lit la séance 1 en anglais")
moi = r("GET", f"eleve/moi?seance={len(M)}", j=el["jeton"])
verif(moi["lecture"]["langue"] == "fr-FR", "et la dernière en français")
# public : ton et exigence de l'IA
import verification, serveur as SV
cfg = r("PUT", f"classes/{code}/config", {**cfg, "public": "superieur"}, J)
verif(cfg["public"] == "superieur" and r("PUT", f"classes/{code}/config", {**cfg, "public": "pirate"}, J)["public"] == "ecole", "public enregistré, valeur inconnue ramenée à l'école")
verif("licence" in verification.consigne_ia("t", "c", ["x"], "superieur") and "rigueur" in verification.consigne_ia("t", "c", ["x"], "superieur")
      and "élémentaire" in verification.consigne_ia("t", "c", ["x"]), "vérification par l'IA adaptée au public")
verif("supérieur" in SV.consignes_ia("questionner", "superieur") and "école" in SV.consignes_ia("elements", "ecole"), "tuteur adapté au public")
# saisie de code (séances de programmation)
cfg = r("PUT", f"classes/{code}/config", {**cfg, "saisieCode": True, "seance": cfg["seance"] + 1, "ouvertes": [cfg["seance"] + 1], "ouverte": True}, J)
verif(cfg["saisieCode"] is True and cfg["archives"][str(cfg["seance"])]["saisieCode"] is True, "saisie de code enregistrée avec la séance")
el2 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Codeur"})
verif(r("GET", f"eleve/moi?seance={cfg['seance']}", None, el2["jeton"])["config"]["saisieCode"] is True, "l'élève reçoit le mode saisie de code")
verif("exécuter" in verification.consigne_ia("t", "c", ["x"], "superieur", True) and "exécuter" not in verification.consigne_ia("t", "c", ["x"], "superieur"),
      "vérification : l'IA sait qu'elle ne peut pas exécuter le code")
verif("programme complet" in SV.consignes_ia("elements", "superieur", True) and "programme complet" not in SV.consignes_ia("elements", "superieur"), "tuteur : jamais de programme complet")
print(f"test_modeles : {ok} vérifications réussies")
