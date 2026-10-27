"""
Viabilis classe — vérification des idées de la tâche ouverte, avec un retour à l'élève.

Deux modes, choisis par l'enseignant :
- « calcul » : chaque idée doit être un calcul qui vaut la cible (ex. 10 pour « payer 10 € avec des pièces de
  1 €, 2 € et 5 € ») ; on peut imposer les nombres autorisés ; les doublons (même somme dans un autre ordre)
  sont repérés. Vérification exacte, sans IA.
- « ia » : l'IA juge chaque idée d'après les critères de réussite écrits par l'enseignant.
Dans les deux cas, le retour ne donne jamais la bonne réponse : il dit ce qui va, ce qui ne va pas, et pose
une question pour avancer.
"""
import ast
import json
import operator
import re
from collections import Counter

from langues import T, NOM_POUR_IA

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _normaliser(texte):
    t = str(texte).lower().replace("€", " ").replace("euros", " ").replace("euro", " ")
    t = t.replace("×", "*").replace("÷", "/").replace(":", "/").replace("−", "-")
    t = re.sub(r"(?<=[\d)])\s*x\s*(?=[\d(])", "*", t)     # 3 x 2, 2 x (5 + 7)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)                   # 2,5
    t = re.sub(r"(?<=\d)\s+(?=\d{3}\b)", "", t)             # 1 000
    t = re.sub(r"\bet\b", "+", t)                           # 5 et 5
    if "=" in t:                                            # « 5 + 5 = 10 » ou « 10 = 5 + 5 » : on garde le côté qui calcule
        cotes = [c.strip() for c in t.split("=") if c.strip()]
        t = next((c for c in cotes if re.search(r"\d\s*[-+*/]\s*\(?\d", c)), cotes[0] if cotes else "")
    return t.strip()


def canonique(n):
    """Forme normale d'un calcul : sommes et produits aplatis et triés, pour que 7 × 3 + 5 − 2 et 5 + 3 × 7 − 2
    soient reconnus comme la même solution."""
    if isinstance(n, ast.Expression):
        return canonique(n.body)
    if isinstance(n, ast.Constant):
        return repr(float(n.value))
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)):
        termes = []

        def plat(x, signe):
            if isinstance(x, ast.BinOp) and isinstance(x.op, ast.Add):
                plat(x.left, signe); plat(x.right, signe)
            elif isinstance(x, ast.BinOp) and isinstance(x.op, ast.Sub):
                plat(x.left, signe); plat(x.right, -signe)
            elif isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.USub):
                plat(x.operand, -signe)
            else:
                termes.append(("+" if signe > 0 else "-") + canonique(x))
        plat(n, 1)
        return "S(" + ",".join(sorted(termes)) + ")"
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
        facteurs = []

        def platm(x):
            if isinstance(x, ast.BinOp) and isinstance(x.op, ast.Mult):
                platm(x.left); platm(x.right)
            else:
                facteurs.append(canonique(x))
        platm(n)
        return "P(" + ",".join(sorted(facteurs)) + ")"
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
        return "D(" + canonique(n.left) + "," + canonique(n.right) + ")"
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        return "S(-" + canonique(n.operand) + ")"
    return ast.dump(n)


def evaluer(texte):
    """(valeur, nombres utilisés, que des additions ?, forme canonique) ou None si l'idée n'est pas un calcul simple."""
    t = _normaliser(texte)
    if not t or not re.fullmatch(r"[0-9+\-*/(). ]+", t) or not re.search(r"\d", t):
        return None
    try:
        arbre = ast.parse(t, mode="eval")
    except SyntaxError:
        return None
    nombres, additions = [], [True]

    def calc(n):
        if isinstance(n, ast.Expression):
            return calc(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            nombres.append(n.value)
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            if not isinstance(n.op, ast.Add):
                additions[0] = False
            return OPS[type(n.op)](calc(n.left), calc(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            additions[0] = False
            return -calc(n.operand)
        raise ValueError("expression non prise en charge")
    try:
        v = calc(arbre)
    except (ValueError, ZeroDivisionError, RecursionError):
        return None
    return v, nombres, additions[0], canonique(arbre)


def _fmt(v):
    return (f"{v:g}" if abs(v - round(v)) > 1e-9 else str(int(round(v)))).replace(".", ",")


def _sommes(cible, parts):
    """Toutes les façons d'écrire cible comme somme de nombres pris dans parts (répétitions permises, ordre ignoré)."""
    out = []

    def rec(reste, i, pris):
        if reste == 0:
            out.append(tuple(pris))
            return
        for j in range(i, len(parts)):
            if parts[j] <= reste and len(out) < 5000:
                rec(reste - parts[j], j, pris + [parts[j]])
    rec(cible, 0, [])
    return out


def conseil_strategie(sommes_trouvees, cible, autorises, une_fois=False, langue="fr"):
    """Un conseil sur la façon de chercher, pour les tâches « trouver toutes les sommes » (pièces, Faire 15…).
    Il dit où chercher (combien de fois le plus grand nombre est utilisé), jamais quelle solution écrire.
    sommes_trouvees : les solutions justes, chacune comme liste des nombres additionnés."""
    parts = sorted({int(x) for x in autorises if float(x) == int(x) and x > 0}, reverse=True)
    if not parts or cible != int(cible) or cible > 200 or len(parts) < 2:
        return None
    cible = int(cible)
    possibles = [t for t in _sommes(cible, parts) if not une_fois or len(set(t)) == len(t)]
    if not possibles or len(possibles) > 400:
        return None
    G = parts[0]
    trouvees = {tuple(sorted((int(x) for x in t), reverse=True)) for t in sommes_trouvees}
    if len(trouvees) >= len(possibles):
        return None
    if une_fois:                                   # nombres tous différents : on regarde combien de nombres sont additionnés
        par_k = lambda ens, k: [t for t in ens if len(t) == k]
        tailles = sorted({len(t) for t in possibles})
        manque = [k for k in tailles if not par_k(trouvees, k)]
        if manque and trouvees:
            return T(langue, "Tes solutions additionnent {k} nombres. As-tu essayé avec {m} nombres ?",
                     k=', '.join(str(k) for k in sorted({len(t) for t in trouvees})), m=manque[0])
        incomplet = [k for k in tailles if len(par_k(trouvees, k)) < len(par_k(possibles, k))]
        if incomplet:
            return T(langue, "Avec {k} nombres, il existe d'autres solutions : change un nombre et compense avec un autre.", k=incomplet[0])
        return None
    fois = lambda t: t.count(G)
    familles = sorted({fois(t) for t in possibles}, reverse=True)
    vues = {fois(t) for t in trouvees}
    nom = lambda k: T(langue, {0: "zéro fois", 1: "une fois", 2: "deux fois", 3: "trois fois"}[k]) if k <= 3 else T(langue, "{k} fois", k=k)
    manque = [k for k in familles if k not in vues]
    if trouvees and manque:
        deja = ", ".join(nom(k) for k in sorted(vues, reverse=True))
        return T(langue, "Dans tes solutions justes, le {g} est utilisé : {deja}. As-tu cherché des solutions où le {g} est utilisé {fois} ?", g=G, deja=deja, fois=nom(manque[0]))
    for k in familles:
        if len([t for t in trouvees if fois(t) == k]) < len([t for t in possibles if fois(t) == k]):
            return T(langue, "Quand le {g} est utilisé {fois}, il te manque encore des solutions. Essaie de découper un des autres nombres en plus petits.", g=G, fois=nom(k))
    return None


def en_ordre(sommes):
    """Les solutions sont-elles rangées (le plus grand nombre de plus en plus ou de moins en moins utilisé) ?"""
    if len(sommes) < 3:
        return True
    g = max(max(t) for t in sommes)
    k = [t.count(g) for t in sommes]
    return k == sorted(k) or k == sorted(k, reverse=True)


def verifier_calcul(idees, cible, nombres_autorises=None, nombre_attendu=None, une_fois=False, langue="fr"):
    autorises = set(nombres_autorises or [])
    retours, vus, justes, sommes = [], [], 0, []
    for texte in idees:
        r = evaluer(texte)
        if r is None:
            retours.append({"statut": "a_revoir", "retour": T(langue, "Je ne reconnais pas un calcul. Écris-le avec des nombres et les signes +, −, × ou ÷.")})
            continue
        v, nombres, additions, forme = r
        interdits = sorted({n for n in nombres if autorises and n not in autorises})
        if interdits:
            retours.append({"statut": "a_revoir", "retour": T(langue, "Tu utilises {n}, qui n'est pas autorisé ici. Avec quels nombres peux-tu remplacer ?", n=', '.join(_fmt(n) for n in interdits))})
            continue
        repetes = sorted(n for n, k in Counter(nombres).items() if k > 1)
        if une_fois and repetes:
            retours.append({"statut": "a_revoir", "retour": T(langue, "Tu utilises {n} plusieurs fois : chaque nombre ne peut servir qu'une fois. Comment faire autrement ?", n=', '.join(_fmt(n) for n in repetes))})
            continue
        if abs(v - cible) > 1e-9:
            modele = ("Ce calcul vaut {v} : c'est trop. Que pourrais-tu changer pour obtenir {c} ?" if v > cible
                      else "Ce calcul vaut {v} : ce n'est pas assez. Que pourrais-tu changer pour obtenir {c} ?")
            retours.append({"statut": "a_revoir", "retour": T(langue, modele, v=_fmt(v), c=_fmt(cible))})
            continue
        cle = forme
        if cle in vus:
            retours.append({"statut": "doublon", "retour": T(langue, "Juste, mais tu as déjà trouvé cette solution, peut-être dans un autre ordre.")})
            continue
        vus.append(cle)
        justes += 1
        if additions:
            sommes.append(nombres)
        retours.append({"statut": "juste", "retour": T(langue, "Juste : ce calcul vaut bien {c}.", c=_fmt(cible))})
    if nombre_attendu and justes >= nombre_attendu:
        bilan = T(langue, "Bravo : tu as trouvé {n} solutions différentes, c'est complet.", n=justes)
    elif nombre_attendu:
        bilan = T(langue, (f"Tu as trouvé {{n}} solution{'s' if justes > 1 else ''} différente{'s' if justes > 1 else ''}. "
                           "Il en existe d'autres : comment pourrais-tu ranger ta recherche pour n'en oublier aucune ?"), n=justes)
    else:
        bilan = T(langue, "Tu as {n} idées justes et différentes." if justes > 1 else "Tu as {n} idée juste et différente.", n=justes)
    conseil = None
    if nombre_attendu and justes < nombre_attendu or not nombre_attendu:
        conseil = conseil_strategie(sommes, cible, autorises, une_fois, langue) if autorises else None
        if conseil is None and nombre_attendu and justes < nombre_attendu and not en_ordre(sommes):
            conseil = T(langue, "Range tes solutions dans un ordre (par exemple du plus grand nombre utilisé au plus petit) : tu verras mieux celles qui manquent.")
    return {"retours": retours, "bilan": bilan, "justes": justes, "conseil": conseil}


EXPRESSION = re.compile(r"[(\d][\d\s+\-−*/×x÷:().,]*[\d)]")


def solution_dans_texte(texte, cible, nombres_autorises=None, une_fois=False):
    """Vrai si le texte (une réponse de l'IA) contient un calcul qui est une solution de la tâche : à ne pas montrer."""
    autorises = set(nombres_autorises or [])
    for m in EXPRESSION.finditer(str(texte)):
        morceau = m.group(0)
        if not re.search(r"\d\s*[-+−*/×x÷:]\s*\(?\s*\d", morceau):
            continue
        r = evaluer(morceau)
        if not r or abs(r[0] - cible) > 1e-9 or len(r[1]) < 2:
            continue
        if autorises and any(x not in autorises for x in r[1]):
            continue
        if une_fois and len(set(r[1])) < len(r[1]):
            continue
        return True
    return False


ELEVE = {"ecole": "un élève d'école élémentaire", "college": "un élève de collège", "lycee": "un élève de lycée",
         "superieur": "un étudiant de l'enseignement supérieur (licence)"}


def consigne_ia(tache, criteres, idees, public="ecole", code=False, langue="fr"):
    liste = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(idees))
    rigueur = ("Vérifie chaque affirmation avec rigueur, selon les exigences de la discipline : une idée vraie mais mal justifiée est « a_revoir ». "
               "Si tu n'es pas certain qu'une affirmation est exacte, mets « a_revoir » et demande une justification plutôt que "
               "de la valider. S'il y a des formules, écris-les en texte simple (√2, ∛2, ζ₅, Gal(K/Q), [K:Q]). " if public == "superieur" else "")
    if code:
        rigueur += ("Les idées sont des programmes. Tu ne peux pas les exécuter : déroule-les à la main sur un ou deux petits "
                    "exemples, et signale les erreurs probables (bornes des boucles, indices, types, division entière, cas limites, "
                    "effets de bord). Ne réécris jamais le programme corrigé : indique la ligne qui pose problème et pose une question. ")
    return (
        f"Tu aides un enseignant à donner un retour formatif à {ELEVE.get(public, ELEVE['ecole'])}. " + rigueur +
        "Pour chaque idée, dis si elle répond à la consigne (statut \"juste\") ou si elle est à revoir (statut \"a_revoir\"), "
        "puis écris un retour d'une phrase, bienveillant et précis. Si l'idée est à revoir, explique ce qui ne va pas et pose une question "
        "pour aider l'élève à corriger, SANS JAMAIS donner la bonne réponse ni proposer une idée à sa place. "
        "Si deux idées disent la même chose, mets le statut \"doublon\" à la seconde. Termine par un bilan d'une phrase qui encourage "
        "à chercher des idées différentes, puis un conseil d'une phrase sur la façon de chercher (comment s'organiser, par où commencer, "
        "quoi essayer de différent), sans donner d'idée toute faite.\n\n"
        f"Consigne de la tâche : {tache or '(non précisée)'}\n"
        f"Critères de réussite donnés par l'enseignant : {criteres or '(aucun : juge la pertinence par rapport à la consigne)'}\n\n"
        f"Idées de l'élève :\n{liste}\n\n"
        f"Écris les retours, le bilan et le conseil {NOM_POUR_IA.get(langue, 'en français')}, mais garde les statuts tels quels (juste, a_revoir, doublon).\n"
        "Réponds uniquement par un objet JSON de cette forme, sans autre texte :\n"
        '{"idees": [{"n": 1, "statut": "juste", "retour": "…"}], "bilan": "…", "conseil": "…"}'
    )


def _json_tolerant(texte):
    """L'objet JSON d'une réponse d'IA, même imparfaite : texte autour, bloc ```json, virgules en trop, guillemets
    typographiques, retours à la ligne dans les chaînes, réponse coupée en cours de route."""
    t = (texte or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    debut = t.find("{")
    if debut < 0:
        raise ValueError("pas d'objet JSON dans la réponse de l'IA")
    t = t[debut:]
    essais = [t[:t.rfind("}") + 1]] if "}" in t else []
    propre = t.replace("\u201c", '"').replace("\u201d", '"')
    propre = re.sub(r",\s*([}\]])", r"\1", propre)
    essais.append(propre[:propre.rfind("}") + 1] if "}" in propre else propre)
    for e in essais:
        try:
            return json.loads(e, strict=False)            # strict=False : accepte les retours à la ligne dans les chaînes
        except ValueError:
            pass
    # réponse coupée (limite de longueur) : on garde les idées complètes
    idees = [m.groupdict() for m in re.finditer(r'\{\s*"n"\s*:\s*(?P<n>\d+)\s*,\s*"statut"\s*:\s*"(?P<statut>[a-z_]+)"\s*,\s*"retour"\s*:\s*"(?P<retour>(?:[^"\\]|\\.)*)"', propre)]
    if idees:
        return {"idees": [{**x, "n": int(x["n"])} for x in idees], "bilan": ""}
    raise ValueError("réponse de l'IA illisible (JSON invalide)")


def lire_reponse_ia(texte, n, langue="fr"):
    """Extrait le JSON de la réponse de l'IA ; complète ou tronque pour avoir exactement n retours."""
    d = _json_tolerant(texte)
    par_n = {int(x.get("n", i + 1)): x for i, x in enumerate(d.get("idees", [])) if isinstance(x, dict)}
    retours = []
    for i in range(1, n + 1):
        x = par_n.get(i, {})
        statut = x.get("statut") if x.get("statut") in ("juste", "a_revoir", "doublon") else "a_revoir"
        retours.append({"statut": statut, "retour": str(x.get("retour", T(langue, "Relis la consigne et vérifie ton idée.")))[:300]})
    justes = sum(1 for r in retours if r["statut"] == "juste")
    return {"retours": retours, "bilan": str(d.get("bilan", ""))[:300], "justes": justes, "conseil": str(d.get("conseil") or "")[:300] or None}
