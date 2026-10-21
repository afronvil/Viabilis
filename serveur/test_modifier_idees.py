# Modifier ou retirer une idée en cours de séance : la trace garde l'ancienne version et l'idée retirée (pour l'enseignant et la recherche).
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8813 --base /tmp/t19.sqlite3
import json, sys, urllib.request
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8813}/api/"
ok = 0


def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    return json.load(urllib.request.urlopen(q))


def verif(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("OK  ", msg)


J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", "classes", {"nom": "Modifier ses idées"}, J)["code"]
cfg = r("GET", f"classes/{code}/config", j=J)
cfg = r("PUT", f"classes/{code}/config", {**cfg, "tache": "Trouve des façons de faire 10.", "seance": 1, "ouvertes": [1], "ouverte": True}, J)
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Noa"})
# l'élève a écrit trois idées, en modifie une et en retire une autre (ce que fait la page élève)
corps = {"phase": "reflexion", "chargeDebut": 3,
         "ideesAvant": [{"t": "2026-10-11T10:00:00Z", "texte": "5+5"},
                        {"t": "2026-10-11T10:01:00Z", "texte": "2+2+2+2+2", "modifiee": "2026-10-11T10:03:00Z",
                         "avant": [{"texte": "2+2+2+2", "t": "2026-10-11T10:01:00Z"}]}],
         "ideesRetirees": [{"t": "2026-10-11T10:02:00Z", "texte": "3+3+3", "retiree": "2026-10-11T10:04:00Z", "depuis": "avant"}]}
r("PUT", "eleve/seance/1", corps, e["jeton"])
s = r("GET", f"classes/{code}/traces", j=J)[e["id"]]["seances"]["1"]
verif([i["texte"] for i in s["ideesAvant"]] == ["5+5", "2+2+2+2+2"], "les idées gardées, dans leur version modifiée")
verif(s["ideesAvant"][1]["avant"][0]["texte"] == "2+2+2+2" and s["ideesAvant"][1]["modifiee"], "l'ancienne version reste dans la trace")
verif(s["ideesRetirees"][0]["texte"] == "3+3+3" and s["ideesRetirees"][0]["depuis"] == "avant", "l'idée retirée reste dans la trace")
moi = r("GET", "eleve/moi?seance=1", j=e["jeton"])
verif([i["texte"] for i in moi["seances"]["1"]["ideesAvant"]] == ["5+5", "2+2+2+2+2"], "l'élève retrouve ses idées modifiées en revenant")
print(f"test_modifier_idees : {ok} vérifications réussies")
