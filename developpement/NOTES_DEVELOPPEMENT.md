# Viabilis — notes de développement

Journal des fonctions, des choix et des vérifications, pour qui développe ou étudie Viabilis. Le mode d'emploi pour les établissements est dans `../LISEZMOI.md`. Les chemins sont donnés depuis le dossier `application/`. Tous les tests se lancent avec `python3 developpement/tests/lancer_tests.py` (ou `… lancer_tests.py langues` pour un seul).


Deux applications pour smartphone et tablette, reliées entre elles :

- **Viabilis élève** : l'élève rejoint la classe avec un code et un pseudonyme, déclare la difficulté ressentie, écrit ses idées, puis utilise une IA dont l'ordre (réflexion d'abord ou IA d'abord) et le rôle (questionner ou donner des éléments) sont fixés par l'enseignant. Chaque étape est une trace.
- **Viabilis enseignant** : l'enseignant ouvre les séances, suit l'état estimé de chaque élève (charge, agentivité, pensée divergente, maîtrise), voit les ruptures qui menacent, reçoit une recommandation tirée de la règle de la séquence et l'applique à un élève ou à la classe. Il exporte les données pour la recherche et peut tout effacer.

Deux versions partagent la même logique (`serveur/web/commun/etat.js`) :

| Version | Dossier | Pour qui | Données |
| --- | --- | --- | --- |
| Prototype pilote | `developpement/prototype/viabilis.html` | Adultes volontaires : étudiants INSPÉ, pilote de recherche | Base de l'artefact claude.ai ; IA du compte de chaque participant |
| Application à déployer | `serveur/` | Classes réelles, élèves mineurs | Serveur de l'établissement (SQLite) ; IA appelée par le serveur |

## 1. Prototype pilote

Publié sur claude.ai : https://claude.ai/artifact/TCMsc8SWKoj19Pwsfz4Nfd

- Ouvert par vous (propriétaire), il affiche la vue enseignant ; le bouton en haut à droite montre la vue élève.
- Partagez le lien avec les participants au rôle **Contributeur** : ils arrivent sur la vue élève.
- Règles d'accès vérifiées : un participant n'écrit et ne lit que ses propres traces ; seuls les éditeurs lisent celles de la classe.
- L'IA utilise le compte Claude de chaque participant (une autorisation est demandée au premier appel).

## 2. Application à déployer

### Lancer

Python 3.9 ou plus, sans aucune dépendance à installer.

```bash
cd serveur
VIABILIS_MDP_ENSEIGNANT='un-mot-de-passe-long' VIABILIS_IA=openai \
VIABILIS_IA_URL='https://…/v1/chat/completions' VIABILIS_IA_MODELE='…' VIABILIS_IA_CLE='…' \
python3 serveur.py --port 8080 --base viabilis.sqlite3
```

- Élèves : `https://<serveur>/eleve/` · Enseignant : `https://<serveur>/enseignant/`
- Sur le téléphone ou la tablette, « Ajouter à l'écran d'accueil » installe chaque application avec son icône.
- Placer le serveur derrière un proxy HTTPS (nginx, Apache) de l'établissement ; il n'écoute que sur 127.0.0.1 par défaut.
- Pour une installation sur un serveur de l'université (service systemd, proxy, sauvegardes, mises à jour), voir `INSTALLATION.md`.
- Pour un ordinateur Ubuntu à la maison, avec Apache, derrière une box : `INSTALLATION_MAISON.md` et le script `installer_ubuntu.sh`, qui fait l'installation complète.

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `VIABILIS_MDP_ENSEIGNANT` | Mot de passe enseignant (10 caractères au moins) | obligatoire |
| `VIABILIS_IA` | `fausse` (tests), `anthropic`, `openai`, `gemini`, `mistral`, `ollama` (modèle local) ; toute autre API compatible OpenAI (Albert, vLLM…) avec `openai` et `VIABILIS_IA_URL` | `fausse` |
| `VIABILIS_IA_URL` | Point d'accès de l'API | selon le fournisseur |
| `VIABILIS_IA_CLE` | Clé d'API, jamais envoyée aux navigateurs | vide |
| `VIABILIS_IA_MODELE` | Modèle | `claude-haiku-4-5-20251001`, `gpt-4o-mini`, `gemini-2.0-flash`, `mistral-small-latest`, `llama3.1` selon le fournisseur |
| `VIABILIS_CONSERVATION_JOURS` | Durée de conservation des traces | 365 |

Au démarrage, le serveur refuse un fournisseur inconnu ou une clé manquante, avec un message explicite. Pendant la séance, si l'IA ne répond pas, l'élève voit « L'IA n'a pas répondu » (ou « La clé d'API de l'IA est refusée »). La cause exacte s'affiche dans le terminal du serveur, sans aucune donnée d'élève.

### Tester

```bash
VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8790 --base /tmp/test.sqlite3
```

puis, dans un autre terminal :

```bash
python3 developpement/tests/lancer_tests.py api
```

Le test vérifie : connexion enseignant, création de classe, connexion élève par code et pseudonyme, refus d'un pseudonyme déjà pris, ordre décidé par le serveur (un élève ne peut pas forcer « IA d'abord »), refus de l'IA avant les idées requises, ordre adaptatif selon la charge, validation des réglages, export, cloisonnement (un élève ne lit pas la classe), effacement d'un élève.

### Ce que le serveur garantit

- **L'ordre et le rôle de l'IA sont décidés par le serveur**, à partir de la règle de la classe, du réglage individuel et de la charge déclarée ; ils sont verrouillés pour la séance. L'élève ne peut pas les contourner depuis son navigateur.
- **Les consignes données à l'IA sont écrites côté serveur** ; l'élève n'envoie que ses messages. 40 appels au plus par élève et par séance.
- **Ce qui est envoyé à l'IA** : la consigne de la tâche, les idées de l'élève et ses messages, jamais son pseudonyme ni un identifiant.
- **Effacement** : un élève (depuis sa fiche) ou toute la classe (onglet Données) ; purge automatique au-delà de la durée de conservation.
- Aucune ressource externe : polices système, aucun traceur, en-têtes de sécurité (CSP, nosniff, no-referrer). Les journaux du serveur ne contiennent aucune donnée d'élève.

## 3. Banques d'exercices (GIFT et Moodle XML)

L'enseignant importe des banques de questions depuis l'onglet **Exercices** de l'application enseignant : fichier `.gift`, `.txt` ou `.xml`, ou contenu collé. Les banques exportées d'Éléa ou de Moodle s'importent telles quelles.

| Type de question | GIFT | Moodle XML |
| --- | --- | --- |
| Choix unique | `{=bonne ~fausse ~fausse}` | `multichoice`, `single` vrai |
| Choix multiple (pondéré) | `{~%50%a ~%50%b ~%-100%c}` | `multichoice`, `single` faux |
| Vrai ou faux | `{T}`, `{F}` (et leurs retours) | `truefalse` |
| Réponse courte, phrase à trous | `{=réponse =variante}` ; texte après l'accolade = trou | `shortanswer` (casse respectée si `usecase`) |
| Numérique | `{#3.14:0.01}`, `{#1..5}` | `numerical` avec `tolerance` |
| Appariement | `{=a -> 1 =b -> 2}` | `matching` |

- **Non importés** (et signalés à l'import) : questions ouvertes ou de rédaction (la tâche ouverte de la séance joue ce rôle), descriptions, types non listés, images.
- **Niveaux** : chaque question a un niveau de 1 à 5, choisi à l'import et modifiable. L'enseignant fixe le niveau de la classe et, depuis l'onglet Classe, un niveau individuel par élève.
- **Dans la séance** : un nombre d'exercices par élève (1 à 10), avant ou après la tâche ouverte. Le serveur tire les questions au niveau de l'élève, puis aux niveaux voisins, en évitant celles déjà faites ; le tirage est fixé pour la séance.
- **Correction côté serveur** : les bonnes réponses ne sont jamais envoyées au navigateur. Deux essais par question ; la réponse attendue s'affiche après le second échec, avec les retours de la banque.
- **Traces** : score (meilleur essai et premier essai), nombre d'essais, durée.

La difficulté devient ainsi une commande de régulation :
- la maîtrise estimée intègre le taux de réussite ;
- la charge estimée intègre les échecs au premier essai (pour 30 %) ;
- la recommandation propose un niveau plus accessible à un élève surchargé dont la maîtrise est insuffisante, et un niveau supérieur à un élève autonome et peu chargé.

La recommandation part du niveau des exercices que l'élève a réellement passés : appliquer une recommandation ne la fait pas glisser d'un niveau supplémentaire.

Exemples fournis : `serveur/exemples/fractions.gift` et `serveur/exemples/sciences.xml`.

**Banques CM1** (`serveur/exemples/ecole/`, 261 questions, 30 fichiers) : un fichier par discipline et par niveau (`maths_`, `francais_`, `histoire_`, `geographie_`, `sciences_`, `anglais_` suivi de `niveau1` à `niveau5`), à importer en choisissant le niveau indiqué dans son nom. Mathématiques et français :

| Niveau | Mathématiques | Français |
| --- | --- | --- |
| 1 · très accessible (révisions de CE2) | calcul posé et mental, tables, double et moitié, comparaison, unités, monnaie | nature des mots, pluriel et féminin, ordre alphabétique, contraires, présent d'être et d'avoir |
| 2 · accessible | grands nombres, × 10 et × 100, fraction d'une pizza, rendu de monnaie, périmètre du carré, conversions, durées | accord sujet-verbe, homophones a/à et et/est, synonymes, familles de mots, déterminant, adjectif, sujet |
| 3 · attendus de fin de CM1 | nombres jusqu'au million, multiplication posée, division euclidienne, fraction d'une quantité, dixièmes, problèmes, polygones | imparfait, futur, passé composé, son/sont, on/ont, ces/ses, accords dans le groupe nominal, classes de mots, préfixes, compréhension |
| 4 · exigeant | décimaux (comparer, intercaler, centièmes), problèmes à étapes, aire et périmètre du rectangle, fractions supérieures à 1, symétrie | imparfait et futur irréguliers, passé composé avec être, compléments d'objet et de temps, suffixes, sens figuré, homophones |
| 5 · très exigeant (vers le CM2) | proportionnalité, ordre de grandeur, trois quarts d'une quantité, conversions de masses, problème de division, somme de décimaux, angles | passé simple, accords avec être, fonctions, types de phrases, implicite, vocabulaire précis, mots invariables |

Histoire, géographie, sciences et anglais (8 questions par niveau) :

| Discipline | Contenus, du niveau 1 au niveau 5 |
| --- | --- |
| Histoire | Préhistoire et Gaule, Romains, Clovis et Charlemagne, le temps des rois (Saint Louis, François Ier, Henri IV, Louis XIV), la Révolution et l'Empire ; frise chronologique, siècles, sources, durées |
| Géographie | Se repérer (carte, légende, points cardinaux, échelle), la France (relief, fleuves, mers, voisins, régions, outre-mer), habiter et se loger, consommer l'eau et l'énergie, communes et collectivités |
| Sciences et technologie | États de l'eau, mélanges et séparation, besoins du vivant, chaînes alimentaires, classification, corps humain (digestion, respiration, muscles), Terre et système solaire, circuits électriques et matériaux, énergie |
| Anglais | Couleurs, nombres, salutations, jours et mois, famille, corps, classe, météo ; have got, can, like, prépositions, l'heure ; présent simple, négation, questions ; compréhension d'un court texte |

Chaque question a été vérifiée automatiquement : sa bonne réponse obtient 100 % et une mauvaise réponse est refusée. Les réponses courtes exigent l'orthographe exacte, accents compris ; les majuscules ne comptent pas. Les deux-points des énoncés sont échappés (`\:`) pour que les fichiers s'importent aussi dans Moodle. Test : `python3 developpement/tests/lancer_tests.py test_exercices` (14 vérifications) avec un serveur de test lancé sur ce port.

Le prototype pilote (claude.ai) n'intègre pas les exercices : ils ne sont disponibles que dans l'application à déployer.

### Choix adaptatif des exercices (à la manière de ZPDES)

Onglet Exercices, menu « Choix des exercices » : « Au niveau fixé » (par défaut) ou « Adaptatif : selon les progrès de chaque élève ».

- **Le principe** est celui de l'algorithme ZPDES (Clément et al., 2015), utilisé dans Adaptiv'Math. Les niveaux de la banque (1 à 5) jouent le rôle des activités.
- **La zone de chaque élève.** Chaque élève a une **zone de niveaux ouverts**. Elle part du niveau prévu (celui de la classe, ou celui que la recommandation a appliqué à l'élève).
  - Elle s'ouvre au niveau supérieur quand l'élève réussit le plus haut niveau ouvert : au moins 75 % au premier essai sur ses 6 derniers exercices, soit environ deux séances de 4 exercices.
  - Elle se referme sur un niveau maîtrisé (au moins 90 % sur 6 exercices), mais seulement une fois que l'élève a fait au moins 4 exercices du niveau suivant : la transition se fait en douceur.
  - Elle rouvre le niveau inférieur quand il échoue au plus bas (au plus 30 %), plus vite : dès 4 exercices. C'est un ajout à ZPDES, qui ne redescend pas.
  - Ces seuils sont en tête de `serveur/zpdes.py` et peuvent être ajustés après les premiers usages.
- **Le tirage.** Les exercices sont tirés de préférence dans les niveaux où l'élève **progresse** le plus (écart entre ses réussites récentes et précédentes), avec 20 % d'exploration au hasard dans la zone.
- **Ce qui reste à la viabilité.** Le modèle de viabilité continue de régler l'aide (rôle de l'IA, ordre, variante, retrait). Le choix adaptatif ne règle que la difficulté des exercices, et le modèle situe l'élève d'après le niveau le plus haut de sa zone.
- **Suivi.** La fiche de chaque élève affiche ses niveaux ouverts et sa réussite récente par niveau.
- **Code et vérification.** `serveur/zpdes.py` ; vérifié par `developpement/tests/test_zpdes.py` (12 vérifications) : un élève qui réussit monte de niveau en niveau, un élève qui échoue voit le niveau inférieur se rouvrir.

## 4. Vérification des idées, avec retour à l'élève

L'élève peut faire vérifier les idées de la tâche ouverte (bouton « Vérifier mes idées ») et reçoit un retour pour chacune, sans que la réponse lui soit donnée. L'enseignant règle la vérification dans l'onglet **Réglages** :

| Mode | Fonctionnement | Exemple |
| --- | --- | --- |
| **Calculs** | Chaque idée doit être un calcul qui vaut le résultat attendu. Vérification exacte, sans IA, avec nombres autorisés facultatifs, doublons repérés (même somme dans un autre ordre) et nombre de solutions à trouver facultatif | « Payer 10 € avec des pièces de 1 €, 2 € et 5 € » : résultat 10, nombres 1 ; 2 ; 5, 10 solutions |
| **IA** | L'IA juge chaque idée d'après les critères de réussite écrits par l'enseignant, explique ce qui ne va pas et pose une question | « Invente un problème avec une fraction » : critères « contient une fraction, une question, et peut se résoudre » |

- **Retours** :
  - « juste » ;
  - « à revoir », avec ce qui ne va pas et une question pour avancer (« Ce calcul vaut 9 : ce n'est pas assez. Que pourrais-tu changer pour obtenir 10 ? ») ;
  - « déjà trouvée » ;
  - un bilan, qui dit s'il manque des solutions sans dire lesquelles.
- **Nombre de vérifications limité** (3 par défaut) : l'élève ne peut pas corriger au hasard jusqu'à ce que tout soit juste.
- **Côté enseignant** : la part d'idées justes est visible sur la carte de l'élève et dans sa fiche, idée par idée. Elle entre dans l'estimation de la maîtrise et dans l'export CSV.
- **Ce que comprend le mode Calculs** : `5 + 2 + 2 + 1`, `5€ + 5€`, `2 × 5`, `5 et 5`, `10 = 5 + 5`, les parenthèses, les décimaux avec virgule.
- **Doublons** : deux calculs qui ne diffèrent que par l'ordre des termes d'une somme ou d'un produit (`3 × 7 + 5 − 2` et `5 + 7 × 3 − 2`) comptent pour une seule solution.
- **Option « chaque nombre une seule fois »**, pour les problèmes du type « le compte est bon ».
- **Problèmes de recherche fournis**, avec leurs exercices de vérification :
  - « Payer 10 € » (`maths_probleme_10euros.gift`, niveau 4 : 10 solutions) ;
  - « Le compte est 24 » (`maths_probleme_compte24.gift`, niveau 5 : avec 2, 3, 5, 7 et +, −, ×, 4 solutions vraiment différentes, vérifiées par énumération).
- Test : `python3 developpement/tests/lancer_tests.py test_verification` (9 vérifications, dont l'absence de solution dans les retours).


**Robustesse de la vérification par l'IA.** La vérification demande à l'IA une réponse en JSON. Les modèles en produisent parfois un imparfait : texte autour, bloc ```json, virgules en trop, guillemets typographiques, retours à la ligne, réponse coupée par la limite de longueur. Le serveur les lit quand même ; d'une réponse coupée, il garde les idées complètes. Si la réponse reste illisible ou trop lente, il refait un essai :
- **délai :** deux minutes ;
- **longueur :** assez de place pour un retour par idée.

Si la vérification échoue encore, l'élève voit « La vérification n'a pas abouti ». La cause exacte (refus du fournisseur, modèle inconnu, délai, réponse illisible) s'affiche dans la fenêtre du serveur, sur une ligne qui commence par `[IA]`. Cette ligne ne contient aucune donnée d'élève. `developpement/tests/test_lecture_ia.py` vérifie la lecture des réponses imparfaites.

## 5. Différenciation : variantes, coups de pouce, groupes de besoin, lecture à voix haute

**Variantes** (onglet Réglages → « Variantes de la tâche ») : en plus de la tâche standard, une variante **accessible** et une variante **exigeante**, avec le même objectif pour toute la classe.
- Chaque variante a sa consigne et, pour la vérification par calculs, son propre résultat attendu et son propre nombre de solutions. Exemple : obtenir 12, 24 ou 100 avec 2, 3, 5 et 7.
- Les champs vides reprennent ceux de la tâche standard.
- La variante d'un élève se règle depuis sa carte (onglet Classe) ; les recommandations en proposent une.
- Elle est fixée au début de la séance, comme l'ordre, et le serveur l'impose.
- **L'élève ne voit jamais le nom de sa variante**, pour éviter toute étiquette : il ne reçoit que sa consigne.

**Coups de pouce gradués** : jusqu'à 3 par tâche ou par variante, du plus léger au plus précis, sans jamais donner la réponse.
- L'élève les ouvre un par un avec « Voir un coup de pouce (1 sur 3) ».
- Le serveur les garde et ne dévoile que le suivant ; il note combien chaque élève en a ouvert.
- Un coup de pouce compte comme une aide dans l'estimation de l'agentivité, comme une demande à l'IA.
- L'IA connaît les coups de pouce déjà donnés et ne les répète pas.

**Recommandation de variante :**
- variante plus accessible si l'élève est surchargé et que sa maîtrise est insuffisante ;
- variante plus exigeante s'il est peu chargé et autonome, ou peu chargé avec une maîtrise d'au moins 0,8 ;
- un seul cran à la fois, à partir de la variante réellement travaillée à la dernière séance.

Pour la viabilité, sans exercices, la variante accessible abaisse d'un cran la difficulté prise en compte par le modèle, et la variante exigeante la relève d'un cran.

Test : `python3 developpement/tests/lancer_tests.py test_variantes` (13 vérifications).

**Groupes de besoin** (onglet **Groupes**) : pour la séance suivante, l'application range chaque élève dans un des trois groupes, à partir de son état estimé et de sa viabilité, avec la raison du choix.

| Groupe | Qui (proposition) | Réglages appliqués |
| --- | --- | --- |
| **Atelier dirigé** | hors du noyau ou du bassin de capture ; surcharge ou dépendance ; charge élevée et maîtrise insuffisante | IA d'abord, qui donne des éléments ; variante accessible |
| **Travail accompagné** | les autres élèves, dans le domaine | réflexion d'abord, IA qui questionne ; tâche standard |
| **Défi en autonomie** | auto-soutenu, ou autonome et peu chargé, ou en risque d'ennui ; toujours avec une maîtrise solide (au moins 0,6) | IA retirée ; variante exigeante |

L'enseignant déplace qui il veut, puis clique sur « Appliquer ces groupes ». Les variantes ne sont appliquées que si elles sont activées. Les groupes sont recalculés à chaque séance : aucun élève n'y est enfermé. Côté élève, un message neutre seulement : « Aujourd'hui, ton enseignant travaille avec toi au début de la séance » (atelier) ou « Aujourd'hui, un défi t'attend » (défi).

**Lecture à voix haute** (Réglages → « Lecture à voix haute », activée par défaut) : un bouton « Écouter » sur la consigne, chaque exercice (avec ses choix), chaque coup de pouce, la dernière réponse de l'IA et les retours de vérification.
- La langue de lecture se règle par séance : français, anglais, espagnol, allemand, italien. Une séance d'anglais est lue en anglais, la suivante en français.
- Seules les **voix installées sur l'appareil** sont utilisées : aucun texte n'est envoyé à un service extérieur. Si aucune voix de la langue choisie n'est installée, le bouton n'apparaît pas. Sur iPad et Android, des voix françaises sont généralement installées ; d'autres langues s'ajoutent dans les réglages d'accessibilité de la tablette.

Test : `python3 developpement/tests/lancer_tests.py test_groupes` (6 vérifications côté serveur).

## 6. Plusieurs séances, retour des élèves, reprise pour s'améliorer

**Plusieurs séances ouvertes en même temps.** La carte **Séances** de l'onglet Classe liste toutes les séances, avec pour chacune sa consigne et un bouton **Fermer** ou **Rouvrir**. « Créer la séance N » en ajoute une, sans fermer les précédentes.
- Chaque séance garde sa tâche : consigne, coups de pouce, variantes, vérification, exercices.
- Les réglages de l'onglet Réglages s'appliquent à la séance la plus récente ; les séances précédentes gardent leur consigne.
- Une séance fermée n'accepte plus d'écriture.

**Terminer définitivement et voir la correction.** Une fois sa séance envoyée, l'élève a deux possibilités : la reprendre pour s'améliorer, ou la **terminer définitivement**. Dans ce second cas, une confirmation lui est demandée, puis :
- **la séance est verrouillée** : plus de modification d'idée, de reprise, d'exercice, de vérification, de coup de pouce ni d'IA ;
- **ses idées reçoivent une correction finale**, par calcul ou par l'IA selon les critères de la séance. Ce n'est pas l'une des vérifications limitées de la séance : chaque idée est marquée juste, à revoir ou déjà trouvée, avec son explication. Sans vérification prévue, ou hors ligne pour une vérification par l'IA, le message indique que l'enseignant lira les idées ;
- **la correction des exercices** montre, pour chaque exercice tiré, la réponse qu'il a donnée, si elle est juste, la bonne réponse et l'explication de la banque. Les réponses données sont désormais enregistrées pour cela ;
- **en évaluation aussi**, la correction s'affiche dès que l'élève termine définitivement. C'est un choix : les premiers à finir pourraient la montrer aux autres. Ne proposez donc la fin définitive qu'au moment de ramasser.

Dans la fiche de l'élève, la séance est marquée « Terminée définitivement » avec la date. Le bouton **Autoriser à reprendre** la rouvre, par exemple après un clic par erreur ; la correction est alors refaite à la prochaine fin définitive.

**Modifier ou retirer une idée.** Tant que la séance est en cours, chaque idée de l'élève porte deux boutons :
- **Modifier** : l'idée se rouvre dans la case de saisie, en police à chasse fixe pour un programme. Une idée modifiée perd son retour de vérification et doit être vérifiée à nouveau ; le nombre de vérifications reste limité.
- **Retirer** : une confirmation est demandée, puis l'idée quitte la liste.

Rien n'est perdu pour l'enseignant ni pour la recherche :
- **dans la trace** : l'ancienne version reste (`avant`, avec l'heure de modification), et l'idée retirée aussi (`ideesRetirees`) ;
- **dans la fiche de l'élève** : les idées modifiées sont marquées « modifiée », avec leurs versions précédentes, et les idées retirées sont regroupées sous « Idées retirées par l'élève ».

Une fois la séance terminée, l'élève améliore son travail avec « Reprendre pour m'améliorer ».

**Retour d'un élève : il choisit son pseudonyme dans une liste.** L'élève saisit le code de la classe, puis **touche son pseudonyme** parmi ceux déjà créés, ou en crée un nouveau. Un pseudonyme déjà pris ne peut pas être recréé.

Aucun code n'est demandé par défaut. Un élève pourrait donc choisir le pseudonyme d'un camarade : c'est un compromis assumé, à surveiller en classe. L'option **« Exiger le code personnel »** (onglet Données) rétablit un code à 4 chiffres, donné à la première connexion et listé dans l'onglet Données pour être imprimé.

**Choisir sa séance et reprendre pour s'améliorer.** Si plusieurs séances sont ouvertes, l'élève voit l'écran **Mes séances**, avec l'état de chacune : à commencer, en cours, ou terminée (avec son nombre d'idées et d'essais). Sur une séance terminée, **« Reprendre pour m'améliorer »** :
- garde ses idées, qu'il peut compléter ou corriger ;
- remet à zéro le compteur de vérifications, pour qu'il refasse vérifier ses idées ;
- lui fait refaire **uniquement les exercices ratés** ;
- lui redemande le bilan de fin (difficulté, compréhension).

Le serveur compte les essais ; l'élève ne peut pas modifier ce nombre. L'enseignant voit « séance 1, essai 2, en cours » sur la carte de l'élève, et le progrès dans sa fiche (par exemple 1 puis 2 idées justes).

**Compatibilité.** Les classes créées avant cette version gardent leur séance ouverte. Les élèves existants apparaissent dans la liste.

Test : `python3 developpement/tests/lancer_tests.py test_seances` (16 vérifications).

**Modifier ou effacer une séance.** Chaque ligne de la carte Séances a trois boutons : **Fermer/Rouvrir**, **Modifier**, **Effacer**.
- **Modifier** ouvre la tâche de cette séance : consigne, coups de pouce, variantes, vérification. Pour une séance précédente, seule sa tâche est modifiée ; la séance la plus récente se règle aussi dans l'onglet Réglages. Les changements sont visibles tout de suite, y compris par les élèves qui ont déjà commencé, et leur travail est conservé.
- **Effacer** supprime la séance et tout le travail des élèves qui s'y rapporte : idées, échanges avec l'IA, exercices, vérifications, coups de pouce. Une confirmation indique combien d'élèves sont concernés. C'est irréversible.
- Les séances restantes sont renumérotées à l'affichage, pour l'enseignant comme pour les élèves : après avoir effacé la séance 2, l'ancienne séance 3 s'affiche « Séance 2 », et la suivante créée s'appelle « Séance 3 ».
- En interne, chaque séance garde son identifiant, qui ne change jamais : les traces des élèves restent attachées à la bonne séance. Les exports CSV donnent les deux : `seance` (identifiant) et `numero` (numéro affiché au moment de l'export).

Test : `python3 developpement/tests/lancer_tests.py test_effacer` (12 vérifications).

**Modèles de séances prêtes à l'emploi.** En haut de l'onglet Réglages, la carte **Modèles de séances** propose 21 tâches ouvertes de CM1 (les 12 ci-dessous, plus Faire 15, Rectangles de 12 carreaux, Toutes les moitiés, La famille de « terre », Faire flotter la pâte à modeler, De quand date cet objet ?, Une cour pour tous, *In the classroom*, *Someone I like*). Chaque modèle fournit :
- la consigne ;
- 3 coups de pouce ;
- une variante accessible et une variante exigeante ;
- la vérification ;
- la banque d'exercices conseillée.

| Discipline | Modèle | Vérification |
|---|---|---|
| Mathématiques | Payer 10 € (pièces de 1, 2, 5 €) | calculs : 10, 10 solutions |
| Mathématiques | Le compte est 24 (2, 3, 5, 7) | calculs : 24, chaque nombre une fois, 4 solutions |
| Mathématiques | Mille façons d'écrire 100 | calculs : 100 |
| Mathématiques | Avec 1, 2, 3 et 4 | calculs : 10, chaque nombre une fois |
| Mathématiques | Rectangles de périmètre 24 cm | IA, critères |
| Français | Une phrase, cinq mots | IA, critères |
| Français | Inventer la suite (la clé dorée) | IA, critères |
| Sciences | La graine a-t-elle besoin de lumière ? | IA, critères (un seul facteur, témoin) |
| Sciences | Garder un glaçon le plus longtemps | IA, critères |
| Géographie | Aller à l'école en polluant moins | IA, critères |
| Histoire | Questions à un enfant gaulois | IA, critères (pas d'anachronisme) |
| Anglais | My favourite animal (lecture en anglais) | IA, critères ; retours en français |

Deux boutons :
- **Remplir la séance N avec ce modèle** charge le modèle dans les champs. Rien n'est envoyé aux élèves avant « Enregistrer » ; « Annuler le modèle » revient en arrière. Le même bouton existe dans « Modifier » pour une séance précédente.
- **Créer la séance N+1 avec ce modèle** garde la séance en cours telle quelle, crée la suivante et l'ouvre aussitôt.

Les banques d'exercices conseillées s'importent à part, dans l'onglet Exercices, depuis `serveur/exemples/ecole/`. Les modèles sont dans `serveur/web/commun/modeles.json`. On peut en ajouter en copiant un bloc : `tache`, `indices`, `verification`, `variantes`, et éventuellement `lecture` pour la langue. Les nombres de solutions annoncés ont été vérifiés par recherche exhaustive.

Test : `python3 developpement/tests/lancer_tests.py test_modeles`.

**Proposer la séance suivante.** À partir de la séance 2, « Créer la séance N+1 » (carte Séances) ouvre **des propositions pour la suite**, construites à partir de la séance précédente et des résultats de chaque élève.

*Le bilan de la séance précédente.* Chaque élève est classé :
- **en difficulté** : groupe « atelier » proposé, ou moins de la moitié d'idées justes, ou d'exercices réussis ;
- **à l'aise** : groupe « défi » proposé, au moins 75 % d'idées justes et, s'il y a un nombre de solutions à trouver, au moins 60 % d'entre elles ;
- **au niveau attendu** dans les autres cas ;
- **sans trace** s'il n'a pas fait la séance.

*Jusqu'à quatre propositions*, tirées du modèle de la séance précédente (chaque modèle indique ses suites) :
- **Consolider** : une tâche voisine plus accessible. Conseillée si au moins 40 % des élèves sont en difficulté.
- **Prolonger** : la suite logique. Conseillée par défaut.
- **Approfondir** : une tâche plus exigeante. Conseillée si au moins la moitié des élèves sont à l'aise.
- **Varier** : une autre discipline, la moins pratiquée jusqu'ici. Le texte signale si la pensée divergente de la classe est basse.
  Seulement en classe polyvalente (« Toutes les disciplines ») : ailleurs, toutes les propositions restent dans la discipline de la classe (aucun lien entre créole et maths, ni entre Galois, Python et Linux).

Une tâche déjà faite est signalée. Si la séance précédente avait une consigne libre, les propositions suivent son niveau de difficulté.

*Pour chaque élève*, l'application prévoit une variante et un réglage d'IA, avec la raison :
- en difficulté → variante accessible, atelier dirigé (ou travail accompagné) ;
- au niveau attendu → tâche standard, travail accompagné ;
- à l'aise → variante exigeante, défi en autonomie sans IA.

Une case permet de ne pas les appliquer. Une autre case garde la séance précédente ouverte pour les élèves qui ne l'ont pas terminée ou qui sont en difficulté (cochée s'il y en a). Ils la reprennent avec « Reprendre pour m'améliorer ».

Tout reste modifiable ensuite, élève par élève, dans l'onglet Classe. « Autre modèle ou consigne libre » mène à l'onglet Réglages. Ces règles sont des choix pédagogiques simples, pas un diagnostic : à ajuster selon votre connaissance des élèves.

Test : `python3 developpement/tests/lancer_tests.py test_suites`.

## 6 bis. Mieux aider chaque élève

**Conseil sur la façon de chercher.** Pour les tâches où il faut trouver toutes les façons de faire une somme (Payer 10 €, Faire 15…), la vérification ajoute un conseil de méthode.
- Le serveur calcule toutes les solutions et regarde lesquelles l'élève a trouvées. Il lui dit **où chercher**, jamais quoi écrire. Exemples : « le 5 est utilisé deux fois, une fois : as-tu cherché des solutions où il est utilisé zéro fois ? », ou « range tes solutions dans un ordre ».
- En vérification par l'IA, l'IA ajoute un conseil d'une phrase sur la démarche.

**Comment as-tu cherché ?** Avant de vérifier ses idées, une fois par essai, l'élève indique en une touche comment il a cherché : au hasard, dans un ordre, en transformant une idée, avec une aide, autrement. Il peut préciser en quelques mots. En fin de séance, il peut dire ce qui l'a aidé. L'enseignant voit ces réponses sur la carte de l'élève (« A cherché : … · Aidé par : … »). Elles ne sont pas utilisées dans l'estimation de l'état.

**Mon parcours.** L'élève voit, pour chaque séance, ses essais successifs (« Essai 1 : 2 idées justes → Essai 2 : 4 idées justes ») et ses exercices. Un message le félicite s'il progresse. Il se compare seulement à lui-même. L'historique des essais est tenu par le serveur.

**Un mot de l'enseignant.** Dans la fiche d'un élève (« Détail »), « Un mot pour l'élève » envoie un court message, affiché au début de sa prochaine séance avec un bouton « Écouter ». L'enseignant voit s'il a été lu.

**Galerie d'idées.** Dans l'onglet Classe, la carte « Galerie d'idées » liste les idées de la séance, les plus originales en premier. L'originalité est la part des autres élèves qui n'ont rien écrit de semblable. L'enseignant en choisit jusqu'à 12 et les publie, sans les noms.
- Les élèves les voient seulement après avoir terminé la séance, avec une invitation à reprendre pour ajouter une idée avec leurs mots.
- Pour une tâche vérifiée par calculs, un avertissement rappelle qu'on peut recopier des solutions lors d'une reprise.

**Accessibilité.** Chaque élève règle son affichage dans la carte « Affichage » : texte plus grand, lecture facilitée (police sans empattement, lettres et lignes espacées), images dans les choix. Le réglage le suit sur toutes les tablettes. L'enseignant peut aussi proposer la **dictée vocale** (Réglages → Lecture à voix haute). Le bouton « Dicter » n'apparaît que si l'appareil reconnaît la parole **sur l'appareil**, sans envoyer la voix à un service extérieur ; sinon il reste caché.

**Qualité des réponses de l'IA.**
- *Blocage automatique* : pour une tâche vérifiée par calculs, une réponse de l'IA qui contient une solution n'est jamais montrée. L'élève reçoit à la place une question sur sa démarche, et le blocage est enregistré.
- *Signalement* : dans la fiche d'un élève, chaque réponse de l'IA peut être signalée (donne la réponse, erreur, inadaptée au niveau, hors sujet).
- L'onglet Données résume les blocages et les signalements et exporte tous les échanges (« Échanges avec l'IA (CSV) »).

**Journal des décisions (validation).** Chaque changement de réglage d'un élève est enregistré avec son origine : recommandation appliquée, toutes les recommandations, groupes, suite proposée, ou choix manuel. Il s'exporte depuis l'onglet Données (« Journal des décisions (CSV) »). Croisé avec l'export des indicateurs, il permet de vérifier, sur des séances réelles, si les recommandations aident vraiment les élèves. C'est la condition pour aller plus loin dans l'adaptation automatique.

Messages, signalements et journal suivent la même durée de conservation que les traces. Ils sont effacés avec l'élève, la séance ou la classe.

Test : `python3 developpement/tests/lancer_tests.py test_aide` (25 vérifications).

## 6 bis 2. Séquence CM1 : résoudre des problèmes

Six séances d'environ 45 minutes de « problèmes pour chercher », de plus en plus ambitieuses. Chaque séance travaille une façon de raisonner différente. L'élève cherche plusieurs méthodes et explique toujours **comment il est sûr** de sa réponse.

| Séance | Problème | Ce qu'on apprend à faire |
|---|---|---|
| 1 | Les poignées de main (6 enfants, puis 10) | dénombrer de façon organisée, sans oubli ni double compte : 15, puis 45 |
| 2 | Poules et lapins (10 têtes, 28 pattes) | essais organisés en tableau, puis raisonnement « et si tous étaient des poules ? » : 6 poules et 4 lapins |
| 3 | Le nombre mystère (trois chiffres, quatre indices) | trouver toutes les solutions et prouver qu'il n'y en a pas d'autre : 291 et 633 ; inventer une énigme à une seule solution |
| 4 | Les carrés d'allumettes | trouver une règle, la justifier par la figure, l'utiliser à l'envers : 31 allumettes pour 10 carrés, 33 carrés avec 100 allumettes |
| 5 | Le plus grand produit (découper 10, puis 12) | chercher un optimum, conjecturer une règle : 36, puis 81 (le plus possible de 3) |
| 6 | Toujours vrai ? (pair et impair) | distinguer exemples et preuve, réfuter par un contre-exemple : 1 + 3 + 5 = 9 |

**Contenu de chaque séance.**
- **Accompagnement :** trois coups de pouce, une variante accessible avec de petits nombres et un dessin guidé, et une variante exigeante qui fait généraliser (20 ou 100 enfants, méthode sans essais, grille d'allumettes, règle pour n'importe quel nombre d'impairs).
- **Critères de réussite de l'IA :** ils donnent les résultats attendus, les démarches à valoriser et les erreurs fréquentes (6 × 6 = 36, 4 × 10 = 40, croire qu'une phrase est vraie parce qu'elle marche sur trois exemples). Ils demandent de juger la démarche autant que le résultat. Toutes les valeurs ont été calculées.

**Exercices.** `serveur/exemples/ecole/maths/maths_problemes_cm1.gift` (14 problèmes corrigés automatiquement, avec une explication, à importer au niveau 4) est produit par `generer_problemes_cm1.py`. Il contient des problèmes voisins : tournoi, vélos et tricycles, escargot dans le puits, âges.

## 6 bis 3. Séquence CM1 de recherche : les sommes de nombres consécutifs

Six séances d'environ 50 minutes autour d'un seul grand problème, pour que les élèves vivent une recherche de mathématicien. Ils explorent, conjecturent, cherchent des contre-exemples, prouvent, puis communiquent leurs résultats.

**La question :** quels nombres peut-on écrire comme une somme d'au moins deux nombres entiers consécutifs (à partir de 1), comme 9 = 4 + 5 = 2 + 3 + 4 ? Réponse : tous, sauf 1, 2, 4, 8, 16, 32, 64… (chacun est le double du précédent). Ce résultat surprenant est à la portée de la classe, et une partie s'y démontre.

| Enquête | Ce que font les élèves | Ce qu'ils découvrent |
|---|---|---|
| 1. Explorer | écrire les nombres de 3 à 30, ranger dans un tableau | certains nombres résistent : 1, 2, 4, 8, 16 |
| 2. Les nombres qui résistent | formuler des conjectures (« je pense que… »), les tester | les résistants doublent ; le suivant, 64, résiste bien ; tous les impairs à partir de 3 s'écrivent |
| 3. Prouver nos premières découvertes | passer des exemples à la preuve | impair = k + (k + 1) (101 = 50 + 51) ; trois consécutifs = 3 × celui du milieu ; cinq consécutifs = 5 × celui du milieu |
| 4. Le record d'écritures | chercher toutes les écritures de façon organisée | 45 détient le record jusqu'à 50, avec 5 écritures ; les nombres qui ont beaucoup de diviseurs impairs ont beaucoup d'écritures |
| 5. Pourquoi 16 résiste-t-il ? | prouver une impossibilité en étudiant tous les cas | ni 2, ni 3, ni 4, ni 5 consécutifs, et 6 consécutifs font déjà au moins 21 ; même preuve pour 32 |
| 6. Le séminaire des chercheurs | écrire l'article de la classe | distinguer prouvé et conjecturé, poser une nouvelle question |

**À faire entre les séances.** À la fin de chaque séance, choisissez quelques découvertes d'élèves pour la **galerie** de la classe. Les élèves les retrouvent, sans les noms, au début de la séance suivante : c'est le « mur des découvertes » de la recherche.

**Critères de réussite.** Ils demandent à l'IA de vérifier chaque écriture et chaque preuve. Elle doit valoriser une conjecture juste même non prouvée, et faire chercher un contre-exemple sans le donner. Toutes les valeurs citées ont été calculées par recherche exhaustive, ce qui a fait corriger une affirmation fausse : en commençant à 0, seul 1 change, 2, 4, 8… résistent toujours.

**Exercices.** `serveur/exemples/ecole/maths/maths_recherche_consecutifs.gift` (12 questions corrigées automatiquement, à importer au niveau 4) est produit par `generer_recherche_consecutifs.py`. La séance 6 n'a pas d'exercices.

## 6 ter. Enseignement supérieur : la théorie de Galois

**Discipline de la classe** (Réglages → Règle de la classe). Une classe suit une discipline, et elle ne voit que les modèles de séances et les suites de cette discipline : une classe de créole ne se voit jamais proposer de maths, une classe de Linux ni Python ni Galois.
- **Par défaut** (« Celle de ses séances »), la discipline est celle des modèles dont viennent ses séances. Une classe sans séance voit tous les modèles de son public, pour choisir la première.
- On peut aussi la fixer explicitement.
- **« Toutes les disciplines (classe polyvalente) »** convient à une classe d'école où l'on enseigne plusieurs matières : le menu montre alors tous les modèles du public, et les suites proposent aussi de varier de discipline.

**Public de la classe** (Réglages → Règle de la classe : école élémentaire, collège, lycée, enseignement supérieur). Ce réglage change trois choses :
- **le ton et l'exigence de l'IA** :
  - le tuteur s'adresse à l'élève avec le vocabulaire et la rigueur de son niveau ; dans le supérieur, il écrit les formules en texte simple (√2, ∛2, ζ₅, Gal(K/Q), [K:Q]) ;
  - la vérification des idées exige des justifications : une idée vraie mais mal justifiée est « à revoir », et une affirmation dont l'IA n'est pas sûre n'est pas validée ;
- **les modèles de séances proposés** : seuls ceux du public de la classe apparaissent (voir aussi « Discipline de la classe » ci-dessous) ;
- **la saisie des idées** : dans le supérieur, une idée peut être une démonstration (case de 5 lignes, jusqu'à 1 500 caractères).

**Introduction à l'irréductibilité (4 séances, avant la progression).** Pour un étudiant qui découvre ces méthodes, chaque séance en présente une seule, sur des exemples guidés : listes de polynômes à étudier, pièges classiques, puis exemples à inventer. La variante accessible est un calcul pas à pas.

| Séance | Modèle | Contenu |
|---|---|---|
| I1 | Racines rationnelles | candidats p/q ; en degré 2 ou 3, sans racine ⇔ irréductible ; le piège x⁴ + 3x² + 2 = (x² + 1)(x² + 2) |
| I2 | Le critère d'Eisenstein | les trois conditions une à une ; polynômes non unitaires ; x³ + 3x + 9, irréductible bien que le critère échoue |
| I3 | Réduction modulo un nombre premier | calculs dans F₂ et F₃ ; une réduction réductible ne prouve rien ; coefficient dominant ; x⁴ + 1 |
| I4 | Changement de variable | f(x + a) ; x² + 1, x² + x + 1, (x + 1)³ − 2, x⁴ + 1, Φ₅ ; polynôme réciproque en variante |

Leurs banques, `galois_intro_racines.gift`, `galois_intro_eisenstein.gift`, `galois_intro_modulo.gift` et `galois_intro_changement.gift` (7 questions chacune), s'importent au niveau 1. Le script `developpement/generateurs/generer_banques_intro.py` les produit et vérifie chaque affirmation avec SymPy. Les banques de la progression montent alors d'un niveau : `galois_niveau1` au niveau 2, … , `galois_niveau4` et `galois_niveau5` au niveau 5. Comme les quatre banques d'introduction partagent le niveau 1, n'activez que celle de la séance en cours (onglet Exercices) : un étudiant ne tombera pas sur le critère d'Eisenstein avant de l'avoir vu.

**Progression de théorie de Galois (licence, 8 séances).** Chaque séance a une tâche ouverte, trois coups de pouce, une variante accessible, une variante exigeante et des critères de réussite détaillés pour la vérification par l'IA.

| Séance | Modèle | Tâche ouverte |
|---|---|---|
| 1 | Polynômes irréductibles | prouver l'irréductibilité en variant les méthodes (Eisenstein, réduction modulo p…) |
| 2 | Degré d'une extension | [Q(√2, √3) : Q] = 4 de plusieurs façons, éléments primitifs |
| 3 | Automorphismes d'un corps | Q(√2, √3) contre Q(∛2) : extensions normales |
| 4 | Corps de décomposition de x³ − 2 | degré 6, groupe S₃ par plusieurs arguments |
| 5 | La correspondance de Galois | sous-groupes de S₃ et sous-corps de Q(∛2, j) |
| 6 | Extensions cyclotomiques | Q(ζₙ) : degré φ(n), groupe (Z/nZ)ˣ, sous-corps quadratiques |
| 7 | Discriminant et cubiques | groupes A₃ et S₃ (et, en variante, les groupes de degré 4) |
| 8 | Résolubilité par radicaux | x⁵ − 4x + 2 et d'autres quintiques de groupe S₅ |

Les exemples cités dans les critères (discriminants, factorisations, polynômes minimaux, nombres de racines réelles, réductions modulo p) ont été vérifiés par calcul formel (SymPy).

**Banques d'exercices de la progression** (`serveur/exemples/superieur/galois/galois_niveau1.gift` à `galois_niveau5.gift`, 8 questions chacune, corrigées automatiquement, à importer aux niveaux 2 à 5) : réponses numériques (degrés, ordres de groupes, discriminants), choix uniques et vrai/faux.

**Avant de les utiliser avec un étudiant :**
- **la vérification par l'IA dépend du modèle de langage.** Juger une démonstration de théorie de Galois dépasse un petit modèle local (par exemple qwen2.5:3b) : il risque de valider des erreurs ou de refuser des preuves justes. Pour ces séances, un modèle plus puissant (Claude, Mistral Large, GPT-4o…) est fortement conseillé. Sinon, mieux vaut désactiver la vérification par l'IA et s'appuyer sur les exercices corrigés automatiquement et sur vos propres retours.
- **les estimations de l'état et les règles** ont été mises au point pour une classe de CM1. La charge reste déclarée par l'étudiant et la maîtrise mesurée par les solutions vérifiées, mais les seuils n'ont pas été éprouvés dans le supérieur, ni avec un seul étudiant.

## 6 quater. Programmation : Python pour la microbiologie (M1, débutants, 12 h)

**Saisie de code** (Réglages → La tâche → « Les idées sont des programmes », réglable séance par séance) :
- l'élève colle ou écrit son programme dans une case en police à chasse fixe : Tab indente de 4 espaces, Entrée passe à la ligne, Ctrl+Entrée (⌘+Entrée sur Mac) ajoute l'idée ; jusqu'à 4 000 caractères ;
- les programmes gardent leur indentation à l'affichage, chez l'élève comme chez l'enseignant ; les énoncés d'exercices qui contiennent du code et les consignes qui contiennent des données (mesures, fichier FASTA) gardent leurs retours à la ligne ;
- le tuteur IA ne donne jamais de programme complet : au plus une ligne, un nom de fonction à explorer ou une question sur une ligne précise, et il fait tester le code sur un petit exemple ;
- la vérification par l'IA déroule le code à la main sur un ou deux exemples (elle ne l'exécute pas) et signale les erreurs probables, sans réécrire le programme corrigé.

**L'application n'exécute jamais le code des élèves.** C'est un choix de sécurité. L'étudiant travaille dans son propre environnement, puis colle son programme avec sa sortie en commentaire (`# sortie : …`). Pour des débutants, le plus simple est **Basthon** (notebook Python dans le navigateur, sans installation, avec NumPy et matplotlib) ; Jupyter convient aussi.

**Progression pour des étudiants de master de microbiologie qui n'ont jamais programmé (6 séances de 2 h, public « supérieur »).** Chaque séance introduit peu de notions nouvelles, sur un objet de microbiologie. Elle a une tâche ouverte, trois coups de pouce, une variante accessible (programme à compléter), une variante exigeante et des critères de réussite chiffrés. Les critères demandent à l'IA de juger en débutant : un programme simple et correct est réussi, les fautes de frappe et de syntaxe sont expliquées avec le message d'erreur, et la lecture du message d'erreur est valorisée.

| Séance | Modèle | Tâche ouverte | Python |
|---|---|---|---|
| 1 | Premiers pas : calculer avec Python | bactéries après 2 h et 3 h (64 000 ; 512 000), numération sur boîtes | print, variables, opérations, types, f-strings, lire une erreur |
| 2 | Répéter et décider | tableau heure par heure, temps pour dépasser 10⁹, boîtes comptables (30 à 300 colonies) | for, range, while, if / elif / else, indentation |
| 3 | Séquences d'ADN | longueur, comptage des bases, %GC (56,41 %), premier codon | chaînes, len, count, tranches, boucle sur une chaîne |
| 4 | Fonctions et dictionnaires : le code génétique | fonctions gc et traduire, dictionnaire de 11 codons fourni (MAIVMGR*KGAR*) | def, return, print ou return, dictionnaires, boucle avec un pas |
| 5 | Courbe de croissance | tracer DO et ln(DO), taux µ par np.polyfit, temps de génération | listes, import, NumPy, matplotlib |
| 6 | Mini-projet guidé FASTA | lire un fichier FASTA, longueur et %GC par séquence, en réutilisant les fonctions de la séance 4 | with open, dictionnaires ; pandas et CSV en variante exigeante |

La variante exigeante de chaque séance occupe les étudiants plus avancés : saisie avec input, croissance limitée par une capacité, complémentaire inverse, les 64 codons, ajustement logistique avec curve_fit, DataFrame pandas. Les données (courbe de DO, petit fichier FASTA de fragments fictifs) figurent dans les consignes. Toutes les valeurs citées dans les critères ont été calculées en Python.

**Banques d'exercices** (`serveur/exemples/superieur/python/python_niveau1.gift` à `python_niveau5.gift`, 8 questions chacune), une par séance (la séance 6 réutilise la banque 5) :
1. calculs, variables, division / et //, f-strings, virgule décimale, `^` n'est pas la puissance ;
2. boucles for et while, range qui commence à 0, conditions, deux-points et indentation ;
3. chaînes et séquences d'ADN, tranches, majuscules et minuscules, texte + nombre ;
4. fonctions, print ou return, dictionnaires, codon absent (KeyError), traduction ;
5. listes, tableaux NumPy, liste × 2 ou tableau × 2, pente, temps de génération, np.log et np.log10, lecture d'un FASTA.

Il y a deux sortes de questions : « Qu'affiche ce programme ? » et « Ce programme s'arrête sur une erreur. Laquelle ? » (NameError, SyntaxError, IndentationError, TypeError, KeyError), pour apprendre à lire les messages d'erreur. Le script `developpement/generateurs/generer_banques_python.py` produit les banques en exécutant chaque programme : la réponse attendue est toujours la sortie réelle, ou l'erreur réellement levée. Pour ajouter des questions, modifiez le script et relancez-le.

**Avant de les utiliser :**
- un modèle de langage puissant est conseillé pour la vérification : un petit modèle local déroule mal le code ;
- pour les deux premières séances, on peut choisir « IA qui donne des éléments » plutôt que « IA qui questionne », car un débutant bloqué sur une erreur de syntaxe a d'abord besoin qu'on la lui montre ;
- les critères de réussite peuvent aller jusqu'à 2 000 caractères.

## 6 quinquies. Système d'exploitation et Linux (M1 microbiologie, 4 h)

Le cours dure 4 h : trois séances d'apprentissage (3 h 30), puis une évaluation de 30 minutes. Il parcourt le cours « Système d'exploitation — M1 Microbiologie » (A. Fronville, 76 diapositives).

**Pour qui.** Des étudiants qui n'ont jamais ouvert de terminal et qui travaillent sur leur propre ordinateur : Terminal sous macOS, Ubuntu avec WSL sous Windows.

**Fonctionnement.** Les critères de réussite précisent à l'IA ce qui diffère d'un système à l'autre et n'est pas une erreur. L'étudiant colle ses commandes avec ce que le terminal affiche (saisie de code, section 6 quater) ; l'application n'exécute rien.

| Séance | Durée | Diapositives | Contenu | Exercices |
|---|---|---|---|---|
| 1. Le système Linux et ses fichiers | 1 h 15 | 2 à 31, 58 à 63 | rôle du système, noyau, shell, GNU/Linux, logiciel libre ; arborescence ; pwd, ls, cd, mkdir, touch, cp, mv, rm, find, man ; Tab, historique, ~ ; *, ? et [ ] ; installation et df en variante exigeante | 4, niveau 1 |
| 2. Utilisateurs, droits et processus | 1 h | 19, 32 à 52 | whoami, id, /etc/passwd ; ls -l ; chmod (u, g, o, a ; +, -, =) ; sleep &, ps, kill | 4, niveau 2 |
| 3. Le shell et le traitement de fichiers texte | 1 h 15 | 53 à 76 | variables, PATH, alias, && et \|\| ; wc, awk, sed sur un tableau de comptages de colonies et un petit fichier FASTA | 4, niveau 3 |
| 4. Évaluation | 30 min | tout le cours | 12 questions corrigées automatiquement, puis un exercice pratique sur le tableau de comptages | 12, niveau 5 |

**L'évaluation.** C'est une séance d'évaluation (la case « Séance d'évaluation » de la carte La tâche) :
- **pas d'aide** : ni IA, ni coup de pouce, ni vérification, quel que soit le réglage de la classe ;
- **les exercices** : une seule réponse par exercice. L'étudiant voit seulement « Réponse enregistrée », sans score ni correction ; vous voyez les scores dans la fiche de chaque élève et dans les exports ;
- **pas de reprise** : la séance ne peut pas être reprise ;
- **déroulé** : les 12 questions viennent d'abord (environ 20 minutes), tirées dans une banque à part. Elles ne figurent dans aucune séance précédente. Puis vient l'exercice pratique, environ 10 minutes : droits, comptage, total et extraction ;
- **corrigé** : les critères de réussite du modèle servent de corrigé à l'enseignante, sur 4 points : -rw-------, 4 échantillons sur LB, 1 644 colonies de E_coli, lignes E1, E3, E5, E8. Ils ont été vérifiés en exécutant les commandes ;
- **durée** : l'application ne minute pas les 30 minutes ; ouvrez puis fermez la séance 4 vous-même.

**Banques d'exercices** (`serveur/exemples/superieur/linux/`, produites par `developpement/generateurs/generer_banques_linux.py`, qui exécute chaque commande avec bash ; les questions de cours reprennent les définitions du cours) :

| Banque | Contenu | Questions | À importer au niveau |
|---|---|---|---|
| `linux_niveau1.gift` | le système, l'arborescence et les fichiers | 16 | 1 |
| `linux_niveau2.gift` | les utilisateurs, les droits et les processus | 8 | 2 |
| `linux_niveau3.gift` | le shell et le traitement de fichiers texte | 16 | 3 |
| `linux_evaluation.gift` | l'évaluation | 12 | 5 |

Une séance créée à partir d'un modèle prend le niveau d'exercices indiqué par le modèle. Le nombre d'exercices par séance peut aller jusqu'à 20.

**Hors ligne.** Le kit hors ligne (section 6 sexies) contient toutes les séances, évaluation comprise. Les réponses des exercices y figurent. Pour l'évaluation, décochez « Ouvrir toutes les séances » avant de télécharger le kit, ou faites-la en salle.

**Conseil.** La classe est réglée sur « réflexion d'abord, puis IA qui questionne » : chacun écrit ses idées avant d'ouvrir l'IA, qui ne donne jamais d'éléments de réponse.

## 6 quinquies bis. Marketing et IA générative (M1, en anglais, 6 h 45)

Cours de marketing pour des étudiants de M1, entièrement en anglais, construit autour d'un cas : une entreprise de vêtements de sport durables lance une ligne de chaussures de course en matériaux recyclés. La séance 2 reprend la consigne d'origine (« Sei un/una junior marketing specialist… »), traduite en anglais.

**Réglages de la classe** (Réglages → Règle de la classe) : public « enseignement supérieur », langue de l'interface « English ». L'interface, le tuteur IA et les retours de la vérification sont alors en anglais. La discipline des modèles est « Marketing and generative AI (M1) ».

| Séance | Durée | Contenu | Exercices |
|---|---|---|---|
| 1. Market and target | 1 h 30 | segments, choix de la cible, persona ; écart entre attitude et comportement | 6, niveau 1 |
| 2. Choosing a launch positioning with a generative AI | 1 h 30 | le cas : propositions de positionnement obtenues avec l'IA, évaluées, puis une recommandation à l'équipe | 6, niveau 2 |
| 3. From positioning to messages, without greenwashing | 1 h 30 | proposition de valeur, messages, allégations environnementales précises et prouvables | 6, niveau 3 |
| 4. Launch plan and pitch | 1 h 30 | marketing mix, prix, KPI, risques, pitch ; seuil de rentabilité en variante exigeante | 6, niveau 4 |
| 5. Final assessment, without AI | 45 min | 10 questions, puis un cas sur un nouveau produit (vestes de randonnée) | 10, niveau 5 |

**Le rôle de l'IA dans la séance 2.** Le tuteur de Viabilis ne donne jamais de liste de réponses toutes faites. Pour que les étudiants obtiennent des propositions de positionnement, réglez cette séance sur « IA d'abord » et « IA qui donne des éléments » : chaque demande donne une proposition partielle. Les étudiants doivent ensuite réécrire chaque proposition retenue dans leurs propres mots et l'évaluer. Les critères de réussite demandent à la vérification de marquer « à revoir » une proposition de l'IA collée sans être réécrite ni évaluée. Pour les autres séances, « réflexion d'abord, puis IA qui questionne » convient ; aux séances 3 et 4, l'IA sert à proposer des messages puis à soulever des objections.

**L'évaluation (séance 5)** se fait sans IA, sans coup de pouce et sans vérification. Elle vérifie que les étudiants savent positionner seuls un nouveau produit une fois l'IA retirée. Les critères de réussite du modèle servent de grille de correction, sur 10 points.

**Les allégations environnementales.** Les séances 3 et 5 s'appuient sur la directive (UE) 2024/825, applicable depuis le 27 septembre 2026. Elle interdit les allégations environnementales génériques (« eco-friendly ») sans performance environnementale excellente reconnue, et la neutralité d'un produit fondée sur la compensation. Elle impose aussi que les labels de durabilité reposent sur un système de certification ou soient établis par les autorités publiques. Vérifiez la transposition dans le pays de vos étudiants.

**Banques d'exercices** (`serveur/exemples/superieur/marketing/`) : `marketing_niveau1.gift` à `marketing_niveau4.gift` (6 questions chacune) et `marketing_evaluation.gift` (10 questions, aucune reprise des séances précédentes). Les calculs (marge sur coût variable, seuil de rentabilité) ont été vérifiés.

**Avant de l'utiliser :** un modèle de langage capable de bien écrire en anglais est conseillé pour le tuteur et la vérification. Les estimations de l'état et les règles de viabilité n'ont pas été éprouvées dans ce public.

## 6 quinquies ter. Créer une séance vide, ou à partir d'un document PDF

L'onglet Réglages commence par la carte « Créer la séance N ». Elle propose deux façons de créer une séance, en plus des modèles de la carte suivante :
- **une séance vide**, que vous écrivez entièrement : consigne, coups de pouce, variantes, vérification ;
- **une séance à partir d'un document PDF** (10 Mo au plus), avec deux options cochées par défaut :
  - **l'IA prépare la séance** : elle lit le texte du PDF et propose une consigne ouverte, trois coups de pouce gradués, une variante accessible, une variante exigeante et des critères de réussite pour la vérification. Un champ facultatif permet de dire ce que vous attendez (durée, niveau, notion à travailler) ;
  - **les élèves peuvent ouvrir le PDF** pendant la séance : un bouton « 📄 Ouvrir le document de la séance » apparaît sous la consigne.

**La nouvelle séance est créée fermée.** Les élèves ne la voient pas : relisez et corrigez ce que l'IA a proposé, puis cliquez sur « Enregistrer et ouvrir la séance N aux élèves ». Les séances précédentes gardent leur consigne et leur document.

**Joindre ou retirer un document** sur une séance existante : dans la carte « La tâche » (Réglages, ou « Modifier » pour une séance précédente). Cela enregistre aussi les réglages de la séance. Un document retiré de toutes les séances est effacé du serveur.

**Ce qu'il faut savoir :**
- **lecture du PDF** : avec `pypdf` s'il est installé (paquet `python3-pypdf`, que l'installateur Ubuntu tente d'installer), sinon avec un lecteur intégré, sans dépendance. Un PDF scanné (des images, sans texte) ne peut pas être lu par l'IA : il peut seulement être montré aux élèves ;
- **données** : pour préparer la séance, le texte du PDF (40 000 caractères au plus) est envoyé au fournisseur d'IA de la plateforme. N'utilisez pas de document contenant des données personnelles ;
- **accès** : un élève n'ouvre que le document d'une séance ouverte ou d'une séance qu'il a déjà travaillée, dans sa propre classe ;
- **hors ligne** : les documents ne sont pas copiés dans le kit de la clé USB ;
- **qualité du brouillon** : elle dépend du modèle de langage. Avec un petit modèle local, relisez particulièrement les critères de réussite.

Test : `developpement/tests/test_documents.py` (21 vérifications).

## 6 quinquies quater. Créer une séance à partir d'un fichier .gift (banques d'exercices modifiables)

Dans l'onglet Réglages, la carte « Créer la séance N à partir d'un fichier .gift » suit celles des modèles et du PDF.

**Choisir une banque** (format GIFT de Moodle), parmi :
- **vos banques** (« Mes banques »), enregistrées dans Viabilis et utilisables dans toutes vos classes ;
- **les banques fournies avec Viabilis** (dossiers `serveur/exemples/<niveau>/<matière>/`) ;
- **un fichier de votre ordinateur** (« Ou ouvrir un fichier .gift de l'ordinateur »).

**Modifier et enregistrer.** Le contenu s'affiche dans un éditeur. « Vérifier le fichier » indique le nombre de questions reconnues, leurs titres et les avertissements. Ensuite :
- **« Enregistrer dans Viabilis »** : avec un **nouveau nom**, une nouvelle banque est créée et l'ancienne est gardée ; avec le **même nom**, votre banque est remplacée. Les banques fournies ne sont jamais modifiées : en partant de l'une d'elles, le nom proposé se termine par « (copie) » ;
- **« Télécharger le fichier .gift »** : le fichier modifié est enregistré sur votre ordinateur, sous le nom choisi ;
- **« Supprimer cette banque »** : pour une de vos banques.

**Créer la séance.** « Créer la séance N avec ces exercices » :
- importe les questions dans la banque de la classe, au niveau choisi (onglet Exercices) ;
- crée la séance **fermée**, avec ces questions comme exercices (placées avant la tâche ouverte, autant d'exercices que de questions, 20 au plus) ;
- propose une tâche ouverte de départ, à relire : « Après les exercices, écris tes idées : ce que tu as compris, une erreur que tu as faite ou évitée et pourquoi, et une question que tu te poses encore. »

La séance **ne tire que les questions de ce fichier**, et pas le reste de la banque de la classe. L'onglet Exercices l'indique par une case « Seulement les questions de… », qu'il suffit de décocher pour tirer de nouveau dans toute la banque. Chaque création importe une nouvelle copie des questions, datée : modifier ensuite la banque ne change pas une séance déjà créée.

Chaque enseignant ne voit que ses propres banques (sans comptes : une seule bibliothèque). Test : `developpement/tests/test_banques.py` (23 vérifications).

## 6 sexies. Travail hors ligne (clé USB)

Ce mode sert à un étudiant qui ne peut pas joindre le serveur de la classe : il travaille sur son propre ordinateur, puis rapporte son travail.

1. **Le kit.** Dans l'onglet Données, la carte « Travail hors ligne » télécharge le kit de la classe (`viabilis_kit_CODE.json`) : les séances et la banque d'exercices.
   - Il ne contient ni les critères de réussite (ils donnent les réponses attendues), ni les réglages, groupes ou idées des autres élèves.
   - Par défaut, toutes les séances y sont ouvertes, pour que l'étudiant avance à son rythme.
   - Copiez le dossier `application` sur une clé USB, et le kit, renommé `kit.json`, dans `application/hors_ligne/`.
2. **Sur l'ordinateur de l'étudiant.** Un double clic sur `lancer.bat` (Windows), `lancer.command` (macOS) ou `sh lancer.sh` (Linux) lance `serveur.py --hors-ligne kit.json` et ouvre la page élève.
   - Le code de la classe est déjà rempli ; l'étudiant choisit son pseudonyme.
   - Le serveur n'écoute que l'ordinateur lui-même (127.0.0.1) et n'a ni page enseignant ni IA : l'étudiant travaille en autonomie, comme le groupe « défi ».
   - Les coups de pouce et les exercices fonctionnent ; les exercices sont corrigés sur place.
   - Le travail est enregistré dans `hors_ligne/travail/viabilis.sqlite3`.
   - Il faut Python 3.9 ou plus récent ; sous Windows, un Python portable peut être placé dans `hors_ligne/python/` (voir `hors_ligne/LISEZMOI.txt`).
3. **Le retour.** L'étudiant touche « Exporter mon travail » et remet le fichier à l'enseignante, qui l'importe dans la même carte. Ses séances, réponses aux exercices, vérifications et coups de pouce rejoignent le suivi, comme s'il avait travaillé en ligne.
   - **Réimport** : réimporter un fichier plus récent du même étudiant met ses séances à jour, sans doublon. Un fichier plus ancien ne remplace jamais une séance plus récente dans la classe.
   - **Pseudonyme déjà pris** : si un élève de la classe porte déjà ce pseudonyme, l'étudiant hors ligne reçoit un pseudonyme numéroté (« Lou 2 »). Une case permet au contraire de rattacher le travail à cet élève (même étudiant, en ligne en classe et hors ligne chez lui).
   - **Contrôles** : un fichier modifié à la main, ou venant d'une autre classe, est refusé.

**Limites.**
- Pas d'IA hors ligne : ni tuteur, ni vérification par l'IA.
- Les réponses des exercices sont dans le kit, lisibles avec un éditeur de texte.
- L'enseignante ne voit le travail qu'après l'import.
- Ni Windows ni le Python portable n'ont été essayés : les lanceurs ont été vérifiés sous macOS et le serveur hors ligne par `developpement/tests/test_hors_ligne.py` (26 vérifications).

## 6 septies. Langues de l'interface : français, anglais, catalan, italien, espagnol, allemand

- **Pour les élèves, la langue se règle par classe.** Onglet Réglages, carte « Règle de la classe », menu « Langue de la classe ».
  - La page élève passe dans cette langue dès que l'élève a saisi le code de la classe, et à sa prochaine visite pour les élèves déjà inscrits.
  - L'IA répond aux élèves dans cette langue : tuteur, vérification des idées et correction finale.
  - Les retours de la vérification par calculs, les messages d'erreur et les corrections d'exercices (« Vrai », « pas de réponse »…) suivent aussi cette langue.
- **Pour l'enseignante, la langue de sa propre page se choisit** dans le menu en haut à droite de la page enseignant. Une nouvelle classe prend cette langue ; on la change ensuite dans les Réglages.
- **Ce qui n'est pas traduit** : les consignes, les coups de pouce, les modèles de séances et les banques d'exercices. Ils restent tels que vous les avez écrits. Pour une classe en catalan, en italien, en espagnol ou en allemand, écrivez donc la consigne dans cette langue. Pensez aussi à choisir la même langue dans « Langue de lecture » (lecture à voix haute).
- **Où sont les traductions.**
  - Interface : `serveur/web/commun/traductions.js`. Chaque ligne associe un texte français à ses traductions, dans cet ordre : anglais, catalan, italien, espagnol, allemand. Pour corriger une traduction, modifiez seulement la partie droite.
  - Messages du serveur : `serveur/langues.py` (anglais et catalan) et `serveur/langues_autres.py` (italien, espagnol, allemand, y compris les mails aux enseignants ; le mail de demande de compte envoyé à l'administratrice reste en français).
  - Côté élèves, le tutoiement (tu, tú, du) ; côté enseignants, la forme de politesse (Lei, usted, Sie).
  - Les traductions italienne, espagnole et allemande ont été faites par Claude, sans relecture humaine : faites-les relire par un collègue de la langue avant un usage en classe.
  - Un texte sans traduction reste en français.
- **Vérifié** par `developpement/tests/test_langues.py` (20 vérifications) et dans le navigateur. Les pages élève et enseignant ont été parcourues en catalan, en anglais, puis à nouveau en français.

## 6 octies. Comptes enseignants : chacun ne voit que ses classes

- **Activation** : variable `VIABILIS_ADMIN`, l'adresse de l'administratrice. Le script `installer_ubuntu.sh` la règle. Sans elle (ni `VIABILIS_DOMAINES`), l'ancien mode reste : un seul mot de passe (`VIABILIS_MDP_ENSEIGNANT`), toutes les classes.
- **Validation** : toute personne peut demander un compte (nom, adresse, présentation).
  - Une fois l'adresse confirmée, la demande part par mail chez l'administratrice. Elle valide ou refuse dans la carte « Comptes enseignants » de sa page, et la personne est prévenue par mail.
  - « Suspendre » coupe l'accès d'un compte ouvert, sans effacer ses classes.
- **Inscription** : toute adresse, ou seulement celles des domaines de `VIABILIS_DOMAINES` s'il est réglé, au domaine exact (`univ-brest.fr` refuse `etudiant.univ-brest.fr` ; `*.exemple.fr` accepte les sous-domaines), et mot de passe de 10 caractères au moins.
  - Le compte ne sert qu'après l'ouverture du lien de confirmation reçu par mail (valable 48 h). Une inscription non confirmée est effacée au bout de 7 jours.
  - Les réponses ne disent jamais si une adresse a déjà un compte. Le titulaire de l'adresse reçoit un mail qui le lui apprend.
- **Cloisonnement** : chaque classe appartient au compte qui l'a créée. Les routes `/api/classes/...` renvoient « Classe inconnue » pour la classe d'un collègue.
  - Les classes créées avant les comptes reviennent au compte de l'administratrice (ou de `VIABILIS_PROPRIETAIRE`) dès que son adresse est confirmée.
- **Mot de passe oublié** : un lien à usage unique, valable une heure. Le nouveau mot de passe ferme les autres sessions.
- **Sécurité** :
  - mots de passe hachés (PBKDF2-SHA256, 300 000 itérations) ;
  - la base ne garde que l'empreinte des liens envoyés ;
  - connexion bloquée après 8 échecs en 15 minutes pour une adresse, 50 pour une même adresse réseau (seuls les échecs comptent) ;
  - au plus 3 mails par heure pour une adresse.
- **Envoi des mails** : `VIABILIS_SMTP_HOTE`, `VIABILIS_SMTP_PORT` (587 avec STARTTLS ; 465 en SSL), `VIABILIS_SMTP_UTILISATEUR`, `VIABILIS_SMTP_MDP`, `VIABILIS_SMTP_EXPEDITEUR`.
  - Les liens partent de `VIABILIS_ADRESSE` (par exemple `https://viabilis.mondomaine.fr`).
  - Sans serveur de mail, le contenu du mail est écrit dans le journal, lignes `[MAIL]`.
- **Vérifié** par `developpement/tests/test_comptes.py` (43 vérifications), dans le navigateur, et par un envoi réel à un serveur SMTP local d'essai.

## 6 nonies. Visuels de la page élève, selon le niveau et la discipline

- **Ce qui est illustré** : la carte « La tâche » s'ouvre sur une bannière dessinée d'après la discipline de la séance. Si la séance ne vient pas d'un modèle, c'est la discipline de la classe qui est prise.
  - Thèmes : mathématiques, algèbre (Galois), terminal (Linux), programmation (Python), créole, langues, français, histoire, géographie, sciences, et un thème général pour les autres disciplines.
  - Chaque thème a ses couleurs, en mode clair comme en mode sombre.
- **Selon le niveau** (« Public de la classe ») :
  - **école** : couleurs vives, boutons arrondis, texte un peu plus grand. Une plante grandit avec chaque idée écrite et fleurit quand le nombre d'idées attendu est atteint ;
  - **collège** : la même bannière illustrée, sans la plante ;
  - **lycée, supérieur** : bannière au trait, discrète.
  - En fin de séance, un bouquet d'étoiles (école, collège) ou une simple marque de réussite (lycée, supérieur) apparaît.
- **Réglage** : dans Réglages, « Règle de la classe », la case « Illustrations adaptées au niveau et à la discipline » est cochée par défaut. Décochez-la pour une page sobre.
- **Technique** : les dessins sont dans `serveur/web/commun/visuels.js` (SVG écrits à la main, aucune image extérieure), leurs couleurs dans `style.css` (classes `.theme-…`). Ils sont décoratifs : un lecteur d'écran les ignore. L'animation de la plante s'arrête si l'appareil demande moins d'animations.
- **Vérifié** dans le navigateur : écran large et téléphone, mode clair et sombre, classes CM1 (mathématiques), créole, Linux (supérieur) ; la case du professeur désactive bien les visuels.

## 7. Viabilité (expérimental)

Chaque carte élève de l'onglet Classe affiche, à partir de l'état estimé (C, A, M, D) :
- son **statut** :
  - auto-soutenu (peut continuer sans aide) ;
  - dans le bassin de capture (autonomie possible en n séances) ;
  - hors du bassin (autonomie inaccessible dans cette situation) ;
  - hors du noyau (rupture probable même avec de l'aide) ;
  - hors du domaine pour l'instant, avec ou sans retour prévu sans aide : quand une contrainte est violée maintenant (une charge très faible, par exemple), l'application ne parle plus de rupture inévitable si le modèle prévoit un retour à la séance suivante ;
- sa **fenêtre d'intervention** : le nombre de séances sans aide avant de sortir du bassin de capture ;
- l'**aide minimale** proposée par la loi de capture : éléments de réponse, questions et ordre dans la séance ;
- les **multiplicateurs de viabilité de l'article** (section 5.6), calculés exactement comme dans `article/julia/src/multiplicateurs.jl`, sur le modèle réduit (charge, agentivité, maîtrise ; module `multiplicateurs.py`) :
  - *prix des seuils à la prochaine séance* : plus petite intervention (éléments de réponse s, questions φ) qui garde l'élève dans le domaine, pour un coût s² + 0,3 φ² ; ses multiplicateurs de Karush-Kuhn-Tucker sont les prix des seuils de surcharge, d'ennui et de dépendance ;
  - *exigence qui motive l'aide sur 10 séances* : plus petite aide constante qui garde l'élève dans le domaine pendant 10 séances, et la contrainte dont la marge est la plus faible ;
  - *sauvegarde ou progression* : une aide proposée par la loi de capture est « de sauvegarde » si, sans aide, l'élève sortirait du domaine dans les 10 séances, « de progression » sinon.
  - Vérification : identiques au code Julia de l'article sur 300 états tirés au hasard, et à 2·10⁻¹³ près sur 100 états qui demandent une intervention ; la propriété de prix (multiplicateur = dérivée du coût par rapport au seuil) est testée dans `developpement/tests/test_tension.py`.
- la **marge dans le noyau** (modèle complet), visible sans ouvrir le détail. C'est une approximation géométrique, différente des multiplicateurs de l'article : ce que `article/sim/multiplicateurs.py` appelle multiplicateurs « idéaux ». On calcule où l'élève irait en une séance sans aide, puis le point le plus proche de la zone viable des tables. Elle tient compte de la pensée divergente et de la maîtrise attendue, ce qui en fait un compte à rebours avant le décrochage.
  - Si l'évolution sort de la zone, la tension est positive : c'est la plus petite correction (C, A, M, D) qui l'y ramène, traduite en levier (alléger la tâche, relever le défi, laisser chercher seul, consolider, ouvrir la recherche).
  - Sinon, elle est négative : c'est la marge avant la frontière la plus proche, avec la menace correspondante (surcharge, ennui, dépendance, rigidité).
  - Le calcul est dans `noyau.py` (`marge`). Le test `developpement/tests/test_tension.py` le vérifie.
- les **prédictions démenties**. À chaque séance, le serveur compare ce que le modèle prévoyait et l'état observé ensuite. La prévision part de l'état après la séance précédente et de l'aide reçue : IA utilisée et son rôle, coups de pouce, ordre.
  - Un écart de plus de 0,15 sur la charge, l'agentivité ou la pensée divergente s'affiche sur la carte, avec le nombre de séances de suite.
  - La maîtrise est comparée mais n'entre pas dans le verdict. Dans le modèle, c'est un niveau cumulé qui monte lentement ; dans l'application, c'est la réussite à la tâche du jour, qui baisse normalement quand la tâche se durcit.
  - Un écart qui dure signale un ennui durable, une difficulté non déclarée, ou un modèle à recalibrer.

**Domaine viable de l'application.** Le domaine du modèle contient une contrainte de maîtrise : M doit suivre les « attendus du curriculum », qui montent jusqu'à 0,6.
- Dans l'article, ils montent sur 60 séances (`TM` = 60), si bien qu'ils ne comptent pas au début.
- Pour l'application, ils montent sur une séquence de **10 séances** (`VIABILIS_TM`), et l'application affiche la « maîtrise attendue à ce stade de la séquence ».
- Un élève n'est « dans le bassin » que s'il peut devenir autonome en au plus **20 séances** (`horizonAutonomie` dans `meta.json`, réglable sans recalcul par `VIABILIS_HORIZON`).
- Pour changer `TM`, relancer l'export avec la variable d'environnement, par exemple `VIABILIS_TM=12 julia --threads=auto --project=. export_tables_app.jl`, puis `compresser_tables.py`. Les résultats de l'article ne changent pas : `TM` vaut 60 par défaut.

Le serveur lit ces informations dans des tables précalculées (`serveur/tables/`, 3,5 Mo) : 5 niveaux de difficulté × 61 séances × 741 321 états, un octet par état. Elles sont produites par le modèle « séance » de l'article :

```bash
cd article/julia && julia --threads=auto --project=. export_tables_app.jl
```

```bash
cd application && python3 developpement/outils/compresser_tables.py
```

Le calcul prend environ 3 minutes. `noyau.py` reproduit la dynamique et la loi de capture ; comparé au modèle Julia, il donne la même dynamique sur 300 états sur 300 et la même aide sur 299 sur 300. Le seul écart concerne un cas de sauvegarde hors du bassin, où Julia se replie sur une marge de sécurité que les tables n'incluent pas.

Le niveau utilisé est le niveau d'exercices de l'élève quand les exercices sont activés, sinon la « difficulté de la tâche ouverte pour le modèle » (onglet Réglages).

**Limites, rappelées dans l'application.** Le modèle n'est pas calibré et l'état est estimé grossièrement à partir de déclarations et de traces : ces indications sont des alertes à vérifier, pas des diagnostics. Seul le statut sert, dans les propositions de groupes de besoin ; la tension est affichée sans déclencher d'action. Une fois les paramètres estimés sur les données recueillies, il suffit de relancer l'export pour mettre les tables à jour.

**Ce que la simulation a montré** (`simulation_cm1/`) :
- La tension donne la bonne direction : ennui pour les élèves rapides, surcharge pour les élèves en difficulté.
- Avec les attendus sur 60 séances, elle n'a anticipé aucune difficulté réelle. Avec une séquence de 10 séances, elle donne un compte à rebours : un élève dont la maîtrise stagne à 0,42 voit sa marge passer de 0,22 à 0,04 entre les séances 4 et 7, et sort du noyau à la séance 8.
- Les prédictions démenties ont repéré l'ennui durable de Lina et de Tom dès la séance 3. Un enseignant simulé qui leur donne alors la variante exigeante fait un peu reculer leur ennui.

## 8. Avant un usage en classe : conformité

Les traces d'élèves mineurs sont des données personnelles. Avant tout déploiement :

1. **Délégué à la protection des données** de l'université et de l'académie : inscription au registre des traitements, analyse d'impact (AIPD) probable (élèves mineurs, usage innovant).
2. **Hébergement** sur un serveur de l'université ou de l'académie, dans l'Union européenne.
3. **IA** : un fournisseur couvert par un contrat de sous-traitance conforme au RGPD, ou un modèle hébergé par l'établissement (API compatible OpenAI). Ne jamais saisir de nom d'élève dans la consigne de la tâche.
4. **Information** des élèves et des responsables légaux : finalité (recherche sur la régulation de l'aide), données recueillies, durée de conservation, droits d'accès et d'effacement.
5. **Recherche** : avis d'un comité d'éthique pour la publication des résultats ; export pseudonymisé uniquement.

## 9. Comment l'état est estimé

Les indicateurs sont des estimations grossières, calculées dans le navigateur de l'enseignant à partir des traces (`commun/etat.js`). Ils aident à regarder un élève ; ils ne le mesurent pas.

| Variable | Estimation |
| --- | --- |
| Charge C | Difficulté déclarée en début et en fin de séance (1 à 5 → 0,1 à 0,9), plus 0,1 si l'élève s'est déclaré bloqué ; avec des exercices, 30 % tiennent aux échecs au premier essai |
| Agentivité A | Pour moitié la part d'idées non reprises des réponses de l'IA, pour moitié la part des idées produites avant toute aide, IA ou coup de pouce (rapportée à au moins 3 idées) |
| Pensée divergente D | Idées distinctes (5 et plus = 1, poids 0,4), originalité dans la classe (0,3), absence de reprise (0,3) |
| Maîtrise M | Compréhension déclarée, appréciation de l'enseignant, taux de réussite aux exercices et réussite à la dernière vérification : part des solutions trouvées quand leur nombre est connu (au plus 8 attendues en une séance : en trouver 8 vaut la note maximale), sinon la meilleure de « part d'idées justes » et « 5 idées justes = 1 » (les essais ratés ne sont pas pénalisés) |

- Les séances successives sont lissées (60 % pour la dernière).
- Les ruptures reprennent les seuils du modèle de viabilité : surcharge au-dessus de 0,85, ennui sous 0,2, dépendance sous 0,3, rigidité sous 0,25.
- La recommandation applique la règle de la séquence : aide d'abord si la charge dépasse le seuil ; retrait de l'IA si l'agentivité dépasse le seuil de retrait **et** que la maîtrise est solide (0,6 au moins), sinon « autonome, mais maîtrise encore fragile » et une IA qui questionne ; sinon réflexion d'abord et une IA qui questionne.
- Variantes : on redescend d'un cran si la charge dépasse le seuil avec une maîtrise insuffisante, **ou** si la maîtrise est insuffisante deux séances de suite. On ne monte qu'après **deux séances** faciles (charge sous 0,35) et réussies (maîtrise d'au moins 0,7) : une seule séance facile ne suffit pas.
- **Palier** : quand la recommandation fait monter un élève, elle note le niveau qu'il a réussi (niveau de la tâche, −1 en variante accessible, +1 en exigeante). Au début d'une séance, le serveur ne lui donne la variante exigeante que si la tâche n'est pas déjà plus difficile que ce palier ; sinon il reçoit la tâche standard, qui suffit à le faire progresser. Une variante exigeante choisie par l'enseignant (sans palier) s'applique toujours.
- **Lecteurs fragiles** : un élève qui a activé la lecture facilitée ou les images n'est jamais monté automatiquement ; la recommandation le signale et laisse l'enseignant décider.
- Groupes : un élève hors du noyau de viabilité par ennui (charge très faible, sans surcharge ni dépendance) est proposé en défi si sa maîtrise est solide, en travail accompagné sinon ; l'atelier dirigé reste pour la surcharge et la dépendance.
- Ces règles ont été mises à l'épreuve par une classe simulée (`simulation_cm1/`, rapport `rapport_simulation.html`). Avec ces règles, aucun élève simulé ne finit en dessous de la classe témoin. Limite connue : dans une progression qui monte d'un niveau à chaque séance, les élèves les plus à l'aise ne reçoivent jamais la variante exigeante ; c'est à l'enseignant de leur proposer une tâche plus riche (« Approfondir ») ou de fixer lui-même la variante.

Les exports CSV permettent d'estimer les paramètres du modèle (érosion par l'ancrage β_D, coût de l'attente κ_r) et de tester les prédictions P1 à P5 de l'étude empirique.

## 9 bis. Calibrer le noyau de viabilité sur vos données

Les tables du noyau sont calculées avec les paramètres **nominaux** du modèle, ceux de l'article. On peut les estimer sur les traces réelles de vos classes, puis recalculer les tables.

**1. Exporter les données.** Dans chaque classe réelle (pas les simulations), onglet Données, cliquez sur « Données pour calibrer le modèle (CSV) ». Le fichier contient, pour chaque élève et chaque séance :
- l'état estimé de la séance (C, A, M, D, sans lissage) ;
- l'aide reçue, traduite dans les commandes du modèle (s : éléments de réponse, φ : questions, r : réflexion d'abord) ;
- le niveau de la tâche.

Il contient des identifiants d'élèves, pas de pseudonymes.

**2. Estimer les paramètres.**

```bash
cd serveur
python3 developpement/outils/calibrer.py calibration_AJGLFY.csv calibration_9D8RJL.csv …
```

Le script n'utilise que la bibliothèque standard ; comptez quelques minutes pour une centaine d'élèves. Il procède ainsi :
- **simulation :** il simule chaque élève de séance en séance avec le modèle, à partir de son premier état observé ;
- **estimation :** il estime les paramètres équation par équation (agentivité, charge, maîtrise, pensée divergente). Un a priori centré sur les valeurs nominales évite qu'ils s'en écartent sans raison ;
- **intervalles :** il donne pour chaque paramètre un intervalle à 90 % (bootstrap par élève) et l'erreur de prédiction sur des élèves non utilisés pour l'estimation.

**Quand un paramètre change.** Le script fabrique des classes simulées avec les paramètres nominaux, qui reprennent les mêmes élèves, aides, niveaux, bruit et valeurs manquantes. Il leur applique l'estimateur, ce qui mesure le biais et la variabilité propres de celui-ci. Un paramètre ne change que si l'estimation réelle sort de ce que donneraient ces classes simulées **et** s'écarte d'au moins 25 % de la valeur nominale. La valeur retenue est alors corrigée de ce biais ; les autres paramètres restent nominaux.

**Quantité de données.** Une équation n'est calibrée qu'avec au moins 30 transitions (deux séances consécutives d'un même élève), venant d'au moins 8 élèves. En deçà, le script le dit et ne change rien.

Le résultat est un rapport à l'écran et un fichier `parametres_estimes.json`.

**3. Recalculer le noyau** (il faut Julia et le projet `article/julia`, environ 2 minutes) :

```bash
python3 developpement/outils/recalculer_noyau.py parametres_estimes.json
```

Le script :
- calcule les tables avec les paramètres qui changent, en gardant la même durée de séquence et le même horizon d'autonomie ;
- garde les anciennes tables dans `tables_avant_AAAA-MM-JJ` ;
- met les nouvelles en place, avec une copie du fichier de paramètres.

Relancez ensuite le serveur : statuts, fenêtres, aide minimale, marges et multiplicateurs utilisent alors les paramètres calibrés. Pour revenir en arrière, remettez le dossier `tables_avant_…` à la place de `tables`.

**Ce qui a été vérifié.**
- **Calcul Julia :** relancé avec les paramètres nominaux, il reproduit à l'identique les 305 tables actuelles.
- **Estimation (`developpement/tests/test_calibration.py`) :** sur des données synthétiques (60 élèves, 8 séances, bruit d'observation de 0,04), elle retrouve trois paramètres volontairement modifiés (ρ 0,38 pour 0,40, λ 0,20 pour 0,20, k_s 0,63 pour 0,65) et ne touche pas aux dix-sept autres. Sur des données conformes au modèle nominal, elle donne au plus un faux signal sur vingt paramètres : σ_D, qui se distingue mal de ρ_D. Avec trop peu d'élèves, elle refuse de conclure.
- **Pourquoi la simulation :** une première version repartait, à chaque séance, de l'état observé, bruité. Elle signalait à tort 5 paramètres sur 20 ; c'est pourquoi l'estimation simule les élèves.

**Limites.**
- La calibration ne vaut que ce que valent les états estimés, qui restent grossiers (section 9).
- Elle suppose que la forme des équations du modèle est juste : elle règle les paramètres, elle ne teste pas le modèle.
- Les erreurs de prédiction hors échantillon indiquent dans quelle mesure il prédit vos élèves.
- À la date du 15 octobre 2026, les classes réelles ne comptent que 13 transitions : il faut attendre que les classes avancent.

## 10. Points non vérifiés

- L'installation hors ligne (service worker) n'a pas pu être testée dans le navigateur de développement ; le reste des deux applications a été testé sur gabarits téléphone et tablette.
- Les traductions anglaise et catalane ont été rédigées sans relecture par une personne dont c'est la langue : faites relire le catalan avant un usage en classe (fichier `serveur/web/commun/traductions.js`). La qualité des réponses de l'IA en catalan dépend du modèle choisi.
- L'appel à une vraie IA n'a été testé qu'avec l'IA factice ; vérifier le format de réponse du fournisseur choisi avant la première séance.
- La dictée vocale repose sur la reconnaissance « sur l'appareil » des navigateurs récents (SpeechRecognition.available avec processLocally). Elle n'a pas pu être testée ici. Sur les appareils qui ne la proposent pas, le bouton reste caché.
- Le conseil de méthode automatique ne couvre que les tâches de sommes (nombres autorisés, résultat entier). Pour les autres tâches vérifiées par calculs (Le compte est 24…), seul le conseil « range tes solutions » peut apparaître.
- Le blocage automatique des réponses de l'IA ne détecte que les calculs écrits en chiffres. Une solution écrite en toutes lettres passerait : relire les échanges reste nécessaire.
