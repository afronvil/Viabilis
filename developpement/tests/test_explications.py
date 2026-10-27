# Test des explications d'erreurs d'exercices par l'IA. Lancer d'abord :
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8797 --base /tmp/t_expl.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, sys, urllib.request, urllib.error
PORT = sys.argv[1] if len(sys.argv) > 1 else "8797"
B = f"http://127.0.0.1:{PORT}/api/"
N = 0
def r(m, p, corps=None, j=None):
    req = urllib.request.Request(B + p, data=None if corps is None else json.dumps(corps).encode(), method=m,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(req) as x: return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
def ok(cond, msg):
    global N
    print(("OK   " if cond else "ÉCHEC ") + msg)
    assert cond, msg
    N += 1

# le garde-fou, sans serveur
import serveur as S
num = {"type": "numerique", "reponses": [{"valeur": 12.0, "tolerance": 0, "fraction": 1}]}
ok(S.revele_reponse("3 × 4 = 12, donc…", num) and not S.revele_reponse("Pense à 120 et à 1,2.", num), "garde-fou : nombre exact repéré, pas ses voisins")
courte = {"type": "reponse_courte", "reponses": [{"texte": "Paris", "fraction": 1}]}
ok(S.revele_reponse("C'est Paris !", courte) and not S.revele_reponse("Les Parisiens…", courte), "garde-fou : mot entier repéré")
c = S.consignes_explication("questionner", "college", "fr", fini=False)
ok("JAMAIS la bonne réponse" in c and "question" in c and "règle" in c, "consignes : question d'abord, règle, pas de réponse tant qu'il reste un essai")
ok("cas semblable" in S.consignes_explication("donner", "ecole", "fr", fini=True), "consignes : un cas semblable une fois l'exercice terminé")

# le parcours, avec le serveur
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "Explications"}, J)[1]["code"]
gift = "::Produit::Combien font 3 × 4 ?{#12}\n\n::Somme::[fuite] Combien font 2 + 3 ?{#5}\n"
ok(r("POST", f"classes/{code}/exercices/import", {"contenu": gift, "niveau": 1}, J)[1]["importes"] == 2, "deux exercices importés")
cfg = r("GET", f"classes/{code}/config", None, J)[1]
ok(cfg["exercices"]["explications"] is True, "explications activées par défaut")
cfg.update(tache="Inventez des calculs", seance=1, ouverte=True, exercices={"actifs": True, "nombre": 2, "placement": "avant", "niveau": 1})
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lina"})[1]["jeton"]
ok(r("GET", "eleve/moi", None, e)[1]["config"]["exercices"]["explications"] is True, "l'élève sait que les explications sont proposées")
exos = {x["titre"]: x["id"] for x in r("GET", "eleve/exercices", None, e)[1]}
p, s_ = exos["Produit"], exos["Somme"]
ok(r("POST", f"eleve/exercices/{p}/expliquer", {}, e)[0] == 409, "pas d'explication avant d'avoir répondu")
r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "13"}, e)
st, d = r("POST", f"eleve/exercices/{p}/expliquer", {}, e)
ok(st == 200 and d["texte"] and d["fini"] is False, "1re erreur : une explication, il reste un essai")
ok(r("POST", f"eleve/exercices/{p}/expliquer", {}, e)[0] == 429, "une seule explication par réponse")
r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "14"}, e)
st, d = r("POST", f"eleve/exercices/{p}/expliquer", {}, e)
ok(st == 200 and d["fini"] is True, "2e erreur : une nouvelle explication, exercice terminé")
r("POST", f"eleve/exercices/{s_}/reponse", {"reponse": "5"}, e)
ok(r("POST", f"eleve/exercices/{s_}/expliquer", {}, e)[0] == 409, "réponse juste : rien à expliquer")
# un second élève : l'IA factice « dévoile » 5 avant le second essai, le garde-fou la remplace
e2 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Noé"})[1]["jeton"]
r("POST", f"eleve/exercices/{s_}/reponse", {"reponse": "4"}, e2)
st, d = r("POST", f"eleve/exercices/{s_}/expliquer", {}, e2)
ok(st == 200 and "5" not in d["texte"] and d["texte"].startswith("Relis l'énoncé"), "garde-fou : la bonne réponse n'est pas montrée avant le second essai")
sig = r("GET", f"classes/{code}/signalements", None, J)
ok(sig[0] != 200 or any("explication bloquée" in json.dumps(x, ensure_ascii=False) for x in sig[1]), "explication bloquée signalée à l'enseignant")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
lina = next(v for v in tr.values() if v["pseudo"] == "Lina")
ok({x["titre"]: x["explications"] for x in lina["seances"]["1"]["exercices"]} == {"Produit": 2, "Somme": 0}, "nombre d'explications visible côté enseignant")
# réglages de l'enseignant
cfg["exercices"]["explications"] = False
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "1"}, e2)
ok(r("POST", f"eleve/exercices/{p}/expliquer", {}, e2)[0] == 403 and r("GET", "eleve/moi", None, e2)[1]["config"]["exercices"]["explications"] is False,
   "explications désactivées par l'enseignant")
cfg["exercices"]["explications"] = True
cfg["evaluation"] = True
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
ok(r("POST", f"eleve/exercices/{p}/expliquer", {}, e2)[0] == 403 and r("GET", "eleve/moi", None, e2)[1]["config"]["exercices"]["explications"] is False,
   "jamais pendant une évaluation")
cfg["evaluation"] = False
cfg["langue"] = "de"
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
req = urllib.request.Request(B + f"eleve/exercices/{s_}/expliquer", data=b"{}", method="POST",
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + e2, "X-Viabilis-Langue": "de"})
try:
    urllib.request.urlopen(req); msg = ""
except urllib.error.HTTPError as x:
    msg = json.loads(x.read())["erreur"]
ok(msg.startswith("Du hast für diese Antwort schon eine Erklärung"), f"message traduit en allemand ({msg[:40]}…)")
print(f"test_explications : {N} vérifications réussies")
