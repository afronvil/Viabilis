# -*- coding: utf-8 -*-
"""
Génère maths_problemes_cm1.gift : problèmes pour chercher (CM1), accompagnant la séquence « Résoudre des problèmes »
(modèles pb-cm1-*). Chaque réponse est CALCULÉE ici (dénombrement, essais exhaustifs), jamais saisie à la main.
Usage : python3 generer_problemes_cm1.py   (depuis ce dossier)
"""
import os

ICI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "serveur", "exemples", "ecole", "maths")   # où écrire les banques


def echapper(t):
    t = t.replace("\\", "\\\\")
    for c in "~=#{}:":
        t = t.replace(c, "\\" + c)
    return t


def num(titre, texte, valeur, retour):
    return f"::{echapper(titre)}::{echapper(texte)}{{#{valeur}####{echapper(retour)}}}"


def vf(titre, texte, valeur, retour):
    return f"::{echapper(titre)}::{echapper(texte)}{{{'T' if valeur else 'F'}#{echapper(retour)}#{echapper('Bravo. ' + retour)}}}"


poignees = lambda n: n * (n - 1) // 2
lapins = lambda tetes, pattes: (pattes - 2 * tetes) // 2


def escargot(puits, monte, descend):
    h, jour = 0, 0
    while True:
        jour += 1
        h += monte
        if h >= puits:
            return jour
        h -= descend


Q = []
Q.append(num("Poignées de main", "5 enfants se serrent la main. Chacun serre la main de chaque autre enfant une seule fois. Combien de poignées de main en tout ?",
             poignees(5), "Le premier serre 4 mains, le deuxième 3 nouvelles, puis 2, puis 1 : 4 + 3 + 2 + 1 = 10."))
Q.append(num("Le tournoi", "8 équipes participent à un tournoi. Chaque équipe joue une seule fois contre chacune des autres. Combien de matchs en tout ?",
             poignees(8), "7 + 6 + 5 + 4 + 3 + 2 + 1 = 28 : c'est le même problème que les poignées de main."))
Q.append(num("Poules et lapins", "Dans un enclos, il y a des poules et des lapins. On compte 12 têtes et 34 pattes. Combien y a-t-il de lapins ?",
             lapins(12, 34), "Si les 12 animaux étaient des poules, il y aurait 24 pattes. Il en manque 10 : chaque lapin en ajoute 2, donc 5 lapins."))
v_t = [(v, t) for v in range(10) for t in range(10) if v + t == 9 and 2 * v + 3 * t == 21]
Q.append(num("Vélos et tricycles", "Dans la cour, il y a 9 vélos et tricycles en tout, et 21 roues. Combien y a-t-il de tricycles ?",
             v_t[0][1], "Avec 9 vélos, il y aurait 18 roues. Il en manque 3 : chaque tricycle ajoute une roue, donc 3 tricycles."))
mysteres = [10 * d + u for d in range(1, 10) for u in range(10) if d + u == 9 and d == 2 * u]
assert len(mysteres) == 1
Q.append(num("Le nombre mystère", "Je suis un nombre de deux chiffres. La somme de mes chiffres est 9 et mon chiffre des dizaines est le double de mon chiffre des unités. Qui suis-je ?",
             mysteres[0], "Les unités valent 1, 2, 3 ou 4 (le double doit rester un chiffre). Seul 3 marche : 6 + 3 = 9, donc 63."))
Q.append(num("Les carrés d'allumettes", "Avec des allumettes, on aligne des carrés collés : 1 carré demande 4 allumettes, 2 carrés en demandent 7. Combien d'allumettes faut-il pour 7 carrés ?",
             3 * 7 + 1, "Chaque nouveau carré ajoute 3 allumettes : 4 + 3 × 6 = 22."))
Q.append(num("Combien de carrés ?", "Avec 40 allumettes, on aligne des carrés collés comme dans l'exercice précédent, sans qu'il reste d'allumette. Combien de carrés obtient-on ?",
             (40 - 1) // 3, "Il faut 1 allumette au départ, puis 3 par carré : 40 = 1 + 3 × 13."))
assert 1 + 3 * ((40 - 1) // 3) == 40
Q.append(num("Le plus grand produit", "Deux nombres entiers ont pour somme 14. Quel est le plus grand produit possible de ces deux nombres ?",
             max(a * (14 - a) for a in range(15)), "Plus les deux nombres sont proches, plus le produit est grand : 7 × 7 = 49."))
Q.append(vf("Impair + impair", "La somme de deux nombres impairs est toujours un nombre pair.", True,
            "Vrai : chaque nombre impair, c'est des paires plus 1 ; les deux « 1 » de trop forment une nouvelle paire."))
Q.append(vf("Impair × impair", "Le produit de deux nombres impairs est toujours un nombre pair.", False,
            "Faux : 3 × 5 = 15 est impair. Un seul contre-exemple suffit pour montrer qu'une affirmation est fausse."))
assert (3 * 5) % 2 == 1
Q.append(num("L'escalier de cubes", "On construit un escalier de cubes : la 1re marche a 1 cube, la 2e en a 2, la 3e en a 3. Combien de cubes faut-il pour un escalier de 4 marches ?",
             sum(range(1, 5)), "1 + 2 + 3 + 4 = 10."))
Q.append(num("Le partage", "3 enfants se partagent 25 billes : chacun en reçoit autant, le plus possible. Combien de billes reste-t-il ?",
             25 % 3, "Chacun en reçoit 8, car 3 × 8 = 24 : il reste 1 bille."))
Q.append(num("L'escargot", "Un escargot est au fond d'un puits de 10 m. Le jour, il monte de 3 m ; la nuit, il redescend de 2 m. Au bout de combien de jours sort-il du puits ?",
             escargot(10, 3, 2), "Attention au piège : le 8e jour, il part de 7 m et monte de 3 m : il sort avant de redescendre. 8 jours, et non 10."))
ages = [(3 * f, f) for f in range(1, 30) if 3 * f + 4 == 2 * (f + 4)]
assert len(ages) == 1
Q.append(num("Les âges", "Léa a 3 fois l'âge de son frère. Dans 4 ans, elle aura seulement le double de son âge. Quel âge a Léa aujourd'hui ?",
             ages[0][0], "Essaie : si le frère a 4 ans, Léa en a 12 ; dans 4 ans, 16 et 8 : c'est bien le double."))

if __name__ == "__main__":
    lignes = ["// CM1 — Résoudre des problèmes : problèmes pour chercher (séquence pb-cm1-*).",
              "// Réponses calculées par generer_problemes_cm1.py.", "$CATEGORY: CM1/Mathématiques/Résoudre des problèmes", ""]
    with open(os.path.join(ICI, "maths_problemes_cm1.gift"), "w", encoding="utf-8") as f:
        f.write("\n".join(lignes + [q + "\n" for q in Q]))
    print(f"maths_problemes_cm1.gift : {len(Q)} questions")
