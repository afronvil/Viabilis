# Viabilis — procédure d'installation sur un serveur

À l'attention du service informatique. Demande d'Alexandra Fronville (INSPÉ de Bretagne, LaTIM), pour des séances avec les étudiants du M1 de microbiologie.

## 1. En bref

Viabilis est une application web pédagogique : une page pour les étudiants (`/eleve/`) et une page pour l'enseignante (`/enseignant/`).

| Élément | Besoin |
|---|---|
| Machine | une petite machine virtuelle Linux (Debian 12 ou Ubuntu 22.04 et plus récents) : 1 vCPU, 1 Go de mémoire, 2 Go de disque suffisent pour un groupe de master |
| Logiciel | Python 3.9 ou plus récent, **bibliothèque standard uniquement** : aucun paquet pip, aucune base de données à installer (SQLite, un fichier) |
| Réseau entrant | HTTPS seulement, par le proxy inverse de l'université (nginx ou Apache). L'application écoute sur 127.0.0.1:8080 |
| Nom de domaine | **un sous-domaine dédié**, par exemple `viabilis.univ-brest.fr`. L'application doit être servie à la racine du domaine : ses pages appellent `/api/…` en chemin absolu, et elle ne fonctionne pas sous un sous-chemin (`…/viabilis/`) |
| Réseau sortant | HTTPS (443) vers l'API du modèle de langage, par exemple `albert.api.etalab.gouv.fr` (Albert, DINUM) ou `api.mistral.ai` |
| Comptes | un seul compte enseignant, protégé par mot de passe ; les étudiants entrent avec un code de classe et un pseudonyme, sans compte ni adresse électronique |
| Adresses | `/eleve/` pour les étudiants (la racine `/` y renvoie), `/enseignant/` pour l'enseignante, `/api/…` pour les échanges |

```
navigateur ──HTTPS──> proxy de l'université ──HTTP──> 127.0.0.1:8080 (python3 serveur.py) ──> /var/lib/viabilis/viabilis.sqlite3
                                                                      └──HTTPS──> API du modèle de langage
```

## 2. Installation

Les commandes suivantes sont pour Debian ou Ubuntu, en administrateur.

**2.1. Paquets et compte de service**

```bash
apt install python3 unzip sqlite3
useradd --system --home-dir /opt/viabilis --shell /usr/sbin/nologin viabilis
mkdir -p /opt/viabilis /var/lib/viabilis /etc/viabilis /var/backups/viabilis
```

Le paquet `sqlite3` ne sert qu'aux sauvegardes (section 5) ; l'application elle-même utilise le module `sqlite3` de Python.

**2.2. Fichiers de l'application**

```bash
unzip viabilis_application.zip -d /opt/viabilis
chown -R root:root /opt/viabilis
chown viabilis:viabilis /var/lib/viabilis
chmod 700 /var/lib/viabilis /var/backups/viabilis
```

Le code est dans `/opt/viabilis/application/serveur/` et reste en lecture seule pour le service. Seul `/var/lib/viabilis/` est modifiable : la base et ses fichiers de journal SQLite.

**2.3. Configuration et secrets**

Créer `/etc/viabilis/viabilis.env` :

```bash
# Mot de passe du compte enseignant (10 caractères au moins), à transmettre à l'enseignante par un canal sûr
VIABILIS_MDP_ENSEIGNANT=…

# Modèle de langage : Albert (API compatible OpenAI)
VIABILIS_IA=openai
VIABILIS_IA_URL=https://albert.api.etalab.gouv.fr/v1/chat/completions
VIABILIS_IA_MODELE=…            # nom donné par GET https://albert.api.etalab.gouv.fr/v1/models
VIABILIS_IA_CLE=…

# Durée de conservation des traces des étudiants, en jours (purge automatique quotidienne)
VIABILIS_CONSERVATION_JOURS=365

# Si la sortie vers Internet passe par un proxy :
# HTTPS_PROXY=http://proxy.univ-brest.fr:3128
```

```bash
chown root:root /etc/viabilis/viabilis.env
chmod 600 /etc/viabilis/viabilis.env
```

Autres fournisseurs possibles :

| `VIABILIS_IA` | Usage |
|---|---|
| `mistral` | Mistral AI (`VIABILIS_IA_URL` inutile) |
| `openai` avec `VIABILIS_IA_URL` | toute API compatible OpenAI : Albert, vLLM ou Ollama hébergés à l'université… |
| `anthropic` | Claude |
| `gemini` | Gemini |
| `ollama` | modèle local, sur la même machine (il faut alors une machine bien plus puissante) |
| `fausse` | réponses factices, pour les essais |

Au démarrage, le serveur refuse un fournisseur inconnu ou une clé manquante, avec un message explicite. La clé d'API reste sur le serveur : elle n'est jamais envoyée aux navigateurs.

**2.4. Service systemd**

Créer `/etc/systemd/system/viabilis.service` :

```ini
[Unit]
Description=Viabilis (application pédagogique)
After=network-online.target
Wants=network-online.target

[Service]
User=viabilis
Group=viabilis
EnvironmentFile=/etc/viabilis/viabilis.env
WorkingDirectory=/opt/viabilis/application/serveur
ExecStart=/usr/bin/python3 /opt/viabilis/application/serveur/serveur.py --hote 127.0.0.1 --port 8080 --base /var/lib/viabilis/viabilis.sqlite3
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/viabilis

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now viabilis
systemctl status viabilis
```

Au démarrage, le journal (`journalctl -u viabilis`) affiche les deux adresses et le fournisseur d'IA. Il ne contient aucune donnée d'étudiant : les requêtes ne sont pas journalisées, et une erreur de l'IA n'y laisse que sa cause.

**2.5. Proxy inverse HTTPS**

nginx :

```nginx
server {
    listen 443 ssl http2;
    server_name viabilis.univ-brest.fr;
    # ssl_certificate … ; ssl_certificate_key … ;   (certificat de l'université)

    add_header Strict-Transport-Security "max-age=31536000" always;
    client_max_body_size 1m;                # le serveur refuse lui-même les requêtes de plus de 256 Ko

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_read_timeout 300s;            # la vérification par l'IA peut faire deux essais de deux minutes
    }
}
server {
    listen 80;
    server_name viabilis.univ-brest.fr;
    return 301 https://$host$request_uri;
}
```

Apache (avec `mod_proxy`, `mod_proxy_http` et `mod_headers`) :

```apache
<VirtualHost *:443>
    ServerName viabilis.univ-brest.fr
    # SSLEngine on ; SSLCertificateFile … ; SSLCertificateKeyFile …
    Header always set Strict-Transport-Security "max-age=31536000"
    ProxyPass        / http://127.0.0.1:8080/ timeout=300
    ProxyPassReverse / http://127.0.0.1:8080/
</VirtualHost>
```

Le HTTPS est nécessaire pour deux fonctions : l'installation de l'application sur l'écran d'accueil des téléphones et la dictée vocale. Le reste fonctionne aussi en HTTP.

**2.6. Pare-feu**

Il suffit d'ouvrir le port 443 (et 80 pour la redirection) au proxy. Le port 8080 n'écoute que sur 127.0.0.1 et ne doit pas être ouvert.

## 3. Vérification

```bash
curl -I https://viabilis.univ-brest.fr/eleve/        # 200, avec Content-Security-Policy et X-Content-Type-Options
curl -I https://viabilis.univ-brest.fr/api/eleve/moi # 401 : l'API répond
```

Ensuite, dans un navigateur :
1. Sur `https://viabilis.univ-brest.fr/enseignant/`, se connecter avec le mot de passe enseignant.
2. Créer une classe d'essai.
3. Sur `/eleve/`, entrer avec son code et un pseudonyme, puis poser une question au tuteur. Une réponse doit s'afficher.
4. Effacer la classe d'essai (onglet Données).

Si l'IA ne répond pas, l'étudiant voit « L'IA n'a pas répondu ». La cause exacte (clé refusée, modèle inconnu, réseau) apparaît dans `journalctl -u viabilis`.

**Tests automatiques (facultatif).** Ils se lancent sur une base jetable et avec une IA factice, sans toucher la base réelle :

```bash
cd /opt/viabilis/application/serveur
VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8790 --base /tmp/essai.sqlite3 &
python3 test_api.py 8790
kill %1; rm -f /tmp/essai.sqlite3*
```

## 4. Sécurité et données

**Ce que fait le serveur**
- En-têtes : Content-Security-Policy (`default-src 'self'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. Aucune ressource externe (polices, scripts, traceurs).
- Corps des requêtes limité à 256 Ko ; un mauvais mot de passe enseignant coûte une seconde d'attente.
- 40 appels à l'IA au plus par étudiant et par séance. Les consignes données à l'IA sont écrites côté serveur.
- Les étudiants ne peuvent ni lire la classe ni les autres étudiants. Effacement possible d'un étudiant ou de toute la classe ; purge automatique après `VIABILIS_CONSERVATION_JOURS`.
- Ce qui part vers l'API d'IA : la consigne de la tâche et les messages et programmes de l'étudiant, jamais son pseudonyme ni un identifiant.

**Données personnelles.** Les traces des étudiants (pseudonymes, réponses, échanges avec l'IA) sont des données personnelles pseudonymisées. L'enseignante prévoit de les utiliser aussi pour la recherche. Le traitement doit donc être inscrit au registre, avec la DPO de l'université. Pour la même raison, une API d'IA hébergée en France sans réutilisation des données, comme Albert, est préférable.

## 5. Exploitation

**Sauvegarde.** Une copie cohérente de la base peut être faite à chaud. Les sauvegardes contiennent des données personnelles : elles restent sur un stockage protégé et sont soumises à la même durée de conservation.

```bash
sqlite3 /var/lib/viabilis/viabilis.sqlite3 ".backup '/var/backups/viabilis/viabilis-$(date +%F).sqlite3'"
find /var/backups/viabilis -name 'viabilis-*.sqlite3' -mtime +30 -delete
```

Ces deux lignes peuvent être lancées chaque nuit, par cron ou par un minuteur systemd.

**Restauration.**

```bash
systemctl stop viabilis
cp /var/backups/viabilis/viabilis-AAAA-MM-JJ.sqlite3 /var/lib/viabilis/viabilis.sqlite3
chown viabilis:viabilis /var/lib/viabilis/viabilis.sqlite3
systemctl start viabilis
```

**Mise à jour de l'application.** La base n'est pas dans l'archive, elle n'est donc pas touchée par une mise à jour.

```bash
systemctl stop viabilis
rm -rf /opt/viabilis/application && unzip nouvelle_version.zip -d /opt/viabilis
systemctl start viabilis
```

Les navigateurs récupèrent la nouvelle version d'eux-mêmes : le cache hors connexion change de nom à chaque version.

**Changer le mot de passe enseignant ou la clé d'API.** Modifier `/etc/viabilis/viabilis.env`, puis `systemctl restart viabilis`.

## 6. Ce que nous demandons au service informatique

1. Une machine virtuelle Linux, comme décrit en section 1.
2. Le sous-domaine `viabilis.univ-brest.fr` (ou un autre), son certificat et la configuration du proxy (section 2.5).
3. L'accès sortant en HTTPS vers l'API du modèle de langage. Si possible, une clé Albert ou une autre API hébergée en France.
4. La sauvegarde quotidienne de `/var/lib/viabilis/` (section 5).
5. Le mot de passe enseignant, transmis à Alexandra Fronville par un canal sûr.

Pour toute question sur l'application : Alexandra Fronville (INSPÉ de Bretagne, LaTIM). La description complète des fonctions est dans `LISEZMOI.md`.
