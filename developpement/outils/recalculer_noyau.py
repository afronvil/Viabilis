#!/usr/bin/env python3
"""
Recalculer le noyau de viabilité avec les paramètres estimés par calibrer.py.

    python3 recalculer_noyau.py parametres_estimes.json [--julia-projet …/article/julia] [--julia julia]

1. lance article/julia/export_tables_app.jl avec ces paramètres (même durée de séquence TM et même horizon d'autonomie
   que les tables actuelles), dans un répertoire de travail ;
2. compresse les tables (compresser_tables.py) ;
3. garde les tables actuelles dans tables_avant_AAAA-MM-JJ, puis met les nouvelles à leur place.
Il faut Julia et le projet article/julia (environ 2 minutes de calcul). Relancez ensuite le serveur.
Le projet Julia est cherché dans --julia-projet, sinon dans la variable VIABILIS_JULIA_PROJET, sinon à côté de
l'application (../../article/julia), sinon dans ../../../Sticef/sticef/article/julia, sinon dans
~/Documents/Claude/Sticef/sticef/article/julia.
Pour revenir en arrière : supprimez tables et renommez tables_avant_… en tables.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date

ICI = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "serveur"))   # dossier du serveur
# le projet Julia de l'article : à côté de l'application, sinon dans ~/Documents/Claude/Sticef/sticef (organisation actuelle)
CANDIDATS = [os.path.join(ICI, "..", "..", "article", "julia"), os.path.join(ICI, "..", "..", "..", "Sticef", "sticef", "article", "julia"),
             os.path.expanduser("~/Documents/Claude/Sticef/sticef/article/julia")]      # application dans ~/Viabilis (hors iCloud)
VOISIN = next((os.path.normpath(c) for c in CANDIDATS if os.path.exists(os.path.join(c, "export_tables_app.jl"))), os.path.normpath(CANDIDATS[0]))


def main():
    ap = argparse.ArgumentParser(description="Recalculer les tables de viabilité avec des paramètres estimés.")
    ap.add_argument("parametres", help="fichier JSON écrit par calibrer.py")
    ap.add_argument("--julia", default="julia")
    ap.add_argument("--julia-projet", default=os.environ.get("VIABILIS_JULIA_PROJET", VOISIN),
                    help="dossier article/julia qui contient export_tables_app.jl")
    a = ap.parse_args()
    JULIA_PROJET = os.path.abspath(a.julia_projet)
    params = json.load(open(a.parametres, encoding="utf-8"))
    if not params.get("changes"):
        print("Ce fichier ne change aucun paramètre : les tables actuelles restent valables.")
        return 0
    if not os.path.exists(os.path.join(JULIA_PROJET, "export_tables_app.jl")):
        raise SystemExit(f"Projet Julia introuvable : {JULIA_PROJET}. Indiquez-le avec --julia-projet …/article/julia.")
    meta = json.load(open(os.path.join(ICI, "tables", "meta.json"), encoding="utf-8"))
    travail = os.path.join(ICI, "tables_calcul")
    shutil.rmtree(travail, ignore_errors=True)
    os.makedirs(travail)
    env = {**os.environ, "VIABILIS_PARAMETRES": os.path.abspath(a.parametres), "VIABILIS_TABLES": travail,
           "VIABILIS_TM": str(meta["domaine"]["TM"]), "VIABILIS_HORIZON": str(meta.get("horizonAutonomie", 20))}
    print("Paramètres qui changent : " + ", ".join(f"{k} = {v}" for k, v in params["changes"].items()))
    print("Calcul des tables (environ 2 minutes)…", flush=True)
    subprocess.run([a.julia, "--threads=auto", "--project=.", "export_tables_app.jl"], cwd=JULIA_PROJET, env=env, check=True)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "compresser_tables.py"), travail], check=True)
    nouveau = json.load(open(os.path.join(travail, "meta.json"), encoding="utf-8"))
    assert all(abs(nouveau["parametres"].get(k, nouveau.get("kappa_r")) - v) < 1e-9 for k, v in params["changes"].items()), "les tables n'ont pas pris les paramètres"
    garde = os.path.join(ICI, f"tables_avant_{date.today().isoformat()}")
    k = 2
    while os.path.exists(garde):
        garde = os.path.join(ICI, f"tables_avant_{date.today().isoformat()}_{k}")
        k += 1
    os.rename(os.path.join(ICI, "tables"), garde)
    os.rename(travail, os.path.join(ICI, "tables"))
    shutil.copy(a.parametres, os.path.join(ICI, "tables", "parametres_estimes.json"))
    print(f"Nouvelles tables en place ; anciennes gardées dans {os.path.basename(garde)}. Relancez le serveur.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
