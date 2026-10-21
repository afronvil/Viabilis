"""
Viabilis classe — lecture des tables de viabilité (expérimental).

Les tables sont calculées par article/julia/export_tables_app.jl avec le modèle « séance » NON CALIBRÉ :
pour chaque niveau de difficulté et chaque séance, chaque état (C, A, M, D) de la grille 41 × 41 × 21 × 21
porte un octet : temps d'atteinte de l'ensemble auto-soutenu (0..253), 254 = dans le noyau hors du bassin
de capture, 255 = hors du noyau (rupture inévitable). Ce module reproduit la dynamique et la loi de capture
de Seance.jl pour proposer l'aide minimale ; il ne sert qu'à éclairer la décision de l'enseignant.
"""
import json
import math
import os
import threading
import zlib

import multiplicateurs as MU

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables")
NC, NA, NM, ND = 41, 41, 21, 21
_cache, _verrou = {}, threading.Lock()


def disponible():
    return os.path.exists(os.path.join(D, "meta.json"))


META = json.load(open(os.path.join(D, "meta.json"), encoding="utf-8")) if disponible() else None
P = META["parametres"] if META else {}
# Horizon d'autonomie : un élève n'est « dans le bassin » que s'il peut devenir autonome en au plus HORIZON séances.
HORIZON = min(253, int(META.get("horizonAutonomie", 253))) if META else 253
TM = (META["domaine"].get("TM") or META["H"]) if META else 60     # durée de la séquence (attendus de maîtrise)


def mcur(t):
    """Maîtrise attendue à la séance t : monte jusqu'à mfin sur la séquence (comme Complet.mcur)."""
    return META["domaine"]["mfin"] * min(t, TM) / TM
LEV = [i * 0.2 for i in range(5)] + [1.0]                      # comme linspace01(6) en Julia
RS = (0.0, 0.5, 1.0)
U = sorted([(s, f, r) for s in LEV for f in LEV for r in RS], key=lambda u: (math.sqrt(u[0] ** 2 + 0.3 * u[1] ** 2), -u[2]))
BRUITS = [(dc, da) for dc in (-1, 0, 1) for da in (-1, 0, 1)]


def table(q, t):
    t = max(0, min(META["H"], t))
    with _verrou:
        if (q, t) not in _cache:
            if len(_cache) > 40:
                _cache.pop(next(iter(_cache)))
            with open(os.path.join(D, f"n{q}_t{t:02d}.z"), "rb") as f:
                _cache[(q, t)] = zlib.decompress(f.read())
        return _cache[(q, t)]


def indice(C, A, M, Dv):
    i = min(NC - 1, max(0, round(C * (NC - 1))))
    j = min(NA - 1, max(0, round(A * (NA - 1))))
    k = min(NM - 1, max(0, round(M * (NM - 1))))
    l = min(ND - 1, max(0, round(Dv * (ND - 1))))
    return i + NC * (j + NA * (k + NM * l))


def code(q, t, x):
    return table(q, t)[indice(*x)]


def g(C):
    return math.exp(-((C - P["c_opt"]) / P["c_w"]) ** 2)


def avance(x, u, ell, vC=0.0, vA=0.0):
    """Une séance du modèle « séance » (identique à Seance.avance5, paramètres nominaux)."""
    C, A, M, Dv = x
    s, f, r = u
    cl = lambda v: min(1.0, max(0.0, v))
    d = cl(ell - P["kappa"] * M)
    L = (1 - P["sigma"] * A) * d + P["sigma"] * A * P["c_opt"] + P["kphi"] * f - P["ks"] * s * (1 - META["kappa_r"] * r)
    Cn = C + P["gamma"] * (L - C) + vC
    gc = g(C)
    e = gc - P["theta"]
    grow = e * (1 - A) if e > 0 else e * A
    An = A + P["rho"] * (1 - s) * grow + P["rho2"] * f * gc * (1 - A) - P["beta"] * s * A + vA
    Mn = M + P["lam"] * gc * (A + P["ksM"] * s) * (1 - M) * ((1 - P["kD"]) + P["kD"] * Dv) - P["delta"] * M
    Dn = Dv + P["rhoD"] * (f + P["sigmaD"] * A) * gc * (1 - Dv) - P["nu"] * (1 - f) * Dv - P["betaD"] * s * (1 - r) * Dv
    return cl(Cn), cl(An), cl(Mn), cl(Dn)


def loi_capture(q, t, x):
    """Aide minimale (s, φ, r) : celle de Seance.politique5 pour la loi de capture. None si aucune ne garde l'élève viable."""
    ell, W = META["ells"][q - 1], META["W"]
    t0 = code(q, t, x)
    suiv = table(q, t + 1)
    if t0 <= HORIZON:
        for u in U:
            pire = max(suiv[indice(*avance(x, u, ell, dc * W, da * W))] for dc, da in BRUITS)
            if pire <= HORIZON and (t0 == 0 or suiv[indice(*avance(x, u, ell))] < t0):
                return u, "capture"
    for u in U:                                   # hors du bassin : rester dans le noyau (sauvegarde)
        if all(suiv[indice(*avance(x, u, ell, dc * W, da * W))] != 255 for dc, da in BRUITS):
            return u, "sauvegarde"
    return None, "aucune"


def fenetre(q, t, x, horizon=20):
    """Séances sans aide avant de sortir du bassin de capture (0 : déjà dehors ; None : pas de sortie sur l'horizon)."""
    ell = META["ells"][q - 1]
    if code(q, t, x) > HORIZON:
        return 0
    for k in range(1, horizon + 1):
        x = avance(x, (0.0, 0.0, 0.0), ell)
        if code(q, t + k, x) > HORIZON:
            return k
    return None


# ---------------------------------------------------------------- marge dans le noyau (modèle complet, tables)
# Où va l'élève en une séance SANS aide, comparé au point le plus proche du noyau dans les tables : correction de l'état
# lui-même (ce que article/sim/multiplicateurs.py appelle multiplicateurs « idéaux »). Les multiplicateurs de viabilité de
# l'article (« réalisables », de Karush-Kuhn-Tucker) sont calculés dans multiplicateurs.py.
PAS = (1 / (NC - 1), 1 / (NA - 1), 1 / (NM - 1), 1 / (ND - 1))
RAYON = 0.3                                                   # au-delà, la correction est jugée hors de portée


def _decalages():
    """Décalages de grille dans une boîte de ±0,3, rangés du plus proche au plus lointain (calculé une fois)."""
    r = [int(round(RAYON / p)) for p in PAS]
    out = [(math.sqrt(sum((d * p) ** 2 for d, p in zip(o, PAS))), o)
           for o in ((i, j, k, l) for i in range(-r[0], r[0] + 1) for j in range(-r[1], r[1] + 1)
                     for k in range(-r[2], r[2] + 1) for l in range(-r[3], r[3] + 1))]
    out.sort()
    return out


_DECALAGES = None


def _cherche(q, t, y, voulu):
    """Point de grille le plus proche de y (au temps t) dont le code vérifie voulu(code). (distance, point) ou (None, None)."""
    global _DECALAGES
    if _DECALAGES is None:
        _DECALAGES = _decalages()
    tab = table(q, t)
    base = (round(y[0] * (NC - 1)), round(y[1] * (NA - 1)), round(y[2] * (NM - 1)), round(y[3] * (ND - 1)))
    bornes = (NC, NA, NM, ND)
    for _, o in _DECALAGES:
        g = tuple(b + d for b, d in zip(base, o))
        if any(v < 0 or v >= n for v, n in zip(g, bornes)):
            continue
        if voulu(tab[g[0] + NC * (g[1] + NA * (g[2] + NM * g[3]))]):
            point = tuple(v * p for v, p in zip(g, PAS))
            return math.sqrt(sum((a - b) ** 2 for a, b in zip(point, y))), point
    return None, None


CIBLES = {"noyau": lambda c: c != 255, "bassin": lambda c: c <= HORIZON}


def dans_domaine(x, t):
    k = META["domaine"]
    return k["Cmin"] <= x[0] <= k["Cmax"] and x[1] >= k["Amin"] and x[3] >= k["Dmin"] and x[2] >= mcur(t)


def marge(q, t, x):
    """Marge dans le noyau et dans le bassin de capture (modèle complet).
    On regarde où va l'élève en une séance sans aide (y) :
    - si y n'est plus viable : tension > 0 = longueur de la plus petite correction qui le ramène dans l'ensemble viable,
      et « vecteur » = cette correction (C, A, M, D) ;
    - si y est viable : tension < 0 = moins la marge (distance à la frontière la plus proche), et « vecteur » = la direction
      de cette frontière, c'est-à-dire la menace la plus proche.
    La dérive est le déplacement sans aide."""
    ell = META["ells"][q - 1]
    y = avance(x, (0.0, 0.0, 0.0), ell)
    t1 = min(META["H"], t + 1)
    out = {"derive": [round(b - a, 3) for a, b in zip(x, y)], "dansDomaine": dans_domaine(x, t), "retourSpontane": dans_domaine(y, t1),
           "maitriseAttendue": round(mcur(t), 2)}
    for cible, ok in CIBLES.items():
        viable = ok(code(q, t1, y))
        d, p = _cherche(q, t1, y, (lambda c, ok=ok: not ok(c)) if viable else ok)
        if d is None:                                         # rien à portée (marge très large, ou correction hors d'atteinte)
            out[cible] = {"tension": -RAYON if viable else None, "vecteur": None}
            continue
        out[cible] = {"tension": round(-d if viable else d, 3), "vecteur": [round(b - a, 3) for a, b in zip(y, p)]}
    return out


# ---------------------------------------------------------------- prédictions démenties
NOMS = ("charge", "agentivité", "maîtrise", "pensée divergente")
ECART_DEMENTI = 0.15                                          # écart (sur une variable) au-delà duquel la prédiction est démentie


def predictions(trajet):
    """Compare, séance après séance, ce que le modèle prévoyait et ce qui a été observé.
    trajet : liste de {t, niveau, x: [C, A, M, D] estimé après la séance, u: [s, phi, r] aide reçue pendant la séance}.
    Pour deux séances consécutives, la prévision part de l'état après la première, avec l'aide reçue pendant la seconde."""
    out = []
    for a, b in zip(trajet, trajet[1:]):
        if b["t"] != a["t"] + 1:                              # séance manquée : pas de comparaison
            continue
        q = min(5, max(1, int(b["niveau"])))
        y = avance(tuple(a["x"]), tuple(b["u"]), META["ells"][q - 1])
        ecart = [round(o - p, 3) for o, p in zip(b["x"], y)]
        # la maîtrise n'entre pas dans le verdict : celle du modèle est un niveau cumulé qui monte lentement, celle de l'application
        # est la réussite à la tâche du jour, qui baisse normalement quand la tâche devient plus difficile (écart de définition)
        i = max((0, 1, 3), key=lambda j: abs(ecart[j]))
        retour = not dans_domaine(a["x"], a["t"]) and dans_domaine(y, b["t"]) and not dans_domaine(b["x"], b["t"])
        out.append({"seance": b["t"] + 1, "prevu": [round(v, 3) for v in y], "observe": [round(v, 3) for v in b["x"]], "ecart": ecart,
                    "variable": NOMS[i], "dementie": abs(ecart[i]) > ECART_DEMENTI or retour, "retourNonRealise": retour})
    suite = 0
    for p in reversed(out):
        if not p["dementie"]:
            break
        suite += 1
    return {"comparaisons": out, "dementiesDeSuite": suite}


def analyser(q, seance, x):
    """Statut de viabilité d'un élève estimé en x = (C, A, M, D) au niveau q, pour la séance donnée."""
    t = max(0, min(META["H"] - 1, seance - 1))
    c = code(q, t, x)
    u, nature = loi_capture(q, t, x)
    statut = "hors_noyau" if c == 255 else "hors_bassin" if c > HORIZON else "auto_soutenu" if c == 0 else "dans_bassin"
    return {"statut": statut, "seancesVersAutonomie": c if c <= HORIZON else None, "fenetre": fenetre(q, t, x),
            "aide": None if u is None else {"etayage": round(u[0], 1), "questions": round(u[1], 1), "reflexion": u[2]}, "nature": nature,
            "marge": marge(q, t, x),
            # multiplicateurs de viabilité de l'article (modèle réduit C, A, M) et nature de l'aide de la loi de capture
            "multiplicateurs": (mu := MU.analyser(x[0], x[1], x[2], META["ells"][q - 1])),
            "natureAide": None if u is None or (u[0] == 0 and u[1] == 0) else ("sauvegarde" if mu["sauvegarde"] else "progression")}
