"""
Génère les banques d'exercices GIFT « Python pour la microbiologie » (M1 de microbiologie, étudiants débutants) : python_niveau1.gift à python_niveau5.gift.

Chaque question « que produit ce programme ? » est EXÉCUTÉE ici : la bonne réponse est la sortie réelle du code,
jamais une valeur saisie à la main ; pour « quelle erreur ? », c'est le type d'exception réellement levé. Les caractères spéciaux du format GIFT (~ = # { } :) sont échappés.
Usage : python3 generer_banques_python.py   (depuis ce dossier)
"""
import contextlib
import io
import os

ICI = os.path.dirname(os.path.abspath(__file__))


def echapper(t):
    t = t.replace("\\", "\\\\")
    for c in "~=#{}:":
        t = t.replace(c, "\\" + c)
    return t


def sortie(code):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(code, {})
    return buf.getvalue().strip()


def question(q):
    genre, titre, intro = q[0], q[1], q[2]
    if genre == "vf":
        valeur, retour = q[3], q[4]
        r = "T" if valeur else "F"
        return f"::{echapper(titre)}::{echapper(intro)}{{{r}#{echapper(retour)}#{echapper('Exact. ' + retour)}}}"
    if genre == "err":
        try:
            exec(q[3], {})
        except Exception as e:
            nom = type(e).__name__
        else:
            raise AssertionError(f"{titre} : le programme ne lève pas d'erreur")
        leurres = [x for x in ERREURS if x != nom][:3] if nom not in ("SyntaxError", "IndentationError") else [x for x in ("NameError", "TypeError", "IndentationError", "SyntaxError") if x != nom][:3]
        return f"::{echapper(titre)}::{echapper(intro + chr(10) + q[3])}{{={nom} " + " ".join("~" + x for x in leurres) + "}"
    code = q[3]
    texte = echapper(intro + "\n" + code)
    attendu = sortie(code)
    if genre == "num":
        float(attendu)                                     # doit être un nombre
        return f"::{echapper(titre)}::{texte}{{#{attendu}}}"
    leurres = [l for l in q[4] if l != attendu]
    assert len(leurres) >= 2, (titre, attendu)
    return f"::{echapper(titre)}::{texte}{{={echapper(attendu)} " + " ".join("~" + echapper(l) for l in leurres) + "}"


AFFICHE = "Qu'affiche ce programme ?"
ERREUR = "Ce programme s'arrête sur une erreur. Laquelle ?"
SEQ = "ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG"
ERREURS = ["SyntaxError", "NameError", "TypeError", "IndentationError", "ZeroDivisionError", "KeyError", "IndexError", "ValueError"]
BANQUES = {
 1: ("Premiers pas : print, variables, calculs, erreurs", [
  ("num", "Un premier calcul", AFFICHE, "print(1000 * 2 ** 6)"),
  ("num", "Variables", AFFICHE, "N0 = 1000\ndivisions = 3\nN = N0 * 2 ** divisions\nprint(N)"),
  ("qcm", "Division décimale", AFFICHE, "print(120 / 20)", ["6", "Une erreur", "0.16666666666666666"]),
  ("qcm", "Division entière", AFFICHE, "print(130 // 20)", ["6.5", "7", "10"]),
  ("qcm", "Texte et nombre", AFFICHE, "N = 64000\nprint(f'Après 2 h : {N} bactéries')", ["Après 2 h : {N} bactéries", "Après 2 h : N bactéries", "Une erreur"]),
  ("err", "Variable non définie", ERREUR, "N0 = 1000\nprint(n0 * 2)"),
  ("vf", "L'opérateur ^", "En Python, 2 ^ 3 calcule 2 puissance 3.", False, "^ est le « ou exclusif » bit à bit : 2 ^ 3 vaut 1. La puissance s'écrit 2 ** 3."),
  ("qcm", "La virgule décimale", AFFICHE, "volume = 0,1\nprint(volume)", ["0.1", "0,1", "Une erreur"]),
 ]),
 2: ("Boucles et conditions", [
  ("num", "Une boucle for", AFFICHE, "s = 0\nfor k in range(1, 5):\n    s = s + k\nprint(s)"),
  ("qcm", "range commence à 0", AFFICHE, "for h in range(3):\n    print(h, end=' ')", ["1 2 3 ", "0 1 2 3 ", "1 2 "]),
  ("num", "Doubler dans une boucle", AFFICHE, "N = 1000\nfor h in range(3):\n    N = N * 2\nprint(N)"),
  ("num", "Boucle while", AFFICHE, "N, t = 1000, 0\nwhile N < 10000:\n    N = N * 2\n    t = t + 20\nprint(t)"),
  ("qcm", "Condition", AFFICHE, "n = 350\nif 30 <= n <= 300:\n    print('comptable')\nelse:\n    print('non comptable')", ["comptable", "Une erreur", "350"]),
  ("num", "Compter les boîtes comptables", AFFICHE, "boites = [250, 31, 2, 350, 28]\nk = 0\nfor n in boites:\n    if 30 <= n <= 300:\n        k = k + 1\nprint(k)"),
  ("err", "Les deux-points", ERREUR, "for h in range(3)\n    print(h)"),
  ("err", "L'indentation", ERREUR, "for h in range(3):\nprint(h)"),
 ]),
 3: ("Chaînes de caractères : séquences d'ADN", [
  ("num", "Longueur d'une séquence", AFFICHE, f"seq = '{SEQ}'\nprint(len(seq))"),
  ("num", "Compter une base", AFFICHE, f"seq = '{SEQ}'\nprint(seq.count('G'))"),
  ("qcm", "Premier codon", AFFICHE, f"seq = '{SEQ}'\nprint(seq[0:3])", ["ATGG", "TGG", "GAT"]),
  ("qcm", "Première lettre", AFFICHE, "print('GATTACA'[0])", ["A", "Une erreur", "GATTACA"]),
  ("num", "Pourcentage de GC", AFFICHE, "seq = 'ATGC'\ngc = (seq.count('G') + seq.count('C')) / len(seq) * 100\nprint(gc)"),
  ("num", "Compter avec une boucle", AFFICHE, "n = 0\nfor base in 'GATTACA':\n    if base == 'A':\n        n = n + 1\nprint(n)"),
  ("qcm", "Minuscules", AFFICHE, "print('atgc'.count('G'))", ["1", "Une erreur", "g"]),
  ("err", "Texte et nombre", ERREUR, "longueur = 39\nprint('Longueur : ' + longueur)"),
 ]),
 4: ("Fonctions et dictionnaires", [
  ("num", "Une fonction", AFFICHE, "def double(n):\n    return 2 * n\nprint(double(21))"),
  ("qcm", "print ou return", AFFICHE, "def f(x):\n    print(x * 2)\nr = f(3)\nprint(r)", ["6", "6\n6", "Une erreur"]),
  ("num", "Fonction pourcentage de GC", AFFICHE, "def gc(s):\n    return (s.count('G') + s.count('C')) / len(s) * 100\nprint(gc('GGCA'))"),
  ("qcm", "Lire un dictionnaire", AFFICHE, "code = {'ATG': 'M', 'TGA': '*', 'GCC': 'A'}\nprint(code['GCC'])", ["GCC", "M", "Une erreur"]),
  ("err", "Codon absent", ERREUR, "code = {'ATG': 'M'}\nprint(code['TTT'])"),
  ("num", "Découper en codons", AFFICHE, f"seq = '{SEQ}'\nprint(len([seq[i:i + 3] for i in range(0, len(seq), 3)]))"),
  ("qcm", "Traduire", AFFICHE, "code = {'ATG': 'M', 'GCC': 'A', 'ATT': 'I', 'TGA': '*'}\nseq = 'ATGGCCATTTGA'\nprot = ''\nfor i in range(0, len(seq), 3):\n    prot = prot + code[seq[i:i + 3]]\nprint(prot)", ["MAI", "ATGGCCATTTGA", "M"]),
  ("num", "Compter avec un dictionnaire", AFFICHE, "d = {}\nfor b in 'GATTACA':\n    d[b] = d.get(b, 0) + 1\nprint(d['A'])"),
 ]),
 5: ("Listes, NumPy, graphiques et fichiers", [
  ("num", "Une liste", AFFICHE, "do = [0.02, 0.05, 0.13, 0.31]\nprint(len(do))"),
  ("num", "Élément d'une liste", AFFICHE, "do = [0.02, 0.05, 0.13, 0.31]\nprint(do[2])"),
  ("qcm", "Calcul sur un tableau NumPy", AFFICHE, "import numpy as np\ndo = np.array([0.1, 0.2, 0.4])\nprint(do * 10)", ["[0.1, 0.2, 0.4, 0.1, 0.2, 0.4]", "Une erreur", "[1, 2, 4]"]),
  ("qcm", "Liste et multiplication", AFFICHE, "do = [0.1, 0.2]\nprint(do * 2)", ["[0.2, 0.4]", "Une erreur", "[0.1, 0.2]"]),
  ("num", "Pente d'une droite", AFFICHE, "import numpy as np\nt = np.array([0, 1, 2, 3])\ny = 0.5 * t + 1\nprint(round(np.polyfit(t, y, 1)[0], 3))"),
  ("num", "Temps de génération", AFFICHE + " (µ = 0,693 h⁻¹)", "import math\nprint(round(math.log(2) / 0.693 * 60))"),
  ("vf", "log et log10", "np.log calcule le logarithme décimal (en base 10).", False, "np.log est le logarithme népérien (base e) ; le logarithme décimal est np.log10. Les confondre divise le taux de croissance par ln 10 ≈ 2,3."),
  ("num", "Lire un FASTA", AFFICHE, "lignes = ['>s1', 'ATGC', 'GG', '>s2', 'AT']\nseqs = {}\nfor l in lignes:\n    if l.startswith('>'):\n        nom = l[1:]\n        seqs[nom] = ''\n    else:\n        seqs[nom] = seqs[nom] + l\nprint(len(seqs['s1']))"),
 ]),
}


if __name__ == "__main__":
    for n, (theme, qs) in BANQUES.items():
        lignes = [f"// M1 de microbiologie — Introduction à Python — niveau {n} : {theme}", f"// Réponses obtenues en exécutant chaque programme (generer_banques_python.py).",
                  f"$CATEGORY: Master/Python/Niveau {n}", ""]
        lignes += [question(q) + "\n" for q in qs]
        with open(os.path.join(ICI, f"python_niveau{n}.gift"), "w", encoding="utf-8") as f:
            f.write("\n".join(lignes))
        print(f"python_niveau{n}.gift : {len(qs)} questions")
