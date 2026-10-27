# Banques d'exercices (.gift) : banques fournies, bibliothèque de l'enseignant (enregistrer sous un nouveau nom), séance qui ne tire que les questions de son fichier.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8835 --base /tmp/t35.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, os, sys, urllib.parse, urllib.request, urllib.error
PORT = sys.argv[1] if len(sys.argv) > 1 else "8835"
B = f"http://127.0.0.1:{PORT}/api/"
ICI = SERVEUR
n_ok = 0


def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(q) as x:
            return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def ok(cond, msg):
    global n_ok
    assert cond, msg
    n_ok += 1
    print("OK  ", msg)


ok(r("GET", "banques")[0] == 401, "sans session enseignant : refusé")
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
s, d = r("GET", "banques", j=J)
fournies = {b["chemin"] for b in d["fournies"]}
ok(s == 200 and d["mes"] == [] and "superieur/marketing/marketing_niveau1.gift" in fournies, f"banques fournies listées ({len(fournies)})")
s, f = r("GET", "banques/fournie?chemin=" + urllib.parse.quote("superieur/marketing/marketing_niveau1.gift"), j=J)
original = open(os.path.join(ICI, "exemples", "superieur", "marketing", "marketing_niveau1.gift"), encoding="utf-8").read()
ok(s == 200 and f["contenu"] == original and f["nom"] == "marketing_niveau1", "lecture d'une banque fournie")
for chemin in ("../serveur.py", "superieur/../../serveur.py", "/etc/passwd", "superieur/marketing/inexistant.gift"):
    ok(r("GET", "banques/fournie?chemin=" + urllib.parse.quote(chemin), j=J)[0] == 404, f"chemin refusé : {chemin}")

s, v = r("POST", "banques/verifier", {"contenu": original}, J)
ok(s == 200 and v["questions"] == 6 and len(v["titres"]) == 6, "vérification : 6 questions reconnues")
ok(r("POST", "banques/verifier", {"contenu": "pas du GIFT"}, J)[1]["questions"] == 0, "vérification : texte sans question")

modifie = original + "\n::Nouvelle::Which segment would you target first?{=The reachable one ~Everyone}\n"
ok(r("POST", "banques", {"nom": "", "contenu": modifie}, J)[0] == 400, "nom obligatoire")
ok(r("POST", "banques", {"nom": "vide", "contenu": "rien"}, J)[0] == 400, "une banque sans question est refusée")
s, b1 = r("POST", "banques", {"nom": "marketing_v2.gift", "contenu": modifie}, J)
ok(s == 201 and b1["nom"] == "marketing_v2" and b1["questions"] == 7, "banque modifiée enregistrée sous un nouveau nom (« .gift » retiré)")
ok(open(os.path.join(ICI, "exemples", "superieur", "marketing", "marketing_niveau1.gift"), encoding="utf-8").read() == original, "la banque fournie n'est pas modifiée")
ok(r("POST", "banques", {"nom": "marketing_v2", "contenu": modifie}, J)[0] == 409, "même nom qu'une banque existante : refusé")
s, b2 = r("POST", "banques", {"nom": "marketing_v3", "contenu": modifie + "\n::Encore::2 + 2 ?{#4}\n"}, J)
ok(s == 201 and b2["questions"] == 8, "enregistrer sous un autre nom crée une deuxième banque")
ok(r("PUT", f"banques/{b2['id']}", {"nom": "marketing_v2", "contenu": modifie}, J)[0] == 409, "renommer vers le nom d'une autre banque : refusé")
s, b = r("PUT", f"banques/{b1['id']}", {"nom": "marketing_v2", "contenu": original}, J)
ok(s == 200 and b["questions"] == 6, "même nom : la banque est remplacée")
mes = r("GET", "banques", j=J)[1]["mes"]
ok([x["nom"] for x in mes] == ["marketing_v2", "marketing_v3"] and r("GET", f"banques/{b2['id']}", j=J)[1]["questions"] == 8, "les deux banques sont gardées")
ok(r("DELETE", f"banques/{b1['id']}", j=J)[0] == 200 and r("GET", f"banques/{b1['id']}", j=J)[0] == 404, "banque supprimée")

# séance créée à partir d'un fichier : seulement ses questions
code = r("POST", "classes", {"nom": "Banques"}, J)[1]["code"]
r("POST", f"classes/{code}/exercices/import", {"contenu": "\n\n".join(f"::Autre {k}::{k} + 1 ?{{#{k + 1}}}" for k in range(10)), "niveau": 2, "source": "autre.gift"}, J)
source = "marketing_v3 · essai"
s, imp = r("POST", f"classes/{code}/exercices/import", {"contenu": r("GET", f"banques/{b2['id']}", j=J)[1]["contenu"], "format": "gift", "niveau": 2, "source": source}, J)
ok(imp["importes"] == 8, "questions de la banque importées dans la classe")
cfg = r("GET", f"classes/{code}/config", j=J)[1]
cfg.update(seance=1, ouvertes=[1], ouverte=True, tache="Après les exercices, écris tes idées.",
           exercices={"actifs": True, "nombre": 8, "placement": "avant", "niveau": 2, "choix": "niveau", "source": source})
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
ok(cfg["exercices"]["source"] == source and cfg["archives"]["1"]["exercices"]["source"] == source, "la séance garde le nom du fichier de ses exercices")
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou"})[1]["jeton"]
exos = r("GET", "eleve/exercices", j=e)[1]
titres = {x["titre"] for x in exos}
ok(len(exos) == 8 and not any(t.startswith("Autre") for t in titres), "l'élève ne reçoit que les questions du fichier de la séance")
cfg = r("PUT", f"classes/{code}/config", {**cfg, "seance": 2, "ouvertes": [1, 2], "tache": "Séance 2", "exercices": {**cfg["exercices"], "source": "", "nombre": 20}}, J)[1]
e2 = r("POST", "eleve/connexion", {"code": code, "pseudo": "Max"})[1]["jeton"]
ok(len(r("GET", "eleve/exercices?seance=2", j=e2)[1]) == 18, "sans limite : toute la banque de la classe")
print(f"test_banques : {n_ok} vérifications réussies")
