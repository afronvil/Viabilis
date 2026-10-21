# Calibration du modèle (calibrer.py) sur des données synthétiques : on simule des élèves avec des paramètres « vrais »
# connus, dont certains diffèrent des valeurs nominales, et un bruit d'observation ; l'estimation doit les retrouver.
#   python3 test_calibration.py        (sans serveur)
import os, random, tempfile
import calibrer as CAL

ok = 0


def verif(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("OK  ", msg)


VRAI = {**CAL.NOMINAL, "rho": 0.40, "lam": 0.20, "ks": 0.65}          # trois paramètres différents des nominaux
BRUIT = 0.04


def classe(n_eleves, n_seances, graine, p=VRAI):
    """Écrit un CSV au format de l'export « Données pour calibrer le modèle » ; renvoie son chemin."""
    rnd = random.Random(graine)
    lignes = ["classe;eleve;seance;rang;niveau;s;phi;r;C;A;M;D"]
    for e in range(n_eleves):
        x = (rnd.uniform(0.3, 0.8), rnd.uniform(0.3, 0.8), rnd.uniform(0.1, 0.5), rnd.uniform(0.3, 0.8))
        for k in range(1, n_seances + 1):
            q = rnd.randint(1, 5)
            u = (rnd.choice([0, 0.2, 0.6, 0.8]), rnd.choice([0, 0.2, 0.6]), rnd.choice([0, 1]))
            x = CAL.avance(x, u, CAL.ELLS[q - 1], p)
            y = [min(1, max(0, v + rnd.gauss(0, BRUIT))) for v in x]
            if rnd.random() < 0.15:
                y[3] = None                                           # une composante parfois manquante
            fr = lambda v: "–" if v is None else f"{v:.3f}".replace(".", ",")
            lignes.append(";".join(["SYN", f"e{e:03d}", str(k), str(k), str(q), *(fr(v) for v in u), *(fr(v) for v in y)]))
    f = os.path.join(tempfile.mkdtemp(), "calibration_SYN.csv")
    open(f, "w", encoding="utf-8").write("﻿" + "\n".join(lignes) + "\n")
    return f


# 1. assez de données : 60 élèves, 8 séances
estime, rapport, n_trs, n_el = CAL.calibrer(CAL.lire([classe(60, 8, 1)]), bootstrap=10, nulles=20)
par = {n: v for l in rapport for n, v in l["parametres"].items()}
verif(n_el == 60 and n_trs == 60 * 7, "transitions entre séances consécutives : 7 par élève")
verif(all(l["statut"] == "calibrée" for l in rapport), "les quatre équations sont calibrées")
for n in ("rho", "lam", "ks"):
    lo, hi = par[n]["intervalle"]
    verif(par[n]["change"] and abs(par[n]["corrige"] - VRAI[n]) < abs(CAL.NOMINAL[n] - VRAI[n]) / 2, f"{n} : retenu {par[n]['corrige']}, près du vrai {VRAI[n]} (nominal {CAL.NOMINAL[n]})")
faux = [n for n, v in par.items() if n not in ("rho", "lam", "ks") and v["change"]]
verif(len(faux) <= 1, f"les dix-sept autres paramètres ne changent pas (faux signaux : {faux or 'aucun'})")
verif(all(l["hors_echantillon"]["estime"] <= l["hors_echantillon"]["nominal"] + 1e-3 for l in rapport), "hors échantillon, les paramètres estimés prédisent au moins aussi bien")

# 2. données conformes au nominal : rien ne doit bouger
estime0, rapport0, _, _ = CAL.calibrer(CAL.lire([classe(40, 6, 2, CAL.NOMINAL)]), bootstrap=5, nulles=20)
bouges = [n for l in rapport0 for n, v in l["parametres"].items() if v["change"]]
verif(len(bouges) <= 1, f"données nominales : au plus un faux signal sur vingt paramètres ({bouges or 'aucun'})")

# 3. trop peu de données : 5 élèves, 4 séances
estime1, rapport1, _, _ = CAL.calibrer(CAL.lire([classe(5, 4, 3)]), bootstrap=5, nulles=5)
verif(all("insuffisantes" in l["statut"] for l in rapport1) and estime1 == CAL.NOMINAL, "trop peu de données : paramètres nominaux, et le rapport le dit")
print(f"test_calibration : {ok} vérifications réussies")
