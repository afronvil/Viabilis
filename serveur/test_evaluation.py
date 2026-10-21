# Séance d'évaluation : sans IA, sans coup de pouce ni vérification, une seule réponse par exercice, corrections masquées pour l'élève
# mais scores visibles pour l'enseignant ; les autres séances de la classe ne changent pas.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8814 --base /tmp/t20.sqlite3
import json, os, sys, urllib.error, urllib.request
ICI = os.path.dirname(os.path.abspath(__file__))
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8814}/api/"
ok = 0


def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        return json.load(urllib.request.urlopen(q))
    except urllib.error.HTTPError as e:
        return {"statut": e.code, **json.loads(e.read() or b"{}")}


def verif(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("OK  ", msg)


M = {m["id"]: m for m in json.load(open(os.path.join(ICI, "web", "commun", "modeles.json"), encoding="utf-8"))["modeles"]}
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", "classes", {"nom": "Linux 4 h"}, J)["code"]
cfg = r("GET", f"classes/{code}/config", j=J)
for k, mid, niveau, nombre in ((1, "lin-4h-texte", 3, 3), (2, "lin-4h-evaluation", 5, 12)):
    m = M[mid]
    cfg = r("PUT", f"classes/{code}/config", {**cfg, "modele": mid, "tache": m["tache"], "indices": m["indices"], "saisieCode": True, "public": "superieur",
            "evaluation": bool(m.get("evaluation")), "ordre": "reflexion", "verification": {**cfg["verification"], **m["verification"]},
            "exercices": {"actifs": True, "nombre": nombre, "placement": "avant", "niveau": niveau}, "seance": k, "ouvertes": [1, 2][:k], "ouverte": True}, J)
verif(cfg["archives"]["2"]["evaluation"] is True and cfg["archives"]["1"]["evaluation"] is False, "l'évaluation est un réglage de la séance 2 seulement")
for f, n in (("linux_niveau3.gift", 3), ("linux_evaluation.gift", 5)):
    r("POST", f"classes/{code}/exercices/import", {"contenu": open(os.path.join(ICI, "exemples", "master", f), encoding="utf-8").read(), "format": "gift", "niveau": n, "source": f}, J)

e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou"})
moi = r("GET", "eleve/moi?seance=2", j=e["jeton"])
verif(moi["config"]["evaluation"] is True and r("GET", "eleve/moi?seance=1", j=e["jeton"])["config"]["evaluation"] is False, "l'élève sait quelle séance est une évaluation")
verif(r("PUT", "eleve/seance/2?seance=2", {"phase": "reflexion", "chargeDebut": 5, "ideesAvant": []}, e["jeton"])["ordre"] == "autonomie", "évaluation : autonomie, même en déclarant la tâche très difficile")
verif(r("POST", "eleve/ia?seance=2", {"echanges": []}, e["jeton"])["statut"] == 403, "évaluation : pas d'IA")
verif(r("POST", "eleve/indice?seance=2", {}, e["jeton"])["statut"] == 403, "évaluation : pas de coup de pouce")
verif(r("POST", "eleve/verifier?seance=2", {}, e["jeton"])["statut"] == 403, "évaluation : pas de vérification")
exos = r("GET", "eleve/exercices?seance=2", j=e["jeton"])
verif(len(exos) == 12, "évaluation : les 12 questions de la banque d'évaluation")
rep = r("POST", f"eleve/exercices/{exos[0]['id']}/reponse?seance=2", {"reponse": "0", "duree": 30}, e["jeton"])
verif(rep == {"enregistre": True, "tentatives": 1, "fini": True}, "évaluation : réponse enregistrée, sans score ni correction")
verif(r("POST", f"eleve/exercices/{exos[0]['id']}/reponse?seance=2", {"reponse": "1"}, e["jeton"])["statut"] == 409, "évaluation : une seule réponse")
apres = next(x for x in r("GET", "eleve/exercices?seance=2", j=e["jeton"]) if x["id"] == exos[0]["id"])
verif(apres["tentatives"] == 1 and apres["score"] is None, "évaluation : le score reste caché à l'élève")
tr = r("GET", f"classes/{code}/traces", j=J)[e["id"]]["seances"]["2"]
verif(tr["exercices"][0]["score"] is not None and tr["exercices"][0]["duree"] == 30, "évaluation : l'enseignant voit le score")
r("PUT", "eleve/seance/2?seance=2", {"phase": "envoye", "chargeDebut": 5, "ideesAvant": [{"texte": "chmod go-r comptages.txt"}]}, e["jeton"])
verif(r("POST", "eleve/reprendre?seance=2", {}, e["jeton"])["statut"] == 409, "évaluation : pas de reprise")
# la séance ordinaire garde l'IA, les coups de pouce et deux essais par exercice
verif(r("PUT", "eleve/seance/1?seance=1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": []}, e["jeton"])["ordre"] == "reflexion", "séance ordinaire : réflexion puis IA")
verif("statut" not in r("POST", "eleve/indice?seance=1", {}, e["jeton"]), "séance ordinaire : coups de pouce disponibles")
x1 = r("GET", "eleve/exercices?seance=1", j=e["jeton"])[0]
verif("score" in r("POST", f"eleve/exercices/{x1['id']}/reponse?seance=1", {"reponse": "zzz"}, e["jeton"]), "séance ordinaire : correction affichée")
print(f"test_evaluation : {ok} vérifications réussies")
