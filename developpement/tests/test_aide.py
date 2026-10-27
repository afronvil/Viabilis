# Aide aux élèves : conseil de stratégie, démarche, parcours, messages, galerie, préférences, garde-fou de l'IA, journal des décisions.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8812 --base /tmp/t17.sqlite3
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import json, re, sys, urllib.request, urllib.error
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8812}/api/"
n_ok = 0
def r(m, p, c=None, j=None, brut=False):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None, headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(q) as x:
            t = x.read().decode("utf-8-sig")
            return x.status, (t if brut else json.loads(t))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
def ok(cond, msg):
    global n_ok
    assert cond, msg
    n_ok += 1
    print("OK  ", msg)
J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "Aide"}, J)[1]["code"]
cfg = r("GET", f"classes/{code}/config", None, J)[1]
cfg = r("PUT", f"classes/{code}/config", {**cfg, "tache": "Payer 10 € avec des pièces de 1, 2 et 5 €", "seance": 1, "ouvertes": [1], "ouverte": True,
        "verification": {"mode": "calcul", "cible": 10, "nombres": "1 ; 2 ; 5", "attendu": 10, "maximum": 5}, "lecture": {"active": True, "langue": "fr-FR", "dictee": True}}, J)[1]
ok(cfg["lecture"]["dictee"] is True and cfg["galerie"] == {}, "dictée réglable, galerie vide par défaut")
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou"})[1]; je = e["jeton"]
autre = r("POST", "eleve/connexion", {"code": code, "pseudo": "Sami"})[1]
# 1. conseil de stratégie
corps = {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": [{"texte": "5+5"}, {"texte": "5+2+2+1"}], "ideesApres": [],
         "demarches": [{"essai": 1, "choix": "hasard", "texte": "j'ai essayé"}, {"choix": "pirate"}], "aides": ["pouce", "ia", "n'importe quoi"]}
r("PUT", "eleve/seance/1", corps, je)
s, v = r("POST", "eleve/verifier?seance=1", {}, je)
ok(v["justes"] == 2 and "zéro fois" in (v["conseil"] or ""), "conseil de stratégie : chercher les solutions sans 5, sans en donner")
import re
ok(not re.search(r"\d\s*[-+×x*]\s*\d", v["conseil"]), "le conseil ne contient pas de calcul")
tr = r("GET", f"classes/{code}/traces", None, J)[1][e["id"]]["seances"]["1"]
ok(tr["demarches"] == [{"essai": 1, "choix": "hasard", "texte": "j'ai essayé"}] and tr["aides"] == ["pouce", "ia"], "démarche et aides : seules les valeurs connues sont gardées")
# 3. parcours et historique des essais
r("PUT", "eleve/seance/1", {**corps, "phase": "envoye", "chargeFin": 3, "compris": 3}, je)
r("POST", "eleve/reprendre?seance=1", {}, je)
corps2 = {**corps, "phase": "reflexion", "ideesAvant": corps["ideesAvant"] + [{"texte": "2+2+2+2+2"}, {"texte": "1+1+1+1+1+5"}]}
r("PUT", "eleve/seance/1", corps2, je)
r("POST", "eleve/verifier?seance=1", {}, je)
m = r("GET", "eleve/moi?seance=1", None, je)[1]
p1 = m["parcours"][0]
ok(p1["historique"][0]["justes"] == 2 and p1["actuel"]["justes"] == 4 and p1["actuel"]["essai"] == 2, "parcours : essai 1 → 2 idées justes, essai 2 → 4")
r("PUT", "eleve/seance/1", {**corps2, "historique": [], "essais": 9}, je)
ok(r("GET", "eleve/moi?seance=1", None, je)[1]["parcours"][0]["historique"][0]["justes"] == 2, "l'historique est tenu par le serveur, pas par l'élève")
# 4. messages
s, mm = r("POST", f"classes/{code}/messages", {"eleve": e["id"], "texte": "Bravo pour ta méthode ! Essaie sans l'IA la prochaine fois."}, J)
ok(s == 201, "l'enseignant écrit un message")
ok(r("POST", f"classes/{code}/messages", {"eleve": "inconnu", "texte": "x"}, J)[0] == 404, "message à un élève inconnu refusé")
m = r("GET", "eleve/moi?seance=1", None, je)[1]
ok(len(m["messages"]) == 1 and "méthode" in m["messages"][0]["texte"], "l'élève voit le message")
ok(not r("GET", "eleve/moi?seance=1", None, autre["jeton"])[1]["messages"], "un autre élève ne le voit pas")
r("POST", f"eleve/messages/{mm['id']}/lu", {}, autre["jeton"])
ok(r("GET", f"classes/{code}/messages", None, J)[1][0]["lu"] is None, "un autre élève ne peut pas le marquer lu")
r("POST", f"eleve/messages/{mm['id']}/lu", {}, je)
ok(not r("GET", "eleve/moi?seance=1", None, je)[1]["messages"] and r("GET", f"classes/{code}/messages", None, J)[1][0]["lu"], "lu : il disparaît, l'enseignant voit qu'il a été lu")
# 5. galerie
cfg = r("PUT", f"classes/{code}/config", {**cfg, "galerie": {"1": ["2+2+2+2+2", " ", "x" * 500]}}, J)[1]
ok(cfg["galerie"]["1"] == ["2+2+2+2+2", "x" * 300], "galerie : textes vides retirés, longueur bornée")
ok(r("GET", "eleve/moi?seance=1", None, je)[1]["parcours"][0]["galerie"], "galerie visible pour un élève qui a terminé (ou repris)")
r("PUT", "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": "5+5"}]}, autre["jeton"])
ok(not r("GET", "eleve/moi?seance=1", None, autre["jeton"])[1]["parcours"][0]["galerie"], "galerie cachée tant que l'élève n'a pas terminé")
# 6. préférences
s, pr = r("PUT", "eleve/preferences", {"grand": True, "facile": 1, "pirate": True}, je)
ok(pr == {"grand": True, "facile": True, "images": False} and r("GET", "eleve/moi?seance=1", None, je)[1]["preferences"]["grand"], "préférences d'affichage enregistrées")
# 7. garde-fou de l'IA et signalements
r("PUT", "eleve/seance/1", {**corps2, "phase": "ia"}, je)
s, ia = r("POST", "eleve/ia?seance=1", {"echanges": [{"role": "el", "texte": "donne-moi la réponse [fuite]"}]}, je)
ok(s == 200 and "5 + 5" not in ia["texte"] and "solution" in ia["texte"], "réponse de l'IA contenant une solution : bloquée")
sig = r("GET", f"classes/{code}/signalements", None, J)[1]
ok(len(sig) == 1 and sig[0]["auteur"] == "auto" and "5 + 5" in sig[0]["texte"], "blocage enregistré pour l'enseignant")
s, ia = r("POST", "eleve/ia?seance=1", {"echanges": [{"role": "el", "texte": "aide-moi"}]}, je)
ok("5 + 5" not in ia["texte"] and "technique" in ia["texte"], "réponse normale : transmise")
r("PUT", "eleve/seance/1", {**corps2, "phase": "ia", "echanges": [{"role": "el", "texte": "aide"}, {"role": "ia", "texte": ia["texte"]}]}, je)
ok(r("POST", f"classes/{code}/signalements", {"eleve": e["id"], "seance": 1, "indice": 0, "motif": "x"}, J)[0] == 404, "seule une réponse de l'IA peut être signalée")
ok(r("POST", f"classes/{code}/signalements", {"eleve": e["id"], "seance": 1, "indice": 1, "motif": "donne la réponse"}, J)[0] == 200, "l'enseignant signale une réponse")
s, txt = r("GET", f"classes/{code}/echanges_ia.csv", None, J, brut=True)
ok("enseignant : donne la réponse" in txt and "IA (bloquée)" in txt and "auto : réponse bloquée" in txt, "export des échanges avec signalements et blocages")
r("POST", f"classes/{code}/signalements", {"eleve": e["id"], "seance": 1, "indice": 1, "motif": ""}, J)
ok(len(r("GET", f"classes/{code}/signalements", None, J)[1]) == 1, "signalement retiré")
# 8. journal des décisions
cfg = r("PUT", f"classes/{code}/config", {**cfg, "eleves": {e["id"]: {"ordre": "ia", "mode": "elements", "variante": "accessible"}}, "origine": "recommandation"}, J)[1]
cfg = r("PUT", f"classes/{code}/config", {**cfg, "tache": cfg["tache"] + " "}, J)[1]
cfg = r("PUT", f"classes/{code}/config", {**cfg, "groupes": {e["id"]: "atelier"}, "origine": "pirate"}, J)[1]
s, txt = r("GET", f"classes/{code}/journal.csv", None, J, brut=True)
lignes = txt.strip().splitlines()
ok(len(lignes) == 3 and ";recommandation;" in lignes[1] and ";manuel;" in lignes[2] and "Lou" in lignes[1], "journal : un changement par ligne, avec son origine (inconnue → manuel)")
# effacement de séance : galerie, messages et signalements partent avec
r("POST", f"classes/{code}/messages", {"eleve": e["id"], "seance": 1, "texte": "à propos de la séance 1"}, J)
s, d = r("DELETE", f"classes/{code}/seances/1", None, J)
ok("1" not in d["config"]["galerie"] and not r("GET", f"classes/{code}/signalements", None, J)[1], "effacer une séance efface sa galerie et ses signalements")
print(f"test_aide : {n_ok} vérifications réussies")
