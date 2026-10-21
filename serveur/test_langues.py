# Langues de l'interface : langue de la classe, messages du serveur traduits, retours de vérification dans la langue de la classe.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8816 --base /tmp/t22.sqlite3
import json, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8816}/api/"
n_ok = 0
def r(m, p, c=None, j=None, langue=None):
    h = {"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {}), **({"X-Viabilis-Langue": langue} if langue else {})}
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None, headers=h)
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

J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "Classe catalane", "langue": "ca"}, J)[1]["code"]
cfg = r("GET", f"classes/{code}/config", j=J)[1]
ok(cfg["langue"] == "ca", "une classe créée depuis une page en catalan est en catalan")
s, d = r("POST", "eleve/classe", {"code": code})
ok(d["langue"] == "ca", "l'élève apprend la langue de la classe avant de choisir son pseudonyme")
ok(r("POST", "eleve/classe", {"code": "ZZZZZZ"}, langue="ca")[1]["erreur"] == "Codi de classe desconegut.", "message d'erreur en catalan")
ok(r("POST", "eleve/classe", {"code": "ZZZZZZ"}, langue="en")[1]["erreur"] == "Unknown class code.", "message d'erreur en anglais")
ok(r("POST", "eleve/classe", {"code": "ZZZZZZ"})[1]["erreur"] == "Code de classe inconnu.", "sans langue : français")
cfg.update(langue="xx")
r("PUT", f"classes/{code}/config", cfg, J)
ok(r("GET", f"classes/{code}/config", j=J)[1]["langue"] == "fr", "langue inconnue : français")
cfg.update(seance=1, ouverte=True, ouvertes=[1], langue="ca", tache="Paga 10 € amb monedes.",
           verification={"mode": "calcul", "cible": 10, "nombres": "1 ; 2 ; 5", "attendu": 10, "criteres": "", "maximum": 3, "uneFois": False})
r("PUT", f"classes/{code}/config", cfg, J)
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lluna"})[1]["jeton"]
moi = r("GET", "eleve/moi", j=e)[1]
ok(moi["config"]["langue"] == "ca", "la séance de l'élève porte la langue de la classe")
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": "5 + 5"}, {"texte": "5 + 2"}], "ideesApres": []}, e)
s, v = r("POST", "eleve/verifier", {}, e)
ok(s == 200 and v["retours"][0]["retour"] == "Correcte: aquest càlcul val 10.", "retour de vérification par calculs en catalan")
ok("no n'hi ha prou" in v["retours"][1]["retour"], "retour « pas assez » en catalan")
print(f"test_langues : {n_ok} vérifications réussies")
