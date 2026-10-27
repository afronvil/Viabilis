# Test de la remédiation après une erreur d'exercice (dialogue avec l'IA, sans jamais donner la réponse). Lancer d'abord :
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
c = S.consignes_remediation("questionner", "college", "fr", fini=False)
ok("JAMAIS la bonne réponse" in c and "TECHNIQUE" in c and "UNE question" in c and "réessayer" in c, "consignes : l'erreur, puis une technique pas à pas par des questions, jamais la réponse")
ok("JAMAIS la bonne réponse" in S.consignes_remediation("donner", "ecole", "fr", fini=True), "consignes : jamais la réponse, même après le dernier essai")

# le parcours, avec le serveur
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "Remédiation"}, J)[1]["code"]
gift = "::Produit::Combien font 3 × 4 ?{#12}\n\n::Somme::[fuite] Combien font 2 + 3 ?{#5}\n"
ok(r("POST", f"classes/{code}/exercices/import", {"contenu": gift, "niveau": 1}, J)[1]["importes"] == 2, "deux exercices importés")
cfg = r("GET", f"classes/{code}/config", None, J)[1]
ok(cfg["exercices"]["explications"] is True and cfg["exercices"]["montrerReponse"] is False, "remédiation activée et bonne réponse cachée par défaut")
cfg.update(tache="Inventez des calculs", seance=1, ouverte=True, exercices={"actifs": True, "nombre": 2, "placement": "avant", "niveau": 1})
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lina"})[1]["jeton"]
ok(r("GET", "eleve/moi", None, e)[1]["config"]["exercices"]["explications"] is True, "l'élève sait que la remédiation est proposée")
exos = {x["titre"]: x["id"] for x in r("GET", "eleve/exercices", None, e)[1]}
p, s_ = exos["Produit"], exos["Somme"]
ok(r("POST", f"eleve/exercices/{p}/expliquer", {}, e)[0] == 409, "pas de remédiation avant d'avoir répondu")
r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "13"}, e)
ok(r("POST", f"eleve/exercices/{p}/expliquer", {"message": "pourquoi ?"}, e)[0] == 409, "répondre à l'IA demande d'abord d'ouvrir la remédiation")
st, d = r("POST", f"eleve/exercices/{p}/expliquer", {}, e)
ok(st == 200 and [m["role"] for m in d["echanges"]] == ["ia"] and d["restantes"] == S.REMEDIATION_MAX and d["fini"] is False, "1re erreur : l'IA ouvre la remédiation")
st, d2 = r("POST", f"eleve/exercices/{p}/expliquer", {}, e)
ok(st == 200 and d2["echanges"] == d["echanges"], "rouvrir renvoie le même dialogue (page rechargée)")
for k in range(S.REMEDIATION_MAX):
    msg = f"Étape {k + 1} : j'essaie"
    st, d = r("POST", f"eleve/exercices/{p}/expliquer", {"message": msg}, e)
    ok(st == 200 and d["restantes"] == S.REMEDIATION_MAX - 1 - k and len(d["echanges"]) == 3 + 2 * k and d["echanges"][-2] == {"role": "eleve", "texte": msg}, f"réponse {k + 1} de l'élève : l'IA réagit")
ok(r("POST", f"eleve/exercices/{p}/expliquer", {"message": "encore"}, e)[0] == 429, f"{S.REMEDIATION_MAX} réponses au plus par remédiation")
st, rep = r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "14"}, e)
ok(rep["fini"] and rep["attendu"] is None and rep["retourGeneral"] == "", "2e erreur : la bonne réponse n'est pas montrée à l'élève")
st, d = r("POST", f"eleve/exercices/{p}/expliquer", {}, e)
ok(st == 200 and d["fini"] is True and len(d["echanges"]) == 1, "après le dernier essai : une nouvelle remédiation")
r("POST", f"eleve/exercices/{s_}/reponse", {"reponse": "5"}, e)
ok(r("POST", f"eleve/exercices/{s_}/expliquer", {}, e)[0] == 409, "réponse juste : rien à remédier")
# un second élève : l'IA factice « dévoile » 5, le garde-fou la remplace, avant comme après le dernier essai
e2 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Noé"})[1]["jeton"]
for essai, mauvaise in ((1, "4"), (2, "6")):
    r("POST", f"eleve/exercices/{s_}/reponse", {"reponse": mauvaise}, e2)
    st, d = r("POST", f"eleve/exercices/{s_}/expliquer", {}, e2)
    ok(st == 200 and "5" not in d["echanges"][-1]["texte"] and d["echanges"][-1]["texte"].startswith("Relis l'énoncé"), f"garde-fou à l'essai {essai} : la bonne réponse n'est jamais montrée")
sig = r("GET", f"classes/{code}/signalements", None, J)
ok(sig[0] != 200 or any("remédiation bloquée" in json.dumps(x, ensure_ascii=False) for x in sig[1]), "remédiation bloquée signalée à l'enseignant")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
lina = {x["titre"]: x for x in next(v for v in tr.values() if v["pseudo"] == "Lina")["seances"]["1"]["exercices"]}
ok(lina["Produit"]["explications"] == 2 and lina["Somme"]["explications"] == 0, "nombre de remédiations visible côté enseignant")
ok(len(lina["Produit"]["remediation"]["1"]) == 1 + 2 * S.REMEDIATION_MAX and len(lina["Produit"]["remediation"]["2"]) == 1, "dialogues de remédiation lisibles par l'enseignant, par essai")
ok(lina["Produit"]["reponse"] == "14" and lina["Produit"]["attendu"] == "12", "l'enseignant voit la réponse donnée et la bonne réponse")
# réglages de l'enseignant
cfg["exercices"]["montrerReponse"] = True
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
e3 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Sam"})[1]["jeton"]
r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "1"}, e3)
ok(r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "2"}, e3)[1]["attendu"] == "12", "bonne réponse montrée si l'enseignant le choisit")
cfg["exercices"]["explications"] = False
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
r("POST", f"eleve/exercices/{p}/reponse", {"reponse": "1"}, e2)
ok(r("POST", f"eleve/exercices/{p}/expliquer", {}, e2)[0] == 403 and r("GET", "eleve/moi", None, e2)[1]["config"]["exercices"]["explications"] is False,
   "remédiation désactivée par l'enseignant")
cfg["exercices"]["explications"] = True
cfg["evaluation"] = True
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
ok(r("POST", f"eleve/exercices/{p}/expliquer", {}, e2)[0] == 403 and r("GET", "eleve/moi", None, e2)[1]["config"]["exercices"]["explications"] is False,
   "jamais pendant une évaluation")
cfg["evaluation"] = False
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
req = urllib.request.Request(B + f"eleve/exercices/{p}/expliquer", data=json.dumps({"message": "?"}).encode(), method="POST",
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + e2, "X-Viabilis-Langue": "de"})
try:
    urllib.request.urlopen(req); msg = ""
except urllib.error.HTTPError as x:
    msg = json.loads(x.read())["erreur"]
ok(msg.startswith("Tippe zuerst"), f"message traduit en allemand ({msg[:40]}…)")
print(f"test_explications : {N} vérifications réussies")
