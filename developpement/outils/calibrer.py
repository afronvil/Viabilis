#!/usr/bin/env python3
"""
Calibrer le modèle de viabilité sur les données réelles des classes.

    python3 calibrer.py calibration_ABC123.csv calibration_DEF456.csv …   [--bootstrap 30] [--sortie parametres_estimes.json]

Entrée : les fichiers « Données pour calibrer le modèle (CSV) » exportés de l'onglet Données de chaque classe réelle
(une ligne par élève et par séance : état estimé C, A, M, D de la séance, sans lissage ; aide reçue traduite en commandes
s, φ, r ; niveau de la tâche). Bibliothèque standard uniquement.

Méthode
- Pour chaque élève, le modèle « séance » (mêmes équations que noyau.avance et article/julia/src/Seance.jl) simule son
  état de séance en séance, à partir de son premier état observé, avec l'aide reçue et la difficulté de chaque séance ;
  la simulation repart des observations après une séance manquante. Les écarts entre états simulés et observés
  mesurent l'ajustement. Repartir à chaque séance de l'état observé, bruité, biaiserait les paramètres (erreur sur les
  variables explicatives) : sur données synthétiques, cette méthode-là signalait à tort cinq paramètres sur vingt.
- Les paramètres sont estimés équation par équation (agentivité, puis charge, maîtrise, pensée divergente), en deux
  passes, par maximum a posteriori : écart quadratique, plus un a priori centré sur la valeur nominale (écart-type 0,5
  sur l'échelle logarithmique, ou logit pour les paramètres compris entre 0 et 1). Avec peu de données, les estimations
  restent près des valeurs nominales ; elles ne s'en écartent que si les données le justifient.
- Incertitude : bootstrap par élève (les élèves sont tirés avec remise). Intervalle à 90 % ; l'erreur de prédiction
  hors échantillon (élèves non tirés) compare honnêtement les paramètres nominaux et estimés.
- Règle de décision, par simulation : on fabrique des classes « nulles », générées avec les paramètres NOMINAUX mais
  avec les mêmes élèves, les mêmes aides, les mêmes niveaux, le même bruit d'observation (estimé sur les écarts) et les
  mêmes valeurs manquantes, et on leur applique l'estimateur. Cela mesure son biais et sa variabilité propres (point
  de départ observé avec bruit, valeurs bornées à [0, 1], compensations entre paramètres comme ρ_D et σ_D), que le
  bootstrap ne voit pas. Un paramètre ne change que si l'estimation réelle sort de l'intervalle à 90 % des estimations
  nulles ET s'écarte d'au moins 25 % ; sa valeur retenue est corrigée du biais (estimation − (médiane nulle − nominal)).
  Les autres gardent leur valeur nominale dans le fichier de sortie.
- Une transition = deux séances consécutives d'un même élève dont la seconde observe la variable de l'équation.
  Une équation n'est calibrée qu'avec au moins MIN_TRANSITIONS transitions venant d'au moins MIN_ELEVES élèves ;
  sinon ses paramètres restent nominaux, et le rapport le dit.

Sortie : un rapport à l'écran et un fichier JSON {"parametres": {...}, …} à passer au calcul des tables :
    cd ../../article/julia
    VIABILIS_PARAMETRES=…/parametres_estimes.json VIABILIS_TABLES=/tmp/tables_calibrees julia --threads=auto --project=. export_tables_app.jl
    python3 …/serveur/compresser_tables.py /tmp/tables_calibrees      puis remplacer serveur/tables par ce répertoire
"""
import argparse
import csv
import json
import math
import os
import random
import sys
from datetime import date

ICI = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "serveur"))   # dossier du serveur
META = json.load(open(os.path.join(ICI, "tables", "meta.json"), encoding="utf-8"))
NOMINAL = {**META["parametres"], "kappa_r": META["kappa_r"]}
ELLS = META["ells"]
MIN_TRANSITIONS, MIN_ELEVES = 30, 8
ECART_MIN = 0.25          # un paramètre ne change que s'il s'écarte d'au moins 25 % de sa valeur nominale (et que l'intervalle l'exclut)
SD_PRIOR = 0.5
DANS_01 = {"sigma", "theta", "c_opt", "kappa_r", "kD"}     # paramètres compris entre 0 et 1 : a priori sur l'échelle logit
# chaque équation, ses paramètres libres et les composantes de l'état de départ qu'elle utilise
EQUATIONS = [
    ("A", "agentivité", ["rho", "theta", "rho2", "beta", "c_opt", "c_w"], "CA"),
    ("C", "charge", ["gamma", "kappa", "sigma", "kphi", "ks", "kappa_r"], "CAM"),
    ("M", "maîtrise", ["lam", "ksM", "delta", "kD"], "CAMD"),
    ("D", "pensée divergente", ["rhoD", "sigmaD", "nu", "betaD"], "CAD"),
]
INDICE = {"C": 0, "A": 1, "M": 2, "D": 3}


# ---------------------------------------------------------------- modèle (mêmes équations que noyau.avance)
def avance(x, u, ell, p):
    C, A, M, Dv = x
    s, f, r = u
    cl = lambda v: min(1.0, max(0.0, v))
    d = cl(ell - p["kappa"] * M)
    L = (1 - p["sigma"] * A) * d + p["sigma"] * A * p["c_opt"] + p["kphi"] * f - p["ks"] * s * (1 - p["kappa_r"] * r)
    Cn = C + p["gamma"] * (L - C)
    gc = math.exp(-((C - p["c_opt"]) / p["c_w"]) ** 2)
    e = gc - p["theta"]
    grow = e * (1 - A) if e > 0 else e * A
    An = A + p["rho"] * (1 - s) * grow + p["rho2"] * f * gc * (1 - A) - p["beta"] * s * A
    Mn = M + p["lam"] * gc * (A + p["ksM"] * s) * (1 - M) * ((1 - p["kD"]) + p["kD"] * Dv) - p["delta"] * M
    Dn = Dv + p["rhoD"] * (f + p["sigmaD"] * A) * gc * (1 - Dv) - p["nu"] * (1 - f) * Dv - p["betaD"] * s * (1 - r) * Dv
    return cl(Cn), cl(An), cl(Mn), cl(Dn)


# ---------------------------------------------------------------- données
def nombre(t):
    t = (t or "").strip().replace(",", ".")
    if t in ("", "–", "-"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def lire(fichiers):
    """{(classe, élève): [lignes triées par rang]} à partir des CSV exportés par la page enseignant."""
    eleves = {}
    for f in fichiers:
        with open(f, encoding="utf-8-sig", newline="") as fd:
            for l in csv.DictReader(fd, delimiter=";"):
                cle = (l["classe"], l["eleve"])
                eleves.setdefault(cle, []).append({"rang": int(l["rang"]), "niveau": int(l["niveau"]),
                                                   "u": tuple(nombre(l[k]) or 0.0 for k in ("s", "phi", "r")),
                                                   "y": tuple(nombre(l[k]) for k in ("C", "A", "M", "D"))})
    for v in eleves.values():
        v.sort(key=lambda l: l["rang"])
    return eleves


def transitions(eleves):
    """Liste de (élève, x départ complété, u, ℓ, y arrivée) pour des séances consécutives d'un même élève."""
    out = []
    for cle, ls in eleves.items():
        connu = [None] * 4
        for a, b in zip(ls, ls[1:]):
            for i, v in enumerate(a["y"]):
                if v is not None:
                    connu[i] = v
            if b["rang"] != a["rang"] + 1:
                continue
            out.append((cle, tuple(connu), b["u"], ELLS[b["niveau"] - 1], b["y"]))
    return out


def pour_equation(trs, eq):
    var, _, _, besoin = eq
    k = INDICE[var]
    return [t for t in trs if t[4][k] is not None and all(t[1][INDICE[c]] is not None for c in besoin)]


# ---------------------------------------------------------------- estimation
def vers_z(nom, v):
    return math.log(v / (1 - v)) if nom in DANS_01 else math.log(v)


def depuis_z(nom, z):
    return 1 / (1 + math.exp(-z)) if nom in DANS_01 else math.exp(z)


def depart(ls, x=None):
    """État complet de départ : chaque composante prise à sa première observation (ou complétée par x)."""
    out = list(x) if x else [None] * 4
    for l in ls:
        out = [v if c is None and v is not None else c for v, c in zip(l["y"], out)]
    return tuple(0.5 if v is None else v for v in out)


def residus(eleves, eq, p):
    """Écarts entre la variable de l'équation observée et simulée, élève par élève."""
    k = CAL_K[eq[0]]
    out = []
    for ls in eleves.values():
        x = depart(ls)
        for a, b in zip(ls, ls[1:]):
            if b["rang"] != a["rang"] + 1:                   # séance manquante : on repart des observations
                x = depart([b], x)
                continue
            x = avance(x, b["u"], ELLS[b["niveau"] - 1], p)
            if b["y"][k] is not None:
                out.append(b["y"][k] - x[k])
    return out


CAL_K = INDICE


def nelder_mead(f, x0, pas=0.3, iterations=600, tol=1e-9):
    n = len(x0)
    pts = [list(x0)] + [[x0[j] + (pas if j == i else 0.0) for j in range(n)] for i in range(n)]
    vals = [f(q) for q in pts]
    for _ in range(iterations):
        ordre = sorted(range(n + 1), key=lambda i: vals[i])
        pts, vals = [pts[i] for i in ordre], [vals[i] for i in ordre]
        if abs(vals[-1] - vals[0]) < tol:
            break
        centre = [sum(q[j] for q in pts[:-1]) / n for j in range(n)]
        refl = [centre[j] + (centre[j] - pts[-1][j]) for j in range(n)]
        fr_ = f(refl)
        if fr_ < vals[0]:
            exp_ = [centre[j] + 2 * (centre[j] - pts[-1][j]) for j in range(n)]
            fe = f(exp_)
            pts[-1], vals[-1] = (exp_, fe) if fe < fr_ else (refl, fr_)
        elif fr_ < vals[-2]:
            pts[-1], vals[-1] = refl, fr_
        else:
            con = [centre[j] + 0.5 * (pts[-1][j] - centre[j]) for j in range(n)]
            fc = f(con)
            if fc < vals[-1]:
                pts[-1], vals[-1] = con, fc
            else:
                pts = [pts[0]] + [[pts[0][j] + 0.5 * (q[j] - pts[0][j]) for j in range(n)] for q in pts[1:]]
                vals = [vals[0]] + [f(q) for q in pts[1:]]
    i = min(range(n + 1), key=lambda i: vals[i])
    return pts[i]


def estimer(eleves, eq, base):
    """Maximum a posteriori des paramètres libres de l'équation, les autres fixés à `base`."""
    noms = eq[2]
    z0 = [vers_z(n, NOMINAL[n]) for n in noms]
    r0 = residus(eleves, eq, base)
    s2 = max(1e-4, sum(r * r for r in r0) / max(1, len(r0)))     # variance des écarts, fixée au modèle nominal

    def perte(z):
        p = {**base, **{n: depuis_z(n, v) for n, v in zip(noms, z)}}
        if not (0 < p["c_w"] < 2 and p["gamma"] <= 1.5):
            return 1e12
        rs = residus(eleves, eq, p)
        return sum(r * r for r in rs) / (2 * s2) + sum((a - b) ** 2 for a, b in zip(z, z0)) / (2 * SD_PRIOR ** 2)

    z = nelder_mead(perte, z0)
    return {n: depuis_z(n, v) for n, v in zip(noms, z)}


def rmse(eleves, eq, p):
    rs = residus(eleves, eq, p)
    return math.sqrt(sum(r * r for r in rs) / len(rs)) if rs else None


def ajuster(eleves, passes=2):
    """Toutes les équations calibrables, en `passes` passes (chaque équation tient compte des estimations des autres)."""
    trs = transitions(eleves)
    calibrables = [eq for eq in EQUATIONS if len(pour_equation(trs, eq)) >= MIN_TRANSITIONS and len({t[0] for t in pour_equation(trs, eq)}) >= MIN_ELEVES]
    p = dict(NOMINAL)
    for _ in range(passes):
        for eq in calibrables:
            p.update(estimer(eleves, eq, p))
    return p, calibrables


def classe_nulle(eleves, sd, rnd):
    """Mêmes élèves, aides, niveaux, rangs et valeurs manquantes, mais états générés par le modèle NOMINAL plus un bruit
    d'observation d'écart-type sd[k], borné à [0, 1]."""
    out = {}
    for c, ls in eleves.items():
        x, nv = depart(ls), []
        for i, l in enumerate(ls):
            if i and l["rang"] == ls[i - 1]["rang"] + 1:
                x = avance(x, l["u"], ELLS[l["niveau"] - 1], NOMINAL)
            y = tuple(None if v is None else min(1.0, max(0.0, x[k] + rnd.gauss(0, sd[k]))) for k, v in enumerate(l["y"]))
            nv.append({**l, "y": y})
        out[c] = nv
    return out


def calibrer(eleves, bootstrap=30, nulles=30, graine=1):
    trs = transitions(eleves)
    estime, calibrables = ajuster(eleves)
    # bruit d'observation : écart-type des écarts du modèle ajusté, par variable
    sd = [0.05] * 4
    for eq in calibrables:
        rs = residus(eleves, eq, estime)
        sd[INDICE[eq[0]]] = math.sqrt(sum(r * r for r in rs) / len(rs))
    rnd_n, nuls = random.Random(graine + 1), []
    for _ in range(nulles if calibrables else 0):
        nuls.append(ajuster(classe_nulle(eleves, sd, rnd_n))[0])
    # bootstrap par élève, et erreur hors échantillon (élèves non tirés)
    rnd, liste, tirages, oob = random.Random(graine), sorted(eleves), [], []
    for _ in range(bootstrap if calibrables else 0):
        tire = [rnd.choice(liste) for _ in liste]
        echant = {(c, i): eleves[c] for i, c in enumerate(tire)}
        v, _ = ajuster(echant)
        tirages.append(v)
        hors = {c: eleves[c] for c in liste if c not in set(tire)}
        if hors:
            oob.append({eq[0]: (rmse(hors, eq, NOMINAL), rmse(hors, eq, v)) for eq in calibrables})
    rapport = []
    for eq in EQUATIONS:
        sous = pour_equation(trs, eq)
        ligne = {"variable": eq[0], "nom": eq[1], "transitions": len(sous), "eleves": len({t[0] for t in sous}), "parametres": {}}
        if eq not in calibrables:
            ligne["statut"] = f"données insuffisantes (il faut au moins {MIN_TRANSITIONS} transitions de {MIN_ELEVES} élèves) : paramètres nominaux"
            for n in eq[2]:
                ligne["parametres"][n] = {"nominal": NOMINAL[n], "estime": NOMINAL[n], "corrige": NOMINAL[n], "intervalle": None, "nul": None, "change": False}
        else:
            q = lambda xs, a: sorted(xs)[min(len(xs) - 1, max(0, int(round(a * (len(xs) - 1)))))]
            for n in eq[2]:
                bt = [t[n] for t in tirages]
                nul = [t[n] for t in nuls]
                lo, hi = q(bt, 0.05), q(bt, 0.95)
                n_lo, n_med, n_hi = q(nul, 0.05), q(nul, 0.5), q(nul, 0.95)
                corrige = max(1e-4, estime[n] - (n_med - NOMINAL[n]))          # estimation corrigée du biais de l'estimateur
                if n in DANS_01:
                    corrige = min(corrige, 0.999)
                ecart = abs(corrige - NOMINAL[n]) / NOMINAL[n]
                ligne["parametres"][n] = {"nominal": NOMINAL[n], "estime": round(estime[n], 4), "corrige": round(corrige, 4),
                                          "intervalle": [round(lo, 4), round(hi, 4)], "nul": [round(n_lo, 4), round(n_hi, 4)],
                                          "change": not (n_lo <= estime[n] <= n_hi) and ecart >= ECART_MIN}
            ligne["erreur_nominale"] = round(rmse(eleves, eq, NOMINAL), 4)
            ligne["erreur_estimee"] = round(rmse(eleves, eq, estime), 4)
            vals = [o[eq[0]] for o in oob if o[eq[0]][0] is not None and o[eq[0]][1] is not None]
            if vals:
                ligne["hors_echantillon"] = {"nominal": round(sum(a for a, _ in vals) / len(vals), 4), "estime": round(sum(b for _, b in vals) / len(vals), 4)}
            ligne["statut"] = "calibrée"
        rapport.append(ligne)
    return estime, rapport, len(trs), len(eleves)


def afficher(rapport, n_trs, n_el, fichiers):
    print(f"Calibration du modèle de viabilité — {len(fichiers)} fichier(s), {n_el} élèves, {n_trs} transitions entre séances consécutives\n")
    for l in rapport:
        print(f"Équation de la {l['nom']} ({l['variable']}) : {l['transitions']} transitions, {l['eleves']} élèves — {l['statut']}")
        if "erreur_estimee" in l:
            h = l.get("hors_echantillon")
            print(f"  erreur de prédiction : {l['erreur_nominale']} avec les paramètres nominaux, {l['erreur_estimee']} estimés"
                  + (f" ; hors échantillon {h['nominal']} → {h['estime']}" if h else ""))
        for n, v in l["parametres"].items():
            iv, nl = v["intervalle"], v["nul"]
            print(f"  {n:8} nominal {v['nominal']:<7} estimé {v['estime']:<8}" + (f" intervalle à 90 % [{iv[0]} ; {iv[1]}]" if iv else "")
                  + (f" · si le nominal était vrai : [{nl[0]} ; {nl[1]}]" if nl else "") + (f" · corrigé {v['corrige']}" if v["change"] else "")
                  + ("  ← change" if v["change"] else ""))
        print()


def main():
    ap = argparse.ArgumentParser(description="Calibrer le modèle de viabilité sur les données exportées des classes.")
    ap.add_argument("fichiers", nargs="+", help="fichiers calibration_*.csv (onglet Données de chaque classe réelle)")
    ap.add_argument("--bootstrap", type=int, default=30, help="nombre de tirages pour les intervalles (30 par défaut)")
    ap.add_argument("--nulles", type=int, default=30, help="classes simulées avec le modèle nominal, pour la règle de décision (30 par défaut)")
    ap.add_argument("--sortie", default="parametres_estimes.json")
    a = ap.parse_args()
    eleves = lire(a.fichiers)
    estime, rapport, n_trs, n_el = calibrer(eleves, a.bootstrap, a.nulles)
    afficher(rapport, n_trs, n_el, a.fichiers)
    calibrees = [l["variable"] for l in rapport if l["statut"] == "calibrée"]
    retenus = {n: v["corrige"] for l in rapport for n, v in l["parametres"].items() if v["change"]}
    with open(a.sortie, "w", encoding="utf-8") as f:
        json.dump({"parametres": {k: retenus.get(k, v) for k, v in NOMINAL.items()}, "changes": retenus,
                   "estimations": {k: round(v, 5) for k, v in estime.items()}, "nominal": NOMINAL, "equations_calibrees": calibrees,
                   "rapport": rapport, "eleves": n_el, "transitions": n_trs, "fichiers": [os.path.basename(x) for x in a.fichiers],
                   "date": date.today().isoformat()}, f, ensure_ascii=False, indent=1)
    if not calibrees:
        print("Aucune équation n'a assez de données : les tables actuelles restent valables. Recommencez quand les classes auront avancé.")
        return 1
    if not retenus:
        print("Les données ne justifient aucun changement : les paramètres nominaux restent valables, inutile de recalculer le noyau.")
        return 0
    print("Paramètres qui changent : " + ", ".join(f"{n} {NOMINAL[n]} → {v}" for n, v in retenus.items()))
    print(f"Écrits dans {a.sortie}. Pour recalculer le noyau avec ces paramètres, voir LISEZMOI, section 9 bis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
