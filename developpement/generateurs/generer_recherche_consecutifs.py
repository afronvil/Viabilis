# -*- coding: utf-8 -*-
"""
Génère maths_recherche_consecutifs.gift : exercices de la séquence de recherche « Les sommes de nombres consécutifs »
(CM1, modèles rech-cm1-*). Chaque réponse est CALCULÉE ici, par recherche exhaustive des écritures.
Usage : python3 generer_recherche_consecutifs.py   (depuis ce dossier)
"""
import os

ICI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "serveur", "exemples", "ecole", "maths")   # où écrire les banques


def echapper(t):
    t = t.replace("\\", "\\\\")
    for c in "~=#{}:":
        t = t.replace(c, "\\" + c)
    return t


def ecritures(n):
    """Toutes les écritures de n comme somme d'au moins deux nombres entiers consécutifs, à partir de 1."""
    out = []
    for a in range(1, n):
        s, b = 0, a
        while s < n:
            s += b
            b += 1
        if s == n and b - a >= 2:
            out.append(list(range(a, b)))
    return out


def num(titre, texte, valeur, retour):
    return f"::{echapper(titre)}::{echapper(texte)}{{#{valeur}####{echapper(retour)}}}"


def vf(titre, texte, valeur, retour):
    return f"::{echapper(titre)}::{echapper(texte)}{{{'T' if valeur else 'F'}#{echapper(retour)}#{echapper('Bravo. ' + retour)}}}"


aff = lambda n: " ; ".join(" + ".join(map(str, e)) for e in ecritures(n))
Q = [
 num("Les écritures de 15", "De combien de façons peut-on écrire 15 comme une somme d'au moins deux nombres entiers consécutifs (à partir de 1) ?",
     len(ecritures(15)), f"{aff(15)}."),
 num("Les écritures de 21", "De combien de façons peut-on écrire 21 comme une somme d'au moins deux nombres entiers consécutifs ?",
     len(ecritures(21)), f"{aff(21)}."),
 num("Trois consécutifs", "On additionne trois nombres consécutifs ; celui du milieu est 12. Quelle est la somme ?",
     11 + 12 + 13, "11 + 12 + 13 = 36, c'est 3 × 12 : la somme de trois consécutifs vaut toujours 3 fois celui du milieu."),
 num("Quatre consécutifs", "Quelle est la somme des quatre nombres consécutifs qui commencent par 5 ?", sum(range(5, 9)), "5 + 6 + 7 + 8 = 26."),
 num("Le nombre qui résiste", "Un seul nombre entre 20 et 40 ne peut pas s'écrire comme une somme d'au moins deux nombres consécutifs. Lequel ?",
     next(n for n in range(20, 41) if not ecritures(n)), "32 : comme 1, 2, 4, 8 et 16, c'est le double du nombre qui résiste précédent."),
 num("Deux consécutifs", "37 est la somme de deux nombres consécutifs. Quel est le plus petit des deux ?", (37 - 1) // 2, "18 + 19 = 37 : on retire 1, puis on partage en deux."),
 vf("Deux consécutifs, toujours impair ?", "La somme de deux nombres consécutifs est toujours un nombre impair.", True,
    "Vrai : deux nombres consécutifs, c'est un nombre et ce nombre plus 1 ; deux fois le même nombre est pair, plus 1 donne un impair."),
 vf("Trois consécutifs, toujours pair ?", "La somme de trois nombres consécutifs est toujours un nombre pair.", False,
    "Faux : 2 + 3 + 4 = 9 est impair. Un seul contre-exemple suffit."),
 vf("Trois consécutifs, multiple de 3 ?", "La somme de trois nombres consécutifs est toujours un multiple de 3.", True,
    "Vrai : on prend 1 au plus grand pour le donner au plus petit, et on obtient trois fois le nombre du milieu."),
 num("De 1 à 10", "Combien font 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10 ?", sum(range(1, 11)), "55 : on peut grouper 1 + 10, 2 + 9, 3 + 8… cinq paquets de 11."),
 num("Combien de nombres résistent ?", "Parmi les nombres de 1 à 50, combien ne peuvent pas s'écrire comme une somme d'au moins deux nombres consécutifs ?",
     sum(1 for n in range(1, 51) if not ecritures(n)), "Six nombres : 1, 2, 4, 8, 16 et 32."),
 num("Le premier à trois écritures", "Quel est le plus petit nombre qui s'écrit de trois façons comme une somme d'au moins deux nombres consécutifs ?",
     next(n for n in range(1, 100) if len(ecritures(n)) == 3), f"15 : {aff(15)}."),
]
assert [n for n in range(1, 51) if not ecritures(n)] == [1, 2, 4, 8, 16, 32]

if __name__ == "__main__":
    lignes = ["// CM1 — Séquence de recherche : les sommes de nombres consécutifs (modèles rech-cm1-*).",
              "// Réponses calculées par generer_recherche_consecutifs.py.", "$CATEGORY: CM1/Mathématiques/Recherche : nombres consécutifs", ""]
    with open(os.path.join(ICI, "maths_recherche_consecutifs.gift"), "w", encoding="utf-8") as f:
        f.write("\n".join(lignes + [q + "\n" for q in Q]))
    print(f"maths_recherche_consecutifs.gift : {len(Q)} questions")
