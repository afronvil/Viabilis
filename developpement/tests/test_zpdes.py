# Choix adaptatif des exercices (à la manière de ZPDES) : la zone de niveaux ouverts suit les réussites de l'élève.
# Seuils : ouverture et fermeture après 6 résultats (environ deux séances), retour au niveau inférieur après 4 échecs.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8828 --base /tmp/t24.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, re, sys, urllib.request, urllib.error
PORT = sys.argv[1] if len(sys.argv) > 1 else "8828"
B = f"http://127.0.0.1:{PORT}/api/"
n_ok = 0
def r(m, p, corps=None, j=None):
    req = urllib.request.Request(B + p, data=None if corps is None else json.dumps(corps).encode(), method=m,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(req) as x: return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
def ok(cond, msg):
    global n_ok
    assert cond, msg
    n_ok += 1
    print("OK  ", msg)

J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "ZPDES"}, J)[1]["code"]
for niv in (1, 2, 3, 4):                       # 8 questions numériques par niveau ; la réponse est dans le titre
    gift = "\n\n".join(f"::N{niv} R{niv * 10 + k}::Écris le nombre {niv * 10 + k}.{{#{niv * 10 + k}}}" for k in range(8))
    r("POST", f"classes/{code}/exercices/import", {"contenu": gift, "niveau": niv}, J)
niveau_de = {x["id"]: x["niveau"] for x in r("GET", f"classes/{code}/exercices", None, J)[1]}
ok(len(niveau_de) == 32, "32 exercices sur 4 niveaux")

cfg = r("GET", f"classes/{code}/config", None, J)[1]
def seance(n):
    cfg.update(tache="Chercher", seance=n, ouverte=True, ouvertes=[n],
               exercices={"actifs": True, "nombre": 4, "placement": "avant", "niveau": 2, "choix": "adaptatif"})
    return r("PUT", f"classes/{code}/config", cfg, J)[1]
ok(seance(1)["exercices"]["choix"] == "adaptatif", "réglage « choix adaptatif » enregistré")

def faire(jeton, juste):
    exos = r("GET", "eleve/exercices", None, jeton)[1]
    for x in exos:
        bon = int(re.search(r"R(\d+)", x["titre"]).group(1))
        for _ in range(1 if juste else 2):
            r("POST", f"eleve/exercices/{x['id']}/reponse", {"reponse": str(bon if juste else bon + 1000)}, jeton)
    return [niveau_de[x["id"]] for x in exos]

lou = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou"})[1]
max_ = r("POST", "eleve/connexion", {"code": code, "pseudo": "Max"})[1]
n1 = faire(lou["jeton"], True); m1 = faire(max_["jeton"], False)
ok(set(n1) == {2} and set(m1) == {2}, "sans historique : exercices au niveau prévu (2)")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
ok(tr[lou["id"]]["zpdes"]["zone"] == [2], "Lou réussit 4 exercices sur 4 : c'est encore trop tôt pour changer de niveau")
ok(tr[max_["id"]]["zpdes"]["zone"] == [1, 2], "Max échoue 4 fois au niveau 2 : le niveau 1 se rouvre sans attendre")
seance(2)
n2 = faire(lou["jeton"], True); m2 = faire(max_["jeton"], False)
ok(set(n2) == {2}, f"séance 2 : Lou reste au niveau 2 ({n2})")
ok(set(m2) <= {1, 2} and 1 in m2, f"séance 2 : Max reçoit des exercices des niveaux 1 et 2 ({m2})")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
z = tr[lou["id"]]["zpdes"]["zone"]
ok(z == [2, 3], f"après 8 réussites (deux séances), le niveau 3 s'ouvre ; le niveau 2 reste ouvert le temps d'essayer le 3 (zone {z})")
seance(3)
n3 = faire(lou["jeton"], True)
ok(set(n3) <= {2, 3} and 3 in n3, f"séance 3 : Lou travaille aux niveaux 2 et 3 ({n3})")
if n3.count(3) >= 4:
    ok(r("GET", f"classes/{code}/traces", None, J)[1][lou["id"]]["zpdes"]["zone"] == [3], "niveau 3 essayé : le niveau 2, maîtrisé, se ferme")
seance(5)
cfg["exercices"]["choix"] = "niveau"
r("PUT", f"classes/{code}/config", cfg, J)
ok(set(faire(lou["jeton"], True)) == {2}, "choix au niveau fixé : de nouveau le niveau de la classe")
ok("zpdes" not in r("GET", f"classes/{code}/traces", None, J)[1][lou["id"]], "zone non calculée hors du choix adaptatif")
print(f"test_zpdes : {n_ok} vérifications réussies")
