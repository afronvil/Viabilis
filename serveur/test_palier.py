# Palier : la variante exigeante ne s'ajoute pas à une tâche déjà plus difficile que le niveau réussi par l'élève.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8814 --base /tmp/t18.sqlite3
import json, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8814}/api/"
def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None, headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(q) as x: return json.loads(x.read())
    except urllib.error.HTTPError as e: return {"statut": e.code}
def ok(cond, msg):
    print(("OK   " if cond else "ÉCHEC ") + msg)
    assert cond, msg
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", "classes", {"nom": "Palier"}, J)["code"]
cfg = r("GET", f"classes/{code}/config", None, J)
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou", "nouveau": True})
va = {"actives": True, "accessible": {"consigne": "facile"}, "exigeante": {"consigne": "difficile"}}
cfg = r("PUT", f"classes/{code}/config", {**cfg, "seance": 1, "ouvertes": [1], "ouverte": True, "tache": "niveau 3", "niveauTache": 3, "variantes": va,
        "eleves": {e["id"]: {"variante": "exigeante", "palier": 3}}}, J)
ok(cfg["eleves"][e["id"]]["palier"] == 3, "le palier est enregistré dans les réglages de l'élève")
ok(r("GET", "eleve/moi?seance=1", None, e["jeton"])["config"]["tache"] == "difficile", "tâche au niveau réussi : variante exigeante")
cfg = r("PUT", f"classes/{code}/config", {**cfg, "seance": 2, "ouvertes": [1, 2], "ouverte": True, "tache": "niveau 4", "niveauTache": 4, "variantes": va}, J)
ok(r("GET", "eleve/moi?seance=2", None, e["jeton"])["config"]["tache"] == "niveau 4", "tâche déjà plus difficile : tâche standard, pas deux marches d'un coup")
r("PUT", "eleve/seance/2", {"phase": "reflexion", "chargeDebut": 2}, e["jeton"])
ok(r("GET", f"classes/{code}/traces", None, J)[e["id"]]["seances"]["2"]["variante"] == "standard", "la variante standard est fixée au début de la séance")
ok(r("GET", "eleve/moi?seance=1", None, e["jeton"])["config"]["tache"] == "difficile", "la séance au niveau du palier garde la variante exigeante")
cfg = r("PUT", f"classes/{code}/config", {**cfg, "eleves": {e["id"]: {"variante": "exigeante"}}}, J)
cfg = r("PUT", f"classes/{code}/config", {**cfg, "seance": 3, "ouvertes": [3], "ouverte": True, "tache": "niveau 5", "niveauTache": 5, "variantes": va}, J)
ok(r("GET", "eleve/moi?seance=3", None, e["jeton"])["config"]["tache"] == "difficile", "sans palier (choix de l'enseignant) : variante exigeante comme avant")
r("PUT", "eleve/preferences", {"facile": True}, e["jeton"])
ok(r("GET", f"classes/{code}/traces", None, J)[e["id"]]["preferences"]["facile"] is True, "l'enseignant reçoit les préférences d'affichage (pour les règles)")
print("test_palier : réussi")
