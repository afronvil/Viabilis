# Terminer définitivement une séance : plus aucune modification, puis la correction (idées et exercices, avec les erreurs) ;
# l'enseignant peut autoriser l'élève à reprendre.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8815 --base /tmp/t21.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, os, sys, urllib.error, urllib.request
ICI = SERVEUR
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8815}/api/"
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
m = M["maths-pieces-10"]                                     # idées vérifiées par calcul : 10 € avec des pièces de 1, 2 et 5 €
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", "classes", {"nom": "Terminer"}, J)["code"]
cfg = r("GET", f"classes/{code}/config", j=J)
cfg = r("PUT", f"classes/{code}/config", {**cfg, "modele": m["id"], "tache": m["tache"], "indices": m["indices"], "ordre": "reflexion",
        "verification": {**cfg["verification"], **m["verification"]}, "exercices": {"actifs": True, "nombre": 3, "placement": "apres", "niveau": 2},
        "seance": 1, "ouvertes": [1], "ouverte": True}, J)
gift = open(os.path.join(ICI, "exemples", "ecole", "maths", "maths_probleme_10euros.gift"), encoding="utf-8").read()
verif(r("POST", f"classes/{code}/exercices/import", {"contenu": gift, "format": "gift", "niveau": 2, "source": "maths"}, J)["importes"] >= 3, "banque importée")

e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Noa"})
idees = [{"texte": "5+5"}, {"texte": "5+4"}]                  # une juste, une fausse
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": idees}, e["jeton"])
exos = r("GET", "eleve/exercices?seance=1", j=e["jeton"])
mauvaise = {"choix_unique": 99, "vrai_faux": "rien", "numerique": "123456", "reponse_courte": "zzz"}
x0 = exos[0]
rep = mauvaise.get(x0["type"], "zzz") if x0["type"] != "choix_unique" else next(c["id"] for c in x0["choix"])
r("POST", f"eleve/exercices/{x0['id']}/reponse?seance=1", {"reponse": rep, "duree": 20}, e["jeton"])
verif(r("POST", "eleve/terminer?seance=1", {}, e["jeton"])["statut"] == 409, "on ne termine définitivement qu'une séance déjà envoyée")
r("PUT", "eleve/seance/1", {"phase": "envoye", "chargeDebut": 3, "chargeFin": 3, "compris": 4, "ideesAvant": idees}, e["jeton"])
corr = r("POST", "eleve/terminer?seance=1", {}, e["jeton"])
verif(corr.get("definitif") and corr["idees"]["idees"] == ["5+5", "5+4"], "fin définitive : la correction porte sur les idées")
st = [x["statut"] for x in corr["idees"]["retours"]]
verif(st[0] == "juste" and st[1] != "juste", f"correction des idées : 5+5 juste, 5+4 à revoir ({st})")
verif(len(corr["exercices"]) == 3 and all(x["attendu"] for x in corr["exercices"]), "correction des exercices : les trois exercices tirés, avec la bonne réponse")
x = corr["exercices"][0]
verif(x["reponse"] not in (None, "pas de réponse") and ("juste" in x), f"l'élève voit sa propre réponse ({x['reponse']}) et si elle est juste")
verif(all(y["reponse"] is None for y in corr["exercices"][1:]), "les exercices non faits apparaissent comme sans réponse, avec la bonne réponse")
# plus aucune écriture
verif(r("PUT", "eleve/seance/1", {"phase": "reflexion", "ideesAvant": []}, e["jeton"])["statut"] == 409, "séance verrouillée : plus de modification")
verif(r("POST", "eleve/reprendre?seance=1", {}, e["jeton"])["statut"] == 409, "séance verrouillée : plus de reprise")
verif(r("POST", f"eleve/exercices/{exos[1]['id']}/reponse?seance=1", {"reponse": "1"}, e["jeton"])["statut"] == 409, "séance verrouillée : plus d'exercice")
verif(r("POST", "eleve/verifier?seance=1", {}, e["jeton"])["statut"] == 409, "séance verrouillée : plus de vérification")
verif(r("GET", "eleve/correction?seance=1", j=e["jeton"])["exercices"] == corr["exercices"], "la correction reste consultable")
verif(r("GET", "eleve/moi?seance=1", j=e["jeton"])["ouvertes"][0]["definitif"] is True, "la liste des séances l'indique")
verif(r("POST", "eleve/terminer?seance=1", {}, e["jeton"])["definitif"] == corr["definitif"], "terminer une seconde fois ne refait pas la correction")
# l'enseignant voit la fin définitive et peut rouvrir
tr = r("GET", f"classes/{code}/traces", j=J)[e["id"]]["seances"]["1"]
verif(tr.get("definitif") and tr["correction"]["idees"]["justes"] == 1, "l'enseignant voit la fin définitive et la correction")
verif(r("POST", f"classes/{code}/eleves/{e['id']}/seances/1/rouvrir", {}, J)["ok"], "l'enseignant autorise l'élève à reprendre")
verif(r("GET", "eleve/correction?seance=1", j=e["jeton"])["statut"] == 409 and "statut" not in r("POST", "eleve/reprendre?seance=1", {}, e["jeton"]),
      "après réouverture, l'élève peut reprendre sa séance")
verif(r("POST", f"classes/{code}/eleves/inconnu/seances/1/rouvrir", {}, J)["statut"] == 404, "réouverture : élève inconnu refusé")
print(f"test_terminer : {ok} vérifications réussies")
