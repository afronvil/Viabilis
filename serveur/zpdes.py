# -*- coding: utf-8 -*-
"""Choix adaptatif des exercices, sur le principe de ZPDES (Clément, Roy, Oudeyer et Lopes, 2015).

Les « activités » sont les niveaux de la banque d'exercices (1 à 5). Pour chaque élève :
- une **zone de développement** : les niveaux ouverts. Elle part du niveau prévu par l'enseignant (ou recommandé par
  le modèle de viabilité), s'ouvre au niveau supérieur quand l'élève réussit le plus haut niveau ouvert, ferme les
  niveaux maîtrisés une fois le niveau suivant essayé et, à la différence de ZPDES, rouvre le niveau inférieur quand l'élève échoue au plus bas ;
- un **progrès** par niveau : l'écart entre la réussite récente et la réussite précédente (au premier essai) ;
- le **choix** : un niveau tiré avec une probabilité proportionnelle à son progrès, mélangée d'une part d'exploration
  uniforme (bandit), puis un exercice de ce niveau, en évitant ceux déjà faits.

La viabilité règle l'aide et l'autonomie ; ce module ne règle que la difficulté des exercices, à l'intérieur de la
zone. Sans historique, il se comporte comme le tirage au niveau fixé.
"""
FENETRE = 6            # résultats récents pris en compte par niveau
MIN_ESSAIS = 6         # avant cela, un niveau n'est jugé ni réussi ni maîtrisé (environ deux séances de 4 exercices)
MIN_ECHECS = 4         # un échec se juge plus tôt : on ne laisse pas un élève en difficulté trop longtemps
OUVRIR = 0.75          # réussite moyenne qui ouvre le niveau supérieur
FERMER = 0.9           # réussite moyenne qui ferme un niveau maîtrisé (s'il en reste un plus haut)
REDESCENDRE = 0.3      # réussite moyenne qui rouvre le niveau inférieur
EXPLORATION = 0.2      # part du tirage uniforme dans la zone
PROGRES_INCONNU = 1.0  # progrès attribué à un niveau peu essayé : on l'explore d'abord


def _recents(h):
    return h[-FENETRE:]


def _moyenne(x):
    return sum(x) / len(x) if x else 0.0


def progres(scores):
    """Progrès d'apprentissage sur un niveau : |réussite de la moitié récente − réussite de la moitié précédente|."""
    r = _recents(scores)
    if len(r) < 2:
        return PROGRES_INCONNU
    m = len(r) // 2
    return abs(_moyenne(r[m:]) - _moyenne(r[:m]))


def zone(historique, depart, niveaux):
    """Niveaux ouverts pour l'élève. historique : {niveau: [scores au premier essai, dans l'ordre]} ;
    depart : niveau prévu ; niveaux : niveaux qui ont des exercices actifs."""
    niveaux = sorted(set(niveaux))
    if not niveaux:
        return []
    depart = min(niveaux, key=lambda n: (abs(n - depart), n))
    Z = {depart}
    juge = lambda n: len(historique.get(n, [])) >= MIN_ESSAIS
    juge_echec = lambda n: len(historique.get(n, [])) >= MIN_ECHECS
    reussite = lambda n: _moyenne(_recents(historique.get(n, [])))
    for _ in range(2 * len(niveaux)):
        avant = set(Z)
        haut, bas = max(Z), min(Z)
        plus_haut = [n for n in niveaux if n > haut]
        if plus_haut and juge(haut) and reussite(haut) >= OUVRIR:
            Z.add(plus_haut[0])
        plus_bas = [n for n in niveaux if n < bas]
        if plus_bas and juge_echec(bas) and reussite(bas) <= REDESCENDRE:
            Z.add(plus_bas[-1])
        for n in sorted(Z):
            suivant = min((m for m in Z if m > n), default=None)
            # un niveau maîtrisé ne se ferme qu'une fois le niveau suivant essayé : la transition se fait en douceur
            if suivant is not None and juge(n) and reussite(n) >= FERMER and juge_echec(suivant):
                Z.discard(n)
        if Z == avant:
            break
    return sorted(Z)


def choisir(historique, depart, par_niveau, deja, nombre, rng):
    """Choisit `nombre` exercices. par_niveau : {niveau: [ids actifs]} ; deja : ids déjà faits par l'élève ;
    rng : random.Random. Renvoie (ids, zone, progrès par niveau de la zone)."""
    Z = zone(historique, depart, [n for n, l in par_niveau.items() if l])
    lp = {n: progres(historique.get(n, [])) for n in Z}
    restants = {n: sorted(par_niveau[n], key=lambda i: (i in deja, rng.random())) for n in Z}
    ids = []
    while len(ids) < nombre:
        candidats = [n for n in Z if restants[n]]
        if not candidats:
            break
        total = sum(lp[n] for n in candidats)
        poids = [(1 - EXPLORATION) * (lp[n] / total if total > 0 else 1 / len(candidats)) + EXPLORATION / len(candidats) for n in candidats]
        x, cumul, choisi = rng.random() * sum(poids), 0.0, candidats[-1]
        for n, w in zip(candidats, poids):
            cumul += w
            if x < cumul:
                choisi = n
                break
        ids.append(restants[choisi].pop(0))
    if len(ids) < nombre:      # zone épuisée : on complète aux niveaux voisins, comme le tirage au niveau fixé
        autres = [(n, i) for n, l in par_niveau.items() if n not in Z for i in l]
        autres.sort(key=lambda x: (min((abs(x[0] - z) for z in Z), default=0), x[1] in deja, rng.random()))
        ids += [i for _, i in autres][:nombre - len(ids)]
    return ids, Z, lp
