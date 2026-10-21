# -*- coding: utf-8 -*-
"""Comptes enseignants : adresse électronique confirmée, mot de passe, liens envoyés par mail.

Le mode « comptes » s'active avec VIABILIS_ADMIN, l'adresse de l'administratrice : chaque demande de compte lui est envoyée
par mail et n'ouvre l'accès qu'une fois validée par elle (page enseignant, carte « Comptes enseignants »).
Chaque enseignant ne voit que ses classes. Facultatif : VIABILIS_DOMAINES limite les adresses qui peuvent demander un compte
(par exemple « univ-brest.fr,ac-rennes.fr » ; « *.exemple.fr » accepte aussi les sous-domaines).
Sans cette variable, l'ancien mode reste : un seul mot de passe (VIABILIS_MDP_ENSEIGNANT), toutes les classes.

Envoi des mails (serveur SMTP de l'établissement) :
    VIABILIS_SMTP_HOTE, VIABILIS_SMTP_PORT (587 par défaut, STARTTLS ; 465 : SSL), VIABILIS_SMTP_UTILISATEUR,
    VIABILIS_SMTP_MDP, VIABILIS_SMTP_EXPEDITEUR (adresse « De : », par défaut l'utilisateur)
    VIABILIS_ADRESSE        adresse publique de Viabilis pour les liens (par exemple https://viabilis.mondomaine.fr)
    VIABILIS_MAIL_DOSSIER   (essais) écrit les mails dans ce dossier au lieu de les envoyer
Sans serveur SMTP ni dossier, le lien est écrit dans le journal du serveur.
"""
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

ITERATIONS = 300_000
DUREE = {"confirmation": 48 * 3600, "reinitialisation": 3600}
ADRESSE = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+)")


def actif():
    return bool(admin() or domaines())


def admin():
    return os.environ.get("VIABILIS_ADMIN", "").strip().lower()


def destinataires_demandes():
    """Adresses qui reçoivent les demandes de compte : VIABILIS_NOTIFICATIONS (séparées par des virgules), sinon l'administratrice."""
    l = [x.strip() for x in os.environ.get("VIABILIS_NOTIFICATIONS", "").split(",") if x.strip()]
    return l or [admin()]


def domaines():
    return [d.strip().lower().lstrip("@") for d in os.environ.get("VIABILIS_DOMAINES", "").split(",") if d.strip()]


def email_valide(email):
    """Adresse normalisée si elle est bien formée et d'un domaine autorisé, sinon None.
    Domaine exact seulement : « univ-brest.fr » n'accepte pas « etudiant.univ-brest.fr » (les étudiants) ; « *.exemple.fr » accepte les sous-domaines."""
    email = str(email or "").strip().lower()[:254]
    m = ADRESSE.fullmatch(email)
    if not m:
        return None
    dom = m.group(1)
    if not domaines():                   # aucune limite : étudiants et autres personnes peuvent demander un compte
        return email
    return email if any(dom == d or d.startswith("*.") and dom.endswith(d[1:]) for d in domaines()) else None


def hacher(mdp):
    sel = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", mdp.encode(), sel, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${sel.hex()}${h.hex()}"


def verifier(mdp, stocke):
    try:
        _, it, sel, h = stocke.split("$")
        essai = hashlib.pbkdf2_hmac("sha256", mdp.encode(), bytes.fromhex(sel), int(it))
        return hmac.compare_digest(essai.hex(), h)
    except (ValueError, AttributeError):
        hashlib.pbkdf2_hmac("sha256", mdp.encode(), b"0" * 16, ITERATIONS)   # même durée qu'un vrai essai
        return False


def empreinte(jeton):
    return hashlib.sha256(jeton.encode()).hexdigest()


def nouveau_jeton(c, enseignant, type_):
    """Jeton à usage unique, envoyé par mail ; la base n'en garde que l'empreinte."""
    j = secrets.token_urlsafe(32)
    c.execute("DELETE FROM jetons_mail WHERE enseignant = ? AND type = ?", (enseignant, type_))
    c.execute("INSERT INTO jetons_mail (empreinte, enseignant, type, expire) VALUES (?, ?, ?, ?)",
              (empreinte(j), enseignant, type_, time.time() + DUREE[type_]))
    return j


def utiliser_jeton(c, jeton, type_):
    """Identifiant de l'enseignant si le jeton est valable (il est alors consommé), sinon None."""
    r = c.execute("SELECT enseignant, expire FROM jetons_mail WHERE empreinte = ? AND type = ?", (empreinte(str(jeton or "")), type_)).fetchone()
    if not r:
        return None
    c.execute("DELETE FROM jetons_mail WHERE empreinte = ?", (empreinte(str(jeton)),))
    return r["enseignant"] if r["expire"] > time.time() else None


# ---------------------------------------------------------------- limites d'essais (connexion, envoi de mails)
_ESSAIS, _VERROU = {}, threading.Lock()


def trop_d_essais(cle, maximum, duree):
    """Vrai si `cle` a déjà fait `maximum` essais pendant les `duree` dernières secondes ; sinon compte cet essai."""
    now = time.time()
    with _VERROU:
        liste = [t for t in _ESSAIS.get(cle, []) if t > now - duree]
        if len(liste) >= maximum:
            _ESSAIS[cle] = liste
            return True
        _ESSAIS[cle] = liste + [now]
        if len(_ESSAIS) > 10000:            # mémoire bornée
            for k in [k for k, v in _ESSAIS.items() if not v or v[-1] < now - 3600]:
                del _ESSAIS[k]
        return False


def bloque(cle, maximum, duree):
    """Vrai si `cle` a déjà `maximum` échecs notés pendant les `duree` dernières secondes (sans rien compter)."""
    now = time.time()
    with _VERROU:
        return len([t for t in _ESSAIS.get(cle, []) if t > now - duree]) >= maximum


def noter_echec(cle):
    with _VERROU:
        _ESSAIS.setdefault(cle, []).append(time.time())


def oublier_essais(cle):
    with _VERROU:
        _ESSAIS.pop(cle, None)


# ---------------------------------------------------------------- envoi
def envoyer(destinataire, sujet, texte):
    """Envoie le mail en arrière-plan (la page n'attend pas le serveur de messagerie)."""
    threading.Thread(target=_envoyer, args=(destinataire, sujet, texte), daemon=True).start()


def _envoyer(destinataire, sujet, texte):
    dossier = os.environ.get("VIABILIS_MAIL_DOSSIER")
    hote = os.environ.get("VIABILIS_SMTP_HOTE")
    utilisateur = os.environ.get("VIABILIS_SMTP_UTILISATEUR", "")
    m = EmailMessage()
    m["From"] = os.environ.get("VIABILIS_SMTP_EXPEDITEUR") or utilisateur or "viabilis@localhost"
    m["To"], m["Subject"], m["Date"], m["Message-ID"] = destinataire, sujet, formatdate(localtime=True), make_msgid("viabilis")
    m.set_content(texte)
    try:
        if dossier:
            os.makedirs(dossier, exist_ok=True)
            with open(os.path.join(dossier, f"{time.time():.6f}.eml"), "wb") as f:
                f.write(bytes(m))
            return
        if not hote:
            print(f"[MAIL] aucun serveur SMTP réglé (VIABILIS_SMTP_HOTE) : mail pour {destinataire} non envoyé.\n{texte}", flush=True)
            return
        port = int(os.environ.get("VIABILIS_SMTP_PORT", "587"))
        contexte = ssl.create_default_context()
        if port == 465:
            s = smtplib.SMTP_SSL(hote, port, context=contexte, timeout=30)
        else:
            s = smtplib.SMTP(hote, port, timeout=30)
            s.ehlo()
            if s.has_extn("starttls"):
                s.starttls(context=contexte)
                s.ehlo()
            elif utilisateur:            # jamais d'identifiant en clair sur le réseau
                s.close()
                raise smtplib.SMTPException("le serveur ne propose pas STARTTLS : connexion refusée sans chiffrement")
        with s:
            if utilisateur:
                mdp = os.environ.get("VIABILIS_SMTP_MDP", "")
                if hote.lower() == "smtp.gmail.com":          # mot de passe d'application Google : affiché par groupes de 4, sans espace en réalité
                    mdp = mdp.replace(" ", "")
                s.login(utilisateur, mdp)
            s.send_message(m)
        print(f"[MAIL] envoyé à {destinataire}", flush=True)
    except Exception as exc:          # tout est écrit au journal : un échec d'envoi ne doit jamais passer inaperçu
        print(f"[MAIL] envoi impossible à {destinataire} : {type(exc).__name__} — {exc}"
              " (essai détaillé : sudo python3 /opt/viabilis/application/serveur/essai_mail.py votre@adresse)", flush=True)
