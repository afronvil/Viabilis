"""Compresse les tables brutes exportées par article/julia/export_tables_app.jl (un fichier .z par niveau et par instant)."""
import os, sys, zlib
# répertoire des tables : en argument (tables recalculées ailleurs), sinon serveur/tables
D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables")
N = 41 * 41 * 21 * 21
for q in range(1, 6):
    brut = os.path.join(D, f"niveau{q}.bin")
    if not os.path.exists(brut):
        continue
    with open(brut, "rb") as f:
        for t in range(61):
            with open(os.path.join(D, f"n{q}_t{t:02d}.z"), "wb") as g:
                g.write(zlib.compress(f.read(N), 9))
    os.remove(brut)
print("tables compressées")
