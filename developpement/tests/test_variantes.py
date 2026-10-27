# Test des variantes de la tâche et des coups de pouce. Lancer d'abord :
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8797 --base /tmp/t7.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8797}/api/"
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
code = r("POST", "classes", {"nom": "Variantes"}, J)[1]["code"]
cfg = r("GET", f"classes/{code}/config", None, J)[1]
cfg.update(tache="Avec 2, 3, 5 et 7, trouve des calculs qui donnent 24.", seance=1, ouverte=True, ordre="reflexion", minIdees=1,
           indices=["Pars du résultat : 24, c'est 2 fois combien ?", "Comment obtenir 12 avec deux des nombres ?", ""],
           verification={"mode": "calcul", "cible": 24, "nombres": "2;3;5;7", "attendu": 4, "uneFois": True, "maximum": 3},
           variantes={"actives": True,
                      "accessible": {"consigne": "Avec 2, 3, 5 et 7, trouve des calculs qui donnent 12.", "indices": ["12, c'est 5 plus combien ?"], "cible": "12", "attendu": ""},
                      "exigeante": {"consigne": "Avec 2, 3, 5 et 7, trouve des calculs qui donnent 100.", "indices": [], "cible": 100, "attendu": None}})
s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
ok(cfg["indices"] == ["Pars du résultat : 24, c'est 2 fois combien ?", "Comment obtenir 12 avec deux des nombres ?"], "coups de pouce standard validés (vides retirés)")
ok(cfg["variantes"]["accessible"]["cible"] == 12.0 and cfg["variantes"]["accessible"]["attendu"] is None, "variante accessible validée")
a = r("POST", "eleve/connexion", {"code": code, "pseudo": "Ana"})[1]
b = r("POST", "eleve/connexion", {"code": code, "pseudo": "Bob"})[1]
cfg["eleves"] = {a["id"]: {"variante": "accessible"}}
s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
s, ma = r("GET", "eleve/moi", None, a["jeton"]); s, mb = r("GET", "eleve/moi", None, b["jeton"])
ok("12" in ma["config"]["tache"] and "24" in mb["config"]["tache"], "chaque élève reçoit la consigne de sa variante")
ok("variante" not in ma["perso"] and "accessible" not in json.dumps(ma), "le nom de la variante n'est pas envoyé à l'élève")
ok(ma["coupsDePouce"] == {"total": 1, "vus": []} and mb["coupsDePouce"]["total"] == 2, "nombre de coups de pouce selon la variante, aucun dévoilé d'avance")
ok(r("POST", "eleve/indice", {}, b["jeton"])[0] == 409, "pas de coup de pouce avant de commencer")
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": [], "ideesApres": []}, a["jeton"])
s, t = r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": [], "ideesApres": []}, b["jeton"])
s, i1 = r("POST", "eleve/indice", {}, b["jeton"]); s, i2 = r("POST", "eleve/indice", {}, b["jeton"])
ok(len(i1["vus"]) == 1 and len(i2["vus"]) == 2 and i2["vus"][0].startswith("Pars"), "coups de pouce dévoilés un par un, dans l'ordre")
ok(r("POST", "eleve/indice", {}, b["jeton"])[0] == 409, "plus de coup de pouce après le dernier")
# changement de variante en cours de séance : sans effet sur la séance commencée
cfg["eleves"] = {a["id"]: {"variante": "exigeante"}}
r("PUT", f"classes/{code}/config", cfg, J)
s, ma = r("GET", "eleve/moi", None, a["jeton"])
ok("12" in ma["config"]["tache"], "la variante reste fixée pour la séance commencée")
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": [{"texte": "5 + 7"}, {"texte": "2 × (5 + 7)"}], "ideesApres": []}, a["jeton"])
s, v = r("POST", "eleve/verifier", {}, a["jeton"])
ok([x["statut"] for x in v["retours"]] == ["juste", "a_revoir"], f"vérification avec le résultat de la variante (12) : {[x['statut'] for x in v['retours']]}")
ok(r("POST", "eleve/ia", {"echanges": [{"role": "el", "texte": "aide"}]}, b["jeton"])[0] == 403, "IA refusée tant que l'élève n'a pas écrit d'idée (réflexion d'abord)")
r("PUT", "eleve/seance/1", {"phase": "ia", "chargeDebut": 3, "ideesAvant": [{"texte": "3 × 8"}], "ideesApres": []}, b["jeton"])
s, ia = r("POST", "eleve/ia", {"echanges": [{"role": "el", "texte": "aide"}]}, b["jeton"])
ok(s == 200, "l'IA répond ensuite (avec les coups de pouce déjà donnés dans son contexte)")
tr = r("GET", f"classes/{code}/traces", None, J)[1]
ok(tr[a["id"]]["seances"]["1"]["variante"] == "accessible" and tr[b["id"]]["seances"]["1"]["indicesVus"] == 2, "variante et coups de pouce visibles côté enseignant")
