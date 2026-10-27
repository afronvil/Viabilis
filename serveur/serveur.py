#!/usr/bin/env python3
"""
Viabilis classe — serveur de l'application (élève + enseignant).

Python 3.9 ou plus, bibliothèque standard uniquement (aucune dépendance à installer).
Données : une base SQLite locale. IA : appel côté serveur à un fournisseur configurable ;
les élèves n'envoient jamais de clé et ne choisissent pas les consignes données à l'IA.

    VIABILIS_MDP_ENSEIGNANT='…' python3 serveur.py          # http://127.0.0.1:8080
    python3 serveur.py --port 8080 --base viabilis.sqlite3

Variables d'environnement (voir LISEZMOI.md et INSTALLATION.md) :
    VIABILIS_MDP_ENSEIGNANT   mot de passe unique enseignant (mode sans comptes)
    VIABILIS_ADMIN            active les comptes enseignants : adresse de l'administratrice, qui valide chaque demande ; voir comptes.py
    VIABILIS_NOTIFICATIONS    (facultatif) adresse(s) qui reçoivent les demandes de compte, par défaut VIABILIS_ADMIN
    VIABILIS_DOMAINES         (facultatif) domaines de messagerie qui peuvent demander un compte
    VIABILIS_PROPRIETAIRE     adresse du compte qui reprend les classes créées avant les comptes (par défaut VIABILIS_ADMIN)
    VIABILIS_IA               "anthropic" | "openai" (API compatible : Mistral, Albert, Ollama…) | "fausse" (tests)
    VIABILIS_IA_URL           point d'accès de l'API (défaut selon le fournisseur)
    VIABILIS_IA_CLE           clé d'API (jamais transmise aux navigateurs)
    VIABILIS_IA_MODELE        nom du modèle
    VIABILIS_CONSERVATION_JOURS  durée de conservation des traces (défaut 365)
"""
import argparse
import base64
import csv
import hashlib
import hmac
import io
import json
import os
import random
import re
import unicodedata
import secrets
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))     # Python « embarquable » de Windows (clé USB) : il ignore le dossier du script
import exercices as EX
import hors_ligne as HL
import noyau as NOYAU
import verification as VERIF
import comptes as CPT
import zpdes as ZPDES
import pdf_texte as PDF
from langues import T, NOM_POUR_IA, langue_valide, traduire_texte

RACINE = os.path.dirname(os.path.abspath(__file__))
STATIQUE = os.path.join(RACINE, "web")


def _disciplines_des_modeles():
    """Discipline de chaque modèle de séance (web/commun/modeles.json) : la page élève choisit ses illustrations d'après elle."""
    try:
        with open(os.path.join(STATIQUE, "commun", "modeles.json"), encoding="utf-8") as f:
            return {m["id"]: m.get("discipline", "") for m in json.load(f).get("modeles", []) if "id" in m}
    except (OSError, ValueError, AttributeError):
        return {}


DISCIPLINE_DU_MODELE = _disciplines_des_modeles()
TAILLE_MAX = 256 * 1024
TAILLE_MAX_TRAVAIL = 4 * 1024 * 1024    # travail hors ligne d'un étudiant, importé par l'enseignante
TAILLE_MAX_PDF = 10 * 1024 * 1024       # document PDF d'une séance
TAILLE_MAX_CONFIG = 2 * 1024 * 1024     # réglages d'une classe : chaque séance y garde sa consigne et ses critères
HORS_LIGNE = None                      # {code, nom, kit} quand le serveur tourne sur l'ordinateur d'un étudiant (--hors-ligne)
IA_MAX_PAR_SEANCE = 40
DEFAUT_CONFIG = {
    "seance": 0, "ouverte": False, "tache": "",
    "ordre": "adaptatif", "mode": "questionner", "minIdees": 3,
    "seuilCharge": 0.7, "retraitAgentivite": 0.8, "seuilMaitrise": 0.5,
    "eleves": {},
    "exercices": {"actifs": False, "nombre": 3, "placement": "avant", "niveau": 2, "choix": "niveau", "source": "", "explications": True},   # choix : niveau fixé ou adaptatif (ZPDES) ; source : seulement les questions de ce fichier ; explications : l'élève peut demander à l'IA d'expliquer son erreur
    "niveauTache": 3,
    "verification": {"mode": "aucune", "cible": 10, "nombres": "", "attendu": 0, "criteres": "", "maximum": 3, "uneFois": False},
    "indices": [],
    "variantes": {"actives": False,
                  "accessible": {"consigne": "", "indices": [], "cible": None, "attendu": None},
                  "exigeante": {"consigne": "", "indices": [], "cible": None, "attendu": None}},
    "groupes": {},
    "lecture": {"active": True, "langue": "fr-FR", "dictee": False},
    "galerie": {},               # idées choisies par l'enseignant, sans nom, montrées à la classe après la séance : {séance: [textes]}
    "evaluation": False,         # séance d'évaluation : sans IA ni coup de pouce, une seule réponse par exercice, corrections masquées
    "saisieCode": False,         # les idées sont du code (police à chasse fixe, indentation conservée) : séances de programmation
    "visuels": True,             # illustrations et couleurs adaptées au niveau et à la discipline, sur la page élève
    "langue": "fr",              # langue de l'interface des élèves et des réponses de l'IA : fr, en ou ca
    "public": "ecole",           # école, collège, lycée ou supérieur : ton et exigence de l'IA, modèles de séances proposés
    "discipline": "",            # discipline de la classe : "" = celle de ses séances, "*" = toutes (classe polyvalente), sinon son nom
    "modele": "",                # identifiant du modèle de séance d'origine (web/commun/modeles.json), vide si consigne libre
    "ouvertes": [],              # séances ouvertes en même temps (l'élève choisit la sienne)
    "archives": {},              # consigne et réglages de la tâche de chaque séance, figés quand une séance plus récente existe
    "codePersonnel": False,      # exiger le code personnel pour revenir sous un pseudonyme existant
    "supprimees": [],            # séances effacées par l'enseignant (leurs numéros ne sont pas réutilisés)
    "document": 0,               # document PDF de la séance, consultable par les élèves (table documents), 0 si aucun
}
INSTANTANE = ("tache", "indices", "variantes", "verification", "exercices", "niveauTache", "minIdees", "lecture", "modele", "saisieCode", "evaluation", "document")
VARIANTES = ("accessible", "standard", "exigeante")
GROUPES = ("atelier", "accompagne", "defi")
LANGUES = ("fr-FR", "en-GB", "en-US", "es-ES", "de-DE", "it-IT")
ORDRES, MODES = {"reflexion", "ia", "adaptatif"}, {"questionner", "elements"}
ORIGINES = ("manuel", "recommandation", "toutes_recommandations", "groupes", "suite")      # d'où vient un changement de réglage d'élève
DEMARCHES = ("hasard", "ordre", "transformer", "aide", "autre")
AIDES = ("idees", "pouce", "ia", "verification", "camarade", "enseignant", "rien")
VERROU = threading.Lock()


def maintenant():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- base de données
SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (code TEXT PRIMARY KEY, nom TEXT, config TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '{}', cree TEXT);
CREATE TABLE IF NOT EXISTS eleves (id TEXT PRIMARY KEY, classe TEXT NOT NULL REFERENCES classes(code) ON DELETE CASCADE,
    pseudo TEXT NOT NULL, jeton TEXT UNIQUE NOT NULL, cree TEXT, UNIQUE(classe, pseudo));
CREATE TABLE IF NOT EXISTS traces (eleve TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE, seance INTEGER NOT NULL,
    donnees TEXT NOT NULL, maj TEXT, appels_ia INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(eleve, seance));
CREATE TABLE IF NOT EXISTS sessions_enseignant (jeton TEXT PRIMARY KEY, expire REAL NOT NULL);
CREATE TABLE IF NOT EXISTS enseignants (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, hash TEXT NOT NULL,
    verifie INTEGER NOT NULL DEFAULT 0, cree TEXT, valide INTEGER NOT NULL DEFAULT 0, nom TEXT, presentation TEXT);
CREATE TABLE IF NOT EXISTS jetons_mail (empreinte TEXT PRIMARY KEY, enseignant INTEGER NOT NULL REFERENCES enseignants(id) ON DELETE CASCADE,
    type TEXT NOT NULL, expire REAL NOT NULL);
CREATE TABLE IF NOT EXISTS exercices (id INTEGER PRIMARY KEY AUTOINCREMENT, classe TEXT NOT NULL REFERENCES classes(code) ON DELETE CASCADE,
    titre TEXT, type TEXT, niveau INTEGER NOT NULL DEFAULT 2, actif INTEGER NOT NULL DEFAULT 1, donnees TEXT NOT NULL, source TEXT, cree TEXT);
CREATE TABLE IF NOT EXISTS verifications (eleve TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE, seance INTEGER NOT NULL,
    nombre INTEGER NOT NULL DEFAULT 0, donnees TEXT, maj TEXT, PRIMARY KEY(eleve, seance));
CREATE TABLE IF NOT EXISTS indices_vus (eleve TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE, seance INTEGER NOT NULL,
    nombre INTEGER NOT NULL DEFAULT 0, maj TEXT, PRIMARY KEY(eleve, seance));
CREATE TABLE IF NOT EXISTS tirages (eleve TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE, seance INTEGER NOT NULL, ids TEXT NOT NULL,
    PRIMARY KEY(eleve, seance));
CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, eleve TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE,
    seance INTEGER, texte TEXT NOT NULL, cree TEXT, lu TEXT);
CREATE TABLE IF NOT EXISTS signalements (id INTEGER PRIMARY KEY AUTOINCREMENT, eleve TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE,
    seance INTEGER NOT NULL, indice INTEGER, texte TEXT, motif TEXT, auteur TEXT, cree TEXT);
CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY AUTOINCREMENT, classe TEXT NOT NULL REFERENCES classes(code) ON DELETE CASCADE,
    eleve TEXT, seance INTEGER, origine TEXT, avant TEXT, apres TEXT, cree TEXT);
CREATE TABLE IF NOT EXISTS reponses (eleve TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE, seance INTEGER NOT NULL, exercice INTEGER NOT NULL,
    tentatives INTEGER NOT NULL DEFAULT 0, score REAL, premier_score REAL, duree INTEGER, maj TEXT, PRIMARY KEY(eleve, seance, exercice));
CREATE TABLE IF NOT EXISTS banques (id INTEGER PRIMARY KEY AUTOINCREMENT, enseignant TEXT NOT NULL, nom TEXT NOT NULL,
    contenu TEXT NOT NULL, questions INTEGER NOT NULL DEFAULT 0, cree TEXT, maj TEXT, UNIQUE(enseignant, nom));
CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, classe TEXT NOT NULL REFERENCES classes(code) ON DELETE CASCADE,
    nom TEXT NOT NULL, contenu BLOB NOT NULL, texte TEXT NOT NULL DEFAULT '', taille INTEGER NOT NULL, cree TEXT);
"""


class Base:
    def __init__(self, chemin):
        self.chemin = chemin
        with self.cnx() as c:
            c.executescript(SCHEMA)
            colonnes = [r["name"] for r in c.execute("PRAGMA table_info(eleves)")]
            if "pin" not in colonnes:                       # bases créées avant le code personnel
                c.execute("ALTER TABLE eleves ADD COLUMN pin TEXT")
            if "preferences" not in colonnes:               # bases créées avant les préférences d'affichage
                c.execute("ALTER TABLE eleves ADD COLUMN preferences TEXT")
            col_rep = [r["name"] for r in c.execute("PRAGMA table_info(reponses)")]
            if "reponse" not in col_rep:                    # bases créées avant la correction
                c.execute("ALTER TABLE reponses ADD COLUMN reponse TEXT")
            if "explications" not in col_rep:               # bases créées avant les explications d'erreurs par l'IA
                c.execute("ALTER TABLE reponses ADD COLUMN explications INTEGER NOT NULL DEFAULT 0")
            if "enseignant" not in [r["name"] for r in c.execute("PRAGMA table_info(classes)")]:   # bases créées avant les comptes enseignants
                c.execute("ALTER TABLE classes ADD COLUMN enseignant INTEGER")
            col_ens = [r["name"] for r in c.execute("PRAGMA table_info(enseignants)")]
            if "valide" not in col_ens:                     # comptes créés avant la validation par l'administratrice : ils restent ouverts
                c.execute("ALTER TABLE enseignants ADD COLUMN valide INTEGER NOT NULL DEFAULT 0")
                c.execute("ALTER TABLE enseignants ADD COLUMN nom TEXT")
                c.execute("ALTER TABLE enseignants ADD COLUMN presentation TEXT")
                c.execute("UPDATE enseignants SET valide = 1 WHERE verifie = 1")
            if "enseignant" not in [r["name"] for r in c.execute("PRAGMA table_info(sessions_enseignant)")]:
                c.execute("ALTER TABLE sessions_enseignant ADD COLUMN enseignant INTEGER")
            for r in c.execute("SELECT id FROM eleves WHERE pin IS NULL").fetchall():
                c.execute("UPDATE eleves SET pin = ? WHERE id = ?", (nouveau_pin(), r["id"]))

    def cnx(self):
        c = sqlite3.connect(self.chemin, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def purger(self, jours):
        limite = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat(timespec="seconds")
        with VERROU, self.cnx() as c:
            c.execute("DELETE FROM traces WHERE maj < ?", (limite,))
            c.execute("DELETE FROM reponses WHERE maj < ?", (limite,))
            c.execute("DELETE FROM verifications WHERE maj < ?", (limite,))
            c.execute("DELETE FROM indices_vus WHERE maj < ?", (limite,))
            for table in ("messages", "signalements", "journal"):
                c.execute(f"DELETE FROM {table} WHERE cree < ?", (limite,))
            c.execute("DELETE FROM sessions_enseignant WHERE expire < ?", (time.time(),))
            c.execute("DELETE FROM jetons_mail WHERE expire < ?", (time.time(),))
            c.execute("DELETE FROM enseignants WHERE verifie = 0 AND cree < ?", (limite_inscription(),))   # inscriptions jamais confirmées


# ---------------------------------------------------------------- IA
PUBLICS = ("ecole", "college", "lycee", "superieur")
# à qui s'adresse l'IA : ton, vocabulaire et exigence de rigueur
DESTINATAIRE = {
    "ecole": "adaptées à un élève d'école élémentaire, avec des mots simples",
    "college": "adaptées à un élève de collège",
    "lycee": "adaptées à un élève de lycée",
    "superieur": ("adaptées à un étudiant de l'enseignement supérieur : vocabulaire précis de la discipline, exigence de rigueur "
                  "(hypothèses, justifications, sources, contre-exemples). S'il y a des formules, écris-les en texte simple lisible "
                  "sans LaTeX, par exemple √2, ∛2, ζ₅, Gal(K/Q), [K:Q], x³ − 2, ≅, ∈"),
}


CODE_TUTEUR = (" L'élève programme : ne donne JAMAIS de programme complet ni de fonction entière. Au plus une ligne de code, "
               "un nom de fonction ou de méthode à explorer, ou une question sur ce que fait une ligne précise. "
               "Fais-lui tester son code sur un petit exemple dont il connaît le résultat.")


def consignes_ia(mode, public="ecole", code=False, langue="fr"):
    pour = DESTINATAIRE.get(public, DESTINATAIRE["ecole"]) + ("." + CODE_TUTEUR if code else "")
    longueur = "Trois phrases au maximum" if public == "superieur" else "Deux phrases au maximum"
    if mode == "questionner":
        return ("Tu accompagnes un élève de façon socratique. Tu ne donnes JAMAIS la réponse, ni une liste d'idées, "
                "ni un exemple d'idée. Tu poses UNE seule question courte à la fois, qui l'aide à approfondir, justifier "
                "ou explorer une piste différente de celles qu'il a déjà ; ou tu proposes un contre-exemple. "
                f"{longueur}, {NOM_POUR_IA.get(langue, 'en français')}, {pour}.")
    return ("Tu aides un élève qui a besoin d'un coup de pouce. Tu donnes UN seul élément de réponse ou un exemple partiel, "
            "jamais une liste complète, puis tu poses une courte question pour qu'il continue seul. "
            f"{'Quatre' if public == 'superieur' else 'Trois'} phrases au maximum, {NOM_POUR_IA.get(langue, 'en français')}, {pour}.")


def consignes_explication(mode, public="ecole", langue="fr", fini=False, code=False):
    """Consignes pour expliquer une erreur d'exercice : ce qui ne va pas, la règle, puis réessayer (ou un cas semblable)."""
    pour = DESTINATAIRE.get(public, DESTINATAIRE["ecole"]) + ("." + CODE_TUTEUR if code else "")
    debut = ("Commence par UNE courte question qui l'aide à repérer lui-même son erreur. Ensuite, " if mode == "questionner" else "")
    fin = ("Montre en une phrase comment la règle mène à la bonne réponse, puis propose un petit cas semblable, différent de "
           "l'exercice, qu'il peut essayer seul (sans en donner la réponse)." if fini else
           "L'élève a encore un essai : ne donne JAMAIS la bonne réponse, ni directement, ni par un calcul ou un exemple qui y mène, "
           "et ne dis pas quel choix cocher. Termine en l'invitant à réessayer en appliquant la règle.")
    return ("Tu aides un élève qui s'est trompé à un exercice à comprendre son erreur. Tu t'appuies sur la bonne réponse donnée par "
            "l'enseignant et tu ne la contredis jamais ; si l'énoncé te semble ambigu, invite l'élève à en parler à son enseignant. "
            "Ne juge jamais l'élève : se tromper fait partie de l'apprentissage. "
            f"{debut}Dis ce qui ne va pas dans SA réponse, en partant de ce qu'il a écrit (la confusion probable). "
            "Puis énonce la règle, la notion ou la méthode en jeu, simplement, en une ou deux phrases. " + fin + " "
            f"{'Six' if public == 'superieur' else 'Cinq'} phrases au maximum, en texte simple, sans titre ni liste, "
            f"{NOM_POUR_IA.get(langue, 'en français')}, {pour}.")


def revele_reponse(texte, q):
    """Vrai si le texte de l'IA contient la bonne réponse d'un exercice à réponse courte, numérique ou à choix unique."""
    t = " " + re.sub(r"\s+", " ", unicodedata.normalize("NFC", texte or "")).lower() + " "
    bonnes = [r for r in q.get("reponses") or [] if r.get("fraction", 0) >= 1]
    if q.get("type") == "numerique":
        for r in bonnes:
            v = r["valeur"]
            formes = {f"{v:g}", f"{v:g}".replace(".", ",")} | ({str(int(v))} if float(v).is_integer() else set())
            if any(re.search(r"(?<![\d.,])" + re.escape(f) + r"(?![\d]|[.,]\d)", t) for f in formes):
                return True
    elif q.get("type") in ("reponse_courte", "choix_unique"):
        for r in bonnes:
            b = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(r.get("texte", "")))).lower().replace("*", "").strip()
            if len(b) >= 2 and re.search(r"(?<!\w)" + re.escape(b) + r"(?!\w)", t):
                return True
    return False


# Fournisseurs à API compatible OpenAI connus par leur nom : point d'accès et modèle par défaut
COMPATIBLES = {
    "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-2.0-flash"),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", "mistral-small-latest"),
    "ollama": ("http://127.0.0.1:11434/v1/chat/completions", "llama3.1"),
}
FOURNISSEURS = ("fausse", "anthropic") + tuple(COMPATIBLES)


def verifier_config_ia():
    """Message clair au démarrage plutôt qu'une erreur muette pendant la séance."""
    f = os.environ.get("VIABILIS_IA", "fausse")
    if f not in FOURNISSEURS:
        raise SystemExit(f"VIABILIS_IA={f} n'est pas reconnu. Valeurs possibles : {', '.join(FOURNISSEURS)}.")
    if f not in ("fausse", "ollama") and not os.environ.get("VIABILIS_IA_CLE"):
        raise SystemExit(f"VIABILIS_IA={f} demande une clé d'API : définissez VIABILIS_IA_CLE.")
    return f


def appeler_ia(systeme, tours, max_tokens=300, delai=60):
    fournisseur = os.environ.get("VIABILIS_IA", "fausse")
    if fournisseur == "fausse":
        if "[fuite]" in tours[-1]["content"]:          # IA factice : simule une IA qui donne une solution (pour tester le garde-fou)
            return "Facile : 5 + 5, et voilà !"
        return "Qu'est-ce qui te fait penser à cette idée ? Peux-tu en imaginer une toute différente ?"
    cle, modele = os.environ.get("VIABILIS_IA_CLE", ""), os.environ.get("VIABILIS_IA_MODELE", "")
    if fournisseur == "anthropic":
        url = os.environ.get("VIABILIS_IA_URL", "https://api.anthropic.com/v1/messages")
        corps = {"model": modele or "claude-haiku-4-5-20251001", "max_tokens": max_tokens, "system": systeme, "messages": tours}
        entetes = {"x-api-key": cle, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    else:  # API compatible OpenAI (OpenAI, Gemini, Mistral, Ollama, Albert, vLLM…)
        url_def, modele_def = COMPATIBLES.get(fournisseur, COMPATIBLES["ollama"])
        url = os.environ.get("VIABILIS_IA_URL", url_def)
        corps = {"model": modele or modele_def, "max_tokens": max_tokens, "messages": [{"role": "system", "content": systeme}] + tours}
        entetes = {"content-type": "application/json"}
        if cle:
            entetes["authorization"] = "Bearer " + cle
    req = urllib.request.Request(url, data=json.dumps(corps).encode(), headers=entetes, method="POST")
    with urllib.request.urlopen(req, timeout=delai) as r:
        rep = json.loads(r.read())
    if fournisseur == "anthropic":
        return "".join(b.get("text", "") for b in rep.get("content", []) if b.get("type") == "text").strip()
    texte = rep["choices"][0]["message"].get("content")
    if not texte:                                       # réponse vide (certains modèles ne renvoient que leur raisonnement)
        raise ValueError("réponse vide de l'IA")
    return texte.strip()


# ---------------------------------------------------------------- banques d'exercices (.gift)
EXEMPLES = os.path.join(RACINE, "exemples")


NIVEAUX = ("ecole", "college", "lycee", "superieur")


def banques_fournies():
    """Fichiers .gift fournis avec Viabilis (serveur/exemples/<niveau>/<matière>/<nom>.gift), par niveau, matière puis nom."""
    out = []
    for racine, dossiers, fichiers in os.walk(EXEMPLES):
        dossiers.sort()
        rel = os.path.relpath(racine, EXEMPLES).replace(os.sep, "/")
        out += [{"chemin": f"{rel}/{f}", "dossier": rel, "nom": f[:-5]} for f in sorted(fichiers) if f.endswith(".gift") and rel != "."]
    rang = lambda b: (NIVEAUX.index(b["dossier"].split("/")[0]) if b["dossier"].split("/")[0] in NIVEAUX else 9, b["chemin"])
    return sorted(out, key=rang)


def nom_banque(nom):
    """Nom de banque sûr : 80 caractères, sans « .gift » final ni caractères de chemin."""
    nom = re.sub(r"\.gift$", "", str(nom or "").strip(), flags=re.I)
    return re.sub(r"[\x00-\x1f/\\:*?\"<>|]", " ", nom).strip()[:80]


def verifier_gift(contenu, langue="fr"):
    """Questions reconnues dans un texte GIFT : nombre, titres, types et avertissements (pour l'éditeur de l'enseignant)."""
    if not contenu.strip():
        return {"questions": 0, "titres": [], "avertissements": []}
    questions, avert = EX.importer(contenu, "gift")
    return {"questions": len(questions), "titres": [f'{q["titre"][:80]} ({q["type"]})' for q in questions][:60],
            "avertissements": [traduire_texte(langue, a) for a in avert]}


# ---------------------------------------------------------------- séance préparée par l'IA à partir d'un document
CONSIGNE_BROUILLON = (
    "Tu es concepteur pédagogique. À partir du document fourni par l'enseignant, tu prépares UNE séance de travail pour Viabilis, "
    "une plateforme où chaque élève écrit ses propres idées sur une tâche ouverte, avec un tuteur IA qui ne donne pas les réponses. "
    "Public visé : {public}. {discipline}"
    "Règles. La tâche est ouverte : plusieurs idées, solutions, exemples ou démarches sont possibles, et elle se travaille en une séance. "
    "Elle s'appuie uniquement sur le contenu du document, sans inventer de faits, de chiffres ni de références qui n'y figurent pas. "
    "Elle demande de produire, justifier, comparer ou appliquer, pas de recopier le document. "
    "Les trois coups de pouce sont gradués, du plus léger au plus précis, et ne donnent jamais la réponse. "
    "La variante accessible guide davantage (étapes, exemple de départ) ; la variante exigeante va plus loin. "
    "Les critères de réussite servent à l'IA qui vérifiera les idées des élèves : ce qui rend une idée juste, les attendus tirés du document, "
    "les erreurs fréquentes à signaler. Écris tous les textes {langue}. "
    "Réponds uniquement par un objet JSON, sans autre texte, de cette forme : "
    '{{"titre": "…", "tache": "…", "indices": ["…", "…", "…"], "accessible": {{"consigne": "…", "indices": ["…", "…"]}}, '
    '"exigeante": {{"consigne": "…"}}, "criteres": "…", "niveauTache": 3}}. '
    "La tâche fait 1500 caractères au plus, les critères 1500 caractères au plus ; niveauTache va de 1 (très accessible) à 5 (très exigeant).")


def brouillon_seance(nom, texte, souhait, cfg):
    """Brouillon de séance (consigne, coups de pouce, variantes, critères) à partir du texte d'un document ; l'enseignant le relit."""
    langue = langue_valide(cfg.get("langue"))
    if os.environ.get("VIABILIS_IA", "fausse") == "fausse":        # IA factice (essais) : un brouillon simple, tiré du document
        debut = re.sub(r"\s+", " ", texte)[:160]
        return {"titre": nom, "tache": f"Lis le document « {nom} » ({debut}…). Propose le plus d'idées possible qui en appliquent le contenu, et justifie chacune.",
                "indices": ["Relis le titre et les intertitres.", "Choisis un passage et explique-le avec tes mots.", "Cherche un exemple qui n'est pas dans le document."],
                "variantes": {"actives": True, "accessible": {"consigne": f"Relève trois idées importantes du document « {nom} » et explique-les.", "indices": ["Commence par la première page."], "cible": None, "attendu": None},
                              "exigeante": {"consigne": f"Critique le document « {nom} » : une limite, une objection, un prolongement.", "indices": [], "cible": None, "attendu": None}},
                "verification": {"mode": "ia", "criteres": "Une idée est juste si elle s'appuie sur le document et qu'elle est justifiée.", "maximum": 3},
                "niveauTache": 3}
    disc = cfg.get("discipline") if cfg.get("discipline") not in ("", "*") else ""
    systeme = CONSIGNE_BROUILLON.format(public=DESTINATAIRE.get(cfg.get("public"), DESTINATAIRE["ecole"]).replace("adaptées à ", "", 1),
                                        discipline=f"Discipline : {disc}. " if disc else "", langue=NOM_POUR_IA.get(langue, "en français"))
    demande = f"Document « {nom} » :\n\n{texte[:40000]}"
    if souhait:
        demande += f"\n\nCe que l'enseignant attend de la séance : {souhait}"
    brut = appeler_ia(systeme, [{"role": "user", "content": demande}], max_tokens=2500, delai=180)
    debut, fin = brut.find("{"), brut.rfind("}")
    if debut < 0 or fin <= debut:
        raise ValueError("réponse sans objet JSON")
    d = json.loads(brut[debut:fin + 1])
    liste = lambda l, n: [str(x).strip()[:300] for x in (l or []) if str(x).strip()][:n]
    acc, exi = d.get("accessible") or {}, d.get("exigeante") or {}
    tache = str(d.get("tache") or "").strip()[:2000]
    if not tache:
        raise ValueError("brouillon sans consigne")
    try:
        niveau = min(5, max(1, int(d.get("niveauTache") or 3)))
    except (TypeError, ValueError):
        niveau = 3
    return {"titre": str(d.get("titre") or nom).strip()[:200], "tache": tache, "indices": liste(d.get("indices"), 3),
            "variantes": {"actives": bool(acc.get("consigne") or exi.get("consigne")),
                          "accessible": {"consigne": str(acc.get("consigne") or "").strip()[:2000], "indices": liste(acc.get("indices"), 3), "cible": None, "attendu": None},
                          "exigeante": {"consigne": str(exi.get("consigne") or "").strip()[:2000], "indices": liste(exi.get("indices"), 3), "cible": None, "attendu": None}},
            "verification": {"mode": "ia", "criteres": str(d.get("criteres") or "").strip()[:2000], "maximum": 3},
            "niveauTache": niveau}


# ---------------------------------------------------------------- utilitaires
def config_valide(cfg):
    """Ne garde que les champs connus, bornés : l'enseignant ne peut pas casser la configuration."""
    out = dict(DEFAUT_CONFIG)
    out["seance"] = max(0, int(cfg.get("seance", 0)))
    out["ouverte"] = bool(cfg.get("ouverte", False))
    out["tache"] = str(cfg.get("tache", ""))[:2000]
    out["public"] = cfg.get("public") if cfg.get("public") in PUBLICS else "ecole"
    out["discipline"] = str(cfg.get("discipline") or "")[:120]
    out["langue"] = langue_valide(cfg.get("langue"))
    out["visuels"] = bool(cfg.get("visuels", True))
    out["saisieCode"] = bool(cfg.get("saisieCode", False))
    out["evaluation"] = bool(cfg.get("evaluation", False))
    out["document"] = max(0, int(cfg.get("document") or 0)) if str(cfg.get("document") or 0).isdigit() else 0
    out["modele"] = str(cfg.get("modele") or "") if re.fullmatch(r"[a-z0-9\-]{0,64}", str(cfg.get("modele") or "")) else ""
    out["ordre"] = cfg.get("ordre") if cfg.get("ordre") in ORDRES else "adaptatif"
    out["mode"] = cfg.get("mode") if cfg.get("mode") in MODES else "questionner"
    out["minIdees"] = min(6, max(0, int(cfg.get("minIdees", 3))))
    for k, lo, hi in (("seuilCharge", 0.5, 0.85), ("retraitAgentivite", 0.4, 1.0), ("seuilMaitrise", 0.2, 0.9)):
        out[k] = min(hi, max(lo, float(cfg.get(k, DEFAUT_CONFIG[k]))))
    eleves = {}
    for eid, r in (cfg.get("eleves") or {}).items():
        if isinstance(r, dict):
            niv = r.get("niveau")
            eleves[str(eid)[:64]] = {"ordre": r.get("ordre") if r.get("ordre") in ORDRES else None,
                                    "mode": r.get("mode") if r.get("mode") in MODES else None,
                                    "retrait": bool(r.get("retrait", False)),
                                    "niveau": min(5, max(1, int(niv))) if niv not in (None, "") else None,
                                    "variante": r.get("variante") if r.get("variante") in VARIANTES else None,
                                    "palier": min(6, max(1, int(r["palier"]))) if r.get("palier") not in (None, "") else None}
    out["eleves"] = eleves
    out["niveauTache"] = min(5, max(1, int(cfg.get("niveauTache", 3))))
    indices = lambda l: [str(x).strip()[:300] for x in (l or []) if str(x).strip()][:3]
    nombre_ou_rien = lambda x: None if x in (None, "") else float(str(x).replace(",", "."))
    out["indices"] = indices(cfg.get("indices"))
    out["groupes"] = {str(k)[:64]: g for k, g in (cfg.get("groupes") or {}).items() if g in GROUPES}
    le = cfg.get("lecture") or {}
    out["lecture"] = {"active": bool(le.get("active", True)), "langue": le.get("langue") if le.get("langue") in LANGUES else "fr-FR",
                      "dictee": bool(le.get("dictee", False))}
    out["galerie"] = {str(int(k)): [str(t).strip()[:300] for t in v if str(t).strip()][:12]
                      for k, v in (cfg.get("galerie") or {}).items() if str(k).isdigit() and isinstance(v, list)}
    va = cfg.get("variantes") or {}
    out["variantes"] = {"actives": bool(va.get("actives", False))}
    for nom in ("accessible", "exigeante"):
        x = va.get(nom) or {}
        att = nombre_ou_rien(x.get("attendu"))
        out["variantes"][nom] = {"consigne": str(x.get("consigne", ""))[:2000], "indices": indices(x.get("indices")),
                                 "cible": nombre_ou_rien(x.get("cible")), "attendu": None if att is None else min(100, max(0, int(att)))}
    v = cfg.get("verification") or {}
    brut_nb = re.sub(r"(?<=\d),(?=\d)", ".", str(v.get("nombres", "")))           # 2,5 -> 2.5 ; « 1, 2, 5 » reste une liste
    nombres = [x for x in re.split(r"[;,\s]+", brut_nb) if re.fullmatch(r"-?\d+(\.\d+)?", x)]
    out["verification"] = {"mode": v.get("mode") if v.get("mode") in ("aucune", "calcul", "ia") else "aucune",
                           "cible": float(v.get("cible", 10) or 0), "nombres": " ; ".join(nombres)[:200],
                           "attendu": min(100, max(0, int(v.get("attendu", 0) or 0))), "criteres": str(v.get("criteres", ""))[:2000],
                           "maximum": min(10, max(1, int(v.get("maximum", 3) or 3))), "uneFois": bool(v.get("uneFois", False))}
    out["codePersonnel"] = bool(cfg.get("codePersonnel", False))
    ex = cfg.get("exercices") or {}
    out["exercices"] = {"actifs": bool(ex.get("actifs", False)), "nombre": min(20, max(1, int(ex.get("nombre", 3)))),
                        "placement": ex.get("placement") if ex.get("placement") in ("avant", "apres") else "avant",
                        "niveau": min(5, max(1, int(ex.get("niveau", 2)))),
                        "choix": ex.get("choix") if ex.get("choix") in ("niveau", "adaptatif") else "niveau",
                        "source": str(ex.get("source") or "")[:120], "explications": bool(ex.get("explications", True))}
    # séances ouvertes : compatibilité avec l'ancien réglage (une seule séance, « ouverte »)
    ouv = cfg.get("ouvertes")
    if ouv is None:
        ouv = [out["seance"]] if cfg.get("ouverte") and out["seance"] else []
    out["supprimees"] = sorted({int(x) for x in (cfg.get("supprimees") or []) if str(x).isdigit() and 1 <= int(x) <= out["seance"]})
    ouv = {int(x) for x in ouv if str(x).lstrip("-").isdigit() and 1 <= int(x) <= out["seance"]}
    if "ouverte" in cfg and out["seance"]:                 # « ouverte » pilote la dernière séance (anciens clients compris)
        (ouv.add if cfg.get("ouverte") else ouv.discard)(out["seance"])
    out["ouvertes"] = sorted(ouv - set(out["supprimees"]))
    out["ouverte"] = out["seance"] in out["ouvertes"]
    # archives : chaque séance garde sa tâche ; la dernière suit les réglages en cours
    out["archives"] = {}
    if cfg.get("archives") is not None:
        for k, v in (cfg.get("archives") or {}).items():
            if str(k).isdigit() and 1 <= int(k) <= out["seance"] and int(k) not in out["supprimees"] and isinstance(v, dict):
                out["archives"][str(int(k))] = instantane(config_valide({"lecture": out.get("lecture"), **v, "archives": None}))   # anciennes archives : lecture de la classe
    for n in out["ouvertes"]:
        out["archives"].setdefault(str(n), instantane(out))
    if out["seance"] and out["seance"] not in out["supprimees"]:
        out["archives"][str(out["seance"])] = instantane(out)
    return out


def nouveau_pin():
    """Code personnel à 4 chiffres, pour revenir sur n'importe quelle tablette."""
    return f"{secrets.randbelow(10000):04d}"


ECHECS = {}                      # (classe, pseudo) -> (nombre d'échecs, heure du dernier) : contre les essais au hasard


def historique_exercices(c, eleve):
    """Résultats de l'élève par niveau d'exercice, au premier essai, dans l'ordre chronologique (choix adaptatif)."""
    hist = {}
    for r in c.execute("""SELECT x.niveau, COALESCE(r.premier_score, r.score) AS s FROM reponses r JOIN exercices x ON x.id = r.exercice
                          WHERE r.eleve = ? AND COALESCE(r.premier_score, r.score) IS NOT NULL ORDER BY r.maj, r.seance""", (eleve,)):
        hist.setdefault(r["niveau"], []).append(float(r["s"]))
    return hist


def limite_inscription():
    """Une inscription non confirmée au bout de 7 jours est effacée."""
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")


def nouveau_code():
    return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


PSEUDO_OK = re.compile(r"^[\w \-'.]{1,24}$", re.UNICODE)


def instantane(cfg):
    return {k: json.loads(json.dumps(cfg.get(k, DEFAUT_CONFIG[k]))) for k in INSTANTANE}


def numero(cfg, n):
    """Numéro affiché d'une séance : son rang parmi les séances qui existent encore (l'identifiant n ne change jamais)."""
    return n - sum(1 for x in cfg.get("supprimees") or [] if x < n)


def ouvertes(cfg):
    if "ouvertes" in cfg:
        return list(cfg["ouvertes"])
    return [cfg["seance"]] if cfg.get("ouverte") and cfg.get("seance") else []


def config_pour_seance(cfg, n):
    """Réglages vus par l'élève pour la séance n : sa tâche archivée, et « ouverte » si elle l'est encore."""
    c = dict(cfg)
    c.update((cfg.get("archives") or {}).get(str(n), {}))
    c["seance"], c["ouverte"] = n, n in ouvertes(cfg)
    return c


def variante_eleve(cfg, perso, trace=None):
    """Variante de la tâche pour un élève : fixée au début de la séance, sinon son réglage individuel, sinon standard."""
    if not (cfg.get("variantes") or {}).get("actives"):
        return "standard"
    if trace and trace.get("variante") in VARIANTES:
        return trace["variante"]
    v = (perso or {}).get("variante") or "standard"
    # palier : niveau que l'élève a réussi. Si la nouvelle tâche est déjà plus difficile, elle suffit à le faire progresser :
    # on ne lui ajoute pas la variante exigeante (deux marches d'un coup).
    palier = (perso or {}).get("palier")
    if v == "exigeante" and palier and int(cfg.get("niveauTache") or 3) > palier:
        return "standard"
    return v


def tache_de(cfg, variante):
    """(consigne, coups de pouce, résultat attendu, nombre de solutions) de la variante ; ce qui manque vient de la tâche standard."""
    v = cfg.get("verification") or DEFAUT_CONFIG["verification"]
    std = (cfg.get("tache", ""), cfg.get("indices") or [], v.get("cible"), v.get("attendu") or None)
    if variante == "standard":
        return std
    x = ((cfg.get("variantes") or {}).get(variante)) or {}
    return (x.get("consigne") or std[0], x.get("indices") or std[1],
            x.get("cible") if x.get("cible") is not None else std[2], x.get("attendu") if x.get("attendu") is not None else std[3])


def ordre_effectif(cfg, perso, charge_debut):
    """Ordre et rôle de l'IA pour un élève, décidés par le serveur (l'élève ne peut pas les choisir)."""
    if HORS_LIGNE or cfg.get("evaluation"):          # hors ligne ou évaluation : pas d'IA, l'étudiant travaille en autonomie
        return "autonomie", cfg["mode"]
    if perso.get("retrait"):
        return "autonomie", perso.get("mode") or cfg["mode"]
    ordre, mode = perso.get("ordre") or cfg["ordre"], perso.get("mode") or cfg["mode"]
    if ordre == "adaptatif":
        surcharge = charge_debut is not None and 0.1 + 0.2 * (int(charge_debut) - 1) >= cfg["seuilCharge"]
        ordre = "ia" if surcharge else "reflexion"
        if not perso.get("mode"):
            mode = "elements" if surcharge else "questionner"
    return ordre, mode


# ---------------------------------------------------------------- serveur HTTP
class Gestionnaire(SimpleHTTPRequestHandler):
    base: Base = None
    mdp_hash: bytes = b""
    sel: bytes = b""
    # types fixés ici : sous Windows, le registre peut annoncer les .js en text/plain et le navigateur refuse alors de les exécuter
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".css": "text/css", ".html": "text/html",
                      ".json": "application/json", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml", ".png": "image/png"}

    def __init__(self, *a, **k):
        super().__init__(*a, directory=STATIQUE, **k)

    def log_message(self, fmt, *args):  # pas de données d'élèves dans les journaux
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")      # le navigateur vérifie à chaque chargement : une mise à jour se voit tout de suite
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        super().end_headers()

    # -- réponses
    def json(self, statut, obj):
        corps = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(statut)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def erreur(self, statut, message, **valeurs):
        self.json(statut, {"erreur": T(self.langue(), message, **valeurs)})

    def langue(self):
        """Langue de l'interface qui fait la requête (en-tête envoyé par les pages élève et enseignant)."""
        return langue_valide(self.headers.get("X-Viabilis-Langue", "")[:2])

    def corps(self, limite=TAILLE_MAX):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limite:
            raise ValueError("requête trop volumineuse")
        return json.loads(self.rfile.read(n) or b"{}")

    def jeton(self):
        h = self.headers.get("Authorization", "")
        return h[7:] if h.startswith("Bearer ") else ""

    def enseignant(self):
        """Identifiant de l'enseignant connecté ("*" sans comptes : toutes les classes), ou None."""
        with self.base.cnx() as c:
            r = c.execute("SELECT expire, enseignant FROM sessions_enseignant WHERE jeton = ?", (self.jeton(),)).fetchone()
        if not r or r["expire"] <= time.time():
            return None
        if not CPT.actif():
            return "*"
        return r["enseignant"]          # une session d'avant les comptes (sans enseignant) ne vaut plus rien

    def ip(self):
        """Adresse du visiteur ; derrière Apache (même machine), celle que transmet le mandataire."""
        if self.client_address[0] in ("127.0.0.1", "::1") and self.headers.get("X-Forwarded-For"):
            return self.headers["X-Forwarded-For"].split(",")[-1].strip()
        return self.client_address[0]

    def eleve(self):
        j = self.jeton()
        if not j:
            return None
        with self.base.cnx() as c:
            return c.execute("SELECT * FROM eleves WHERE jeton = ?", (j,)).fetchone()

    def classe(self, code):
        with self.base.cnx() as c:
            return c.execute("SELECT * FROM classes WHERE code = ?", (code,)).fetchone()

    # -- routage
    def do_GET(self):
        chemin = urlparse(self.path).path
        self.requete = parse_qs(urlparse(self.path).query)
        if chemin.startswith("/api/"):
            return self.api("GET", chemin)
        if chemin in ("/", "") or HORS_LIGNE and chemin.startswith("/enseignant"):   # hors ligne : pas de page enseignant
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/eleve/")
            return self.end_headers()
        return super().do_GET()

    def do_POST(self):
        self.requete = parse_qs(urlparse(self.path).query)
        self.api("POST", urlparse(self.path).path)

    def do_PUT(self):
        self.requete = parse_qs(urlparse(self.path).query)
        self.api("PUT", urlparse(self.path).path)

    def do_DELETE(self):
        self.requete = parse_qs(urlparse(self.path).query)
        self.api("DELETE", urlparse(self.path).path)

    def api(self, verbe, chemin):
        try:
            p = chemin.strip("/").split("/")[1:]
            if p == ["hors-ligne"] and verbe == "GET":            # la page élève préremplit le code de la classe du kit
                return self.json(200, HORS_LIGNE) if HORS_LIGNE else self.erreur(404, "Ce serveur n'est pas en mode hors ligne.")
            if HORS_LIGNE and p and p[0] in ("enseignant", "classes"):
                return self.erreur(403, "Mode hors ligne : la page enseignant n'est pas disponible sur cet ordinateur.")
            # ---------- enseignant
            if p and p[0] == "enseignant" and CPT.actif():
                return self.api_comptes(verbe, p[1:])
            if p == ["enseignant", "mode"] and verbe == "GET":
                return self.json(200, {"comptes": False})
            if p == ["enseignant", "connexion"] and verbe == "POST":
                mdp = str(self.corps().get("motdepasse", "")).encode()
                essai = hashlib.pbkdf2_hmac("sha256", mdp, self.sel, 200_000)
                if not hmac.compare_digest(essai, self.mdp_hash):
                    time.sleep(1)
                    return self.erreur(401, "Mot de passe incorrect.")
                j = secrets.token_urlsafe(32)
                with VERROU, self.base.cnx() as c:
                    c.execute("INSERT INTO sessions_enseignant (jeton, expire) VALUES (?, ?)", (j, time.time() + 12 * 3600))
                return self.json(200, {"jeton": j})
            if p and p[0] == "banques":
                ens = self.enseignant()
                if ens is None:
                    return self.erreur(401, "Session enseignant requise.")
                return self.api_banques(verbe, p[1:], str(ens))
            if p and p[0] == "classes":
                ens = self.enseignant()
                if ens is None:
                    return self.erreur(401, "Session enseignant requise.")
                return self.api_classes(verbe, p[1:], ens)
            # ---------- élève
            if p == ["eleve", "classe"] and verbe == "POST":           # pseudonymes déjà créés, pour se reconnecter
                code = str(self.corps().get("code", "")).strip().upper()
                cl = self.classe(code)
                if not cl:
                    time.sleep(0.5)
                    return self.erreur(404, "Code de classe inconnu.")
                with self.base.cnx() as c:
                    pseudos = [r["pseudo"] for r in c.execute("SELECT pseudo FROM eleves WHERE classe = ? ORDER BY lower(pseudo)", (code,)).fetchall()]
                cfgc = json.loads(cl["config"])
                return self.json(200, {"nom": cl["nom"], "pseudos": pseudos, "codePersonnel": bool(cfgc.get("codePersonnel", False)),
                                       "langue": langue_valide(cfgc.get("langue"))})
            if p == ["eleve", "connexion"] and verbe == "POST":
                d = self.corps()
                code, pseudo = str(d.get("code", "")).strip().upper(), str(d.get("pseudo", "")).strip()
                if not self.classe(code):
                    return self.erreur(404, "Code de classe inconnu.")
                if not PSEUDO_OK.match(pseudo):
                    return self.erreur(400, "Pseudonyme : 1 à 24 lettres, chiffres ou espaces.")
                pin = re.sub(r"\D", "", str(d.get("pin", "")))[:4]
                cle = (code, pseudo.lower())
                with VERROU, self.base.cnx() as c:
                    deja = c.execute("SELECT * FROM eleves WHERE classe = ? AND lower(pseudo) = lower(?)", (code, pseudo)).fetchone()
                    exiger = bool(json.loads(self.classe(code)["config"]).get("codePersonnel", False))
                    if deja and d.get("nouveau"):            # création demandée avec un pseudonyme déjà pris
                        return self.erreur(409, "Ce pseudonyme existe déjà. Si c'est le vôtre, touchez-le dans la liste ; sinon, choisissez-en un autre.")
                    if deja and not exiger:                  # retour d'un élève : il choisit son pseudonyme dans la liste
                        j = secrets.token_urlsafe(32)
                        c.execute("UPDATE eleves SET jeton = ? WHERE id = ?", (j, deja["id"]))
                        return self.json(200, {"jeton": j, "id": deja["id"], "pseudo": deja["pseudo"], "pin": deja["pin"], "retour": True})
                    if deja:                                 # code personnel exigé par l'enseignant
                        n, t = ECHECS.get(cle, (0, 0))
                        if n >= 5 and time.time() - t < 600:
                            return self.erreur(429, "Trop d'essais : demandez votre code personnel à votre enseignant.")
                        if not pin:
                            return self.erreur(409, "Ce pseudonyme existe déjà. Si c'est le vôtre, entrez votre code personnel ; sinon, choisissez-en un autre.")
                        if not hmac.compare_digest(pin, deja["pin"] or ""):
                            ECHECS[cle] = (n + 1, time.time())
                            return self.erreur(401, "Code personnel incorrect.")
                        ECHECS.pop(cle, None)
                        j = secrets.token_urlsafe(32)        # nouvelle connexion : l'ancienne tablette est déconnectée
                        c.execute("UPDATE eleves SET jeton = ? WHERE id = ?", (j, deja["id"]))
                        return self.json(200, {"jeton": j, "id": deja["id"], "pseudo": deja["pseudo"], "pin": deja["pin"], "retour": True})
                    eid, j, pin = "e" + secrets.token_hex(8), secrets.token_urlsafe(32), nouveau_pin()
                    c.execute("INSERT INTO eleves (id, classe, pseudo, jeton, cree, pin) VALUES (?, ?, ?, ?, ?, ?)", (eid, code, pseudo, j, maintenant(), pin))
                return self.json(200, {"jeton": j, "id": eid, "pseudo": pseudo, "pin": pin, "retour": False})
            if p and p[0] == "eleve":
                e = self.eleve()
                if not e:
                    return self.erreur(401, "Reconnectez-vous avec le code de la classe.")
                return self.api_eleve(verbe, p[1:], e)
            return self.erreur(404, "Ressource inconnue.")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self.erreur(400, "Requête invalide : {exc}", exc=exc)

    # ---------------------------------------------------------------- comptes enseignants (mail confirmé + mot de passe)
    def api_comptes(self, verbe, p):
        lg = self.langue()
        if p == ["mode"] and verbe == "GET":
            return self.json(200, {"comptes": True, "domaines": CPT.domaines(), "validation": bool(CPT.admin())})
        if p and p[0] == "comptes":                        # administration des comptes (administratrice seulement)
            return self.api_admin(verbe, p[1:])
        if verbe != "POST":
            return self.erreur(404, "Ressource inconnue.")
        d = self.corps()
        envoye = T(lg, "Si cette adresse peut recevoir un compte, un mail vient de lui être envoyé. Pensez à regarder dans les indésirables.")
        if p == ["inscription"]:
            email, mdp = CPT.email_valide(d.get("email")), str(d.get("motdepasse", ""))
            nom, presentation = str(d.get("nom", "")).strip()[:80], str(d.get("presentation", "")).strip()[:500]
            if CPT.admin() and email != CPT.admin() and not nom:
                return self.erreur(400, "Indiquez votre nom : l'administratrice en a besoin pour valider votre demande.")
            if not email:
                return self.erreur(400, "Adresse refusée : seules les adresses {domaines} peuvent créer un compte.",
                                   domaines=", ".join("@" + x for x in CPT.domaines()))
            if len(mdp) < 10:
                return self.erreur(400, "Le mot de passe doit faire au moins 10 caractères.")
            if CPT.trop_d_essais("mail:" + self.ip(), 40, 3600) or CPT.trop_d_essais("mail:" + email, 3, 3600):
                return self.erreur(429, "Trop de demandes : réessayez dans une heure.")
            with VERROU, self.base.cnx() as c:
                r = c.execute("SELECT * FROM enseignants WHERE email = ?", (email,)).fetchone()
                if r and r["verifie"]:              # compte existant : on le dit seulement au propriétaire de l'adresse
                    j = CPT.nouveau_jeton(c, r["id"], "reinitialisation")
                    sujet, texte = T(lg, "Viabilis : vous avez déjà un compte"), T(lg, "MAIL_DEJA", lien=f"{self.adresse}/enseignant/?reinitialiser={j}")
                else:
                    if r:
                        c.execute("UPDATE enseignants SET hash = ?, nom = ?, presentation = ? WHERE id = ?", (CPT.hacher(mdp), nom, presentation, r["id"]))
                        eid = r["id"]
                    else:
                        eid = c.execute("INSERT INTO enseignants (email, hash, cree, nom, presentation) VALUES (?, ?, ?, ?, ?)",
                                        (email, CPT.hacher(mdp), maintenant(), nom, presentation)).lastrowid
                    j = CPT.nouveau_jeton(c, eid, "confirmation")
                    sujet, texte = T(lg, "Viabilis : confirmez votre adresse"), T(lg, "MAIL_CONFIRMER", lien=f"{self.adresse}/enseignant/?confirmer={j}")
            CPT.envoyer(email, sujet, texte)
            return self.json(200, {"message": envoye})
        if p == ["confirmer"]:
            with VERROU, self.base.cnx() as c:
                eid = CPT.utiliser_jeton(c, d.get("jeton"), "confirmation")
                if eid is None:
                    return self.erreur(400, "Ce lien n'est plus valable. Recommencez l'inscription pour en recevoir un nouveau.")
                c.execute("UPDATE enseignants SET verifie = 1 WHERE id = ?", (eid,))
                r = c.execute("SELECT * FROM enseignants WHERE id = ?", (eid,)).fetchone()
                attente = bool(CPT.admin()) and r["email"] != CPT.admin() and not r["valide"]
                if not attente:
                    c.execute("UPDATE enseignants SET valide = 1 WHERE id = ?", (eid,))
                self.reprendre_classes(c, eid)
            if attente:                                    # l'administratrice reçoit la demande ; elle décide depuis sa page enseignant
                for dest in CPT.destinataires_demandes():
                    CPT.envoyer(dest, f"Viabilis : demande de compte de {r['nom'] or r['email']}",
                                T("fr", "MAIL_DEMANDE", nom=r["nom"] or "(sans nom)", email=r["email"], presentation=r["presentation"] or "(aucune)",
                                  lien=f"{self.adresse}/enseignant/"))
                return self.json(200, {"message": T(lg, "Adresse confirmée. Votre demande est transmise à l'administratrice : vous recevrez un mail dès qu'elle l'aura validée.")})
            return self.json(200, {"message": T(lg, "Adresse confirmée. Vous pouvez vous connecter.")})
        if p == ["connexion"]:
            email, mdp = str(d.get("email", "")).strip().lower()[:254], str(d.get("motdepasse", ""))
            # seuls les échecs comptent ; une même adresse de réseau (université, box) sert à beaucoup de personnes
            if CPT.bloque("cnx:" + self.ip(), 50, 900) or CPT.bloque("cnx:" + email, 8, 900):
                return self.erreur(429, "Trop d'essais : attendez un quart d'heure, ou utilisez « Mot de passe oublié ».")
            with self.base.cnx() as c:
                r = c.execute("SELECT * FROM enseignants WHERE email = ?", (email,)).fetchone()
            if not CPT.verifier(mdp, r["hash"] if r else None):
                CPT.noter_echec("cnx:" + self.ip()); CPT.noter_echec("cnx:" + email)
                time.sleep(1)
                return self.erreur(401, "Adresse ou mot de passe incorrect.")
            if not r["verifie"]:
                return self.erreur(403, "Confirmez d'abord votre adresse : ouvrez le lien reçu par mail.")
            if not r["valide"]:
                return self.erreur(403, "Votre demande de compte attend la validation de l'administratrice : vous recevrez un mail.")
            CPT.oublier_essais("cnx:" + email)
            j = secrets.token_urlsafe(32)
            with VERROU, self.base.cnx() as c:
                c.execute("INSERT INTO sessions_enseignant (jeton, expire, enseignant) VALUES (?, ?, ?)", (j, time.time() + 12 * 3600, r["id"]))
                self.reprendre_classes(c, r["id"])
            return self.json(200, {"jeton": j, "email": r["email"], "admin": bool(CPT.admin()) and r["email"] == CPT.admin()})
        if p == ["oubli"]:
            email = str(d.get("email", "")).strip().lower()[:254]
            if CPT.trop_d_essais("mail:" + self.ip(), 40, 3600) or CPT.trop_d_essais("mail:" + email, 3, 3600):
                return self.erreur(429, "Trop de demandes : réessayez dans une heure.")
            with VERROU, self.base.cnx() as c:
                r = c.execute("SELECT * FROM enseignants WHERE email = ? AND verifie = 1", (email,)).fetchone()
                j = CPT.nouveau_jeton(c, r["id"], "reinitialisation") if r else None
            if j:
                CPT.envoyer(email, T(lg, "Viabilis : nouveau mot de passe"), T(lg, "MAIL_OUBLI", lien=f"{self.adresse}/enseignant/?reinitialiser={j}"))
            return self.json(200, {"message": envoye})
        if p == ["reinitialiser"]:
            mdp = str(d.get("motdepasse", ""))
            if len(mdp) < 10:
                return self.erreur(400, "Le mot de passe doit faire au moins 10 caractères.")
            with VERROU, self.base.cnx() as c:
                eid = CPT.utiliser_jeton(c, d.get("jeton"), "reinitialisation")
                if eid is None:
                    return self.erreur(400, "Ce lien n'est plus valable. Demandez-en un nouveau avec « Mot de passe oublié ».")
                c.execute("UPDATE enseignants SET hash = ?, verifie = 1 WHERE id = ?", (CPT.hacher(mdp), eid))   # le lien prouve l'adresse
                c.execute("DELETE FROM sessions_enseignant WHERE enseignant = ?", (eid,))                  # les autres appareils sont déconnectés
                self.reprendre_classes(c, eid)
            return self.json(200, {"message": T(lg, "Mot de passe changé. Vous pouvez vous connecter.")})
        if p == ["deconnexion"]:
            with VERROU, self.base.cnx() as c:
                c.execute("DELETE FROM sessions_enseignant WHERE jeton = ?", (self.jeton(),))
            return self.json(200, {})
        return self.erreur(404, "Ressource inconnue.")

    def reprendre_classes(self, c, eid):
        """Les classes créées avant les comptes reviennent au compte désigné par VIABILIS_PROPRIETAIRE."""
        proprio = (os.environ.get("VIABILIS_PROPRIETAIRE") or CPT.admin()).strip().lower()
        if proprio and c.execute("SELECT 1 FROM enseignants WHERE id = ? AND email = ? AND verifie = 1", (eid, proprio)).fetchone():
            n = c.execute("UPDATE classes SET enseignant = ? WHERE enseignant IS NULL", (eid,)).rowcount
            if n:
                print(f"[COMPTES] {n} classe(s) existante(s) rattachée(s) au compte {proprio}", flush=True)

    def api_admin(self, verbe, p):
        """Demandes de compte et comptes ouverts : l'administratrice (VIABILIS_ADMIN) valide, refuse ou suspend."""
        ens = self.enseignant()
        with self.base.cnx() as c:
            moi = c.execute("SELECT email FROM enseignants WHERE id = ?", (ens,)).fetchone() if ens not in (None, "*") else None
        if not moi or not CPT.admin() or moi["email"] != CPT.admin():
            return self.erreur(403, "Réservé à l'administratrice.")
        if p == [] and verbe == "GET":
            with self.base.cnx() as c:
                rows = c.execute("""SELECT e.id, e.email, e.nom, e.presentation, e.cree, e.valide, e.verifie,
                                    (SELECT count(*) FROM classes k WHERE k.enseignant = e.id) AS classes
                                    FROM enseignants e WHERE e.verifie = 1 ORDER BY e.valide, e.cree DESC""").fetchall()
            return self.json(200, [dict(r) for r in rows])
        if len(p) == 2 and p[0].isdigit() and p[1] in ("valider", "refuser", "suspendre") and verbe == "POST":
            with VERROU, self.base.cnx() as c:
                r = c.execute("SELECT * FROM enseignants WHERE id = ?", (int(p[0]),)).fetchone()
                if not r or r["email"] == CPT.admin():
                    return self.erreur(404, "Compte inconnu.")
                lg = "fr"
                if p[1] == "valider":
                    c.execute("UPDATE enseignants SET valide = 1 WHERE id = ?", (r["id"],))
                    mail = ("Viabilis : votre compte est ouvert", "MAIL_VALIDE")
                elif p[1] == "suspendre":
                    c.execute("UPDATE enseignants SET valide = 0 WHERE id = ?", (r["id"],))
                    c.execute("DELETE FROM sessions_enseignant WHERE enseignant = ?", (r["id"],))
                    mail = None
                else:                                    # refus d'une demande : le compte est effacé (pas une classe ouverte)
                    if r["valide"] or c.execute("SELECT 1 FROM classes WHERE enseignant = ?", (r["id"],)).fetchone():
                        return self.erreur(409, "Ce compte a déjà servi : suspendez-le plutôt.")
                    c.execute("DELETE FROM enseignants WHERE id = ?", (r["id"],))
                    mail = ("Viabilis : votre demande de compte", "MAIL_REFUSE")
            if mail:
                CPT.envoyer(r["email"], T(lg, mail[0]), T(lg, mail[1], lien=f"{self.adresse}/enseignant/"))
            return self.json(200, {"fait": p[1]})
        return self.erreur(404, "Ressource inconnue.")

    def api_classes(self, verbe, p, ens):
        """Routes de l'enseignant `ens` : il ne voit et ne modifie que ses classes ("*" : toutes, mode sans comptes)."""
        if not p:
            if verbe == "GET":
                with self.base.cnx() as c:
                    rows = c.execute("SELECT code, nom, cree FROM classes WHERE ? = '*' OR enseignant = ? ORDER BY cree DESC", (str(ens), ens)).fetchall()
                return self.json(200, [dict(r) for r in rows])
            if verbe == "POST":
                d = self.corps()
                nom = str(d.get("nom", "")).strip()[:80] or "Ma classe"
                with VERROU, self.base.cnx() as c:
                    code = nouveau_code()
                    while c.execute("SELECT 1 FROM classes WHERE code = ?", (code,)).fetchone():
                        code = nouveau_code()
                    c.execute("INSERT INTO classes (code, nom, config, cree, enseignant) VALUES (?, ?, ?, ?, ?)",
                              (code, nom, json.dumps({**DEFAUT_CONFIG, "langue": langue_valide(d.get("langue"))}), maintenant(), None if ens == "*" else ens))
                return self.json(201, {"code": code, "nom": nom})
        code = p[0]
        cl = self.classe(code)
        if not cl or ens != "*" and cl["enseignant"] != ens:      # la classe d'un collègue n'existe pas pour cet enseignant
            return self.erreur(404, "Classe inconnue.")
        rest = p[1:]
        if rest == [] and verbe == "DELETE":   # droit à l'effacement : toute la classe et ses traces
            with VERROU, self.base.cnx() as c:
                c.execute("DELETE FROM classes WHERE code = ?", (code,))
            return self.json(200, {"supprime": code})
        if rest == ["config"]:
            if verbe == "GET":                             # normalisée : les classes plus anciennes reçoivent les nouveaux champs
                return self.json(200, config_valide(json.loads(cl["config"])))
            if verbe == "PUT":
                corps = self.corps(TAILLE_MAX_CONFIG)
                cfg, ancien = config_valide(corps), config_valide(json.loads(cl["config"]))
                origine = corps.get("origine") if corps.get("origine") in ORIGINES else "manuel"
                with VERROU, self.base.cnx() as c:
                    c.execute("UPDATE classes SET config = ? WHERE code = ?", (json.dumps(cfg), code))
                    for eid in set(cfg["eleves"]) | set(ancien["eleves"]):    # journal : chaque réglage d'élève modifié
                        av = {**ancien["eleves"].get(eid, {}), "groupe": ancien["groupes"].get(eid)}
                        ap = {**cfg["eleves"].get(eid, {}), "groupe": cfg["groupes"].get(eid)}
                        if av != ap:
                            c.execute("INSERT INTO journal (classe, eleve, seance, origine, avant, apres, cree) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                      (code, eid, cfg["seance"], origine, json.dumps(av), json.dumps(ap), maintenant()))
                return self.json(200, cfg)
        if rest == ["notes"]:
            if verbe == "GET":
                return self.json(200, json.loads(cl["notes"]))
            if verbe == "PUT":
                notes = self.corps()
                with VERROU, self.base.cnx() as c:
                    c.execute("UPDATE classes SET notes = ? WHERE code = ?", (json.dumps(notes), code))
                return self.json(200, notes)
        if rest == ["traces"] and verbe == "GET":
            return self.json(200, self.traces_classe(code))
        if len(rest) == 5 and rest[0] == "eleves" and rest[2] == "seances" and rest[3].isdigit() and rest[4] == "rouvrir" and verbe == "POST":
            with VERROU, self.base.cnx() as c:              # l'élève pourra de nouveau modifier ou reprendre sa séance
                t = c.execute("SELECT t.donnees FROM traces t JOIN eleves e ON e.id = t.eleve WHERE t.eleve = ? AND t.seance = ? AND e.classe = ?",
                              (rest[1], int(rest[3]), code)).fetchone()
                if not t:
                    return self.erreur(404, "Séance introuvable pour cet élève.")
                d = json.loads(t["donnees"])
                d.pop("definitif", None)
                d.pop("correction", None)
                c.execute("UPDATE traces SET donnees = ? WHERE eleve = ? AND seance = ?", (json.dumps(d, ensure_ascii=False), rest[1], int(rest[3])))
            return self.json(200, {"ok": True})
        if len(rest) == 2 and rest[0] == "eleves" and verbe == "DELETE":   # effacement d'un élève
            with VERROU, self.base.cnx() as c:
                c.execute("DELETE FROM eleves WHERE id = ? AND classe = ?", (rest[1], code))
            return self.json(200, {"supprime": rest[1]})
        if len(rest) == 2 and rest[0] == "seances" and rest[1].isdigit() and verbe == "DELETE":
            return self.effacer_seance(code, cl, int(rest[1]))
        if rest == ["export.csv"] and verbe == "GET":
            return self.export(code)
        if rest == ["echanges_ia.csv"] and verbe == "GET":
            return self.export_echanges(code)
        if rest == ["journal.csv"] and verbe == "GET":
            return self.export_journal(code)
        if rest and rest[0] == "messages":
            return self.api_messages(verbe, code, rest[1:])
        if rest == ["signalements"]:
            return self.api_signalements(verbe, code)
        if rest and rest[0] == "exercices":
            return self.api_exercices(verbe, code, rest[1:])
        if rest and rest[0] == "documents":
            return self.api_documents(verbe, code, cl, rest[1:])
        if rest == ["viabilite"] and verbe == "POST":
            return self.viabilite()
        if rest == ["kit"] and verbe == "GET":                   # mode hors ligne : séances et exercices pour la clé USB
            with self.base.cnx() as c:
                exos = c.execute("SELECT * FROM exercices WHERE classe = ? ORDER BY id", (code,)).fetchall()
            toutes = (getattr(self, "requete", {}).get("toutes") or ["1"])[0] != "0"
            return self.json(200, HL.preparer_kit(cl, config_valide(json.loads(cl["config"])), exos, maintenant, toutes))
        if rest == ["import-eleve"] and verbe == "POST":         # travail hors ligne d'un étudiant
            d = self.corps(TAILLE_MAX_TRAVAIL)
            try:
                with VERROU, self.base.cnx() as c:
                    res = HL.importer(c, code, config_valide(json.loads(cl["config"])), d.get("travail"), bool(d.get("fusionner")),
                                      maintenant, nouveau_pin, PSEUDO_OK)
            except (ValueError, KeyError, TypeError) as exc:
                return self.erreur(400, "Import impossible : {exc}.", exc=exc)
            return self.json(200, res)
        return self.erreur(404, "Ressource inconnue.")

    # -- banques d'exercices (.gift) : celles fournies avec Viabilis, et la bibliothèque de chaque enseignant
    def api_banques(self, verbe, p, ens):
        """Bibliothèque de l'enseignant `ens` ("*" sans comptes) : lister, lire, vérifier, enregistrer sous un nom, effacer."""
        if p == [] and verbe == "GET":
            with self.base.cnx() as c:
                mes = [dict(r) for r in c.execute("SELECT id, nom, questions, maj FROM banques WHERE enseignant = ? ORDER BY nom COLLATE NOCASE", (ens,))]
            return self.json(200, {"mes": mes, "fournies": banques_fournies()})
        if p == ["fournie"] and verbe == "GET":
            chemin = (getattr(self, "requete", {}).get("chemin") or [""])[0]
            if chemin not in {b["chemin"] for b in banques_fournies()}:
                return self.erreur(404, "Banque introuvable.")
            with open(os.path.join(EXEMPLES, *chemin.split("/")), encoding="utf-8") as f:
                return self.json(200, {"nom": chemin.split("/")[-1][:-5], "contenu": f.read()})
        if p == ["verifier"] and verbe == "POST":
            return self.json(200, verifier_gift(str(self.corps().get("contenu", "")), self.langue()))
        if p == [] and verbe == "POST" or len(p) == 1 and p[0].isdigit() and verbe == "PUT":
            d = self.corps()
            nom = nom_banque(d.get("nom"))
            if not nom:
                return self.erreur(400, "Donnez un nom à la banque.")
            res = verifier_gift(str(d.get("contenu", "")), self.langue())
            if not res["questions"]:
                return self.erreur(400, "Aucune question reconnue : vérifiez le format GIFT.")
            with VERROU, self.base.cnx() as c:
                autre = c.execute("SELECT id FROM banques WHERE enseignant = ? AND nom = ?", (ens, nom)).fetchone()
                if verbe == "POST":
                    if autre:
                        return self.erreur(409, "Une de vos banques porte déjà ce nom : choisissez-en un autre.")
                    ident = c.execute("INSERT INTO banques (enseignant, nom, contenu, questions, cree, maj) VALUES (?, ?, ?, ?, ?, ?)",
                                      (ens, nom, d["contenu"], res["questions"], maintenant(), maintenant())).lastrowid
                else:
                    ident = int(p[0])
                    if autre and autre["id"] != ident:
                        return self.erreur(409, "Une de vos banques porte déjà ce nom : choisissez-en un autre.")
                    if not c.execute("UPDATE banques SET nom = ?, contenu = ?, questions = ?, maj = ? WHERE id = ? AND enseignant = ?",
                                     (nom, d["contenu"], res["questions"], maintenant(), ident, ens)).rowcount:
                        return self.erreur(404, "Banque introuvable.")
            return self.json(201 if verbe == "POST" else 200, {"id": ident, "nom": nom, **res})
        if len(p) == 1 and p[0].isdigit():
            with VERROU, self.base.cnx() as c:
                if verbe == "GET":
                    r = c.execute("SELECT id, nom, contenu, questions, maj FROM banques WHERE id = ? AND enseignant = ?", (int(p[0]), ens)).fetchone()
                    return self.json(200, dict(r)) if r else self.erreur(404, "Banque introuvable.")
                if verbe == "DELETE":
                    c.execute("DELETE FROM banques WHERE id = ? AND enseignant = ?", (int(p[0]), ens))
                    return self.json(200, {"supprime": int(p[0])})
        return self.erreur(404, "Ressource inconnue.")

    # -- documents PDF des séances
    def nom_document(self, classe, ident):
        """{id, nom} du document d'une séance, ou None."""
        if not ident:
            return None
        with self.base.cnx() as c:
            r = c.execute("SELECT id, nom FROM documents WHERE id = ? AND classe = ?", (ident, classe)).fetchone()
        return {"id": r["id"], "nom": r["nom"]} if r else None

    def envoyer_pdf(self, nom, contenu):
        nom_ascii = re.sub(r"[^\w.\- ]", "_", nom.encode("ascii", "replace").decode())[:120] or "document.pdf"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{nom_ascii}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(contenu)))
        self.end_headers()
        self.wfile.write(contenu)

    def api_documents(self, verbe, code, cl, p):
        """Documents PDF de la classe : dépôt (en base64), liste, lecture, effacement, brouillon de séance par l'IA."""
        if p == [] and verbe == "GET":
            with self.base.cnx() as c:
                rows = c.execute("SELECT id, nom, taille, length(texte) AS caracteres, cree FROM documents WHERE classe = ? ORDER BY id DESC", (code,)).fetchall()
            return self.json(200, [dict(r) for r in rows])
        if p == [] and verbe == "POST":
            d = self.corps(TAILLE_MAX_PDF * 4 // 3 + 4096)
            try:
                contenu = base64.b64decode(str(d.get("contenu", "")), validate=False)
            except (ValueError, TypeError):
                contenu = b""
            if not contenu.startswith(b"%PDF"):
                return self.erreur(400, "Le fichier n'est pas un PDF.")
            if len(contenu) > TAILLE_MAX_PDF:
                return self.erreur(413, "PDF trop volumineux : {mo} Mo au plus.", mo=TAILLE_MAX_PDF // (1024 * 1024))
            nom = re.sub(r"[\r\n\t/\\]", " ", str(d.get("nom") or "document.pdf")).strip()[:120] or "document.pdf"
            texte = PDF.extraire(contenu)
            with VERROU, self.base.cnx() as c:
                ident = c.execute("INSERT INTO documents (classe, nom, contenu, texte, taille, cree) VALUES (?, ?, ?, ?, ?, ?)",
                                  (code, nom, contenu, texte, len(contenu), maintenant())).lastrowid
            return self.json(201, {"id": ident, "nom": nom, "taille": len(contenu), "caracteres": len(texte)})
        if len(p) >= 1 and p[0].isdigit():
            with self.base.cnx() as c:
                doc = c.execute("SELECT * FROM documents WHERE id = ? AND classe = ?", (int(p[0]), code)).fetchone()
            if not doc:
                return self.erreur(404, "Document introuvable.")
            if len(p) == 1 and verbe == "GET":
                return self.envoyer_pdf(doc["nom"], doc["contenu"])
            if len(p) == 1 and verbe == "DELETE":
                with VERROU, self.base.cnx() as c:
                    c.execute("DELETE FROM documents WHERE id = ?", (doc["id"],))
                return self.json(200, {"supprime": doc["id"]})
            if p[1:] == ["brouillon"] and verbe == "POST":
                if len((doc["texte"] or "").strip()) < 200:
                    return self.erreur(422, "Aucun texte lisible dans ce PDF (document scanné ?) : écrivez la consigne vous-même.")
                cfg = config_valide(json.loads(cl["config"]))
                souhait = str(self.corps().get("souhait") or "").strip()[:1000]
                try:
                    return self.json(200, brouillon_seance(doc["nom"], doc["texte"], souhait, cfg))
                except Exception as exc:             # IA indisponible ou réponse illisible : l'enseignant écrit la séance lui-même
                    return self.erreur(502, "L'IA n'a pas pu préparer la séance : {exc}.", exc=exc)
        return self.erreur(404, "Ressource inconnue.")

    def effacer_seance(self, code, cl, n):
        """Efface une séance : sa tâche et toutes les traces des élèves qui s'y rapportent. Irréversible."""
        cfg = config_valide(json.loads(cl["config"]))
        if not 1 <= n <= cfg["seance"] or n in cfg["supprimees"]:
            return self.erreur(404, "Séance inconnue.")
        with VERROU, self.base.cnx() as c:
            ids = [r["id"] for r in c.execute("SELECT id FROM eleves WHERE classe = ?", (code,)).fetchall()]
            marques = ",".join("?" * len(ids))
            touches = c.execute(f"SELECT count(*) FROM traces WHERE seance = ? AND eleve IN ({marques})", (n, *ids)).fetchone()[0] if ids else 0
            for table in ("traces", "reponses", "verifications", "indices_vus", "tirages", "messages", "signalements"):
                if ids:
                    c.execute(f"DELETE FROM {table} WHERE seance = ? AND eleve IN ({marques})", (n, *ids))
            cfg["supprimees"] = sorted(set(cfg["supprimees"]) | {n})
            cfg["ouvertes"] = [k for k in cfg["ouvertes"] if k != n]
            cfg["archives"].pop(str(n), None)
            cfg["galerie"].pop(str(n), None)
            cfg["ouverte"] = cfg["seance"] in cfg["ouvertes"]
            cfg = config_valide(cfg)
            c.execute("UPDATE classes SET config = ? WHERE code = ?", (json.dumps(cfg), code))
        return self.json(200, {"config": cfg, "elevesConcernes": touches})

    def traces_classe(self, code):
        with self.base.cnx() as c:
            rows = c.execute("""SELECT e.id, e.pseudo, e.pin, e.preferences, t.seance, t.donnees FROM eleves e LEFT JOIN traces t ON t.eleve = e.id
                                WHERE e.classe = ?""", (code,)).fetchall()
            reps = c.execute("""SELECT r.*, x.titre, x.niveau, x.type FROM reponses r JOIN eleves e ON e.id = r.eleve
                                LEFT JOIN exercices x ON x.id = r.exercice WHERE e.classe = ?""", (code,)).fetchall()
            verifs = c.execute("""SELECT v.* FROM verifications v JOIN eleves e ON e.id = v.eleve WHERE e.classe = ?""", (code,)).fetchall()
            pouces = c.execute("""SELECT i.* FROM indices_vus i JOIN eleves e ON e.id = i.eleve WHERE e.classe = ?""", (code,)).fetchall()
        out = {}
        for r in rows:
            d = out.setdefault(r["id"], {"pseudo": r["pseudo"], "pin": r["pin"], "preferences": json.loads(r["preferences"] or "{}"), "seances": {}})
            if r["seance"] is not None:
                d["seances"][str(r["seance"])] = json.loads(r["donnees"])
        for r in reps:
            s = out.get(r["eleve"], {}).get("seances", {}).setdefault(str(r["seance"]), {})
            s.setdefault("exercices", []).append({"id": r["exercice"], "titre": r["titre"], "niveau": r["niveau"], "type": r["type"],
                                                  "tentatives": r["tentatives"], "score": r["score"], "premierScore": r["premier_score"], "duree": r["duree"],
                                                  "explications": r["explications"]})
        for v in verifs:
            s = out.get(v["eleve"], {}).get("seances", {}).setdefault(str(v["seance"]), {})
            s["verification"] = {"nombre": v["nombre"], **json.loads(v["donnees"] or "{}")}
        for i in pouces:
            out.get(i["eleve"], {}).get("seances", {}).setdefault(str(i["seance"]), {})["indicesVus"] = i["nombre"]
        cfg = config_valide(json.loads(self.classe(code)["config"]))
        if cfg["exercices"]["choix"] == "adaptatif":    # zone de développement actuelle de chaque élève
            with self.base.cnx() as c:
                niveaux = [r["niveau"] for r in c.execute("SELECT DISTINCT niveau FROM exercices WHERE classe = ? AND actif = 1", (code,))]
                for eid, d in out.items():
                    hist = historique_exercices(c, eid)
                    depart = (cfg["eleves"].get(eid, {}) or {}).get("niveau") or cfg["exercices"]["niveau"]
                    Z = ZPDES.zone(hist, depart, niveaux)
                    d["zpdes"] = {"zone": Z, "progres": {str(k): round(ZPDES.progres(hist.get(k, [])), 2) for k in Z},
                                  "reussite": {str(k): round(sum(v[-ZPDES.FENETRE:]) / len(v[-ZPDES.FENETRE:]), 2) for k, v in hist.items() if v}}
        return out

    def export(self, code):
        """Export brut (les indicateurs estimés sont calculés et exportés côté enseignant)."""
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        cfg = json.loads(self.classe(code)["config"])
        w.writerow(["pseudo", "seance", "numero", "ordre", "mode", "charge_debut", "charge_fin", "compris", "bloque",
                    "premiere_demande_s", "idees_avant", "idees_apres", "echanges_ia"])
        for eid, d in self.traces_classe(code).items():
            for n, s in sorted(d["seances"].items(), key=lambda kv: int(kv[0])):
                w.writerow([d["pseudo"], n, numero(cfg, int(n)), s.get("ordre"), s.get("mode"), s.get("chargeDebut"), s.get("chargeFin"),
                            s.get("compris"), int(bool(s.get("bloque"))), s.get("premiereDemande"),
                            " | ".join(i.get("texte", "") for i in s.get("ideesAvant") or []),
                            " | ".join(i.get("texte", "") for i in s.get("ideesApres") or []),
                            len(s.get("echanges") or [])])
        self.csv(f"traces_{code}.csv", buf)

    def csv(self, nom, buf):
        corps = ("﻿" + buf.getvalue()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{nom}"')
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def export_echanges(self, code):
        """Tous les échanges avec l'IA, pour relire leur qualité ; les réponses signalées portent leur motif."""
        with self.base.cnx() as c:
            sig = {(r["eleve"], r["seance"], r["indice"]): f'{r["auteur"]} : {r["motif"]}' for r in c.execute(
                "SELECT s.* FROM signalements s JOIN eleves e ON e.id = s.eleve WHERE e.classe = ?", (code,)).fetchall()}
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        cfg = json.loads(self.classe(code)["config"])
        w.writerow(["pseudo", "seance", "numero_seance", "numero", "role", "texte", "signalement"])
        for eid, d in self.traces_classe(code).items():
            for n, s in sorted(d["seances"].items(), key=lambda kv: int(kv[0])):
                for k, x in enumerate(s.get("echanges") or []):
                    w.writerow([d["pseudo"], n, numero(cfg, int(n)), k, "IA" if x.get("role") == "ia" else "élève", x.get("texte", ""), sig.get((eid, int(n), k), "")])
                for (e2, n2, k), m in sig.items():                  # réponses bloquées automatiquement (jamais montrées à l'élève)
                    if e2 == eid and n2 == int(n) and k is None:
                        w.writerow([d["pseudo"], n, numero(cfg, int(n)), "", "IA (bloquée)", "", m])
        self.csv(f"echanges_ia_{code}.csv", buf)

    def export_journal(self, code):
        """Journal des décisions : chaque changement de réglage d'un élève, avec son origine (pour la validation empirique)."""
        with self.base.cnx() as c:
            rows = c.execute("""SELECT j.*, e.pseudo FROM journal j LEFT JOIN eleves e ON e.id = j.eleve WHERE j.classe = ? ORDER BY j.id""", (code,)).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        cfg = json.loads(self.classe(code)["config"])
        w.writerow(["date", "pseudo", "seance", "numero", "origine", "avant", "apres"])
        for r in rows:
            w.writerow([r["cree"], r["pseudo"] or "(effacé)", r["seance"], numero(cfg, r["seance"]) if r["seance"] else "", r["origine"], r["avant"], r["apres"]])
        self.csv(f"journal_{code}.csv", buf)

    def api_messages(self, verbe, code, p):
        """Messages de l'enseignant à un élève, affichés au début de sa prochaine séance."""
        if p == [] and verbe == "GET":
            with self.base.cnx() as c:
                rows = c.execute("SELECT m.* FROM messages m JOIN eleves e ON e.id = m.eleve WHERE e.classe = ? ORDER BY m.id DESC", (code,)).fetchall()
            return self.json(200, [dict(r) for r in rows])
        if p == [] and verbe == "POST":
            d = self.corps()
            texte = str(d.get("texte", "")).strip()[:500]
            if not texte:
                return self.erreur(400, "Message vide.")
            with VERROU, self.base.cnx() as c:
                if not c.execute("SELECT 1 FROM eleves WHERE id = ? AND classe = ?", (str(d.get("eleve")), code)).fetchone():
                    return self.erreur(404, "Élève inconnu.")
                seance = d.get("seance") if isinstance(d.get("seance"), int) else None
                cur = c.execute("INSERT INTO messages (eleve, seance, texte, cree) VALUES (?, ?, ?, ?)", (d["eleve"], seance, texte, maintenant()))
            return self.json(201, {"id": cur.lastrowid})
        if len(p) == 1 and p[0].isdigit() and verbe == "DELETE":
            with VERROU, self.base.cnx() as c:
                c.execute("DELETE FROM messages WHERE id = ? AND eleve IN (SELECT id FROM eleves WHERE classe = ?)", (int(p[0]), code))
            return self.json(200, {"supprime": int(p[0])})
        return self.erreur(404, "Ressource inconnue.")

    def api_signalements(self, verbe, code):
        """Réponses de l'IA jugées inadaptées par l'enseignant, ou bloquées automatiquement par le serveur."""
        if verbe == "GET":
            with self.base.cnx() as c:
                rows = c.execute("SELECT s.* FROM signalements s JOIN eleves e ON e.id = s.eleve WHERE e.classe = ? ORDER BY s.id DESC", (code,)).fetchall()
            return self.json(200, [dict(r) for r in rows])
        if verbe == "POST":
            d = self.corps()
            eid, n, k = str(d.get("eleve")), int(d.get("seance")), int(d.get("indice"))
            with self.base.cnx() as c:
                t = c.execute("SELECT t.donnees FROM traces t JOIN eleves e ON e.id = t.eleve WHERE t.eleve = ? AND t.seance = ? AND e.classe = ?", (eid, n, code)).fetchone()
            ech = json.loads(t["donnees"]).get("echanges") or [] if t else []
            if not 0 <= k < len(ech) or ech[k].get("role") != "ia":
                return self.erreur(404, "Réponse de l'IA introuvable.")
            with VERROU, self.base.cnx() as c:
                c.execute("DELETE FROM signalements WHERE eleve = ? AND seance = ? AND indice = ?", (eid, n, k))
                if d.get("motif"):
                    c.execute("INSERT INTO signalements (eleve, seance, indice, texte, motif, auteur, cree) VALUES (?, ?, ?, ?, ?, 'enseignant', ?)",
                              (eid, n, k, str(ech[k].get("texte", ""))[:2000], str(d["motif"])[:200], maintenant()))
            return self.json(200, {"ok": True})
        return self.erreur(404, "Ressource inconnue.")

    def api_eleve(self, verbe, p, e):
        cl = self.classe(e["classe"])
        cfg = json.loads(cl["config"])
        ouv = ouvertes(cfg)
        demande = (getattr(self, "requete", {}).get("seance") or [""])[0]
        n = int(demande) if demande.isdigit() else (max(ouv) if ouv else cfg.get("seance", 0))
        cfgS = config_pour_seance(cfg, n)                  # réglages de la séance choisie par l'élève
        if p == ["moi"] and verbe == "GET":
            perso = cfg.get("eleves", {}).get(e["id"], {})
            with self.base.cnx() as c:
                rows = {r["seance"]: json.loads(r["donnees"]) for r in c.execute("SELECT seance, donnees FROM traces WHERE eleve = ?", (e["id"],)).fetchall()}
                vf = c.execute("SELECT nombre, donnees FROM verifications WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
                vus = c.execute("SELECT nombre FROM indices_vus WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            with self.base.cnx() as c:
                msgs = [dict(r) for r in c.execute("SELECT id, texte, cree FROM messages WHERE eleve = ? AND lu IS NULL ORDER BY id", (e["id"],)).fetchall()]
                bilans = {r["seance"]: json.loads(r["donnees"] or "{}") for r in c.execute("SELECT seance, donnees FROM verifications WHERE eleve = ?", (e["id"],)).fetchall()}
                scores = {r["seance"]: r["m"] for r in c.execute("SELECT seance, avg(score) AS m FROM reponses WHERE eleve = ? AND score IS NOT NULL GROUP BY seance", (e["id"],)).fetchall()}
                prefs = c.execute("SELECT preferences FROM eleves WHERE id = ?", (e["id"],)).fetchone()["preferences"]
            parcours = []
            for k in sorted(rows):
                if k in cfg.get("supprimees", []):
                    continue
                tk, b = rows[k], bilans.get(k, {})
                ck = config_pour_seance(cfg, k)
                parcours.append({"seance": k, "numero": numero(cfg, k), "titre": tache_de(ck, variante_eleve(ck, perso, tk))[0] or tk.get("tache", ""),
                                 "phase": tk.get("phase"), "essais": tk.get("essais", 1), "historique": tk.get("historique", []),
                                 "actuel": {"essai": tk.get("essais", 1), "idees": len(tk.get("ideesAvant") or []) + len(tk.get("ideesApres") or []),
                                            "justes": b.get("justes"), "verifiees": len(b.get("idees") or []) or None,
                                            "exercices": None if scores.get(k) is None else round(scores[k], 2)},
                                 "galerie": (cfg.get("galerie") or {}).get(str(k), []) if tk.get("phase") == "envoye" or tk.get("essais", 1) > 1 else []})
            tr = rows.get(n)
            variante = variante_eleve(cfgS, perso, tr)
            consigne, indices, _, _ = tache_de(cfgS, variante)
            consigne = consigne or (tr or {}).get("tache", "")   # la consigne actuelle de la séance (modifiable par l'enseignant)
            nvus = vus["nombre"] if vus else 0
            vmax = (cfgS.get("verification") or DEFAUT_CONFIG["verification"])["maximum"]
            derniere = {**json.loads(vf["donnees"]), "nombre": vf["nombre"], "restantes": max(0, vmax - vf["nombre"])} if vf else None
            if derniere and langue_valide(cfg.get("langue")) != "fr":     # retours enregistrés avant un changement de langue de la classe
                lg = langue_valide(cfg.get("langue"))
                derniere["retours"] = [{**x, "retour": traduire_texte(lg, x.get("retour"))} for x in derniere.get("retours") or []]
                derniere["bilan"], derniere["conseil"] = traduire_texte(lg, derniere.get("bilan")), traduire_texte(lg, derniere.get("conseil"))
            ex = cfgS.get("exercices") or DEFAUT_CONFIG["exercices"]
            liste = []
            for k in sorted(ouv):
                ck, tk = config_pour_seance(cfg, k), rows.get(k)
                titre = tache_de(ck, variante_eleve(ck, perso, tk))[0] or (tk or {}).get("tache", "")
                liste.append({"seance": k, "numero": numero(cfg, k), "titre": titre, "phase": (tk or {}).get("phase"), "essais": (tk or {}).get("essais", 1 if tk else 0),
                              "definitif": bool((tk or {}).get("definitif")),
                              "idees": len((tk or {}).get("ideesAvant") or []) + len((tk or {}).get("ideesApres") or [])})
            return self.json(200, {"id": e["id"], "pseudo": e["pseudo"], "classe": cl["nom"], "pin": e["pin"], "codePersonnel": bool(cfg.get("codePersonnel", False)),
                                   "horsLigne": bool(HORS_LIGNE),
                                   "ouvertes": liste,
                                   "coupsDePouce": {"total": len(indices), "vus": indices[:nvus]},
                                   "groupe": (cfg.get("groupes") or {}).get(e["id"]),
                                   "lecture": cfgS.get("lecture") or DEFAUT_CONFIG["lecture"],   # langue de la séance choisie
                                   "messages": msgs, "parcours": parcours, "preferences": json.loads(prefs or "{}"),
                                   "config": {**{k: cfgS[k] for k in ("seance", "ouverte", "ordre", "mode", "minIdees", "seuilCharge")}, "numero": numero(cfg, n),
                                              "public": cfg.get("public", "ecole"), "langue": langue_valide(cfg.get("langue")), "visuels": bool(cfg.get("visuels", True)),
                                              "discipline": DISCIPLINE_DU_MODELE.get(cfgS.get("modele") or "") or (cfg.get("discipline") if cfg.get("discipline") != "*" else ""),
                                              "saisieCode": bool(cfgS.get("saisieCode")), "evaluation": bool(cfgS.get("evaluation")), "tache": consigne,
                                              "document": self.nom_document(e["classe"], cfgS.get("document")),
                                              "exercices": {"actifs": ex["actifs"], "placement": ex["placement"],
                                                             "explications": bool(ex.get("explications", True)) and not HORS_LIGNE and not cfgS.get("evaluation")},
                                              "verification": {k: (cfgS.get("verification") or DEFAUT_CONFIG["verification"])[k] for k in ("mode", "maximum")}},
                                   "perso": {k: v for k, v in perso.items() if k != "variante"}, "seances": {str(k): v for k, v in rows.items()}, "derniereVerification": derniere})
        if p == ["document"] and verbe == "GET":            # document PDF de la séance (ouverte, ou déjà travaillée par l'élève)
            with self.base.cnx() as c:
                deja = c.execute("SELECT 1 FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
                d = c.execute("SELECT nom, contenu FROM documents WHERE id = ? AND classe = ?", (cfgS.get("document") or 0, e["classe"])).fetchone()
            if not d or (n not in ouv and not deja):
                return self.erreur(404, "Aucun document pour cette séance.")
            return self.envoyer_pdf(d["nom"], d["contenu"])
        if p == ["terminer"] and verbe == "POST":
            return self.terminer(e, cfgS)
        if p == ["correction"] and verbe == "GET":
            return self.correction(e, cfgS)
        if verbe in ("PUT", "POST") and p and p[0] in ("seance", "reprendre", "ia", "verifier", "indice", "exercices"):
            with self.base.cnx() as c:              # une séance terminée définitivement n'accepte plus aucune écriture
                tr = c.execute("SELECT donnees FROM traces WHERE eleve = ? AND seance = ?", (e["id"], int(p[1]) if p[0] == "seance" and len(p) == 2 and p[1].isdigit() else n)).fetchone()
            if tr and json.loads(tr["donnees"]).get("definitif"):
                return self.erreur(409, "Vous avez terminé définitivement cette séance : elle ne peut plus être modifiée.")
        if p == ["reprendre"] and verbe == "POST":
            if cfgS.get("evaluation"):
                return self.erreur(409, "Une évaluation ne se reprend pas.")
            return self.reprendre(e, cfgS)
        if len(p) == 2 and p[0] == "seance" and verbe == "PUT":
            n = int(p[1])
            if n not in ouv:
                return self.erreur(409, "Cette séance n'est plus ouverte.")
            cfg = config_pour_seance(cfg, n)
            d = self.corps()
            brut_d = d
            d = {k: d.get(k) for k in ("phase", "tache", "debut", "fin", "chargeDebut", "chargeFin", "compris", "ideesAvant",
                                       "ideesApres", "ideesRetirees", "echanges", "premiereDemande", "ideesAvantAide", "bloque", "suite")}
            # comment l'élève a cherché (avant de vérifier) et ce qui l'a aidé (en fin de séance)
            d["demarches"] = [{"essai": int(x.get("essai", 1)), "choix": x.get("choix"), "texte": str(x.get("texte") or "")[:300]}
                              for x in (brut_d.get("demarches") or [])[:20] if isinstance(x, dict) and x.get("choix") in DEMARCHES]
            d["aides"] = [a for a in (brut_d.get("aides") or []) if a in AIDES][:len(AIDES)]
            with self.base.cnx() as c:
                ancien = c.execute("SELECT donnees FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            ancien = json.loads(ancien["donnees"]) if ancien else {}
            d["essais"] = ancien.get("essais", 1)              # compté par le serveur (reprises)
            d["historique"] = ancien.get("historique", [])     # résultats des essais précédents, tenus par le serveur
            perso = cfg.get("eleves", {}).get(e["id"], {})
            if ancien.get("ordre"):            # fixés au début de la séance, puis verrouillés
                d["ordre"], d["mode"] = ancien["ordre"], ancien["mode"]
                d["variante"], d["tache"] = ancien.get("variante", "standard"), ancien.get("tache", cfg.get("tache"))
            elif d.get("phase") not in (None, "pseudo", "charge"):
                d["ordre"], d["mode"] = ordre_effectif(cfg, perso, d.get("chargeDebut"))
                d["variante"] = variante_eleve(cfg, perso)
                d["tache"] = tache_de(cfg, d["variante"])[0]
            with VERROU, self.base.cnx() as c:
                c.execute("""INSERT INTO traces (eleve, seance, donnees, maj) VALUES (?, ?, ?, ?)
                             ON CONFLICT(eleve, seance) DO UPDATE SET donnees = excluded.donnees, maj = excluded.maj""",
                          (e["id"], n, json.dumps(d, ensure_ascii=False), maintenant()))
            return self.json(200, {"ok": True, "ordre": d.get("ordre"), "mode": d.get("mode")})
        if p == ["ia"] and verbe == "POST":
            return self.ia(e, cfgS)
        if len(p) == 3 and p[0] == "messages" and p[1].isdigit() and p[2] == "lu" and verbe == "POST":
            with VERROU, self.base.cnx() as c:
                c.execute("UPDATE messages SET lu = ? WHERE id = ? AND eleve = ?", (maintenant(), int(p[1]), e["id"]))
            return self.json(200, {"ok": True})
        if p == ["preferences"] and verbe == "PUT":
            d = self.corps()
            prefs = {k: bool(d.get(k)) for k in ("grand", "facile", "images")}
            with VERROU, self.base.cnx() as c:
                c.execute("UPDATE eleves SET preferences = ? WHERE id = ?", (json.dumps(prefs), e["id"]))
            return self.json(200, prefs)
        if p == ["exercices"] and verbe == "GET":
            return self.exercices_eleve(e, cfgS)
        if p == ["verifier"] and verbe == "POST":
            if cfgS.get("evaluation"):
                return self.erreur(403, "Pendant une évaluation, la vérification n'est pas disponible : votre enseignant corrigera.")
            if HORS_LIGNE and (cfgS.get("verification") or {}).get("mode") == "ia":
                return self.erreur(403, "Hors ligne, la vérification par l'IA n'est pas disponible.")
            return self.verifier(e, cfgS)
        if p == ["export"] and verbe == "GET":                    # travail hors ligne, à remettre à l'enseignante
            with self.base.cnx() as c:
                return self.json(200, HL.exporter(c, e, maintenant))
        if p == ["indice"] and verbe == "POST":
            if cfgS.get("evaluation"):
                return self.erreur(403, "Pendant une évaluation, pas d'IA ni de coup de pouce.")
            return self.coup_de_pouce(e, cfgS)
        if len(p) == 3 and p[0] == "exercices" and p[2] == "reponse" and verbe == "POST":
            return self.repondre(e, cfgS, int(p[1]))
        if len(p) == 3 and p[0] == "exercices" and p[2] == "expliquer" and verbe == "POST":
            return self.expliquer(e, cfgS, int(p[1]))
        return self.erreur(404, "Ressource inconnue.")

    # ---------------------------------------------------------------- viabilité (expérimental)
    def viabilite(self):
        """Statut de viabilité de chaque élève à partir de son état estimé (calculé dans l'application enseignant)."""
        if not NOYAU.disponible():
            return self.erreur(503, "Tables de viabilité absentes du serveur.")
        d = self.corps()
        seance = max(1, int(d.get("seance", 1)))
        out = {}
        for uid, e in list((d.get("eleves") or {}).items())[:200]:
            try:
                x = tuple(min(1.0, max(0.0, float(e[k]))) for k in ("C", "A", "M", "D"))
                q = min(5, max(1, int(e.get("niveau") or 3)))
            except (KeyError, TypeError, ValueError):
                continue
            out[str(uid)[:64]] = NOYAU.analyser(q, seance, x)
            trajet = []
            for pt in (e.get("trajet") or [])[-12:]:          # états estimés des séances précédentes, pour les prédictions démenties
                try:
                    trajet.append({"t": max(0, int(pt["t"])), "niveau": min(5, max(1, int(pt.get("niveau") or q))),
                                   "x": [min(1.0, max(0.0, float(pt[k]))) for k in ("C", "A", "M", "D")],
                                   "u": [min(1.0, max(0.0, float(v))) for v in (pt.get("u") or [0, 0, 0])[:3]]})
                except (KeyError, TypeError, ValueError):
                    continue
            if len(trajet) >= 2:
                out[str(uid)[:64]]["prediction"] = NOYAU.predictions(trajet)
        return self.json(200, out)

    # ---------------------------------------------------------------- exercices
    def api_exercices(self, verbe, code, p):
        if p == [] and verbe == "GET":
            with self.base.cnx() as c:
                rows = c.execute("SELECT id, titre, type, niveau, actif, source, donnees FROM exercices WHERE classe = ? ORDER BY niveau, id", (code,)).fetchall()
            return self.json(200, [{"id": r["id"], "titre": r["titre"], "type": r["type"], "niveau": r["niveau"], "actif": bool(r["actif"]),
                                    "source": r["source"], "texte": json.loads(r["donnees"])["texte"][:200]} for r in rows])
        if p == ["import"] and verbe == "POST":
            d = self.corps()
            contenu = str(d.get("contenu", ""))
            if not contenu.strip():
                return self.erreur(400, "Fichier vide.")
            fmt = d.get("format") if d.get("format") in ("gift", "xml") else None
            niveau = min(5, max(1, int(d.get("niveau", 2))))
            source = str(d.get("source", ""))[:120]
            questions, avert = EX.importer(contenu, fmt)
            with VERROU, self.base.cnx() as c:
                for q in questions:
                    c.execute("INSERT INTO exercices (classe, titre, type, niveau, donnees, source, cree) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (code, q["titre"][:200], q["type"], niveau, json.dumps(q, ensure_ascii=False), source, maintenant()))
            return self.json(200, {"importes": len(questions), "avertissements": [traduire_texte(self.langue(), a) for a in avert]})
        if len(p) == 1 and verbe in ("PUT", "DELETE"):
            with VERROU, self.base.cnx() as c:
                if verbe == "DELETE":
                    c.execute("DELETE FROM exercices WHERE id = ? AND classe = ?", (int(p[0]), code))
                    return self.json(200, {"supprime": int(p[0])})
                d = self.corps()
                if "niveau" in d:
                    c.execute("UPDATE exercices SET niveau = ? WHERE id = ? AND classe = ?", (min(5, max(1, int(d["niveau"]))), int(p[0]), code))
                if "actif" in d:
                    c.execute("UPDATE exercices SET actif = ? WHERE id = ? AND classe = ?", (1 if d["actif"] else 0, int(p[0]), code))
            return self.json(200, {"ok": True})
        return self.erreur(404, "Ressource inconnue.")

    def tirage(self, e, cfg):
        """Exercices de la séance pour cet élève : tirés une fois au niveau voulu, puis fixés."""
        n = cfg["seance"]
        with self.base.cnx() as c:
            t = c.execute("SELECT ids FROM tirages WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            if t:
                return json.loads(t["ids"])
            ex = cfg.get("exercices") or DEFAUT_CONFIG["exercices"]
            niveau = (cfg.get("eleves", {}).get(e["id"], {}) or {}).get("niveau") or ex["niveau"]
            dispo = c.execute("SELECT id, niveau, source FROM exercices WHERE classe = ? AND actif = 1", (e["classe"],)).fetchall()
        if ex.get("source"):                    # séance créée à partir d'un fichier .gift : seulement ses questions
            dispo = [r for r in dispo if r["source"] == ex["source"]]
        deja = set()
        with self.base.cnx() as c:
            for r in c.execute("SELECT exercice FROM reponses WHERE eleve = ?", (e["id"],)).fetchall():
                deja.add(r["exercice"])
        rng = random.Random(f"{e['id']}-{n}")
        if ex.get("choix") == "adaptatif":      # zone de développement et progrès de l'élève, à la manière de ZPDES
            par_niveau = {}
            for r in dispo:
                par_niveau.setdefault(r["niveau"], []).append(r["id"])
            with self.base.cnx() as c:
                hist = historique_exercices(c, e["id"])
            ids = ZPDES.choisir(hist, niveau, par_niveau, deja, ex["nombre"], rng)[0]
        else:
            # au niveau voulu d'abord, puis aux niveaux voisins ; ceux déjà faits passent en dernier
            dispo = sorted(dispo, key=lambda r: (abs(r["niveau"] - niveau), r["id"] in deja, rng.random()))
            ids = [r["id"] for r in dispo[:ex["nombre"]]]
        with VERROU, self.base.cnx() as c:
            c.execute("INSERT OR IGNORE INTO tirages VALUES (?, ?, ?)", (e["id"], n, json.dumps(ids)))
        return ids

    def exercices_eleve(self, e, cfg):
        if not cfg.get("ouverte") or not (cfg.get("exercices") or {}).get("actifs"):
            return self.json(200, [])
        ids = self.tirage(e, cfg)
        with self.base.cnx() as c:
            rows = {r["id"]: r for r in c.execute(f"SELECT * FROM exercices WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()} if ids else {}
            reps = {r["exercice"]: r for r in c.execute("SELECT * FROM reponses WHERE eleve = ? AND seance = ?", (e["id"], cfg["seance"])).fetchall()}
        out = []
        for i in ids:
            if i in rows:
                v = EX.pour_eleve(json.loads(rows[i]["donnees"]), f"{e['id']}-{i}")
                r = reps.get(i)
                v.update(id=i, tentatives=r["tentatives"] if r else 0, score=None if cfg.get("evaluation") else (r["score"] if r else None))
                out.append(v)
        return self.json(200, out)

    def repondre(self, e, cfg, xid):
        if not cfg.get("ouverte"):
            return self.erreur(409, "Aucune séance ouverte.")
        n = cfg["seance"]
        if xid not in self.tirage(e, cfg):
            return self.erreur(404, "Exercice inconnu pour cette séance.")
        with self.base.cnx() as c:
            x = c.execute("SELECT donnees FROM exercices WHERE id = ?", (xid,)).fetchone()
            r = c.execute("SELECT * FROM reponses WHERE eleve = ? AND seance = ? AND exercice = ?", (e["id"], n, xid)).fetchone()
        if not x:
            return self.erreur(404, "Exercice supprimé.")
        tent = r["tentatives"] if r else 0
        evaluation = bool(cfg.get("evaluation"))             # une seule réponse, et la correction reste chez l'enseignant
        if tent >= (1 if evaluation else 2) or (r and r["score"] is not None and r["score"] >= 1):
            return self.erreur(409, "Exercice déjà terminé.")
        d = self.corps()
        q = json.loads(x["donnees"])
        score, retour, attendu = EX.corriger(q, d.get("reponse"))
        tent += 1
        premier = r["premier_score"] if r else score
        duree = int(d.get("duree") or 0) + (r["duree"] or 0 if r else 0)
        meilleur = max(score, r["score"] or 0) if r else score
        with VERROU, self.base.cnx() as c:
            c.execute("""INSERT INTO reponses (eleve, seance, exercice, tentatives, score, premier_score, duree, maj, reponse) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                         ON CONFLICT(eleve, seance, exercice) DO UPDATE SET tentatives = excluded.tentatives, score = excluded.score,
                         duree = excluded.duree, maj = excluded.maj, reponse = excluded.reponse""",
                      (e["id"], n, xid, tent, meilleur, premier, min(duree, 3600), maintenant(), json.dumps(d.get("reponse"), ensure_ascii=False)[:2000]))
        if evaluation:
            return self.json(200, {"enregistre": True, "tentatives": tent, "fini": True})
        fini = score >= 1 or tent >= 2
        lg = self.langue()
        return self.json(200, {"score": score, "juste": score >= 1, "retour": traduire_texte(lg, retour), "tentatives": tent, "fini": fini,
                               "attendu": traduire_texte(lg, attendu) if fini and score < 1 else None,
                               "retourGeneral": q.get("retour_general", "") if fini else ""})

    def expliquer(self, e, cfg, xid):
        """Après une réponse fausse, l'IA explique l'erreur et la règle en jeu, en s'appuyant sur la bonne réponse de l'enseignant.
        Tant qu'il reste un essai, elle ne donne pas la bonne réponse. Une explication par réponse donnée."""
        if not cfg.get("ouverte"):
            return self.erreur(409, "Aucune séance ouverte.")
        if cfg.get("evaluation"):
            return self.erreur(403, "Pendant une évaluation, pas d'IA ni de coup de pouce.")
        if HORS_LIGNE:
            return self.erreur(403, "Hors ligne, l'IA ne peut pas expliquer les erreurs : relisez le commentaire de l'exercice.")
        if not (cfg.get("exercices") or {}).get("explications", True):
            return self.erreur(403, "Votre enseignant n'a pas activé les explications de l'IA pour les exercices.")
        n = cfg["seance"]
        if xid not in self.tirage(e, cfg):
            return self.erreur(404, "Exercice inconnu pour cette séance.")
        with self.base.cnx() as c:
            x = c.execute("SELECT donnees FROM exercices WHERE id = ?", (xid,)).fetchone()
            r = c.execute("SELECT * FROM reponses WHERE eleve = ? AND seance = ? AND exercice = ?", (e["id"], n, xid)).fetchone()
        if not x:
            return self.erreur(404, "Exercice supprimé.")
        if not r or r["reponse"] is None:
            return self.erreur(409, "Répondez d'abord à l'exercice.")
        q, donnee = json.loads(x["donnees"]), json.loads(r["reponse"])
        score, retour, _ = EX.corriger(q, donnee)
        if score >= 1:
            return self.erreur(409, "Cette réponse est juste : il n'y a pas d'erreur à expliquer.")
        if r["explications"] >= r["tentatives"]:
            return self.erreur(429, "Vous avez déjà une explication pour cette réponse : relisez-la, puis réessayez.")
        fini = r["tentatives"] >= 2
        lg = langue_valide(cfg.get("langue"))
        choix = "".join(f"\n- {c_['texte']}" for c_ in q["reponses"]) if q["type"] in ("choix_unique", "choix_multiple") else ""
        contexte = (f"Énoncé de l'exercice : {q.get('texte', '')}" + (f"\nChoix proposés :{choix}" if choix else "")
                    + f"\n\nRéponse de l'élève : {EX.reponse_lisible(q, donnee) or '(vide)'}"
                    + f"\nBonne réponse, donnée par l'enseignant : {EX.reponse_attendue(q)}"
                    + (f"\nCommentaire prévu par l'enseignant pour cette réponse : {retour}" if retour else "")
                    + (f"\nExplication générale prévue par l'enseignant : {q['retour_general']}" if q.get("retour_general") else "")
                    + ("\n\nL'élève a encore un essai." if not fini else "\n\nL'élève n'a plus d'essai : il connaît maintenant la bonne réponse."))
        try:
            texte = appeler_ia(consignes_explication(cfg.get("mode"), cfg.get("public", "ecole"), lg, fini, cfg.get("saisieCode", False)),
                              [{"role": "user", "content": contexte}], max_tokens=600 if cfg.get("public") == "superieur" else 400)
        except urllib.error.HTTPError as exc:     # la cause va dans le terminal du serveur, sans donnée d'élève
            print(f"[IA] explication refusée par le fournisseur : HTTP {exc.code} — {exc.read()[:300].decode('utf-8', 'replace')}", flush=True)
            return self.erreur(502, "L'IA n'a pas répondu. Réessayez dans un moment.")
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError, IndexError, OSError, AttributeError, TypeError) as exc:
            print(f"[IA] explication impossible : {type(exc).__name__} — {exc}", flush=True)
            return self.erreur(502, "L'IA n'a pas répondu. Réessayez dans un moment.")
        if not fini and revele_reponse(texte, q):  # garde-fou : la bonne réponse n'est jamais montrée avant le second essai
            with VERROU, self.base.cnx() as c:
                c.execute("INSERT INTO signalements (eleve, seance, indice, texte, motif, auteur, cree) VALUES (?, ?, NULL, ?, ?, 'auto', ?)",
                          (e["id"], n, texte[:2000], "explication bloquée : elle contenait la bonne réponse", maintenant()))
            texte = T(lg, "Relis l'énoncé mot par mot et compare-le à ta réponse : où se trouve la différence ? "
                          "Pense à la règle que tu as apprise sur cette notion, puis réessaie.")
        with VERROU, self.base.cnx() as c:
            c.execute("UPDATE reponses SET explications = explications + 1 WHERE eleve = ? AND seance = ? AND exercice = ?", (e["id"], n, xid))
            c.execute("UPDATE traces SET appels_ia = appels_ia + 1 WHERE eleve = ? AND seance = ?", (e["id"], n))
        return self.json(200, {"texte": texte, "fini": fini})

    # ---------------------------------------------------------------- reprise d'une séance terminée
    def reprendre(self, e, cfg):
        """Nouvel essai sur une séance encore ouverte : les idées restent, la vérification repart à zéro,
        les exercices ratés peuvent être refaits."""
        n = cfg["seance"]
        if not cfg.get("ouverte"):
            return self.erreur(409, "Cette séance n'est plus ouverte.")
        with self.base.cnx() as c:
            t = c.execute("SELECT donnees FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
        if not t:
            return self.erreur(409, "Cette séance n'a pas encore été commencée.")
        d = json.loads(t["donnees"])
        if d.get("phase") != "envoye":
            return self.json(200, d)                         # déjà en cours : rien à faire
        ex = cfg.get("exercices") or DEFAUT_CONFIG["exercices"]
        with self.base.cnx() as c:
            vf = c.execute("SELECT donnees FROM verifications WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            sc = c.execute("SELECT avg(score) FROM reponses WHERE eleve = ? AND seance = ? AND score IS NOT NULL", (e["id"], n)).fetchone()[0]
        vf = json.loads(vf["donnees"] or "{}") if vf else {}
        d.setdefault("historique", []).append({"essai": d.get("essais", 1), "idees": len(d.get("ideesAvant") or []) + len(d.get("ideesApres") or []),
                                               "justes": vf.get("justes"), "verifiees": len(vf.get("idees") or []) or None,
                                               "exercices": None if sc is None else round(sc, 2)})
        with VERROU, self.base.cnx() as c:
            rates = c.execute("SELECT count(*) FROM reponses WHERE eleve = ? AND seance = ? AND (score IS NULL OR score < 1)", (e["id"], n)).fetchone()[0]
            c.execute("DELETE FROM reponses WHERE eleve = ? AND seance = ? AND (score IS NULL OR score < 1)", (e["id"], n))
            c.execute("UPDATE verifications SET nombre = 0 WHERE eleve = ? AND seance = ?", (e["id"], n))
            d["essais"] = d.get("essais", 1) + 1
            d["chargeFin"] = d["compris"] = d["fin"] = None
            d["suite"] = None
            if ex.get("actifs") and rates and ex.get("placement") == "avant":
                d["phase"], d["suite"] = "exercices", "tache"
            elif d.get("ordre") == "autonomie":
                d["phase"] = "reflexion"
            elif d.get("ordre") == "ia" or len(d.get("ideesAvant") or []) >= cfg.get("minIdees", 3) or d.get("bloque"):
                d["phase"] = "ia"
            else:
                d["phase"] = "reflexion"
            c.execute("UPDATE traces SET donnees = ?, maj = ? WHERE eleve = ? AND seance = ?", (json.dumps(d, ensure_ascii=False), maintenant(), e["id"], n))
        d["exercicesARefaire"] = bool(ex.get("actifs") and rates)
        return self.json(200, d)

    # ---------------------------------------------------------------- coups de pouce
    def coup_de_pouce(self, e, cfg):
        """Dévoile le coup de pouce suivant de la variante de l'élève et le note."""
        if not cfg.get("ouverte"):
            return self.erreur(409, "Aucune séance ouverte.")
        n = cfg["seance"]
        with self.base.cnx() as c:
            t = c.execute("SELECT donnees FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            vus = c.execute("SELECT nombre FROM indices_vus WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
        if not t:
            return self.erreur(409, "Commencez la séance avant de demander un coup de pouce.")
        _, indices, _, _ = tache_de(cfg, variante_eleve(cfg, cfg.get("eleves", {}).get(e["id"], {}), json.loads(t["donnees"])))
        nombre = (vus["nombre"] if vus else 0) + 1
        if nombre > len(indices):
            return self.erreur(409, "Il n'y a plus de coup de pouce : essayez avec ce que vous avez déjà.")
        with VERROU, self.base.cnx() as c:
            c.execute("""INSERT INTO indices_vus (eleve, seance, nombre, maj) VALUES (?, ?, ?, ?)
                         ON CONFLICT(eleve, seance) DO UPDATE SET nombre = excluded.nombre, maj = excluded.maj""", (e["id"], n, nombre, maintenant()))
        return self.json(200, {"vus": indices[:nombre], "total": len(indices)})

    # ---------------------------------------------------------------- vérification des idées
    def verifier(self, e, cfg):
        v = cfg.get("verification") or DEFAUT_CONFIG["verification"]
        if not cfg.get("ouverte") or v["mode"] == "aucune":
            return self.erreur(409, "La vérification n'est pas proposée pour cette séance.")
        n = cfg["seance"]
        with self.base.cnx() as c:
            t = c.execute("SELECT donnees FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            deja = c.execute("SELECT nombre FROM verifications WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
        s = json.loads(t["donnees"]) if t else {}
        idees = [str(i.get("texte", ""))[:4000] for i in (s.get("ideesAvant") or []) + (s.get("ideesApres") or [])][:40]
        if not idees:
            return self.erreur(409, "Écrivez d'abord des idées.")
        nombre = (deja["nombre"] if deja else 0) + 1
        if nombre > v["maximum"]:
            return self.erreur(429, "Vous avez déjà vérifié {n} fois : relisez les retours et améliorez vos idées.", n=v["maximum"])
        res = self.juger_idees(e, cfg, s, idees)
        if res is None:
            return self.erreur(502, "La vérification n'a pas abouti. Réessayez dans un moment.")
        with VERROU, self.base.cnx() as c:
            c.execute("""INSERT INTO verifications (eleve, seance, nombre, donnees, maj) VALUES (?, ?, ?, ?, ?)
                         ON CONFLICT(eleve, seance) DO UPDATE SET nombre = excluded.nombre, donnees = excluded.donnees, maj = excluded.maj""",
                      (e["id"], n, nombre, json.dumps(res, ensure_ascii=False), maintenant()))
        return self.json(200, {**res, "nombre": nombre, "restantes": v["maximum"] - nombre})

    def juger_idees(self, e, cfg, s, idees):
        """Retour sur chaque idée (calcul, ou IA selon les critères de la séance) ; None si l'IA n'a pas répondu."""
        v = cfg.get("verification") or DEFAUT_CONFIG["verification"]
        consigne, _, cible, attendu = tache_de(cfg, variante_eleve(cfg, cfg.get("eleves", {}).get(e["id"], {}), s))
        if v["mode"] == "calcul":
            autorises = [float(x) for x in v["nombres"].split(" ; ") if x]
            res = VERIF.verifier_calcul(idees, cible, autorises, attendu or None, v.get("uneFois", False), langue_valide(cfg.get("langue")))
        elif os.environ.get("VIABILIS_IA", "fausse") == "fausse":
            res = {"retours": [{"statut": "a_revoir", "retour": "Retour factice (IA non configurée) : explique en quoi ton idée répond à la consigne."} for _ in idees],
                   "bilan": "Retour factice : configurez une IA pour obtenir de vrais retours.", "justes": 0}
        else:
            consigne_ia = VERIF.consigne_ia(consigne, v["criteres"], idees, cfg.get("public", "ecole"), cfg.get("saisieCode", False), langue_valide(cfg.get("langue")))
            res = None
            for essai in (1, 2):                           # un second essai si la réponse est illisible ou trop lente
                try:
                    texte = appeler_ia("Tu réponds uniquement en JSON valide, sans aucun texte autour.", [{"role": "user", "content": consigne_ia}],
                                      max_tokens=1200 + 150 * len(idees), delai=120)   # un retour par idée : assez de place pour toutes
                    res = VERIF.lire_reponse_ia(texte, len(idees), langue_valide(cfg.get("langue")))
                    break
                except urllib.error.HTTPError as exc:      # la cause va dans le terminal, sans donnée d'élève
                    detail = exc.read()[:300].decode("utf-8", "replace")
                    print(f"[IA] vérification refusée par le fournisseur : HTTP {exc.code} — {detail}", flush=True)
                    return None
                except (urllib.error.URLError, KeyError, ValueError, TimeoutError, IndexError, OSError, AttributeError, TypeError) as exc:
                    print(f"[IA] vérification, essai {essai} : {type(exc).__name__} — {exc}", flush=True)
            if res is None:
                return None
        res["idees"] = idees
        res["attendu"] = attendu if v["mode"] == "calcul" else None     # pour estimer la maîtrise sans pénaliser les essais
        return res

    # ---------------------------------------------------------------- fin définitive et correction
    def terminer(self, e, cfg):
        """L'élève termine définitivement la séance : plus de modification ni de reprise ; ses idées reçoivent une correction finale."""
        n = cfg["seance"]
        with self.base.cnx() as c:
            t = c.execute("SELECT donnees FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
        s = json.loads(t["donnees"]) if t else {}
        if s.get("definitif"):
            return self.correction(e, cfg)
        if s.get("phase") != "envoye":
            return self.erreur(409, "Terminez d'abord la séance (« J'ai terminé »), puis vous pourrez la terminer définitivement.")
        v = cfg.get("verification") or DEFAUT_CONFIG["verification"]
        idees = [str(i.get("texte", ""))[:4000] for i in (s.get("ideesAvant") or []) + (s.get("ideesApres") or [])][:40]
        corr = {"idees": None, "message": None}
        if not idees or v["mode"] == "aucune":
            corr["message"] = None if not idees else "Vos idées ne sont pas corrigées automatiquement dans cette séance : votre enseignant les lira."
        elif HORS_LIGNE and v["mode"] == "ia":
            corr["message"] = "Hors ligne, vos idées ne peuvent pas être corrigées par l'IA : votre enseignant les lira après l'import."
        else:
            res = self.juger_idees(e, cfg, s, idees)
            if res is None:
                return self.erreur(502, "La correction n'a pas abouti. Réessayez dans un moment : votre séance n'est pas encore terminée définitivement.")
            corr["idees"] = res
        s["definitif"], s["correction"] = maintenant(), corr
        with VERROU, self.base.cnx() as c:
            c.execute("UPDATE traces SET donnees = ?, maj = ? WHERE eleve = ? AND seance = ?", (json.dumps(s, ensure_ascii=False), maintenant(), e["id"], n))
        return self.correction(e, cfg)

    def correction(self, e, cfg):
        """La correction d'une séance terminée définitivement : idées (retour final) et exercices (réponse donnée, bonne réponse, explication)."""
        n = cfg["seance"]
        with self.base.cnx() as c:
            t = c.execute("SELECT donnees FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            s = json.loads(t["donnees"]) if t else {}
            if not s.get("definitif"):
                return self.erreur(409, "La correction est disponible quand la séance est terminée définitivement.")
            tir = c.execute("SELECT ids FROM tirages WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
            ids = json.loads(tir["ids"]) if tir else []
            exos = {r["id"]: json.loads(r["donnees"]) for r in c.execute(f"SELECT id, donnees FROM exercices WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
            reps = {r["exercice"]: r for r in c.execute("SELECT * FROM reponses WHERE eleve = ? AND seance = ?", (e["id"], n))}
        exercices = []
        for i in ids:
            q = exos.get(i)
            if not q:
                continue
            r = reps.get(i)
            donnee = json.loads(r["reponse"]) if r and r["reponse"] else None
            score, retour, _ = EX.corriger(q, donnee) if r else (0.0, "", "")
            attendu = EX.reponse_attendue(q)
            lg = self.langue()
            exercices.append({"titre": q.get("titre", ""), "texte": q.get("texte", ""), "reponse": traduire_texte(lg, EX.reponse_lisible(q, donnee)) if r else None,
                              "score": round(r["score"] if r and r["score"] is not None else score, 2), "juste": bool(r) and (r["score"] or 0) >= 1,
                              "retour": traduire_texte(lg, retour), "attendu": traduire_texte(lg, attendu), "retourGeneral": q.get("retour_general", "")})
        return self.json(200, {"definitif": s["definitif"], "idees": (s.get("correction") or {}).get("idees"),
                               "message": traduire_texte(self.langue(), (s.get("correction") or {}).get("message")), "exercices": exercices})

    def ia(self, e, cfg):
        """L'IA passe par le serveur : il applique l'ordre et le rôle décidés par l'enseignant, pas ceux du navigateur."""
        if not cfg.get("ouverte"):
            return self.erreur(409, "Aucune séance ouverte.")
        n = cfg["seance"]
        with self.base.cnx() as c:
            t = c.execute("SELECT donnees, appels_ia FROM traces WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
        if not t:
            return self.erreur(409, "Commencez la séance avant d'utiliser l'IA.")
        s = json.loads(t["donnees"])
        if s.get("ordre") == "autonomie":
            return self.erreur(403, "Aujourd'hui, vous travaillez sans l'IA.")
        if s.get("ordre") == "reflexion" and not s.get("bloque") and len(s.get("ideesAvant") or []) < cfg.get("minIdees", 3):
            return self.erreur(403, "Écrivez d'abord vos idées.")
        if t["appels_ia"] >= IA_MAX_PAR_SEANCE:
            return self.erreur(429, "Nombre de questions à l'IA atteint pour cette séance.")
        d = self.corps()
        echanges = [x for x in (d.get("echanges") or []) if isinstance(x, dict)][-10:]
        idees = [str(i.get("texte", ""))[:4000] for i in (s.get("ideesAvant") or []) + (s.get("ideesApres") or [])]
        consigne, indices, _, _ = tache_de(cfg, variante_eleve(cfg, cfg.get("eleves", {}).get(e["id"], {}), s))
        with self.base.cnx() as c:
            vus = c.execute("SELECT nombre FROM indices_vus WHERE eleve = ? AND seance = ?", (e["id"], n)).fetchone()
        donnes = indices[:vus["nombre"]] if vus else []
        contexte = (f"La tâche de l'élève : {consigne or '(non précisée)'}\n\nLes idées déjà écrites par l'élève :\n"
                    + ("\n".join("- " + i for i in idees) or "(aucune pour l'instant)")
                    + ("\n\nCoups de pouce déjà donnés par l'enseignant (ne les répète pas) :\n" + "\n".join("- " + i for i in donnes) if donnes else ""))
        tours = [{"role": "user", "content": contexte}]
        for x in echanges:
            tours.append({"role": "assistant" if x.get("role") == "ia" else "user", "content": str(x.get("texte", ""))[:1000] or "…"})
        if tours[-1]["role"] != "user":
            tours.append({"role": "user", "content": "Continue."})
        fusion = []   # les API exigent des rôles alternés
        for x in tours:
            if fusion and fusion[-1]["role"] == x["role"]:
                fusion[-1]["content"] += "\n\n" + x["content"]
            else:
                fusion.append(dict(x))
        try:
            texte = appeler_ia(consignes_ia(s.get("mode") or cfg.get("mode"), cfg.get("public", "ecole"), cfg.get("saisieCode", False), langue_valide(cfg.get("langue"))), fusion,
                              max_tokens=500 if cfg.get("public") == "superieur" else 300)
        except urllib.error.HTTPError as exc:     # la cause va dans le terminal du serveur, sans donnée d'élève
            detail = exc.read()[:300].decode("utf-8", "replace")
            print(f"[IA] le fournisseur a refusé l'appel : HTTP {exc.code} — {detail}", flush=True)
            cle_refusee = exc.code in (401, 403) or "api key" in detail.lower() or "api_key" in detail.lower()
            msg = "La clé d'API de l'IA est refusée : prévenez votre enseignant." if cle_refusee else "L'IA n'a pas répondu. Réessayez dans un moment."
            return self.erreur(502, msg)
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError, IndexError, OSError, AttributeError, TypeError) as exc:
            print(f"[IA] appel impossible : {type(exc).__name__} — {exc}", flush=True)
            return self.erreur(502, "L'IA n'a pas répondu. Réessayez dans un moment.")
        v = cfg.get("verification") or {}
        if v.get("mode") == "calcul":           # garde-fou : une réponse qui contient une solution n'est jamais montrée
            _, _, cible, _ = tache_de(cfg, variante_eleve(cfg, cfg.get("eleves", {}).get(e["id"], {}), s))
            autorises = [float(x) for x in (v.get("nombres") or "").split(" ; ") if x]
            if cible is not None and VERIF.solution_dans_texte(texte, cible, autorises, v.get("uneFois", False)):
                with VERROU, self.base.cnx() as c:
                    c.execute("INSERT INTO signalements (eleve, seance, indice, texte, motif, auteur, cree) VALUES (?, ?, NULL, ?, ?, 'auto', ?)",
                              (e["id"], n, texte[:2000], "réponse bloquée : elle contenait une solution", maintenant()))
                texte = T(langue_valide(cfg.get("langue")), "Je ne vais pas te donner de solution : c'est à toi de la trouver. "
                          "Dis-moi plutôt comment tu cherches : quel calcul as-tu essayé, et qu'as-tu obtenu ?")
        with VERROU, self.base.cnx() as c:
            c.execute("UPDATE traces SET appels_ia = appels_ia + 1 WHERE eleve = ? AND seance = ?", (e["id"], n))
        return self.json(200, {"texte": texte})


def main():
    ap = argparse.ArgumentParser(description="Serveur Viabilis classe")
    ap.add_argument("--hote", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--base", default=None)
    ap.add_argument("--hors-ligne", metavar="KIT", help="mode hors ligne sur l'ordinateur d'un étudiant, avec le kit de la classe (fichier JSON)")
    ap.add_argument("--sans-navigateur", action="store_true", help="hors ligne : ne pas ouvrir la page dans le navigateur (tests)")
    a = ap.parse_args()
    if a.hors_ligne:
        return hors_ligne(a)
    a.base = a.base or os.path.join(RACINE, "viabilis.sqlite3")
    mdp = os.environ.get("VIABILIS_MDP_ENSEIGNANT")
    Gestionnaire.sel = secrets.token_bytes(16)
    if CPT.actif():                                # comptes enseignants : le mot de passe unique ne sert plus
        mdp = secrets.token_urlsafe(32)
    elif not mdp or len(mdp) < 10:
        raise SystemExit("Définissez VIABILIS_MDP_ENSEIGNANT (10 caractères au moins), ou VIABILIS_DOMAINES pour des comptes enseignants.")
    fournisseur = verifier_config_ia()
    Gestionnaire.mdp_hash = hashlib.pbkdf2_hmac("sha256", mdp.encode(), Gestionnaire.sel, 200_000)
    Gestionnaire.adresse = (os.environ.get("VIABILIS_ADRESSE") or f"http://{a.hote}:{a.port}").rstrip("/")
    Gestionnaire.base = Base(a.base)
    jours = int(os.environ.get("VIABILIS_CONSERVATION_JOURS", "365"))

    def purge():
        while True:
            Gestionnaire.base.purger(jours)
            time.sleep(24 * 3600)
    threading.Thread(target=purge, daemon=True).start()
    print(f"Viabilis classe : http://{a.hote}:{a.port}/eleve/  et  http://{a.hote}:{a.port}/enseignant/")
    print("Comptes enseignants : " + (f"validés par {CPT.admin()}" if CPT.admin() else "sans validation")
          + (" ; domaines " + ", ".join(CPT.domaines()) if CPT.domaines() else " ; toutes les adresses") + (f" ; serveur de mail {os.environ['VIABILIS_SMTP_HOTE']}" if os.environ.get("VIABILIS_SMTP_HOTE")
          else " ; aucun serveur de mail réglé (VIABILIS_SMTP_HOTE)") if CPT.actif() else "Mode sans comptes : un seul mot de passe enseignant (VIABILIS_MDP_ENSEIGNANT)")
    print(f"IA : {fournisseur}" + (" (réponses factices, pour les essais)" if fournisseur == "fausse" else f", modèle {os.environ.get('VIABILIS_IA_MODELE') or COMPATIBLES.get(fournisseur, ('', 'claude-haiku-4-5-20251001'))[1]}"), flush=True)
    ThreadingHTTPServer((a.hote, a.port), Gestionnaire).serve_forever()


def hors_ligne(a):
    """Sur l'ordinateur d'un étudiant : la classe du kit, sans IA ni page enseignant, accessible seulement depuis cet ordinateur."""
    global HORS_LIGNE
    import webbrowser
    kit = os.path.abspath(a.hors_ligne)
    base = a.base or os.path.join(os.path.dirname(kit), "travail", "viabilis.sqlite3")
    os.makedirs(os.path.dirname(base), exist_ok=True)
    Gestionnaire.sel = secrets.token_bytes(16)
    Gestionnaire.mdp_hash = hashlib.pbkdf2_hmac("sha256", secrets.token_bytes(32), Gestionnaire.sel, 1000)   # aucun mot de passe ne convient
    Gestionnaire.base = Base(base)
    HORS_LIGNE = HL.charger_kit(Gestionnaire.base.cnx, kit, maintenant)
    for port in range(a.port, a.port + 20):            # un autre programme occupe peut-être le port
        try:
            serveur = ThreadingHTTPServer(("127.0.0.1", port), Gestionnaire)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"Aucun port libre entre {a.port} et {a.port + 19}.")
    adresse = f"http://127.0.0.1:{port}/eleve/"
    print(f"Viabilis hors ligne — {HORS_LIGNE['nom']} (code {HORS_LIGNE['code']})")
    print(f"Page de l'étudiant : {adresse}")
    print(f"Travail enregistré dans : {base}")
    print("Laissez cette fenêtre ouverte pendant le travail ; fermez-la (ou Ctrl+C) pour arrêter.", flush=True)
    if not a.sans_navigateur:
        threading.Timer(1.0, lambda: webbrowser.open(adresse)).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
