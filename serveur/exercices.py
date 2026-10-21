"""
Viabilis classe — banques d'exercices : import GIFT et Moodle XML, correction côté serveur.

Format interne d'une question (stocké en base, jamais envoyé tel quel à l'élève) :
    {"titre", "texte", "type", "reponses": [...], "retour_general"}
types et réponses :
    choix_unique / choix_multiple : [{"texte", "fraction" (-1..1), "retour"}]
    vrai_faux                     : [{"valeur": bool, "retour_si_juste", "retour_si_faux"}]
    reponse_courte                : [{"texte", "fraction", "retour"}], "casse": bool
    numerique                     : [{"valeur", "tolerance", "fraction", "retour"}]
    appariement                   : [{"gauche", "droite"}]
Les questions sans réponse attendue (texte libre, description) sont ignorées : la tâche ouverte
de la séance joue déjà ce rôle.
"""
import html
import random
import re
import unicodedata
import xml.etree.ElementTree as ET

TYPES = ("choix_unique", "choix_multiple", "vrai_faux", "reponse_courte", "numerique", "appariement")


# ---------------------------------------------------------------- texte
def texte_brut(t, fmt="html"):
    """HTML ou Markdown Moodle -> texte simple (l'application affiche du texte, jamais du HTML)."""
    t = t or ""
    if fmt in ("html", "moodle_auto_format"):
        t = re.sub(r"<\s*br\s*/?>|</p>|</div>|</li>", "\n", t, flags=re.I)
        t = re.sub(r"<[^>]+>", "", t)
        t = html.unescape(t)
    t = t.replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


# ---------------------------------------------------------------- GIFT
_ECHAPPES = {"\\:": "\x01", "\\~": "\x02", "\\=": "\x03", "\\#": "\x04", "\\{": "\x05", "\\}": "\x06", "\\n": "\n"}
_RESTAURE = {"\x01": ":", "\x02": "~", "\x03": "=", "\x04": "#", "\x05": "{", "\x06": "}"}


def _echapper(s):
    for a, b in _ECHAPPES.items():
        s = s.replace(a, b)
    return s


def _restaurer(s):
    for a, b in _RESTAURE.items():
        s = s.replace(a, b)
    return s


def _nettoyer_gift(s):
    s = _restaurer(s).strip()
    fmt = "html" if s.startswith("[html]") else "markdown" if s.startswith("[markdown]") else "plain"
    s = re.sub(r"^\[(html|markdown|plain|moodle)\]", "", s).strip()
    return texte_brut(s, fmt) if fmt == "html" else s


def _scinder_reponses(corps):
    """Découpe le contenu entre accolades en réponses commençant par = ou ~."""
    morceaux, cour = [], ""
    for ch in corps:
        if ch in "=~" and cour.strip():
            morceaux.append(cour.strip())
            cour = ""
        cour += ch
    if cour.strip():
        morceaux.append(cour.strip())
    return morceaux


def _retour(s):
    if "#" in s:
        a, b = s.split("#", 1)
        return a, _nettoyer_gift(b)
    return s, ""


def lire_gift(contenu):
    """Renvoie (questions, avertissements)."""
    questions, avert = [], []
    lignes = [l for l in contenu.replace("\r\n", "\n").split("\n") if not l.strip().startswith("//")]
    texte = _echapper("\n".join(lignes))
    blocs = [b.strip() for b in re.split(r"\n\s*\n", texte) if b.strip()]
    for n, bloc in enumerate(blocs, 1):
        if bloc.startswith("$CATEGORY"):
            continue
        titre = ""
        m = re.match(r"^::(.*?)::(.*)$", bloc, re.S)
        if m:
            titre, bloc = _nettoyer_gift(m.group(1)), m.group(2).strip()
        if "{" not in bloc or "}" not in bloc:
            continue                                   # description : pas de question
        avant, reste = bloc.split("{", 1)
        corps, apres = reste.rsplit("}", 1)
        enonce = _nettoyer_gift(avant) + (" ____ " + _nettoyer_gift(apres) if apres.strip() else "")
        corps = corps.strip()
        retour_general = ""
        if "####" in corps:
            corps, rg = corps.split("####", 1)
            retour_general, corps = _nettoyer_gift(rg), corps.strip()
        q = {"titre": titre or enonce[:60], "texte": enonce.strip(), "retour_general": retour_general}
        try:
            if corps == "":
                avert.append(f"Question {n} « {q['titre']} » : texte libre, ignorée.")
                continue
            if re.fullmatch(r"(T|F|TRUE|FALSE|VRAI|FAUX)(\s*#.*)?", corps, re.S | re.I):
                parts = corps.split("#")
                valeur = parts[0].strip().upper() in ("T", "TRUE", "VRAI")
                q.update(type="vrai_faux", reponses=[{"valeur": valeur, "retour_si_faux": _nettoyer_gift(parts[1]) if len(parts) > 1 else "",
                                                      "retour_si_juste": _nettoyer_gift(parts[2]) if len(parts) > 2 else ""}])
            elif corps.startswith("#"):
                reps = []
                for r in _scinder_reponses(corps[1:]) if corps[1:].lstrip()[:1] in "=~" else ["=" + corps[1:]]:
                    r, ret = _retour(r.lstrip("=~").strip())
                    frac = 1.0
                    mf = re.match(r"^%(-?\d+(?:\.\d+)?)%(.*)$", r)
                    if mf:
                        frac, r = float(mf.group(1)) / 100, mf.group(2)
                    r = r.strip()
                    if ".." in r:
                        a, b = (float(x) for x in r.split(".."))
                        reps.append({"valeur": (a + b) / 2, "tolerance": abs(b - a) / 2, "fraction": frac, "retour": ret})
                    else:
                        v, _, tol = r.partition(":")
                        reps.append({"valeur": float(v), "tolerance": float(tol or 0), "fraction": frac, "retour": ret})
                q.update(type="numerique", reponses=reps)
            else:
                morceaux = _scinder_reponses(corps)
                if morceaux and all(m.startswith("=") and "->" in m for m in morceaux):
                    paires = []
                    for m_ in morceaux:
                        g, d = m_[1:].split("->", 1)
                        paires.append({"gauche": _nettoyer_gift(g), "droite": _nettoyer_gift(d)})
                    q.update(type="appariement", reponses=paires)
                elif morceaux and all(m.startswith("=") for m in morceaux):
                    reps = []
                    for m_ in morceaux:
                        r, ret = _retour(m_[1:])
                        frac = 1.0
                        mf = re.match(r"^%(-?\d+(?:\.\d+)?)%(.*)$", r.strip(), re.S)
                        if mf:
                            frac, r = float(mf.group(1)) / 100, mf.group(2)
                        reps.append({"texte": _nettoyer_gift(r), "fraction": frac, "retour": ret})
                    q.update(type="reponse_courte", reponses=reps, casse=False)
                else:
                    reps, multiple = [], False
                    for m_ in morceaux:
                        signe, r = m_[0], m_[1:]
                        r, ret = _retour(r)
                        mf = re.match(r"^%(-?\d+(?:\.\d+)?)%(.*)$", r.strip(), re.S)
                        if mf:
                            frac, r = float(mf.group(1)) / 100, mf.group(2)
                            multiple = True
                        else:
                            frac = 1.0 if signe == "=" else 0.0
                        reps.append({"texte": _nettoyer_gift(r), "fraction": frac, "retour": ret})
                    if not any(r["fraction"] > 0 for r in reps):
                        raise ValueError("aucune bonne réponse")
                    multiple = multiple and sum(1 for r in reps if r["fraction"] > 0) > 1
                    q.update(type="choix_multiple" if multiple else "choix_unique", reponses=reps)
            questions.append(q)
        except (ValueError, IndexError) as exc:
            avert.append(f"Question {n} « {q['titre']} » : format non reconnu ({exc}), ignorée.")
    return questions, avert


# ---------------------------------------------------------------- Moodle XML
def _txt(noeud, chemin="text"):
    if noeud is None:
        return ""
    e = noeud.find(chemin)
    return texte_brut(e.text if e is not None else "", noeud.get("format", "html"))


def lire_moodle_xml(contenu):
    questions, avert = [], []
    try:
        racine = ET.fromstring(contenu.encode("utf-8") if isinstance(contenu, str) else contenu)
    except ET.ParseError as exc:
        return [], [f"Fichier XML illisible : {exc}"]
    for n, qx in enumerate(racine.iter("question"), 1):
        t = qx.get("type", "")
        if t in ("category", "description"):
            continue
        titre = _txt(qx.find("name")) or f"Question {n}"
        q = {"titre": titre, "texte": _txt(qx.find("questiontext")), "retour_general": _txt(qx.find("generalfeedback"))}
        if "@@PLUGINFILE@@" in (qx.findtext("questiontext/text") or ""):
            avert.append(f"« {titre} » : contient une image, non importée ; le texte seul est gardé.")
        reps = qx.findall("answer")
        frac = lambda a: float(a.get("fraction", "0")) / 100
        if t == "multichoice":
            r = [{"texte": _txt(a), "fraction": frac(a), "retour": _txt(a.find("feedback"))} for a in reps]
            unique = (qx.findtext("single") or "true").strip().lower() in ("true", "1")
            q.update(type="choix_unique" if unique else "choix_multiple", reponses=r)
        elif t == "truefalse":
            vrai = next((a for a in reps if _txt(a).lower() in ("true", "vrai")), None)
            faux = next((a for a in reps if _txt(a).lower() in ("false", "faux")), None)
            valeur = vrai is not None and frac(vrai) > 0
            rv = _txt(vrai.find("feedback")) if vrai is not None else ""
            rf = _txt(faux.find("feedback")) if faux is not None else ""
            q.update(type="vrai_faux", reponses=[{"valeur": valeur, "retour_si_juste": rv if valeur else rf, "retour_si_faux": rf if valeur else rv}])
        elif t == "shortanswer":
            q.update(type="reponse_courte", casse=(qx.findtext("usecase") or "0").strip() == "1",
                     reponses=[{"texte": _txt(a), "fraction": frac(a), "retour": _txt(a.find("feedback"))} for a in reps])
        elif t == "numerical":
            r = []
            for a in reps:
                try:
                    r.append({"valeur": float(_txt(a)), "tolerance": float(a.findtext("tolerance") or 0), "fraction": frac(a), "retour": _txt(a.find("feedback"))})
                except ValueError:
                    pass
            q.update(type="numerique", reponses=r)
        elif t == "matching":
            q.update(type="appariement", reponses=[{"gauche": _txt(s), "droite": _txt(s.find("answer"))} for s in qx.findall("subquestion") if _txt(s)])
        else:
            avert.append(f"« {titre} » : type « {t} » non pris en charge, ignorée.")
            continue
        if not q["reponses"] or (q["type"] in ("choix_unique", "choix_multiple", "reponse_courte", "numerique") and not any(r.get("fraction", 0) > 0 for r in q["reponses"])):
            avert.append(f"« {titre} » : aucune bonne réponse trouvée, ignorée.")
            continue
        questions.append(q)
    return questions, avert


def importer(contenu, fmt=None):
    """Détecte le format si besoin et renvoie (questions, avertissements)."""
    if fmt is None:
        debut = contenu.lstrip()[:200].lower()
        fmt = "xml" if debut.startswith("<?xml") or "<quiz" in debut else "gift"
    return lire_moodle_xml(contenu) if fmt == "xml" else lire_gift(contenu)


# ---------------------------------------------------------------- ce que voit l'élève
def pour_eleve(q, graine):
    """Version sans les réponses attendues ; l'ordre des choix est mélangé de façon stable."""
    rng = random.Random(graine)
    vue = {"titre": q["titre"], "texte": q["texte"], "type": q["type"]}
    if q["type"] in ("choix_unique", "choix_multiple"):
        idx = list(range(len(q["reponses"])))
        rng.shuffle(idx)
        vue["choix"] = [{"id": i, "texte": q["reponses"][i]["texte"]} for i in idx]
    elif q["type"] == "appariement":
        vue["gauches"] = [p["gauche"] for p in q["reponses"]]
        droites = sorted({p["droite"] for p in q["reponses"]})
        rng.shuffle(droites)
        vue["droites"] = droites
    return vue


# ---------------------------------------------------------------- correction
def _norm(s, casse):
    s = re.sub(r"\s+", " ", str(s).strip())
    return s if casse else s.lower()


def reponse_lisible(q, rep):
    """La réponse donnée par l'élève, en texte (pour la correction) : le texte du choix coché, Vrai ou Faux, le nombre…"""
    t, R = q["type"], q["reponses"]
    if rep is None or rep == "" or rep == [] or rep == {}:
        return "pas de réponse"
    if t == "choix_unique":
        i = int(rep) if str(rep).lstrip("-").isdigit() else -1
        return R[i]["texte"] if 0 <= i < len(R) else "pas de réponse"
    if t == "choix_multiple":
        choisis = [int(x) for x in (rep or []) if str(x).lstrip("-").isdigit() and 0 <= int(x) < len(R)]
        return " ; ".join(R[i]["texte"] for i in sorted(choisis)) or "pas de réponse"
    if t == "vrai_faux":
        return "Vrai" if str(rep).lower() in ("true", "vrai", "1") else "Faux"
    if t == "appariement":
        return " ; ".join(f"{g} → {d}" for g, d in (rep or {}).items() if d) or "pas de réponse"
    return str(rep)[:500]


def reponse_attendue(q):
    """La bonne réponse, en texte, quelle que soit la réponse donnée (corriger ne la renvoie pas pour un nombre illisible)."""
    return corriger(q, "nan" if q["type"] == "numerique" else None)[2]


def corriger(q, rep):
    """Renvoie (score entre 0 et 1, retour à afficher, réponse attendue lisible)."""
    t, R = q["type"], q["reponses"]
    if t == "choix_unique":
        i = int(rep) if str(rep).lstrip("-").isdigit() else -1
        bonne = max(R, key=lambda r: r["fraction"])
        if 0 <= i < len(R):
            return max(0.0, R[i]["fraction"]), R[i].get("retour", ""), bonne["texte"]
        return 0.0, "", bonne["texte"]
    if t == "choix_multiple":
        choisis = {int(x) for x in (rep or []) if str(x).lstrip("-").isdigit() and 0 <= int(x) < len(R)}
        score = min(1.0, max(0.0, sum(R[i]["fraction"] for i in choisis)))
        retours = " ".join(R[i]["retour"] for i in sorted(choisis) if R[i].get("retour"))
        return score, retours, " ; ".join(r["texte"] for r in R if r["fraction"] > 0)
    if t == "vrai_faux":
        v = R[0]["valeur"]
        dit = str(rep).lower() in ("true", "vrai", "1")
        ok = dit == v
        return (1.0 if ok else 0.0), R[0]["retour_si_juste"] if ok else R[0]["retour_si_faux"], "Vrai" if v else "Faux"
    if t == "reponse_courte":
        casse = q.get("casse", False)
        donnee = _norm(rep, casse)
        meilleur, retour = 0.0, ""
        for r in R:
            motif = "^" + re.escape(_norm(r["texte"], casse)).replace(r"\*", ".*") + "$"
            if re.match(motif, donnee, 0 if casse else re.I) and r["fraction"] > meilleur:
                meilleur, retour = r["fraction"], r.get("retour", "")
        return meilleur, retour, next((r["texte"] for r in sorted(R, key=lambda r: -r["fraction"])), "")
    if t == "numerique":
        try:
            x = float(str(rep).replace(",", ".").strip())
        except ValueError:
            return 0.0, "Entrez un nombre.", ""
        meilleur, retour = 0.0, ""
        for r in R:
            if abs(x - r["valeur"]) <= r["tolerance"] + 1e-12 and r["fraction"] > meilleur:
                meilleur, retour = r["fraction"], r.get("retour", "")
        bonne = max(R, key=lambda r: r["fraction"])
        attendu = f"{bonne['valeur']:g}" + (f" (à {bonne['tolerance']:g} près)" if bonne["tolerance"] else "")
        return meilleur, retour, attendu.replace(".", ",")
    if t == "appariement":
        donnees = rep if isinstance(rep, dict) else {}
        justes = sum(1 for p in R if _norm(donnees.get(p["gauche"], ""), False) == _norm(p["droite"], False))
        return justes / len(R), "", " ; ".join(f"{p['gauche']} → {p['droite']}" for p in R)
    return 0.0, "", ""
