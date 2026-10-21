"""
Mode hors ligne (clé USB) : l'étudiant travaille sur son propre ordinateur, sans le serveur de la classe, puis rapporte son travail.

1. L'enseignante télécharge le « kit » de sa classe (onglet Données) : les séances et les exercices, sans les critères de réussite,
   sans les réglages ni les idées des autres élèves.
2. Sur l'ordinateur de l'étudiant, `serveur.py --hors-ligne kit.json` (ou un lanceur du dossier hors_ligne/) ouvre la page élève.
   Pas d'IA (l'étudiant travaille en autonomie) ni de page enseignant ; les exercices sont corrigés sur place.
3. L'étudiant exporte son travail (un fichier JSON) et le remet à l'enseignante, qui l'importe dans la classe : ses séances,
   exercices, vérifications et coups de pouce rejoignent le suivi comme s'il avait travaillé en ligne.
"""
import hashlib
import json
import re
import secrets

FORMAT_KIT, FORMAT_TRAVAIL, VERSION = "viabilis-kit", "viabilis-travail", 1
ID_ELEVE = re.compile(r"^e[0-9a-f]{16}$")
# champs d'une trace que le serveur accepte : ceux que l'élève envoie (PUT /api/eleve/seance/n) et ceux que le serveur y ajoute
CHAMPS_TRACE = {"phase", "tache", "debut", "fin", "chargeDebut", "chargeFin", "compris", "ideesAvant", "ideesApres", "ideesRetirees", "echanges",
                "premiereDemande", "ideesAvantAide", "bloque", "suite", "demarches", "aides", "essais", "historique", "ordre", "mode", "variante",
                "definitif", "correction"}


def controle(contenu):
    """Empreinte du contenu exporté : un fichier abîmé ou modifié à la main est refusé à l'import."""
    return hashlib.sha256(json.dumps(contenu, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ---------------------------------------------------------------- côté enseignant : préparer le kit
def preparer_kit(cl, cfg, exercices, maintenant, toutes=True):
    """Kit de la classe `cl` (ligne de la table classes) : `cfg` est la configuration normalisée, `exercices` les lignes de la banque."""
    cfg = json.loads(json.dumps(cfg))
    for c in [cfg] + list((cfg.get("archives") or {}).values()):
        if isinstance(c.get("verification"), dict):
            c["verification"]["criteres"] = ""           # les critères contiennent les réponses attendues
    cfg.update({"eleves": {}, "groupes": {}, "galerie": {}, "codePersonnel": False})   # rien sur les autres élèves
    if toutes:                                            # hors ligne, l'étudiant avance à son rythme : toutes les séances sont ouvertes
        existantes = [n for n in range(1, cfg["seance"] + 1) if n not in cfg.get("supprimees", [])
                      and (n == cfg["seance"] or str(n) in (cfg.get("archives") or {}))]
        cfg["ouvertes"], cfg["ouverte"] = existantes, bool(existantes)
    return {"format": FORMAT_KIT, "version": VERSION, "kit": secrets.token_hex(8), "cree": maintenant(),
            "classe": {"code": cl["code"], "nom": cl["nom"], "config": cfg},
            "exercices": [{k: x[k] for k in ("id", "titre", "type", "niveau", "actif", "donnees", "source")} for x in exercices]}


# ---------------------------------------------------------------- côté étudiant : charger le kit, exporter le travail
def charger_kit(cnx, chemin, maintenant):
    """Installe (ou met à jour) la classe du kit dans la base locale ; renvoie {code, nom, kit}."""
    with open(chemin, encoding="utf-8") as f:
        kit = json.load(f)
    if kit.get("format") != FORMAT_KIT or kit.get("version") != VERSION:
        raise SystemExit(f"{chemin} n'est pas un kit Viabilis : téléchargez-le depuis l'onglet Données de la page enseignant.")
    cl = kit["classe"]
    code = str(cl["code"])
    with cnx() as c:
        deja = c.execute("SELECT notes FROM classes WHERE code = ?", (code,)).fetchone()
        notes = json.dumps({"kit": kit["kit"]})
        if not deja:
            c.execute("INSERT INTO classes (code, nom, config, notes, cree) VALUES (?, ?, ?, ?, ?)",
                      (code, cl["nom"], json.dumps(cl["config"]), notes, maintenant()))
        elif json.loads(deja["notes"] or "{}").get("kit") != kit["kit"]:      # nouveau kit de la même classe : séances et exercices à jour
            c.execute("UPDATE classes SET nom = ?, config = ?, notes = ? WHERE code = ?", (cl["nom"], json.dumps(cl["config"]), notes, code))
        ids = [int(x["id"]) for x in kit["exercices"]]
        c.execute(f"DELETE FROM exercices WHERE classe = ? AND id NOT IN ({','.join('?' * len(ids)) or 'NULL'})", (code, *ids))
        for x in kit["exercices"]:                        # mêmes identifiants qu'en ligne : les réponses se rattachent à l'import
            c.execute("""INSERT INTO exercices (id, classe, titre, type, niveau, actif, donnees, source, cree) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                         ON CONFLICT(id) DO UPDATE SET titre = excluded.titre, type = excluded.type, niveau = excluded.niveau,
                         actif = excluded.actif, donnees = excluded.donnees, source = excluded.source""",
                      (int(x["id"]), code, x["titre"], x["type"], int(x["niveau"]), int(x["actif"]), x["donnees"], x["source"], maintenant()))
    return {"code": code, "nom": cl["nom"], "kit": kit["kit"]}


def exporter(c, e, maintenant):
    """Tout le travail de l'élève `e` (ligne de la table eleves), dans un fichier à remettre à l'enseignante."""
    lignes = lambda sql: [dict(r) for r in c.execute(sql, (e["id"],)).fetchall()]
    notes = c.execute("SELECT notes FROM classes WHERE code = ?", (e["classe"],)).fetchone()
    contenu = {
        "format": FORMAT_TRAVAIL, "version": VERSION, "kit": json.loads(notes["notes"] or "{}").get("kit"), "classe": e["classe"], "exporte": maintenant(),
        "eleve": {"id": e["id"], "pseudo": e["pseudo"], "cree": e["cree"], "preferences": e["preferences"]},
        "traces": lignes("SELECT seance, donnees, maj FROM traces WHERE eleve = ?"),
        "reponses": lignes("SELECT seance, exercice, tentatives, score, premier_score, duree, maj, reponse FROM reponses WHERE eleve = ?"),
        "verifications": lignes("SELECT seance, nombre, donnees, maj FROM verifications WHERE eleve = ?"),
        "indices_vus": lignes("SELECT seance, nombre, maj FROM indices_vus WHERE eleve = ?"),
        "tirages": lignes("SELECT seance, ids FROM tirages WHERE eleve = ?"),
    }
    return {**contenu, "controle": controle(contenu)}


# ---------------------------------------------------------------- côté enseignant : importer le travail d'un étudiant
def _objet(texte):
    d = json.loads(texte) if isinstance(texte, str) else texte
    if not isinstance(d, dict):
        raise ValueError("donnée de séance invalide")
    return d


def importer(c, code, cfg, travail, fusionner, maintenant, nouveau_pin, pseudo_ok):
    """Ajoute le travail hors ligne d'un étudiant à la classe `code`. Une séance déjà plus récente dans la classe est gardée.

    Réimporter un fichier plus récent du même étudiant met ses séances à jour. Si un autre élève de la classe porte déjà ce pseudonyme,
    le travail est rattaché à cet élève quand `fusionner` est vrai ; sinon l'étudiant hors ligne reçoit un pseudonyme numéroté."""
    if not isinstance(travail, dict) or travail.get("format") != FORMAT_TRAVAIL or travail.get("version") != VERSION:
        raise ValueError("ce fichier n'est pas un travail exporté depuis Viabilis hors ligne")
    if travail.get("classe") != code:
        raise ValueError(f"ce fichier vient de la classe {travail.get('classe')}, pas de celle-ci ({code})")
    contenu = {k: v for k, v in travail.items() if k != "controle"}
    if controle(contenu) != travail.get("controle"):
        raise ValueError("le fichier a été modifié ou abîmé depuis son export")
    el = travail["eleve"]
    eid, pseudo = str(el["id"]), str(el["pseudo"]).strip()
    if not ID_ELEVE.match(eid) or not pseudo_ok.match(pseudo):
        raise ValueError("identifiant ou pseudonyme invalide")

    renomme, fusionne = None, False
    meme_id = c.execute("SELECT * FROM eleves WHERE id = ?", (eid,)).fetchone()
    if meme_id and meme_id["classe"] != code:             # identifiant déjà pris ailleurs (improbable) : on en crée un autre
        eid, meme_id = "e" + secrets.token_hex(8), None
    if meme_id:                                           # réimport du même étudiant
        cible = eid
    else:
        homonyme = c.execute("SELECT * FROM eleves WHERE classe = ? AND lower(pseudo) = lower(?)", (code, pseudo)).fetchone()
        if homonyme and fusionner:
            cible, fusionne = homonyme["id"], True
        else:
            if homonyme:
                pris = {r["p"] for r in c.execute("SELECT lower(pseudo) AS p FROM eleves WHERE classe = ?", (code,)).fetchall()}
                k = 2
                while f"{pseudo[:21]} {k}".lower() in pris:
                    k += 1
                pseudo = renomme = f"{pseudo[:21]} {k}"
            c.execute("INSERT INTO eleves (id, classe, pseudo, jeton, cree, pin, preferences) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (eid, code, pseudo, secrets.token_urlsafe(32), str(el.get("cree") or maintenant())[:40], nouveau_pin(),
                       el.get("preferences") if isinstance(el.get("preferences"), str) else None))
            cible = eid

    valides = {n for n in range(1, cfg["seance"] + 1) if n not in cfg.get("supprimees", [])}
    exos = {r["id"] for r in c.execute("SELECT id FROM exercices WHERE classe = ?", (code,)).fetchall()}
    importees, gardees, ignorees = [], [], []
    for t in travail.get("traces") or []:
        n = int(t["seance"])
        if n not in valides:
            ignorees.append(n)
            continue
        donnees = {k: v for k, v in _objet(t["donnees"]).items() if k in CHAMPS_TRACE}
        ici = c.execute("SELECT donnees, maj FROM traces WHERE eleve = ? AND seance = ?", (cible, n)).fetchone()
        if ici and str(ici["maj"] or "") >= str(t.get("maj") or "") and json.loads(ici["donnees"]) != donnees:
            gardees.append(n)                             # le travail fait ici est plus récent (à la seconde près : on garde celui de la classe)
            continue
        c.execute("""INSERT INTO traces (eleve, seance, donnees, maj) VALUES (?, ?, ?, ?)
                     ON CONFLICT(eleve, seance) DO UPDATE SET donnees = excluded.donnees, maj = excluded.maj""",
                  (cible, n, json.dumps(donnees, ensure_ascii=False), str(t.get("maj") or maintenant())[:40]))
        for table in ("reponses", "verifications", "indices_vus", "tirages"):
            c.execute(f"DELETE FROM {table} WHERE eleve = ? AND seance = ?", (cible, n))
        importees.append(n)
    a_jour = set(importees)
    for r in travail.get("reponses") or []:
        if int(r["seance"]) in a_jour and int(r["exercice"]) in exos:
            c.execute("INSERT OR REPLACE INTO reponses (eleve, seance, exercice, tentatives, score, premier_score, duree, maj, reponse) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (cible, int(r["seance"]), int(r["exercice"]), int(r.get("tentatives") or 0),
                       None if r.get("score") is None else float(r["score"]), None if r.get("premier_score") is None else float(r["premier_score"]),
                       None if r.get("duree") is None else int(r["duree"]), str(r.get("maj") or "")[:40],
                       None if r.get("reponse") is None else str(r["reponse"])[:2000]))
    for r in travail.get("verifications") or []:
        if int(r["seance"]) in a_jour:
            c.execute("INSERT OR REPLACE INTO verifications (eleve, seance, nombre, donnees, maj) VALUES (?, ?, ?, ?, ?)",
                      (cible, int(r["seance"]), int(r.get("nombre") or 0), json.dumps(_objet(r.get("donnees") or "{}"), ensure_ascii=False), str(r.get("maj") or "")[:40]))
    for r in travail.get("indices_vus") or []:
        if int(r["seance"]) in a_jour:
            c.execute("INSERT OR REPLACE INTO indices_vus (eleve, seance, nombre, maj) VALUES (?, ?, ?, ?)",
                      (cible, int(r["seance"]), int(r.get("nombre") or 0), str(r.get("maj") or "")[:40]))
    for r in travail.get("tirages") or []:
        if int(r["seance"]) in a_jour:
            ids = [int(x) for x in json.loads(r["ids"]) if int(x) in exos]
            c.execute("INSERT OR REPLACE INTO tirages (eleve, seance, ids) VALUES (?, ?, ?)", (cible, int(r["seance"]), json.dumps(ids)))
    final = c.execute("SELECT pseudo FROM eleves WHERE id = ?", (cible,)).fetchone()["pseudo"]
    return {"eleve": final, "id": cible, "renomme": renomme is not None, "fusionne": fusionne,
            "importees": sorted(importees), "gardees": sorted(gardees), "ignorees": sorted(ignorees)}
