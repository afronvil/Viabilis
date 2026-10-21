# Mode hors ligne (clé USB) : kit de la classe, travail sur l'ordinateur de l'étudiant sans IA ni page enseignant, export puis import.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8812 --base /tmp/t18.sqlite3
# Le test lance lui-même le serveur hors ligne, sur une base jetable.
import json, os, subprocess, sys, tempfile, time, urllib.error, urllib.request
ICI = os.path.dirname(os.path.abspath(__file__))
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8812}/api/"
ok = 0


def r(m, url, c=None, j=None):
    q = urllib.request.Request(url, method=m, data=json.dumps(c).encode() if c is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        return json.load(urllib.request.urlopen(q))
    except urllib.error.HTTPError as e:
        return {"statut": e.code, **json.loads(e.read() or b"{}")}


def verif(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("OK  ", msg)


# ---------- en ligne : une classe à deux séances, avec vérification par l'IA et exercices
M = {m["id"]: m for m in json.load(open(os.path.join(ICI, "web", "commun", "modeles.json"), encoding="utf-8"))["modeles"]}
J = r("POST", B + "enseignant/connexion", {"motdepasse": "motdepasse-test"})["jeton"]
code = r("POST", B + "classes", {"nom": "Linux hors ligne"}, J)["code"]
cfg = r("GET", B + f"classes/{code}/config", j=J)
for k, mid in ((1, "lin-4h-systeme"), (2, "lin-4h-texte")):
    m = M[mid]
    cfg = r("PUT", B + f"classes/{code}/config", {**cfg, "modele": mid, "tache": m["tache"], "indices": m["indices"], "saisieCode": True, "public": "superieur",
            "verification": {**cfg["verification"], **m["verification"]}, "exercices": {"actifs": True, "nombre": 3, "placement": "apres", "niveau": 2},
            "seance": k, "ouvertes": [1], "ouverte": k == 1, "galerie": {"1": ["une idée d'un autre élève"]}}, J)
gift = open(os.path.join(ICI, "exemples", "master", "linux_niveau2.gift"), encoding="utf-8").read()
verif(r("POST", B + f"classes/{code}/exercices/import", {"contenu": gift, "format": "gift", "niveau": 2, "source": "linux_niveau2.gift"}, J)["importes"] == 8, "banque importée en ligne")
lou = r("POST", B + "eleve/connexion", {"code": code, "pseudo": "Lou"})                 # une élève en ligne, homonyme de l'étudiante hors ligne
r("PUT", B + "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": [{"texte": "ls"}]}, lou["jeton"])
sami = r("POST", B + "eleve/connexion", {"code": code, "pseudo": "Sami"})

# ---------- le kit : séances et exercices, sans critères ni données des autres élèves
kit = r("GET", B + f"classes/{code}/kit", j=J)
k_cfg = kit["classe"]["config"]
verif(kit["format"] == "viabilis-kit" and kit["classe"]["code"] == code and len(kit["exercices"]) == 8, "kit : la classe et ses exercices")
verif(k_cfg["verification"]["criteres"] == "" and all(a["verification"]["criteres"] == "" for a in k_cfg["archives"].values()), "kit : aucun critère de réussite (ils contiennent les réponses)")
verif(k_cfg["eleves"] == {} and k_cfg["galerie"] == {} and k_cfg["groupes"] == {} and "Lou" not in json.dumps(kit), "kit : rien sur les autres élèves")
verif(k_cfg["ouvertes"] == [1, 2], "kit : toutes les séances ouvertes, l'étudiant avance à son rythme")
verif(r("GET", B + f"classes/{code}/kit?toutes=0", j=J)["classe"]["config"]["ouvertes"] == [1], "kit : ou seulement les séances ouvertes en classe")
verif(r("GET", B + f"classes/{code}/kit")["statut"] == 401, "kit : réservé à l'enseignant")

# ---------- hors ligne, sur l'ordinateur de l'étudiante
dossier = tempfile.mkdtemp()
with open(os.path.join(dossier, "kit.json"), "w", encoding="utf-8") as f:
    json.dump(kit, f)
env = {k: v for k, v in os.environ.items() if not k.startswith("VIABILIS_")}             # aucun mot de passe ni clé d'API sur la clé USB
port = 8812 + 40
hl = subprocess.Popen([sys.executable, os.path.join(ICI, "serveur.py"), "--hors-ligne", os.path.join(dossier, "kit.json"), "--port", str(port), "--sans-navigateur"],
                      env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    H = f"http://127.0.0.1:{port}/api/"
    for _ in range(50):
        try:
            urllib.request.urlopen(H + "hors-ligne"); break
        except Exception:
            time.sleep(0.1)
    verif(r("GET", H + "hors-ligne") == {"code": code, "nom": "Linux hors ligne", "kit": kit["kit"]}, "hors ligne : la page élève connaît la classe du kit")
    verif(r("POST", H + "enseignant/connexion", {"motdepasse": "motdepasse-test"})["statut"] == 403, "hors ligne : pas de connexion enseignant")
    verif(urllib.request.urlopen(f"http://127.0.0.1:{port}/enseignant/").geturl().endswith("/eleve/"), "hors ligne : la page enseignant renvoie vers la page élève")
    verif(urllib.request.urlopen(f"http://127.0.0.1:{port}/eleve/app.js").headers["Content-Type"].startswith("text/javascript"), "les scripts sont servis comme JavaScript (Windows)")
    lea = r("POST", H + "eleve/connexion", {"code": code, "pseudo": "Lou", "nouveau": True})
    moi = r("GET", H + "eleve/moi?seance=1", j=lea["jeton"])
    verif(moi["horsLigne"] and [o["seance"] for o in moi["ouvertes"]] == [1, 2], "hors ligne : l'étudiante voit les deux séances")
    rep = r("PUT", H + "eleve/seance/1?seance=1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": "mkdir -p projet_microbio/donnees"}]}, lea["jeton"])
    verif(rep["ordre"] == "autonomie", "hors ligne : travail en autonomie, sans IA")
    verif(r("POST", H + "eleve/ia?seance=1", {"echanges": []}, lea["jeton"])["statut"] == 403, "hors ligne : l'IA est refusée")
    verif(r("POST", H + "eleve/verifier?seance=1", {}, lea["jeton"])["statut"] == 403, "hors ligne : la vérification par l'IA est refusée")
    r("POST", H + "eleve/indice?seance=1", {}, lea["jeton"])
    exos = r("GET", H + "eleve/exercices?seance=1", j=lea["jeton"])
    verif(len(exos) == 3, "hors ligne : exercices tirés dans la banque du kit")
    corr = r("POST", H + f"eleve/exercices/{exos[0]['id']}/reponse?seance=1", {"reponse": "0", "duree": 12}, lea["jeton"])
    verif("score" in corr or "fini" in corr, "hors ligne : exercice corrigé sur place")
    r("PUT", H + "eleve/seance/2?seance=2", {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": [{"texte": "awk '{print $3}' comptages.txt"}]}, lea["jeton"])
    travail = r("GET", H + "eleve/export", j=lea["jeton"])
    verif(travail["format"] == "viabilis-travail" and travail["kit"] == kit["kit"] and {t["seance"] for t in travail["traces"]} == {1, 2}
          and len(travail["reponses"]) == 1 and travail["indices_vus"], "export : séances, exercice et coup de pouce")
    # un second étudiant hors ligne, homonyme d'un élève en ligne sans travail
    sam = r("POST", H + "eleve/connexion", {"code": code, "pseudo": "Sami", "nouveau": True})
    r("PUT", H + "eleve/seance/1?seance=1", {"phase": "reflexion", "chargeDebut": 3, "ideesAvant": [{"texte": "pwd"}]}, sam["jeton"])
    travail_sami = r("GET", H + "eleve/export", j=sam["jeton"])
finally:
    hl.terminate()
    hl.wait()

# ---------- retour en ligne : l'enseignante importe le travail
res = r("POST", B + f"classes/{code}/import-eleve", {"travail": travail}, J)
verif(res["renomme"] and res["eleve"] == "Lou 2" and res["importees"] == [1, 2], "import : pseudonyme déjà pris, l'étudiante devient « Lou 2 »")
tr = r("GET", B + f"classes/{code}/traces", j=J)
d = tr[res["id"]]
verif(d["pseudo"] == "Lou 2" and d["seances"]["1"]["ordre"] == "autonomie" and d["seances"]["1"]["exercices"][0]["duree"] == 12
      and d["seances"]["1"]["indicesVus"] == 1 and "awk" in d["seances"]["2"]["ideesAvant"][0]["texte"], "import : séances, exercices et coups de pouce dans le suivi")
verif(tr[lou["id"]]["seances"]["1"]["ideesAvant"][0]["texte"] == "ls", "import : le travail de l'élève en ligne n'est pas touché")
n_eleves = len(tr)
res2 = r("POST", B + f"classes/{code}/import-eleve", {"travail": travail}, J)
verif(res2["id"] == res["id"] and not res2["renomme"] and len(r("GET", B + f"classes/{code}/traces", j=J)) == n_eleves, "réimport du même fichier : même élève, pas de doublon")
lou2 = r("POST", B + "eleve/connexion", {"code": code, "pseudo": "Lou 2"})            # elle continue en ligne, puis rapporte un vieux fichier
r("PUT", B + "eleve/seance/1", {"phase": "reflexion", "chargeDebut": 2, "ideesAvant": [{"texte": "travail en ligne, plus récent"}]}, lou2["jeton"])
res3 = r("POST", B + f"classes/{code}/import-eleve", {"travail": travail}, J)
verif(res3["gardees"] == [1] and res3["importees"] == [2], "un fichier plus ancien ne remplace pas le travail fait en ligne depuis")
abime = {**travail, "traces": travail["traces"][:1]}
verif(r("POST", B + f"classes/{code}/import-eleve", {"travail": abime}, J)["statut"] == 400, "fichier modifié : refusé")
autre = r("POST", B + "classes", {"nom": "Autre"}, J)["code"]
verif(r("POST", B + f"classes/{autre}/import-eleve", {"travail": travail}, J)["statut"] == 400, "fichier d'une autre classe : refusé")
res4 = r("POST", B + f"classes/{code}/import-eleve", {"travail": travail_sami, "fusionner": True}, J)
verif(res4["fusionne"] and res4["id"] == sami["id"] and res4["eleve"] == "Sami", "option : rattacher le travail à l'élève du même pseudonyme")
print(f"test_hors_ligne : {ok} vérifications réussies")
