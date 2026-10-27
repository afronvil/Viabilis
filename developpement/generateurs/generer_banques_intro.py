"""
Génère les banques GIFT d'introduction à l'irréductibilité (licence, avant galois_niveau1.gift) :
galois_intro_racines.gift, galois_intro_eisenstein.gift, galois_intro_modulo.gift, galois_intro_changement.gift.

Chaque affirmation mathématique d'une question (racines, irréductibilité sur Q ou sur F_p, critère d'Eisenstein,
développements) est VÉRIFIÉE ici avec SymPy avant d'écrire le fichier : une question fausse arrête le script.
Usage : python3 generer_banques_intro.py   (depuis ce dossier ; nécessite SymPy : pip install sympy)
"""
import os
from fractions import Fraction
from sympy import Poly, Rational, expand, factor_list, primerange, symbols

ICI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "serveur", "exemples", "superieur", "galois")   # où écrire les banques
x = symbols("x")


def echapper(t):
    t = t.replace("\\", "\\\\")
    for c in "~=#{}:":
        t = t.replace(c, "\\" + c)
    return t


def P(texte):
    return Poly(eval(texte.replace("^", "**").replace("²", "**2").replace("³", "**3").replace("⁴", "**4").replace("⁵", "**5")
                     .replace("−", "-"), {"x": x}), x)


def racines_rationnelles(f):
    return sorted({Fraction(int(r.p), int(r.q)) for r in f.ground_roots() if r.is_Rational})


def candidats(f):
    c = [int(a) for a in f.all_coeffs()]
    div = lambda n: [d for d in range(1, abs(n) + 1) if n % d == 0]
    return sorted({s * Fraction(p, q) for p in div(c[-1]) for q in div(c[0]) for s in (1, -1)})


def eisenstein(f, p):
    c = [int(a) for a in f.all_coeffs()]
    return all(a % p == 0 for a in c[1:]) and c[0] % p != 0 and c[-1] % (p * p) != 0


def premiers_eisenstein(f):
    return [p for p in primerange(2, 200) if eisenstein(f, p)]


def irreductible_mod(f, p):
    return Poly(f.as_expr(), x, modulus=p).is_irreducible


def racines_mod(f, p):
    return [a for a in range(p) if int(f.eval(a)) % p == 0]


def num(titre, texte, valeur):
    return f"::{echapper(titre)}::{echapper(texte)}{{#{valeur}}}"


def qcm(titre, texte, bonne, leurres):
    return f"::{echapper(titre)}::{echapper(texte)}{{={echapper(bonne)} " + " ".join("~" + echapper(l) for l in leurres) + "}"


def vf(titre, texte, valeur, retour):
    return f"::{echapper(titre)}::{echapper(texte)}{{{'T' if valeur else 'F'}#{echapper(retour)}#{echapper('Exact. ' + retour)}}}"


def verifie(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ---------------------------------------------------------------- 1. racines rationnelles
def racines():
    q = []
    f = P("x³ - 2*x + 4")
    verifie(len(candidats(f)) == 6, "candidats x³ − 2x + 4")
    q.append(num("Candidats", "Théorème des racines rationnelles : combien y a-t-il de racines rationnelles possibles (candidats) pour x³ − 2x + 4 ?", 6))
    f = P("2*x³ + x² + 1")
    verifie(candidats(f) == sorted({Fraction(s * a, b) for a in (1,) for b in (1, 2) for s in (1, -1)}), "candidats 2x³ + x² + 1")
    q.append(qcm("Coefficient dominant", "Quelles sont les racines rationnelles possibles de 2x³ + x² + 1 ?",
                 "±1 et ±1/2", ["±1 seulement", "±1 et ±2", "±1/2 seulement"]))
    f = P("x³ - 7*x + 6")
    verifie(len(racines_rationnelles(f)) == 3, "racines x³ − 7x + 6")
    q.append(num("Compter les racines", "Combien de racines rationnelles a le polynôme x³ − 7x + 6 ?", 3))
    f = P("2*x³ + x² + 1")
    verifie(racines_rationnelles(f) == [Fraction(-1)] and not f.is_irreducible, "2x³ + x² + 1")
    q.append(qcm("Une racine cachée", "Le polynôme 2x³ + x² + 1 est-il irréductible sur Q ?",
                 "Non : −1 est racine, donc x + 1 le divise", ["Oui : il n'a aucune racine rationnelle", "Oui : ce n'est pas un polynôme unitaire", "On ne peut pas savoir en degré 3"]))
    f = P("x³ - 3*x - 1")
    verifie(f.is_irreducible and not racines_rationnelles(f), "x³ − 3x − 1")
    q.append(vf("Degré 3 sans racine", "x³ − 3x − 1 est irréductible sur Q.", True,
                "Les seuls candidats sont 1 et −1, qui donnent −3 et 1. Sans racine rationnelle, un polynôme de degré 3 est irréductible sur Q."))
    f = P("x⁴ + 3*x² + 2")
    verifie(not racines_rationnelles(f) and not f.is_irreducible, "x⁴ + 3x² + 2")
    q.append(vf("Le piège du degré 4", "x⁴ + 3x² + 2 n'a aucune racine rationnelle, donc il est irréductible sur Q.", False,
                "Faux : x⁴ + 3x² + 2 = (x² + 1)(x² + 2). En degré 4, un produit de deux facteurs de degré 2 n'a pas forcément de racine."))
    q.append(qcm("Pourquoi les petits degrés", "Un polynôme de degré 3 à coefficients rationnels, réductible sur Q, a forcément…",
                 "un facteur de degré 1, donc une racine rationnelle", ["deux facteurs de degré 2", "une racine double", "une racine complexe non réelle"]))
    return "Racines rationnelles", q


# ---------------------------------------------------------------- 2. critère d'Eisenstein
def critere():
    q = []
    f = P("x³ - 6*x + 3")
    verifie(premiers_eisenstein(f) == [3], "x³ − 6x + 3")
    q.append(num("Choisir p", "Pour quel nombre premier p le critère d'Eisenstein s'applique-t-il à x³ − 6x + 3 ?", 3))
    f = P("x⁵ + 10*x + 5")
    verifie(premiers_eisenstein(f) == [5], "x⁵ + 10x + 5")
    q.append(num("Degré 5", "Pour quel nombre premier p le critère d'Eisenstein s'applique-t-il à x⁵ + 10x + 5 ?", 5))
    f = P("x³ + 3*x + 9")
    verifie(not eisenstein(f, 3) and f.LC() % 3 != 0 and int(f.all_coeffs()[-1]) % 9 == 0, "x³ + 3x + 9")
    q.append(qcm("Quelle condition échoue ?", "Pourquoi le critère d'Eisenstein ne s'applique-t-il pas à x³ + 3x + 9 avec p = 3 ?",
                 "Parce que 3² = 9 divise le terme constant", ["Parce que 3 ne divise pas le coefficient dominant", "Parce que 3 ne divise pas 3", "Parce que le polynôme a une racine rationnelle"]))
    verifie(premiers_eisenstein(f) == [] and f.is_irreducible and not racines_rationnelles(f), "x³ + 3x + 9 irréductible")
    q.append(vf("Le critère est suffisant, pas nécessaire", "Le critère d'Eisenstein ne s'applique à x³ + 3x + 9 pour aucun premier p : ce polynôme est donc réductible sur Q.", False,
                "Faux : ses candidats ±1, ±3, ±9 ne sont pas racines ; de degré 3 sans racine rationnelle, il est irréductible. Le critère d'Eisenstein est une condition suffisante, pas nécessaire."))
    f = P("2*x³ + 6*x + 3")
    verifie(premiers_eisenstein(f) == [3], "2x³ + 6x + 3")
    q.append(qcm("Polynôme non unitaire", "Pour 2x³ + 6x + 3 et p = 3, le critère d'Eisenstein…",
                 "s'applique : 3 divise 6 et 3, ne divise pas 2, et 9 ne divise pas 3", ["ne s'applique pas, car le polynôme n'est pas unitaire",
                 "ne s'applique pas, car 3 ne divise pas 2", "ne s'applique qu'avec p = 2"]))
    f = P("x⁴ + 30*x + 30")
    verifie(premiers_eisenstein(f) == [2, 3, 5], "x⁴ + 30x + 30")
    q.append(num("Plusieurs premiers", "Pour combien de nombres premiers p le critère d'Eisenstein s'applique-t-il à x⁴ + 30x + 30 ?", 3))
    verifie(all(eisenstein(Poly(x**n - 2, x), 2) for n in range(1, 30)), "xⁿ − 2")
    q.append(vf("Une famille entière", "Pour tout entier n ≥ 1, le polynôme xⁿ − 2 est irréductible sur Q.", True,
                "Vrai : le critère d'Eisenstein s'applique avec p = 2, quel que soit n. Donc ⁿ√2 est de degré n sur Q."))
    return "Critère d'Eisenstein", q


# ---------------------------------------------------------------- 3. réduction modulo p
def modulo():
    q = []
    g = P("x³ + x + 1")
    verifie(racines_mod(g, 2) == [], "x³ + x + 1 dans F₂")
    q.append(num("Racines dans F₂", "Combien de racines le polynôme x³ + x + 1 a-t-il dans F₂ ?", 0))
    f = P("x³ + 3*x + 5")
    verifie(Poly(f.as_expr(), x, modulus=2) == Poly(g.as_expr(), x, modulus=2) and irreductible_mod(f, 2) and f.is_irreducible, "x³ + 3x + 5 mod 2")
    q.append(qcm("Réduire", "Quelle est la réduction modulo 2 de x³ + 3x + 5 ?", "x³ + x + 1", ["x³ + 3x + 5", "x³ + x", "x³ + 1"]))
    verifie(irreductible_mod(P("x² + x + 1"), 2), "x² + x + 1 sur F₂")
    q.append(vf("Le seul de degré 2", "x² + x + 1 est irréductible sur F₂.", True,
                "Vrai : il vaut 1 en 0 et 1 en 1 (car 1 + 1 + 1 = 3 ≡ 1), donc il n'a pas de racine dans F₂, et en degré 2 cela suffit."))
    f = P("x³ + 2*x + 4")
    verifie(not irreductible_mod(f, 2) and f.is_irreducible, "x³ + 2x + 4 mod 2")
    q.append(qcm("Quand la réduction est réductible", "Modulo 2, x³ + 2x + 4 devient x³, qui est réductible. Qu'en déduit-on sur Q ?",
                 "Rien : il faut essayer un autre nombre premier", ["Il est réductible sur Q", "Il a une racine rationnelle", "Il est irréductible sur Q"]))
    verifie(racines_mod(f, 3) == [] and irreductible_mod(f, 3), "x³ + 2x + 4 mod 3")
    q.append(num("Modulo 3", "Combien de racines la réduction modulo 3 de x³ + 2x + 4 a-t-elle dans F₃ ?", 0))
    h = P("x⁴ + x² + 1")
    verifie(racines_mod(h, 2) == [] and not irreductible_mod(h, 2)
            and factor_list(h.as_expr(), modulus=2)[1] == [(x**2 + x + 1, 2)], "x⁴ + x² + 1 sur F₂")
    q.append(vf("Le piège du degré 4, modulo 2", "x⁴ + x² + 1 n'a pas de racine dans F₂, donc il est irréductible sur F₂.", False,
                "Faux : sur F₂, x⁴ + x² + 1 = (x² + x + 1)². En degré 4, il faut aussi exclure les facteurs de degré 2."))
    f = P("2*x³ + x + 1")
    verifie(Poly(f.as_expr(), x, modulus=2).degree() < 3 and f.is_irreducible, "2x³ + x + 1")
    q.append(qcm("Le coefficient dominant", "Pourquoi ne peut-on pas utiliser la réduction modulo 2 pour prouver que 2x³ + x + 1 est irréductible sur Q ?",
                 "Parce que 2 divise le coefficient dominant : le degré baisse", ["Parce que 2 est le seul premier pair", "Parce que x + 1 est réductible", "On peut : la réduction x + 1 est irréductible, donc 2x³ + x + 1 aussi"]))
    return "Réduction modulo un nombre premier", q


# ---------------------------------------------------------------- 4. changement de variable
def changement():
    q = []
    f = P("x² + 1")
    verifie(expand(f.as_expr().subs(x, x + 1)) == x**2 + 2*x + 2 and eisenstein(Poly(x**2 + 2*x + 2, x), 2), "x² + 1")
    q.append(qcm("Développer", "Si f(x) = x² + 1, que vaut f(x + 1) ?", "x² + 2x + 2", ["x² + 2", "x² + x + 2", "x² + 2x + 1"]))
    f = P("x² + x + 1")
    g = Poly(expand(f.as_expr().subs(x, x + 1)), x)
    verifie(g == Poly(x**2 + 3*x + 3, x) and premiers_eisenstein(g) == [3], "x² + x + 1")
    q.append(num("Choisir p après le changement", "Pour f(x) = x² + x + 1, on a f(x + 1) = x² + 3x + 3. Pour quel nombre premier p le critère d'Eisenstein s'applique-t-il ?", 3))
    q.append(vf("Pourquoi cela marche", "Si f(x + 1) est irréductible sur Q, alors f(x) l'est aussi.", True,
                "Vrai : si f(x) = g(x)h(x) avec g et h non constants, alors f(x + 1) = g(x + 1)h(x + 1), avec des facteurs de mêmes degrés."))
    f = P("x³ + 3*x² + 3*x - 1")
    g = Poly(expand(f.as_expr().subs(x, x - 1)), x)
    verifie(premiers_eisenstein(f) == [] and g == Poly(x**3 - 2, x), "x³ + 3x² + 3x − 1")
    q.append(qcm("Reconnaître un binôme", "Pour f(x) = x³ + 3x² + 3x − 1, quel changement de variable le transforme en un polynôme d'Eisenstein ?",
                 "Remplacer x par x − 1 : on obtient x³ − 2", ["Remplacer x par x + 1 : on obtient x³ − 2", "Remplacer x par 2x", "Aucun : il est réductible"]))
    f = P("x⁴ + x³ + x² + x + 1")
    g = Poly(expand(f.as_expr().subs(x, x + 1)), x)
    verifie(int(g.all_coeffs()[-1]) == 5 and premiers_eisenstein(g) == [5], "Φ₅")
    q.append(num("Terme constant", "Pour f(x) = x⁴ + x³ + x² + x + 1, quel est le terme constant de f(x + 1) ?", 5))
    f = P("3*x³ + 3*x + 1")
    r = Poly(expand(x**3 * f.as_expr().subs(x, 1 / x)), x)
    verifie(premiers_eisenstein(f) == [] and r == Poly(x**3 + 3*x**2 + 3, x) and premiers_eisenstein(r) == [3], "réciproque")
    q.append(qcm("Le polynôme réciproque", "Le polynôme réciproque x³ f(1/x) de f(x) = 3x³ + 3x + 1 est…",
                 "x³ + 3x² + 3, d'Eisenstein pour p = 3", ["3x³ + 3x² + 1", "x³ + 3x + 3", "1/(3x³ + 3x + 1)"]))
    f = P("x⁴ + 1")
    verifie(premiers_eisenstein(f) == [] and premiers_eisenstein(Poly(expand(f.as_expr().subs(x, x + 1)), x)) == [2], "x⁴ + 1")
    q.append(vf("x⁴ + 1", "Le critère d'Eisenstein s'applique directement à x⁴ + 1 avec p = 2.", False,
                "Faux : 2 ne divise pas le terme constant 1. Mais (x + 1)⁴ + 1 = x⁴ + 4x³ + 6x² + 4x + 2 est d'Eisenstein pour p = 2, donc x⁴ + 1 est irréductible sur Q."))
    return "Changement de variable", q


if __name__ == "__main__":
    for nom, fonction in (("racines", racines), ("eisenstein", critere), ("modulo", modulo), ("changement", changement)):
        theme, qs = fonction()
        lignes = [f"// Licence — Théorie de Galois — introduction à l'irréductibilité : {theme}",
                  "// À importer au niveau 1 ; chaque affirmation est vérifiée avec SymPy (generer_banques_intro.py).",
                  f"$CATEGORY: Licence/Théorie de Galois/Introduction/{theme}", ""]
        with open(os.path.join(ICI, f"galois_intro_{nom}.gift"), "w", encoding="utf-8") as f:
            f.write("\n".join(lignes + [q + "\n" for q in qs]))
        print(f"galois_intro_{nom}.gift : {len(qs)} questions")
