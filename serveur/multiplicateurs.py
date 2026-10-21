"""
Viabilis classe — multiplicateurs de viabilité de l'article (section 5.6), sur le modèle réduit (C, A, M).

Traduction fidèle de article/julia/src/multiplicateurs.jl (et de article/sim/multiplicateurs.py) :

1. Multiplicateurs « myopes » (une séquence). Plus petite intervention u = (s, φ) qui garde l'état suivant dans K :
       min s² + 0,3 φ²   s.c.  C⁺ <= Cmax,  C⁺ >= Cmin,  A⁺ >= Amin,  0 <= s, φ <= 1.
   L'état suivant est affine en u : problème quadratique convexe, résolu exactement par énumération des ensembles
   actifs. Ses multiplicateurs de Karush-Kuhn-Tucker (λ surcharge, ennui, dépendance) sont les multiplicateurs de
   viabilité : λ_i est la dérivée du coût minimal par rapport au seuil i (le « prix » du seuil).
2. Multiplicateurs « anticipateurs » (horizon H = 10). Plus petite aide constante (pas de 0,02) qui garde l'état
   dans K pendant H séquences (modèle nominal) ; la contrainte qui motive l'aide est celle dont la marge est la plus
   faible.
3. Intervention de sauvegarde : intervention effectuée dans un état où, sans aide, l'élève sortirait de K dans les
   10 séquences suivantes ; sinon, intervention de progression (elle rapproche de l'autonomie).

Ces calculs portent sur le modèle réduit de l'article (paramètres P0, domaine K à trois seuils) : ils ignorent la
pensée divergente et la contrainte de maîtrise, que seules les tables du modèle complet prennent en compte.
"""
import itertools
import json
import math
import os

P0 = dict(gamma=0.5, kappa=0.35, sigma=0.85, kphi=0.30, ks=0.45, rho=0.25, theta=0.5, rho2=0.08, beta=0.15,
          lam=0.12, ksM=0.6, delta=0.01, c_opt=0.55, c_w=0.2)
# paramètres en vigueur : ceux des tables (tables/meta.json), qui peuvent avoir été calibrés sur les données (calibrer.py)
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables", "meta.json"), encoding="utf-8") as _f:
        P0.update({k: v for k, v in json.load(_f)["parametres"].items() if k in P0})
except (OSError, KeyError, ValueError):
    pass
KD = dict(Cmin=0.20, Cmax=0.85, Amin=0.30)
RW = (1.0, 0.3)                                  # poids de l'intervention : étayage s, friction φ
NOMS = ("surcharge", "ennui", "dependance")


def g(C, p=P0):
    return math.exp(-((C - p["c_opt"]) / p["c_w"]) ** 2)


def avance(C, A, M, s, phi, ell, p=P0):
    """Une séquence du modèle réduit (Viabilite.avance)."""
    d = min(1.0, max(0.0, ell - p["kappa"] * M))
    L = (1 - p["sigma"] * A) * d + p["sigma"] * A * p["c_opt"] + p["kphi"] * phi - p["ks"] * s
    Cn = C + p["gamma"] * (L - C)
    gc = g(C, p)
    e = gc - p["theta"]
    grow = e * (1 - A) if e > 0 else e * A
    An = A + p["rho"] * (1 - s) * grow + p["rho2"] * phi * gc * (1 - A) - p["beta"] * s * A
    Mn = M + p["lam"] * gc * (A + p["ksM"] * s) * (1 - M) - p["delta"] * M
    cl = lambda v: min(1.0, max(0.0, v))
    return cl(Cn), cl(An), cl(Mn)


def successeur_affine(C, A, M, ell, p=P0):
    """(C⁺, A⁺) = (C0, A0) + (dC, dA)·u, sans écrêtage."""
    d = min(1.0, max(0.0, ell - p["kappa"] * M))
    L0 = (1 - p["sigma"] * A) * d + p["sigma"] * A * p["c_opt"]
    e = g(C, p) - p["theta"]
    grow = e * (1 - A) if e > 0 else e * A
    C0 = C + p["gamma"] * (L0 - C)
    A0 = A + p["rho"] * grow
    dC = (-p["gamma"] * p["ks"], p["gamma"] * p["kphi"])
    dA = (-p["rho"] * grow - p["beta"] * A, p["rho2"] * g(C, p) * (1 - A))
    return C0, A0, dC, dA


def _resoudre(Mx, r):
    """Élimination de Gauss avec pivot partiel ; None si la matrice est singulière."""
    n = len(r)
    a = [row[:] + [r[i]] for i, row in enumerate(Mx)]
    for c in range(n):
        piv = max(range(c, n), key=lambda i: abs(a[i][c]))
        if abs(a[piv][c]) < 1e-14:
            return None
        a[c], a[piv] = a[piv], a[c]
        for i in range(c + 1, n):
            f = a[i][c] / a[c][c]
            for j in range(c, n + 1):
                a[i][j] -= f * a[c][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (a[i][n] - sum(a[i][j] * x[j] for j in range(i + 1, n))) / a[i][i]
    return x


def qp(C, A, M, ell):
    """Intervention minimale à une séquence : (u, coût, multiplicateurs (surcharge, ennui, dépendance)) ou None."""
    C0, A0, dC, dA = successeur_affine(C, A, M, ell)
    # contraintes a·u + b >= 0 : surcharge, ennui, dépendance, puis s >= 0, φ >= 0, s <= 1, φ <= 1
    a = [(-dC[0], -dC[1]), (dC[0], dC[1]), (dA[0], dA[1]), (1, 0), (0, 1), (-1, 0), (0, -1)]
    b = [KD["Cmax"] - C0, C0 - KD["Cmin"], A0 - KD["Amin"], 0, 0, 1, 1]
    meilleur = None
    actifs = [()] + [(i,) for i in range(7)] + list(itertools.combinations(range(7), 2))
    for S in actifs:
        n = 2 + len(S)
        Mx = [[0.0] * n for _ in range(n)]
        r = [0.0] * n
        Mx[0][0], Mx[1][1] = 2 * RW[0], 2 * RW[1]
        for k, i in enumerate(S):
            Mx[0][2 + k], Mx[1][2 + k] = -a[i][0], -a[i][1]
            Mx[2 + k][0], Mx[2 + k][1] = a[i][0], a[i][1]
            r[2 + k] = -b[i]
        sol = _resoudre(Mx, r)
        if sol is None or not all(math.isfinite(v) for v in sol):
            continue
        u, lam = sol[:2], sol[2:]
        if all(a[i][0] * u[0] + a[i][1] * u[1] + b[i] >= -1e-9 for i in range(7)) and all(l >= -1e-9 for l in lam):
            cout = RW[0] * u[0] ** 2 + RW[1] * u[1] ** 2
            if meilleur is None or cout < meilleur[1] - 1e-12:
                L = [0.0] * 7
                for k, i in enumerate(S):
                    L[i] = lam[k]
                meilleur = (u, cout, L[:3])
    return meilleur


def _linspace01(n):
    pas = 1.0 / (n - 1)
    v = [i * pas for i in range(n)]
    v[-1] = 1.0
    return v


UG = [(s, f) for s in _linspace01(51) for f in _linspace01(51)]          # aides constantes, pas de 0,02
COUT_UG = [RW[0] * u[0] ** 2 + RW[1] * u[1] ** 2 for u in UG]
ORDRE_UG = sorted(range(len(UG)), key=lambda k: COUT_UG[k])               # de la moins coûteuse à la plus coûteuse


def marges_aide(C, A, M, ell, H, u):
    """Plus petite marge de chaque contrainte (surcharge, ennui, dépendance) sur H séquences avec l'aide constante u."""
    sl = [math.inf] * 3
    c, a, m = C, A, M
    for _ in range(H):
        c, a, m = avance(c, a, m, u[0], u[1], ell)
        sl[0] = min(sl[0], KD["Cmax"] - c)
        sl[1] = min(sl[1], c - KD["Cmin"])
        sl[2] = min(sl[2], a - KD["Amin"])
    return sl


def aide_minimale(C, A, M, ell, H=10):
    """Aide constante minimale sur H séquences : (u, coût, marges) ou None si aucune aide ne suffit.
    Même résultat que Viabilite.aide_minimale (argmin du coût parmi les aides admissibles, premier indice en cas d'égalité)."""
    meilleure = None
    for k in ORDRE_UG:
        if meilleure is not None and COUT_UG[k] > COUT_UG[meilleure] + 1e-15:
            break
        sl = marges_aide(C, A, M, ell, H, UG[k])
        if all(v >= 0 for v in sl) and (meilleure is None or k < meilleure):
            meilleure = k
    if meilleure is None:
        return None
    return UG[meilleure], COUT_UG[meilleure], marges_aide(C, A, M, ell, H, UG[meilleure])


def est_sauvegarde(C, A, M, ell, H=10):
    """Vrai si, sans aide, l'élève sortirait de K dans les H séquences suivantes (Viabilite.est_sauvegarde)."""
    r = aide_minimale(C, A, M, ell, H)
    return r is None or r[1] > 0


def analyser(C, A, M, ell, H=10):
    """Les trois indicateurs de l'article pour un état (C, A, M) et une difficulté ℓ."""
    r1 = qp(C, A, M, ell)
    myopes = None if r1 is None else {"intervention": [round(r1[0][0], 3), round(r1[0][1], 3)],
                                      "cout": round(r1[1], 4), "prix": {n: round(v, 4) for n, v in zip(NOMS, r1[2])}}
    rH = aide_minimale(C, A, M, ell, H)
    if rH is None:
        anticip = {"H": H, "aide": None, "cout": None, "contrainte": None, "aucuneAideSuffisante": True}
    else:
        u, cout, sl = rH
        anticip = {"H": H, "aide": [round(u[0], 2), round(u[1], 2)], "cout": round(math.sqrt(cout), 3),
                   "contrainte": NOMS[min(range(3), key=lambda i: sl[i])] if cout > 0 else None, "aucuneAideSuffisante": False,
                   "marges": [round(v, 3) for v in sl]}
    return {"myopes": myopes, "anticipateurs": anticip, "sauvegarde": rH is None or rH[1] > 0}
