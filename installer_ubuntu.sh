#!/bin/bash
# Installation de Viabilis sur un ordinateur Ubuntu qui fait déjà tourner Apache (serveur à la maison, derrière une box).
#
#   sudo bash installer_ubuntu.sh               installation ou mise à jour (questions, valeurs proposées entre crochets)
#   sudo bash installer_ubuntu.sh --auto        sans questions : valeurs de installer_ubuntu.conf et de l'installation précédente
#   sudo bash installer_ubuntu.sh --verifier    affiche seulement les valeurs trouvées, sans rien installer
#
# À lancer depuis le dossier « application » copié sur la machine (clé USB…). Le script :
#   1. installe Python 3, SQLite et Certbot (paquets Ubuntu) ;
#   2. copie l'application dans /opt/viabilis (en lecture seule) et les données dans /var/lib/viabilis ;
#   3. reprend la base viabilis.sqlite3 si elle est à côté du script (vos classes actuelles) ;
#   4. règle les comptes enseignants (adresse confirmée par mail), le serveur de mail et la clé d'API
#      (les mots de passe ne s'affichent pas et ne restent pas dans l'historique) ;
#   5. crée le service systemd « viabilis » et le site Apache du nom de domaine choisi ;
#   6. demande un certificat HTTPS (Let's Encrypt) ;
#   7. programme une sauvegarde quotidienne de la base.
# Il peut être relancé : il remplace l'application, garde la base existante et propose les réglages précédents (Entrée pour les garder).
# lancé avec « sh » (dash) : on relance avec bash, dont le script a besoin
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -euo pipefail
VERSION_SCRIPT="2026-10-19 (lit installer_ubuntu.conf)"
MODE="questions"
case "${1:-}" in --auto) MODE="auto" ;; --verifier) MODE="verifier" ;; "") ;; *) echo "Option inconnue : $1 (--auto ou --verifier)"; exit 1 ;; esac

ICI="$(cd "$(dirname "$0")" && pwd)"
echo "Script d'installation de Viabilis, version $VERSION_SCRIPT, dans $ICI"
[ "$(id -u)" -eq 0 ] || { echo "Lancez-le avec sudo : sudo bash installer_ubuntu.sh"; exit 1; }
[ -f "$ICI/serveur/serveur.py" ] || { echo "Lancez ce script depuis le dossier « application » de Viabilis."; exit 1; }
grep -qi ubuntu /etc/os-release || echo "Attention : ce système n'est pas Ubuntu ; le script suppose Ubuntu (apt, systemd, Apache 2)."
command -v apache2 >/dev/null || { echo "Apache 2 n'est pas installé (paquet apache2)."; exit 1; }

echo "== Viabilis : installation =="
# Valeurs proposées (Entrée = garder la valeur entre crochets), de la moins prioritaire à la plus prioritaire :
#   1. les valeurs ci-dessous ;
#   2. l'installation précédente (/etc/viabilis/viabilis.env et /etc/viabilis/installation.conf) ;
#   3. le fichier installer_ubuntu.conf, à côté de ce script : ce que vous y écrivez est toujours proposé.
DEFAUT_DOMAINE=""; DEFAUT_COURRIEL=""; DEFAUT_ADMIN=""; DEFAUT_NOTIFICATIONS=""; DEFAUT_DOMAINES=""
DEFAUT_SMTP_HOTE=""; DEFAUT_SMTP_PORT="587"; DEFAUT_SMTP_UTILISATEUR=""; DEFAUT_SMTP_EXPEDITEUR=""
DEFAUT_MODELE="mistral-small-3-2-24b-instruct-2506"
NOMS="DOMAINE COURRIEL ADMIN NOTIFICATIONS DOMAINES SMTP_HOTE SMTP_PORT SMTP_UTILISATEUR SMTP_EXPEDITEUR MODELE"
ANCIEN=/etc/viabilis/viabilis.env
ancien() { [ -f "$ANCIEN" ] && sed -n "s/^$1=//p" "$ANCIEN" | tr -d '\r' | tail -1 || true; }   # lu, jamais exécuté
garder() { [ -n "$2" ] && printf -v "$1" '%s' "$2" || true; }
if [ -f /etc/viabilis/installation.conf ]; then
  garder DEFAUT_DOMAINE "$(sed -n 's/^DOMAINE=//p' /etc/viabilis/installation.conf)"
  garder DEFAUT_COURRIEL "$(sed -n 's/^COURRIEL=//p' /etc/viabilis/installation.conf)"
fi
garder DEFAUT_ADMIN "$(ancien VIABILIS_ADMIN)"; garder DEFAUT_NOTIFICATIONS "$(ancien VIABILIS_NOTIFICATIONS)"; garder DEFAUT_DOMAINES "$(ancien VIABILIS_DOMAINES)"
garder DEFAUT_SMTP_HOTE "$(ancien VIABILIS_SMTP_HOTE)"; garder DEFAUT_SMTP_PORT "$(ancien VIABILIS_SMTP_PORT)"
garder DEFAUT_SMTP_UTILISATEUR "$(ancien VIABILIS_SMTP_UTILISATEUR)"; garder DEFAUT_SMTP_EXPEDITEUR "$(ancien VIABILIS_SMTP_EXPEDITEUR)"
garder DEFAUT_MODELE "$(ancien VIABILIS_IA_MODELE)"
CONF="$ICI/installer_ubuntu.conf"
if [ -f "$CONF" ]; then
  # lu dans un sous-shell : on accepte DEFAUT_DOMAINE=…, DOMAINE=… ou VIABILIS_…=…, et les fins de ligne Windows
  LUES="$(
    set +eu
    for n in $NOMS; do unset "DEFAUT_$n" "$n" "VIABILIS_$n"; done; unset VIABILIS_IA_MODELE
    eval "$(tr -d '\r' < "$CONF")" >/dev/null 2>&1
    VIABILIS_MODELE="${VIABILIS_IA_MODELE:-}"
    for n in $NOMS; do
      for v in "DEFAUT_$n" "$n" "VIABILIS_$n"; do
        [ -n "${!v:-}" ] && { printf '%s=%s\n' "$n" "${!v}"; break; }
      done
    done
    true
  )"
  while IFS='=' read -r n v; do [ -n "$n" ] && printf -v "DEFAUT_$n" '%s' "$v" || true; done <<< "$LUES"
  echo "Valeurs proposées lues dans $CONF ($(printf '%s\n' "$LUES" | grep -c '=' || true) réglage(s))."
else
  echo "Pas de fichier $CONF : valeurs proposées par défaut seulement."
fi

if [ "$MODE" = "verifier" ]; then
  echo "Installation précédente : $([ -f "$ANCIEN" ] && echo "trouvée ($ANCIEN)" || echo "aucune")"
  for n in $NOMS; do v="DEFAUT_$n"; printf '  %-17s [%s]\n' "$n" "${!v}"; done
  for n in VIABILIS_SMTP_MDP VIABILIS_IA_CLE; do printf '  %-17s %s\n' "$n" "$([ -n "$(ancien $n)" ] && echo "déjà enregistré" || echo "non enregistré")"; done
  echo "Rien n'a été installé (--verifier)."
  exit 0
fi

# demander VARIABLE "question" "valeur proposée" ; en mode --auto, la valeur proposée est prise sans question (même vide)
demander() {
  local rep
  if [ "$MODE" = "auto" ]; then echo "$2 : ${3:-(vide)}"; printf -v "$1" '%s' "$3"; return; fi
  if [ -n "$3" ]; then read -r -p "$2 [$3] : " rep || true; else read -r -p "$2 : " rep || true; fi
  printf -v "$1" '%s' "${rep:-$3}"
}
# secret : jamais affiché ; Entrée garde celui de l'installation précédente
demander_secret() {
  local rep deja; deja="$(ancien "$3")"
  if [ "$MODE" = "auto" ] && [ -n "$deja" ]; then echo "$2 : celui de l'installation précédente"; printf -v "$1" '%s' "$deja"; return; fi
  if [ -n "$deja" ]; then read -r -s -p "$2 (Entrée = garder l'actuel) : " rep || true; else read -r -s -p "$2 : " rep || true; fi
  echo
  printf -v "$1" '%s' "${rep:-$deja}"
}

demander DOMAINE "Nom de domaine de Viabilis (par exemple viabilis.mondomaine.fr)" "$DEFAUT_DOMAINE"
[ -n "$DOMAINE" ] || { echo "Il faut un nom de domaine."; exit 1; }
demander COURRIEL "Adresse électronique pour le certificat HTTPS (avis d'expiration de Let's Encrypt)" "$DEFAUT_COURRIEL"
echo "Comptes enseignants : chacun demande un compte avec une adresse confirmée par mail ; vous validez chaque demande"
echo "(mail reçu, puis carte « Comptes enseignants » de votre page). Chacun ne voit que ses propres classes."
demander ADMIN "Votre adresse d'administratrice (elle reçoit les demandes et reprend les classes déjà créées)" "${DEFAUT_ADMIN:-$COURRIEL}"
[ -n "$ADMIN" ] || { echo "Il faut l'adresse de l'administratrice."; exit 1; }
demander NOTIFICATIONS "Adresse qui reçoit les demandes de compte (plusieurs : séparées par des virgules)" "${DEFAUT_NOTIFICATIONS:-$ADMIN}"
demander DOMAINES "Limiter les demandes à certains domaines (par exemple univ-brest.fr), vide = toute adresse" "$DEFAUT_DOMAINES"
demander SMTP_HOTE "Serveur de mail (SMTP) de l'établissement, par exemple smtp.univ-brest.fr" "$DEFAUT_SMTP_HOTE"
demander SMTP_PORT "Port du serveur de mail" "$DEFAUT_SMTP_PORT"
demander SMTP_UTILISATEUR "Identifiant sur ce serveur de mail" "$DEFAUT_SMTP_UTILISATEUR"
demander_secret SMTP_MDP "Mot de passe de ce compte de messagerie" VIABILIS_SMTP_MDP
demander SMTP_EXPEDITEUR "Adresse d'expédition des mails" "${DEFAUT_SMTP_EXPEDITEUR:-$SMTP_UTILISATEUR}"
demander_secret CLE "Clé d'API Albert (vide : configurer l'IA plus tard)" VIABILIS_IA_CLE
demander MODELE "Modèle Albert" "$DEFAUT_MODELE"

echo "-- 1. Paquets"
apt-get update -qq
apt-get install -y -qq python3 sqlite3 certbot python3-certbot-apache >/dev/null
apt-get install -y -qq python3-pypdf >/dev/null 2>&1 || echo "   (python3-pypdf indisponible : Viabilis lira les PDF avec son lecteur intégré)"
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9 ou plus récent est nécessaire"'

echo "-- 2. Compte de service et dossiers"
id viabilis >/dev/null 2>&1 || useradd --system --home-dir /opt/viabilis --shell /usr/sbin/nologin viabilis
mkdir -p /opt/viabilis /var/lib/viabilis /etc/viabilis /var/backups/viabilis
rm -rf /opt/viabilis/application
cp -r "$ICI" /opt/viabilis/application
rm -f /opt/viabilis/application/serveur/viabilis.sqlite3*
find /opt/viabilis/application -name "__pycache__" -type d -prune -exec rm -rf {} +
chown -R root:root /opt/viabilis
chmod 700 /var/lib/viabilis /var/backups/viabilis
chown viabilis:viabilis /var/lib/viabilis

echo "-- 3. Base de données"
if [ -f /var/lib/viabilis/viabilis.sqlite3 ]; then
  echo "Base existante gardée : /var/lib/viabilis/viabilis.sqlite3"
elif [ -f "$ICI/serveur/viabilis.sqlite3" ]; then
  sqlite3 "$ICI/serveur/viabilis.sqlite3" ".backup '/var/lib/viabilis/viabilis.sqlite3'"
  echo "Base reprise depuis la clé : vos classes sont conservées."
else
  echo "Pas de base trouvée : Viabilis démarrera avec une base vide."
fi
chown -R viabilis:viabilis /var/lib/viabilis

echo "-- 4. Secrets (/etc/viabilis/viabilis.env, lisible par root seulement)"
umask 077
{
  echo "VIABILIS_ADMIN=$ADMIN"
  echo "VIABILIS_NOTIFICATIONS=${NOTIFICATIONS:-$ADMIN}"
  [ -n "$DOMAINES" ] && echo "VIABILIS_DOMAINES=$DOMAINES"
  echo "VIABILIS_ADRESSE=https://$DOMAINE"
  echo "VIABILIS_SMTP_HOTE=$SMTP_HOTE"
  echo "VIABILIS_SMTP_PORT=$SMTP_PORT"
  echo "VIABILIS_SMTP_UTILISATEUR=$SMTP_UTILISATEUR"
  echo "VIABILIS_SMTP_MDP=$SMTP_MDP"
  echo "VIABILIS_SMTP_EXPEDITEUR=$SMTP_EXPEDITEUR"
  if [ -n "$CLE" ]; then
    echo "VIABILIS_IA=openai"
    echo "VIABILIS_IA_URL=https://albert.api.etalab.gouv.fr/v1/chat/completions"
    echo "VIABILIS_IA_MODELE=$MODELE"
    echo "VIABILIS_IA_CLE=$CLE"
  else
    echo "VIABILIS_IA=fausse"
  fi
  echo "VIABILIS_CONSERVATION_JOURS=365"
} > /etc/viabilis/viabilis.env
printf 'DOMAINE=%s\nCOURRIEL=%s\n' "$DOMAINE" "$COURRIEL" > /etc/viabilis/installation.conf   # proposés à la prochaine mise à jour
umask 022
chown root:root /etc/viabilis/viabilis.env
chmod 600 /etc/viabilis/viabilis.env
unset CLE SMTP_MDP

echo "-- 5. Service systemd"
cat > /etc/systemd/system/viabilis.service <<'UNITE'
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
UNITE
systemctl daemon-reload
systemctl enable --now viabilis
systemctl restart viabilis
sleep 2
systemctl is-active --quiet viabilis || { journalctl -u viabilis -n 20 --no-pager; echo "Le service ne démarre pas : voir ci-dessus."; exit 1; }
curl -fsS -o /dev/null http://127.0.0.1:8080/eleve/ && echo "Viabilis répond sur la machine."

echo "-- 6. Site Apache ($DOMAINE)"
a2enmod -q proxy proxy_http headers >/dev/null
cat > /etc/apache2/sites-available/viabilis.conf <<SITE
<VirtualHost *:80>
    ServerName $DOMAINE
    ProxyPreserveHost On
    # la vérification par l'IA peut prendre deux essais de deux minutes
    ProxyPass        / http://127.0.0.1:8080/ timeout=300
    ProxyPassReverse / http://127.0.0.1:8080/
    LimitRequestBody 5242880
</VirtualHost>
SITE
a2ensite -q viabilis >/dev/null
apache2ctl configtest
systemctl reload apache2

echo "-- 7. Certificat HTTPS (Let's Encrypt)"
echo "Il faut que $DOMAINE pointe vers votre box et que la box redirige les ports 80 et 443 vers cette machine (voir INSTALLATION_MAISON.md)."
if [ "$MODE" = "auto" ]; then           # sans questions : un certificat seulement s'il n'y en a pas encore
  if [ -d "/etc/letsencrypt/live/$DOMAINE" ]; then OUI="n"; echo "Certificat déjà présent : gardé."; else OUI="o"; fi
else
  read -r -p "Demander le certificat maintenant ? [o/N] " OUI
fi
if [ "${OUI,,}" = "o" ]; then
  certbot --apache --non-interactive --agree-tos --redirect -m "$COURRIEL" -d "$DOMAINE" \
    && sed -i 's#</VirtualHost>#    Header always set Strict-Transport-Security "max-age=31536000"\n</VirtualHost>#' /etc/apache2/sites-available/viabilis-le-ssl.conf \
    && systemctl reload apache2 && echo "HTTPS en place : https://$DOMAINE/eleve/" \
    || echo "Le certificat n'a pas pu être obtenu : vérifiez le nom de domaine et la redirection des ports, puis relancez : sudo certbot --apache -d $DOMAINE"
else
  echo "Plus tard : sudo certbot --apache --redirect -d $DOMAINE"
fi

echo "-- 8. Sauvegarde quotidienne (3 h du matin, 30 jours gardés, dans /var/backups/viabilis)"
cat > /etc/cron.d/viabilis-sauvegarde <<'CRON'
0 3 * * * root sqlite3 /var/lib/viabilis/viabilis.sqlite3 ".backup '/var/backups/viabilis/viabilis-$(date +\%F).sqlite3'" && find /var/backups/viabilis -name 'viabilis-*.sqlite3' -mtime +30 -delete
CRON
chmod 644 /etc/cron.d/viabilis-sauvegarde

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow "Apache Full" >/dev/null && echo "Pare-feu : ports 80 et 443 ouverts."
fi

echo
echo "-- 9. Essai d'envoi d'un mail"
if [ -n "$SMTP_HOTE" ]; then
  DEST_ESSAI="$(printf '%s' "${NOTIFICATIONS:-$ADMIN}" | cut -d, -f1 | tr -d ' ')"
  if [ "$(printf '%s' "$DEST_ESSAI" | tr 'A-Z' 'a-z')" = "$(printf '%s' "$SMTP_UTILISATEUR" | tr 'A-Z' 'a-z')" ]; then
    echo "Attention : les demandes de compte partent de $SMTP_UTILISATEUR vers la même adresse."
    echo "Gmail range ces mails dans « Messages envoyés », pas dans la boîte de réception : préférez une autre adresse pour les demandes."
  fi
  if [ "$MODE" = "auto" ]; then ESSAI="o"; else read -r -p "Envoyer un mail d'essai à $DEST_ESSAI ? [O/n] " ESSAI || true; fi
  if [ "${ESSAI,,}" != "n" ]; then
    python3 /opt/viabilis/application/serveur/essai_mail.py "$DEST_ESSAI" || echo "Le mail d'essai n'est pas parti : voir la cause ci-dessus (INSTALLATION_MAISON.md, section 5 ter)."
  fi
else
  echo "Aucun serveur de mail réglé : les mails (confirmations, demandes de compte) ne partiront pas."
fi

echo "== Terminé =="
echo "Étudiants : https://$DOMAINE/eleve/    Enseignant : https://$DOMAINE/enseignant/"
echo "Créez votre compte sur la page enseignant (« Créer un compte ») avec $ADMIN : vos classes actuelles y seront rattachées."
echo "Si le mail de confirmation n'arrive pas, la ligne [MAIL] du journal en donne la cause : sudo journalctl -u viabilis | grep MAIL"
echo "Journal du serveur : sudo journalctl -u viabilis -f      Redémarrer : sudo systemctl restart viabilis"
