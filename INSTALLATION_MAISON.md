# Installer Viabilis sur un ordinateur Ubuntu à la maison

Pour un ordinateur sous Ubuntu qui fait déjà tourner Apache, branché derrière une box (Bbox), et que les étudiants doivent atteindre depuis Internet. Comptez une heure la première fois.

## Avant de commencer : les données des étudiants

Héberger chez soi les traces d'étudiants, qui serviront aussi à la recherche, n'est pas anodin.
- **La DPO doit valider ce lieu d'hébergement**, en plus de l'inscription au registre.
- **L'ordinateur doit rester allumé, à jour et protégé**, avec des sauvegardes (section 7).

Pour un usage durable, un serveur de l'université reste préférable (`INSTALLATION.md`). La procédure ci-dessous convient bien pour démarrer ou pour des essais.

## 1. Donner une adresse fixe à l'ordinateur Ubuntu, dans la Bbox

La box doit toujours envoyer les visiteurs vers le même ordinateur.
1. Sur l'ordinateur Ubuntu, relevez son adresse locale avec la commande `hostname -I`, par exemple `192.168.1.20`.
2. Dans l'interface de la Bbox (http://mabbox.bytel.fr ou http://192.168.1.254), réservez cette adresse à l'ordinateur. Le menu s'appelle en général « DHCP » ou « Baux statiques ».

## 2. Un nom de domaine

Le certificat HTTPS demande un nom, par exemple `viabilis.mondomaine.fr` : il ne s'obtient pas pour une simple adresse IP.
- **Un nom de domaine à vous** (quelques euros par an chez OVH, Gandi…). Créez un enregistrement **A** qui pointe vers l'adresse IP publique de votre box. Sur l'ordinateur Ubuntu, `curl -4 ifconfig.me` affiche cette adresse.
- **Si l'adresse publique de votre box change** (vérifiez dans l'interface de la Bbox), utilisez un service de DNS dynamique (DuckDNS, No-IP…). La Bbox propose un réglage DynDNS dans son interface, qui suit ce changement.

## 3. Ouvrir les ports dans la Bbox

Dans l'interface de la Bbox, menu « Redirection de ports » (NAT/PAT), créez deux règles vers l'adresse fixée en 1 :

| Port externe | Port interne | Protocole | Vers |
|---|---|---|---|
| 80 | 80 | TCP | l'ordinateur Ubuntu |
| 443 | 443 | TCP | l'ordinateur Ubuntu |

Le port 80 sert à obtenir et renouveler le certificat, puis à rediriger vers https. N'ouvrez **aucun autre port**, surtout pas 8080 : Viabilis n'écoute que l'ordinateur lui-même.

## 4. Copier Viabilis, avec vos classes

Sur le Mac :
1. Arrêtez le serveur Viabilis (Ctrl+C dans sa fenêtre), pour que la base soit complète.
2. Copiez **tout le dossier** `~/Documents/Claude/Viabilis/application` sur une clé USB. Ne prenez pas l'archive `.zip`, qui ne contient pas la base de vos classes.

## 5. Lancer l'installation sur l'ordinateur Ubuntu

Branchez la clé, ouvrez un terminal, puis :

```bash
cd /media/$USER/NOM_DE_LA_CLE/application
sudo bash installer_ubuntu.sh
```

Le script vous demande :
- le nom de domaine ;
- une adresse électronique pour le certificat ;
- **votre adresse d'administratrice** : vous recevrez les demandes de compte, et votre compte reprendra les classes déjà créées ;
- éventuellement des **domaines** auxquels limiter les demandes. Laissez vide pour que les étudiants et toute autre personne puissent demander à essayer ;
- le **serveur de mail de l'université** (nom, port, identifiant, mot de passe, adresse d'expédition). Demandez ces réglages à la DSI : voir la section 5 bis ;
- la clé Albert et le nom du modèle.

Chaque question propose une valeur entre crochets : Entrée la garde.
- **Valeurs proposées** : elles viennent du fichier `installer_ubuntu.conf`, à côté du script (domaine, adresses, serveur de mail, modèle). Modifiez-le avec un éditeur de texte. N'y mettez jamais de mot de passe ni de clé.
- **Lors d'une mise à jour**, le script propose les réglages de l'installation précédente, y compris les mots de passe et la clé Albert (« Entrée = garder l'actuel »). Une mise à jour se fait donc en appuyant sur Entrée à chaque question.
- **Ordre de priorité** : une valeur écrite dans `installer_ubuntu.conf` passe avant celle de l'installation précédente. Au début, le script affiche « Valeurs proposées lues dans … (n réglages) » : si ce message manque, c'est que la clé porte une ancienne version du script.
- **Vérifier sans rien installer** : `sudo bash installer_ubuntu.sh --verifier` affiche les valeurs trouvées. Les mots de passe n'apparaissent jamais : le script indique seulement s'ils sont déjà enregistrés.
- **Sans aucune question** : `sudo bash installer_ubuntu.sh --auto` prend les valeurs du fichier et de l'installation précédente. Il ne demande que les mots de passe absents.

Les secrets ne s'affichent pas à l'écran. Ils vont dans `/etc/viabilis/viabilis.env`, lisible seulement par l'administrateur.

Le script fait ensuite le reste : service `viabilis`, site Apache, certificat HTTPS, sauvegarde chaque nuit. Il reprend la base de la clé, donc vos classes et leurs codes sont conservés.

## 5 bis. Les comptes enseignants

- **Toute personne peut demander un compte** (enseignant, étudiant, collègue d'ailleurs) sur la page enseignant, avec « Créer un compte ». Elle indique :
  - son nom ;
  - son adresse ;
  - qui elle est et ce qu'elle veut essayer ;
  - un mot de passe d'au moins 10 caractères.
- **Elle confirme d'abord son adresse** par un lien reçu par mail, valable 48 heures : l'adresse doit donc vraiment fonctionner.
- **Vous recevez alors un mail** avec son nom, son adresse et sa présentation. Il arrive à l'adresse de `VIABILIS_NOTIFICATIONS` (question « Adresse qui reçoit les demandes de compte »), ou, à défaut, à votre adresse d'administratrice.
  - Connectez-vous : sous vos classes, la carte « Comptes enseignants » propose « Valider » ou « Refuser ».
  - La personne reçoit un mail dans les deux cas. Tant que vous n'avez pas validé, elle ne peut pas se connecter.
- **« Suspendre »** coupe aussitôt l'accès d'un compte déjà ouvert. Ses classes sont gardées, et « Valider » le rouvre.
- **Limiter à certains domaines** (facultatif) : réglage `VIABILIS_DOMAINES`, au domaine exact. `univ-brest.fr` refuse `etudiant.univ-brest.fr` ; `*.exemple.fr` accepte les sous-domaines.
- **Chaque enseignant ne voit que ses classes.** La classe d'un collègue est introuvable pour lui, même avec son code.
- **Mot de passe oublié** : un lien valable une heure permet d'en choisir un nouveau. Les autres appareils sont alors déconnectés.
- **Protection** : après 8 essais de mot de passe ratés en un quart d'heure, la connexion est bloquée un moment.
- **Le serveur de mail.** Demandez à la DSI :
  - le nom du serveur SMTP et son port (587 en général) ;
  - si possible une adresse fonctionnelle (par exemple `viabilis-noreply@univ-brest.fr`), pour ne pas laisser le mot de passe de votre propre messagerie sur l'ordinateur de la maison ;
  - si ce serveur accepte les envois depuis l'extérieur de l'université (depuis votre box).
- **Votre compte** s'ouvre sans validation, puisque c'est le vôtre. Vos classes actuelles y sont rattachées dès que vous confirmez votre adresse.
- Les élèves ne changent rien : ils entrent toujours avec le code de la classe et un pseudonyme.

## 5 ter. Envoyer les mails avec Gmail

Viabilis peut envoyer ses mails (confirmations, demandes de compte, mots de passe oubliés) par un compte Gmail, sans passer par la DSI.

1. **Activez la validation en deux étapes** du compte Google : https://myaccount.google.com/security. Elle est nécessaire pour l'étape suivante.
2. **Créez un « mot de passe d'application »** : https://myaccount.google.com/apppasswords. Nommez-le « Viabilis ».
   - Google affiche 16 lettres, par groupes de 4. Copiez-les : elles ne seront plus affichées.
   - Ce mot de passe ne sert qu'à envoyer des mails depuis Viabilis. Vous pouvez le supprimer à tout moment sur la même page, sans toucher au mot de passe de votre compte Google.
3. **Lancez `installer_ubuntu.sh`** et répondez :
   - serveur de mail : `smtp.gmail.com` ;
   - port : `587` ;
   - identifiant : votre adresse Gmail ;
   - mot de passe : les 16 lettres, avec ou sans espaces.

   Ces valeurs sont déjà proposées par `installer_ubuntu.conf`, sauf le mot de passe.
4. **Vérifiez** : faites une demande de compte d'essai. Les mails partent de votre adresse Gmail, et la ligne `[MAIL] envoyé à …` apparaît dans le journal :

```bash
sudo journalctl -u viabilis | grep MAIL
```

Limites :
- environ 500 mails par jour, bien assez pour Viabilis ;
- les destinataires voient votre adresse Gmail comme expéditrice ;
- **Essai détaillé** : `sudo python3 /opt/viabilis/application/serveur/essai_mail.py votre@adresse` envoie un mail d'essai étape par étape (connexion, chiffrement, identification, envoi). En cas d'échec, il affiche l'étape et la cause. Il n'affiche jamais le mot de passe.
- `Username and Password not accepted` dans le journal veut dire que c'est le mot de passe habituel du compte qui a été saisi, et non le mot de passe d'application.

## 6. Vérifier

- **Depuis un téléphone en 4G**, Wi-Fi coupé : ouvrez `https://viabilis.mondomaine.fr/eleve/`. Certaines box n'acceptent pas qu'on visite son propre domaine depuis la maison ; le test en 4G est donc le bon.
- **Côté enseignant :** ouvrez `https://viabilis.mondomaine.fr/enseignant/` et créez votre compte : le mail de confirmation doit arriver (regardez aussi les indésirables). Posez ensuite une question au tuteur pour vérifier l'IA.

Dès que tout marche, **n'utilisez plus le serveur du Mac**. Sinon, deux bases divergent. Gardez la copie du Mac comme archive.

Commandes utiles :

| Pour | Commande |
|---|---|
| voir le journal (les lignes `[IA]` donnent la cause d'une erreur de l'IA) | `sudo journalctl -u viabilis -f` |
| redémarrer | `sudo systemctl restart viabilis` |
| changer l'adresse d'administratrice, les domaines, le serveur de mail ou la clé d'API | `sudo nano /etc/viabilis/viabilis.env`, puis redémarrer |
| voir pourquoi un mail n'est pas parti | `sudo journalctl -u viabilis \| grep MAIL` |

## 7. Sécurité, au quotidien

- **Mises à jour automatiques d'Ubuntu :** `sudo apt install unattended-upgrades`, puis `sudo dpkg-reconfigure unattended-upgrades`.
- **Sauvegardes :** elles sont faites chaque nuit dans `/var/backups/viabilis`, sur le même disque. Copiez-les régulièrement ailleurs, par exemple chaque semaine sur une clé chiffrée ou dans NextCloud, sinon une panne de disque emporte tout.
- **Accès :** le compte Ubuntu doit avoir un mot de passe solide, et l'écran se verrouiller. Si possible, chiffrez le disque.
- **Mots de passe enseignants :** prenez-en un long. La page enseignant est visible depuis Internet ; les mots de passe ne sont gardés que sous forme chiffrée (empreinte), jamais en clair.
- **Certificat :** il se renouvelle tout seul (Certbot). Vérifiez-le de temps en temps avec `sudo certbot renew --dry-run`.

## 8. Mettre à jour Viabilis plus tard

Copiez le nouveau dossier `application` sur la clé, **sans** `viabilis.sqlite3`, puis relancez `sudo bash installer_ubuntu.sh`. Le script remplace l'application, garde la base de l'ordinateur et propose les réglages précédents : appuyez sur Entrée à chaque question.
