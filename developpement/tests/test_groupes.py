# Test des groupes de besoin et de la lecture à voix haute (côté serveur). Lancer d'abord :
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8798 --base /tmp/t8.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8798}/api/"
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
code = r("POST", "classes", {"nom": "Groupes"}, J)[1]["code"]
cfg = r("GET", f"classes/{code}/config", None, J)[1]
ok({k: cfg["lecture"][k] for k in ("active", "langue")} == {"active": True, "langue": "fr-FR"}, "lecture activée en français par défaut")
a = r("POST", "eleve/connexion", {"code": code, "pseudo": "Ana"})[1]; b = r("POST", "eleve/connexion", {"code": code, "pseudo": "Bob"})[1]
cfg.update(tache="t", seance=1, ouverte=True, groupes={a["id"]: "atelier", b["id"]: "defi", "x": "pirates"},
           lecture={"active": True, "langue": "en-GB"}, eleves={a["id"]: {"ordre": "ia", "mode": "elements"}, b["id"]: {"ordre": "reflexion", "mode": "questionner", "retrait": True}})
s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
ok(cfg["groupes"] == {a["id"]: "atelier", b["id"]: "defi"}, "groupes validés (groupe inconnu retiré)")
s, ma = r("GET", "eleve/moi", None, a["jeton"]); s, mb = r("GET", "eleve/moi", None, b["jeton"])
ok(ma["groupe"] == "atelier" and mb["groupe"] == "defi", "chaque élève connaît son groupe")
ok({k: ma["lecture"][k] for k in ("active", "langue")} == {"active": True, "langue": "en-GB"}, "réglage de lecture transmis à l'élève")
cfg["lecture"] = {"active": False, "langue": "klingon"}
s, cfg = r("PUT", f"classes/{code}/config", cfg, J)
ok({k: cfg["lecture"][k] for k in ("active", "langue")} == {"active": False, "langue": "fr-FR"}, "langue inconnue ramenée au français")
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 3}, b["jeton"])
s, t = r("GET", f"classes/{code}/traces", None, J)
ok(t[b["id"]]["seances"]["1"]["ordre"] == "autonomie", "le groupe défi applique le retrait de l'IA")
