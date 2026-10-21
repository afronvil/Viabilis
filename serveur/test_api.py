import json, sys, urllib.request
# Test de bout en bout de l API. Lancer d abord :
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8790 --base /tmp/test.sqlite3
B = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8790}/api/"
def r(m, p, corps=None, j=None):
    req = urllib.request.Request(B+p, data=None if corps is None else json.dumps(corps).encode(), method=m,
        headers={"Content-Type":"application/json", **({"Authorization":"Bearer "+j} if j else {})})
    try:
        with urllib.request.urlopen(req) as x: t=x.read().decode(); return x.status, (json.loads(t) if x.headers.get_content_type()=="application/json" else t)
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
print("mauvais mdp", r("POST","enseignant/connexion",{"motdepasse":"x"}))
s, d = r("POST","enseignant/connexion",{"motdepasse":"motdepasse-test"}); J=d["jeton"]
s, k = r("POST","classes",{"nom":"4e B"},J); code=k["code"]; print("classe", s, k)
print("élève sans séance ia", r("POST","eleve/ia",{},"faux"))
s, cfg = r("GET",f"classes/{code}/config",None,J)
cfg.update(tache="Trouvez des usages d'un trombone", seance=1, ouverte=True, ordre="adaptatif", minIdees=2)
print("config", r("PUT",f"classes/{code}/config",cfg,J)[0])
s, e1 = r("POST","eleve/connexion",{"code":code,"pseudo":"Panda 7","nouveau":True}); print("connexion élève", s)
print("pseudo pris", r("POST","eleve/connexion",{"code":code,"pseudo":"Panda 7","nouveau":True}))
s, e2 = r("POST","eleve/connexion",{"code":code.lower(),"pseudo":"Lynx"})
s, moi = r("GET","eleve/moi",None,e1["jeton"]); print("moi", moi["config"]["tache"], moi["config"]["seance"])
# élève 1 : peu chargé -> réflexion d'abord
t = {"phase":"reflexion","chargeDebut":2,"debut":"2026-10-03T10:00:00+00:00","ideesAvant":[],"ideesApres":[],"echanges":[],"ordre":"ia"}
print("début élève 1 (tente de forcer ia)", r("PUT","eleve/seance/1",t,e1["jeton"]))
print("IA refusée avant les idées", r("POST","eleve/ia",{"echanges":[{"role":"el","texte":"aide"}]},e1["jeton"]))
t["ideesAvant"]=[{"texte":"attacher des feuilles"},{"texte":"ouvrir le tiroir de la carte SIM"}]; t["phase"]="ia"
r("PUT","eleve/seance/1",t,e1["jeton"])
print("IA acceptée", r("POST","eleve/ia",{"echanges":[{"role":"el","texte":"je cherche d'autres idées"}]},e1["jeton"]))
# élève 2 : surchargé -> IA d'abord
t2 = {"phase":"reflexion","chargeDebut":5,"debut":"2026-10-03T10:00:00+00:00","ideesAvant":[],"ideesApres":[{"texte":"faire un bijou"}],"echanges":[]}
print("début élève 2", r("PUT","eleve/seance/1",t2,e2["jeton"]))
print("IA directe élève 2", r("POST","eleve/ia",{"echanges":[{"role":"el","texte":"je ne sais pas"}]},e2["jeton"])[0])
# enseignant : retrait individuel
s, cfg = r("GET",f"classes/{code}/config",None,J); cfg["eleves"]={e1["id"]:{"ordre":"reflexion","mode":"questionner","retrait":True}, "x":{"ordre":"pirate"}}
s, cfg2 = r("PUT",f"classes/{code}/config",cfg,J); print("config validée", cfg2["eleves"])
s, tr = r("GET",f"classes/{code}/traces",None,J); print("traces", {v["pseudo"]: list(v["seances"]) for v in tr.values()})
s, csvt = r("GET",f"classes/{code}/export.csv",None,J); print("csv", csvt.splitlines()[:3])
print("élève lit traces classe", r("GET",f"classes/{code}/traces",None,e1["jeton"]))
print("effacer élève", r("DELETE",f"classes/{code}/eleves/{e2['id']}",None,J))
s, tr = r("GET",f"classes/{code}/traces",None,J); print("après effacement", [v["pseudo"] for v in tr.values()])
print("jeton élève effacé", r("GET","eleve/moi",None,e2["jeton"]))
