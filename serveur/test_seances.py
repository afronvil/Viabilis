# Test : connexion par la liste des pseudonymes, plusieurs séances ouvertes, reprise pour s'améliorer, code personnel en option.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8799 --base /tmp/t9.sqlite3
import json, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8799}/api/"
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
code = r("POST", "classes", {"nom": "Séances"}, J)[1]["code"]
r("POST", f"classes/{code}/exercices/import", {"contenu": "::Q1::2 + 2 ?{#4}\n\n::Q2::3 × 3 ?{#9}", "niveau": 2}, J)
cfg = r("GET", f"classes/{code}/config", None, J)[1]
cfg.update(tache="Payer 10 €", seance=1, ouvertes=[1], ouverte=True, ordre="reflexion", minIdees=1,
           verification={"mode": "calcul", "cible": 10, "nombres": "1;2;5", "attendu": 10, "maximum": 1},
           exercices={"actifs": True, "nombre": 2, "placement": "avant", "niveau": 2})
s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
# --- connexion par la liste
s, e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Panda 7", "nouveau": True})
s, cl = r("POST", "eleve/classe", {"code": code.lower()})
ok(cl["pseudos"] == ["Panda 7"] and cl["codePersonnel"] is False, "la classe liste les pseudonymes existants")
ok(r("POST", "eleve/connexion", {"code": code, "pseudo": "panda 7", "nouveau": True})[0] == 409, "créer un pseudonyme déjà pris est refusé")
s, e2 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Panda 7"})
ok(s == 200 and e2["id"] == e["id"], "retour en touchant son pseudonyme, sans code")
e = e2
# --- séance 1 : exercices (un raté), idées, vérification, envoi
s, exos = r("GET", "eleve/exercices?seance=1", None, e["jeton"])
r("PUT", "eleve/seance/1", {"phase": "exercices", "chargeDebut": 2, "suite": "tache"}, e["jeton"])
for x in exos:
    rep = "4" if "2 + 2" in x["texte"] else "0"
    for _ in range(2 if rep == "0" else 1): r("POST", f"eleve/exercices/{x['id']}/reponse?seance=1", {"reponse": rep}, e["jeton"])
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": "5 + 5"}, {"texte": "5 + 2 + 2"}]}, e["jeton"])
s, v = r("POST", "eleve/verifier?seance=1", {}, e["jeton"])
ok(v["justes"] == 1 and r("POST", "eleve/verifier?seance=1", {}, e["jeton"])[0] == 429, "séance 1 : vérification utilisée (1 maximum)")
r("PUT", "eleve/seance/1", {"phase": "envoye", "chargeDebut": 2, "chargeFin": 2, "compris": 3, "ideesAvant": [{"texte": "5 + 5"}, {"texte": "5 + 2 + 2"}]}, e["jeton"])
# --- séance 2 ouverte en même temps, autre consigne
cfg.update(seance=2, ouvertes=[1, 2], ouverte=True, tache="Le compte est 24", verification={**cfg["verification"], "cible": 24, "nombres": "2;3;5;7", "attendu": 4})
s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
s, m = r("GET", "eleve/moi", None, e["jeton"])
ok([o["seance"] for o in m["ouvertes"]] == [1, 2] and m["config"]["seance"] == 2, "deux séances ouvertes ; par défaut la plus récente")
ok(m["ouvertes"][0]["titre"] == "Payer 10 €" and m["ouvertes"][0]["phase"] == "envoye" and m["ouvertes"][1]["titre"] == "Le compte est 24", "chaque séance garde sa consigne et son état")
s, m1 = r("GET", "eleve/moi?seance=1", None, e["jeton"])
ok(m1["config"]["tache"] == "Payer 10 €" and m1["config"]["seance"] == 1, "l'élève peut ouvrir la séance 1")
# --- reprise de la séance 1
s, d = r("POST", "eleve/reprendre?seance=1", {}, e["jeton"])
ok(d["essais"] == 2 and d["phase"] == "exercices" and d["suite"] == "tache" and d["ideesAvant"][1]["texte"] == "5 + 2 + 2", "reprise : 2e essai, idées gardées, exercices ratés d'abord")
s, exos = r("GET", "eleve/exercices?seance=1", None, e["jeton"])
ok(sorted((x["tentatives"], x["score"] or 0) for x in exos) == [(0, 0), (1, 1.0)], "seul l'exercice raté est à refaire")
x = next(x for x in exos if x["tentatives"] == 0)
s, rep = r("POST", f"eleve/exercices/{x['id']}/reponse?seance=1", {"reponse": "9"}, e["jeton"])
ok(rep["juste"], "l'exercice raté est réussi au 2e essai de la séance")
r("PUT", "eleve/seance/1", {"phase": "reflexion", "ideesAvant": [{"texte": "5 + 5"}, {"texte": "5 + 2 + 2 + 1"}]}, e["jeton"])
s, v = r("POST", "eleve/verifier?seance=1", {}, e["jeton"])
ok(s == 200 and v["justes"] == 2, "la vérification est à nouveau possible et montre le progrès (1 → 2 idées justes)")
tr = r("GET", f"classes/{code}/traces", None, J)[1][e["id"]]["seances"]["1"]
ok(tr["essais"] == 2 and tr["verification"]["justes"] == 2, "l'enseignant voit les essais et le progrès")
ok(r("PUT", "eleve/seance/1", {"phase": "envoye", "essais": 99}, e["jeton"])[1] and r("GET", f"classes/{code}/traces", None, J)[1][e["id"]]["seances"]["1"]["essais"] == 2, "le nombre d'essais n'est pas modifiable par l'élève")
# --- fermeture d'une séance
cfg["ouvertes"] = [2]; r("PUT", f"classes/{code}/config", cfg, J)
ok(r("PUT", "eleve/seance/1", {"phase": "reflexion"}, e["jeton"])[0] == 409 and r("POST", "eleve/reprendre?seance=1", {}, e["jeton"])[0] == 409, "séance fermée : plus d'écriture ni de reprise")
# --- code personnel en option
cfg["codePersonnel"] = True; r("PUT", f"classes/{code}/config", cfg, J)
ok(r("POST", "eleve/connexion", {"code": code, "pseudo": "Panda 7"})[0] == 409, "avec l'option, le code personnel est demandé")
ok(r("POST", "eleve/connexion", {"code": code, "pseudo": "Panda 7", "pin": e["pin"]})[0] == 200, "et le bon code est accepté")
