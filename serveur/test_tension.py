# Multiplicateur de viabilité : tension signée et direction, renvoyés avec le statut de viabilité.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8815 --base /tmp/t19.sqlite3
import json, sys, urllib.request
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8815}/api/"
def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None, headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    with urllib.request.urlopen(q) as x: return json.loads(x.read())
def ok(cond, msg):
    print(("OK   " if cond else "ÉCHEC ") + msg)
    assert cond, msg
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", "classes", {"nom": "Tension"}, J)["code"]
etats = {"moyen": {"C": .5, "A": .6, "M": .6, "D": .6, "niveau": 3}, "ennui": {"C": .1, "A": 1, "M": .84, "D": .71, "niveau": 4},
         "crise": {"C": .9, "A": .25, "M": .2, "D": .3, "niveau": 5}, "proche": {"C": .69, "A": .75, "M": .32, "D": .86, "niveau": 3}}
v = r("POST", f"classes/{code}/viabilite", {"seance": 4, "eleves": etats}, J)
m = {k: v[k]["marge"] for k in etats}
ok(all(set(x) >= {"derive", "dansDomaine", "retourSpontane", "noyau", "bassin"} for x in m.values()), "chaque élève reçoit son multiplicateur")
ok(m["moyen"]["bassin"]["tension"] <= -0.25, "élève moyen : grande marge (tension négative)")
ok(m["crise"]["bassin"]["tension"] > 0 and m["crise"]["bassin"]["vecteur"][0] < 0 and m["crise"]["bassin"]["vecteur"][1] > 0,
   "surcharge et dépendance : correction nécessaire, dans le sens « alléger » et « plus d'autonomie »")
ok(not m["ennui"]["dansDomaine"] and m["ennui"]["retourSpontane"] and v["ennui"]["statut"] == "hors_noyau",
   "ennui : hors du domaine maintenant, mais retour prévu sans aide (et non « rupture inévitable »)")
ok(-0.3 < m["proche"]["bassin"]["tension"] < 0 and m["proche"]["bassin"]["vecteur"][0] > 0, "charge élevée : marge, avec la surcharge comme menace la plus proche")
# prédictions démenties
import noyau
x0 = (0.5, 0.6, 0.5, 0.6)
y = noyau.avance(x0, (0.0, 0.6, 1.0), noyau.META["ells"][2])
coherent = [{"t": 2, "niveau": 3, "C": x0[0], "A": x0[1], "M": x0[2], "D": x0[3], "u": [0, 0, 1]},
            {"t": 3, "niveau": 3, "C": y[0], "A": y[1], "M": y[2], "D": y[3], "u": [0, 0.6, 1]}]
ennui = [{"t": k, "niveau": 3, "C": 0.1, "A": 1, "M": 0.9, "D": 0.7, "u": [0, 0, 1]} for k in range(3)]
v = r("POST", f"classes/{code}/viabilite", {"seance": 4, "eleves": {"a": {**etats["moyen"], "trajet": coherent}, "b": {**etats["ennui"], "trajet": ennui}}}, J)
pa, pb = v["a"]["prediction"], v["b"]["prediction"]
ok(not pa["comparaisons"][0]["dementie"] and pa["dementiesDeSuite"] == 0, "évolution conforme au modèle : prédiction confirmée")
ok(pb["dementiesDeSuite"] == 2 and pb["comparaisons"][-1]["variable"] == "charge" and pb["comparaisons"][-1]["retourNonRealise"],
   "charge restée basse deux fois alors que le modèle prévoyait un retour : prédiction démentie deux fois de suite")
trou = [dict(ennui[0]), dict(ennui[2])]
ok(r("POST", f"classes/{code}/viabilite", {"seance": 4, "eleves": {"c": {**etats["ennui"], "trajet": trou}}}, J)["c"]["prediction"]["comparaisons"] == [],
   "séance manquée : pas de comparaison")
# multiplicateurs de viabilité de l'article (KKT, horizon 10, sauvegarde / progression)
import multiplicateurs as MU
v = r("POST", f"classes/{code}/viabilite", {"seance": 3, "eleves": {"d": {"C": 0.75, "A": 0.33, "M": 0.4, "D": 0.5, "niveau": 5},
                                                                      "m": etats["moyen"]}}, J)
md, mm = v["d"]["multiplicateurs"], v["m"]["multiplicateurs"]
ok(md["sauvegarde"] and md["anticipateurs"]["contrainte"] == "dependance" and md["anticipateurs"]["aide"][0] > 0,
   "charge élevée, agentivité au seuil : sauvegarde, motivée par la dépendance")
ok(v["d"]["natureAide"] in ("sauvegarde", None) and not mm["sauvegarde"] and mm["anticipateurs"]["cout"] == 0, "élève moyen : aucune aide nécessaire sur 10 séances")
q = MU.qp(0.8567, 0.3313, 0.7903, 0.3)          # état fourni par le code Julia de l'article (intervention non nulle)
ok(q is not None and q[1] > 0 and q[2][2] > 0, "au bord du seuil de dépendance : intervention minimale non nulle, prix du seuil de dépendance positif")
h = 1e-6
def cout(seuil):
    MU.KD["Amin"] = seuil; c = MU.qp(0.8567, 0.3313, 0.7903, 0.3)[1]; MU.KD["Amin"] = 0.30; return c
ok(abs((cout(0.30 + h) - cout(0.30 - h)) / (2 * h) - q[2][2]) < 1e-5 * max(1, q[2][2]), "propriété de prix : le multiplicateur égale la dérivée du coût par rapport au seuil")
print("test_tension : réussi")
