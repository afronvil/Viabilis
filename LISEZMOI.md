# Viabilis

Viabilis est une application web pour la classe, sur smartphone, tablette ou ordinateur. Elle aide l'enseignant à garder chaque élève dans une zone où il apprend : ni débordé, ni ennuyé, et toujours acteur de sa réflexion, y compris quand une IA générative l'accompagne.

- **Viabilis élève.** L'élève rejoint la classe avec un code et un pseudonyme. Il déclare la difficulté qu'il ressent, écrit ses idées, puis échange avec une IA. L'enseignant fixe l'ordre (réflexion d'abord ou IA d'abord) et le rôle de l'IA (questionner ou donner des éléments). Il fait aussi des exercices tirés de banques adaptées à son niveau. Après une erreur, il peut demander à l'IA de lui expliquer ce qui ne va pas et la règle en jeu ; tant qu'il lui reste un essai, l'IA ne donne pas la bonne réponse.
- **Viabilis enseignant.** L'enseignant prépare ses séances et suit l'état estimé de chaque élève : charge, agentivité, pensée divergente et maîtrise. Il voit les ruptures qui menacent et reçoit une recommandation, qu'il applique à un élève ou à toute la classe. Il peut exporter les données pour la recherche, ou tout effacer.

Langues de l'interface : français, anglais, catalan, italien, espagnol et allemand.

## Installer Viabilis dans un établissement

Viabilis ne demande que Python 3.9 ou plus, sans aucune dépendance à installer. Les données sont rangées dans une base SQLite, sur le serveur de l'établissement.

| Situation | Guide |
| --- | --- |
| Serveur de l'établissement (service systemd, proxy HTTPS, sauvegardes, mises à jour) | [`INSTALLATION.md`](INSTALLATION.md) |
| Ordinateur Ubuntu avec Apache, derrière une box | [`INSTALLATION_MAISON.md`](INSTALLATION_MAISON.md), avec le script `installer_ubuntu.sh` (remplissez d'abord `installer_ubuntu.conf`) |
| Travail sans réseau, sur clé USB | dossier `hors_ligne/` (voir `hors_ligne/LISEZMOI.txt`) |

Essai rapide sur votre ordinateur, avec une IA factice :

```bash
cd serveur
VIABILIS_MDP_ENSEIGNANT='un-mot-de-passe-long' VIABILIS_IA=fausse python3 serveur.py --port 8080
```

Ouvrez ensuite `http://127.0.0.1:8080/enseignant/` pour la vue enseignant, et `http://127.0.0.1:8080/eleve/` pour la vue élève.

### Principaux réglages

| Variable | Rôle |
| --- | --- |
| `VIABILIS_MDP_ENSEIGNANT` | Mot de passe enseignant unique, quand il n'y a pas de comptes |
| `VIABILIS_ADMIN` | Active les comptes enseignants. Chaque enseignant ne voit que ses classes ; cette adresse valide chaque demande de compte |
| `VIABILIS_DOMAINES` | Limite les demandes de compte à certains domaines de messagerie (facultatif) |
| `VIABILIS_IA`, `VIABILIS_IA_URL`, `VIABILIS_IA_MODELE`, `VIABILIS_IA_CLE` | Fournisseur d'IA : `anthropic`, `openai`, `gemini`, `mistral`, `ollama` (modèle local), ou toute API compatible OpenAI, comme Albert |
| `VIABILIS_CONSERVATION_JOURS` | Durée de conservation des traces, 365 jours par défaut |

La clé d'API reste sur le serveur : elle n'est jamais envoyée aux navigateurs. La liste complète des réglages est dans `INSTALLATION.md`.

## Préparer une séance

Dans la vue enseignant, une séance se crée de quatre façons :
- à partir d'un **modèle de séance** (la liste propose ceux du niveau et de la discipline de la classe) ;
- à partir d'un **modèle vide**, entièrement rédigé par l'enseignant ;
- à partir d'un **document PDF** : l'IA propose un brouillon, et les élèves peuvent ouvrir le document ;
- à partir d'un **fichier .gift** (format Moodle) : on modifie les exercices dans un éditeur, puis on les enregistre sous un nouveau nom, dans la bibliothèque de Viabilis ou sur son ordinateur.

## Exemples fournis

Les banques d'exercices sont rangées par niveau, puis par matière, dans `serveur/exemples/<niveau>/<matière>/`. Les modèles de séance (`serveur/web/commun/modeles.json`) suivent le même découpage.

| Niveau | Matières |
| --- | --- |
| École (`ecole/`) | Mathématiques, français, sciences, histoire, géographie, anglais, créole guyanais |
| Collège (`college/`) | Mathématiques (fractions, calcul littéral, proportionnalité), français, SVT, physique-chimie, histoire-géographie, anglais, créole martiniquais |
| Lycée (`lycee/`) | Mathématiques, physique-chimie, SES, philosophie, français |
| Supérieur (`superieur/`) | Théorie de Galois, statistiques, biologie, Python, Linux, marketing et IA générative (en anglais) |

Vous pouvez ajouter vos propres banques : déposez un fichier `.gift` ou Moodle XML dans le bon dossier, ou importez-le depuis la vue enseignant.

## Protection des données

- Les élèves utilisent un pseudonyme : aucune donnée d'identité n'est demandée.
- Les traces restent sur le serveur de l'établissement. Elles sont effacées automatiquement après la durée de conservation choisie, et l'enseignant peut tout effacer à tout moment.
- Avant un usage en classe, faites inscrire le traitement au registre de l'établissement et faites-le valider par votre délégué ou déléguée à la protection des données (DPO). Faites-le aussi pour le fournisseur d'IA choisi.

## Pour aller plus loin

Le code source, les tests et les outils de recherche (dont la calibration du noyau de viabilité) se trouvent dans le dépôt GitHub : https://github.com/afronvil/Viabilis, dossier `developpement/`.
