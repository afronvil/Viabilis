# -*- coding: utf-8 -*-
"""Essai d'envoi d'un mail avec les réglages du serveur Viabilis, étape par étape, avec la cause exacte d'un échec.

    sudo python3 /opt/viabilis/application/serveur/essai_mail.py votre.adresse@exemple.fr

Lit /etc/viabilis/viabilis.env (ou le fichier donné par --env). N'affiche jamais le mot de passe.
"""
import argparse
import smtplib
import socket
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

AIDE = {
    "auth": "Identifiant ou mot de passe refusé. Avec Gmail, il faut le « mot de passe d'application » de 16 lettres "
            "(https://myaccount.google.com/apppasswords), pas le mot de passe habituel du compte, et la validation en deux étapes doit être active.",
    "reseau": "Le serveur de mail ne répond pas : nom mal écrit, port bloqué par la box ou le pare-feu, ou pas d'accès à Internet.",
    "tls": "Échec du chiffrement (STARTTLS/SSL) : vérifiez le port (587 pour STARTTLS, 465 pour SSL).",
    "expediteur": "Adresse d'expédition refusée : avec Gmail, elle doit être l'adresse du compte (VIABILIS_SMTP_EXPEDITEUR vide ou identique).",
}


def lire_env(chemin):
    env = {}
    try:
        for ligne in open(chemin, encoding="utf-8"):
            ligne = ligne.strip().replace("\r", "")
            if ligne and not ligne.startswith("#") and "=" in ligne:
                k, v = ligne.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError as exc:
        sys.exit(f"Impossible de lire {chemin} : {exc}. Lancez la commande avec sudo.")
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("destinataire")
    ap.add_argument("--env", default="/etc/viabilis/viabilis.env")
    a = ap.parse_args()
    env = lire_env(a.env)
    hote, port = env.get("VIABILIS_SMTP_HOTE", ""), int(env.get("VIABILIS_SMTP_PORT") or 587)
    util, mdp = env.get("VIABILIS_SMTP_UTILISATEUR", ""), env.get("VIABILIS_SMTP_MDP", "")
    exp = env.get("VIABILIS_SMTP_EXPEDITEUR") or util
    if hote.lower() == "smtp.gmail.com":
        mdp = mdp.replace(" ", "")
    print(f"Réglages lus dans {a.env} :")
    print(f"  serveur      {hote or '(vide !)'}  port {port}")
    print(f"  identifiant  {util or '(vide)'}")
    print(f"  mot de passe {'(vide !)' if not mdp else f'{len(mdp)} caractères'}" + (" — un mot de passe d'application Gmail en a 16" if hote.lower() == "smtp.gmail.com" and mdp and len(mdp) != 16 else ""))
    print(f"  expéditeur   {exp or '(vide)'}")
    print(f"  liens        {env.get('VIABILIS_ADRESSE') or '(VIABILIS_ADRESSE vide !)'}")
    if not hote:
        sys.exit("\nÉCHEC : VIABILIS_SMTP_HOTE est vide ; relancez installer_ubuntu.sh ou complétez le fichier, puis : sudo systemctl restart viabilis")
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = exp, a.destinataire, "Viabilis : essai d'envoi"
    m["Date"], m["Message-ID"] = formatdate(localtime=True), make_msgid("viabilis")
    m.set_content("Ce mail d'essai prouve que Viabilis peut envoyer ses mails (confirmations, demandes de compte).\n\nViabilis")
    etape = "reseau"
    try:
        print(f"\n1. Connexion à {hote}:{port}…", flush=True)
        ctx = ssl.create_default_context()
        if port == 465:
            etape = "tls"
            s = smtplib.SMTP_SSL(hote, port, context=ctx, timeout=20)
        else:
            s = smtplib.SMTP(hote, port, timeout=20)
            s.ehlo()
            etape = "tls"
            print("2. Chiffrement STARTTLS…", flush=True)
            s.starttls(context=ctx)
            s.ehlo()
        with s:
            if util:
                etape = "auth"
                print("3. Identification…", flush=True)
                s.login(util, mdp)
            etape = "expediteur"
            print(f"4. Envoi à {a.destinataire}…", flush=True)
            s.send_message(m)
        print(f"\nRÉUSSI : mail envoyé à {a.destinataire} (regardez aussi dans les indésirables).")
        print("Si les mails de Viabilis ne partent toujours pas, redémarrez le service : sudo systemctl restart viabilis")
    except (OSError, smtplib.SMTPException, socket.timeout) as exc:
        print(f"\nÉCHEC à l'étape « {etape} » : {type(exc).__name__} — {exc}")
        print(AIDE.get(etape, ""))
        sys.exit(1)


if __name__ == "__main__":
    main()
