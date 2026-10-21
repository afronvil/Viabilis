# -*- coding: utf-8 -*-
"""
Génère les banques d'exercices GIFT « Système d'exploitation et Linux » (M1 de microbiologie, étudiants qui n'ont
jamais utilisé de terminal), d'après le cours « Système d'exploitation — M1 Microbiologie » (A. Fronville) :
cours de 4 h, une banque par séance des modèles lin-* :
linux_niveau1.gift (système d'exploitation, GNU/Linux, installation, arborescence, fichiers, méta-caractères ; séance 1),
linux_niveau2.gift (utilisateurs, droits d'accès, processus ; séance 2),
linux_niveau3.gift (le shell : variables, enchaînements ; traitement de fichiers texte : wc, awk, sed ; séance 3),
linux_evaluation.gift (évaluation finale de 30 minutes, à importer au niveau 5).

Chaque commande est EXÉCUTÉE ici avec bash, dans un dossier temporaire qui imite /home/lea : la bonne réponse est
la sortie réelle de la commande. Pour les questions « quelle commande ? », chaque proposition est exécutée et seule
la bonne doit donner le résultat attendu. Les sorties retenues sont les mêmes sous Linux, macOS et WSL.
Usage : python3 generer_banques_linux.py   (depuis ce dossier)
"""
import os
import shutil
import subprocess
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))

# fichiers des séances (les mêmes que dans les consignes des modèles lin-*)
COMPTAGES = """echantillon milieu espece colonies
E1 LB E_coli 230
E2 LB S_aureus 45
E3 MH E_coli 1200
E4 MH P_aeruginosa 8
E5 LB E_coli 150
E6 MH S_aureus 87
E7 LB P_aeruginosa 310
E8 MH E_coli 64
"""
FASTA = """>Ecoli_frag1
ATGGCGAATTCGTTAGCCGATAA
>Saureus_frag2
ATGGAATTCAAAGGTTGATGA
>Paeruginosa_frag3
ATGCCGGGCGCCGGCTGA
"""
SOUCHES_CSV = """souche;espece;gram;origine
S1;Escherichia coli;negatif;urine
S2;Staphylococcus aureus;positif;peau
S3;Pseudomonas aeruginosa;negatif;eau
S4;Enterococcus faecalis;positif;selles
S5;Klebsiella pneumoniae;negatif;urine
"""
SOUCHES = ["souche1.fasta", "souche2.fasta", "souche12.fasta", "gelA.png", "gelB.png", "notes.txt"]


def echapper(t):
    t = t.replace("\\", "\\\\")
    for c in "~=#{}:":
        t = t.replace(c, "\\" + c)
    return t


def executer(commande, dossiers=(), fichiers=None, ou="", prep=""):
    """Exécute la commande avec bash dans /home/lea/<ou> (simulé), après la préparation prep (non affichée) ;
    renvoie (sortie, erreur, code, contenu des fichiers)."""
    racine = os.path.realpath(tempfile.mkdtemp())
    maison = os.path.join(racine, "home", "lea")
    os.makedirs(maison)
    for d in dossiers:
        os.makedirs(os.path.join(maison, d), exist_ok=True)
    for nom, contenu in (fichiers or {}).items():
        chemin = os.path.join(maison, nom)
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "w") as f:
            f.write(contenu)
    script = "umask 022\n" + (prep + " >/dev/null 2>&1\n" if prep else "") + commande
    p = subprocess.run(["bash", "-c", script], cwd=os.path.join(maison, ou), capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": maison, "LC_ALL": "C"})
    sortie = "\n".join(l.strip() for l in p.stdout.replace(racine, "").strip().splitlines())   # wc aligne ses nombres sous macOS
    etat = {}
    for base, _, noms in os.walk(maison):
        for n in noms:
            etat[os.path.relpath(os.path.join(base, n), maison)] = open(os.path.join(base, n)).read()
    shutil.rmtree(racine)
    return sortie, p.stderr, p.returncode, etat


def enonce(intro, commande, fichiers=None, ou="", montrer=()):
    lignes = [intro]
    for nom in montrer:
        lignes += [f"Contenu de {nom} :", fichiers[nom].rstrip("\n")]
    invite = "~" + ("/" + ou if ou else "")
    lignes += [f"lea@pc:{invite}$ " + l for l in commande.split(" ; ")]
    return "\n".join(lignes)


CLES = ("dossiers", "fichiers", "ou", "prep")


def num(titre, intro, commande, **k):
    s = executer(commande.replace(" ; ", "\n"), **{x: k[x] for x in CLES if x in k})[0]
    s = s.splitlines()[-1]
    int(s)
    return f"::{echapper(titre)}::{echapper(enonce(intro, commande, k.get('fichiers'), k.get('ou', ''), k.get('montrer', ())))}{{#{s}}}"


def qcm(titre, intro, commande, leurres, **k):
    s = executer(commande.replace(" ; ", "\n"), **{x: k[x] for x in CLES if x in k})[0]
    assert s, (titre, "sortie vide")
    l = [x for x in leurres if x != s]
    assert len(l) >= 3, (titre, s)
    return f"::{echapper(titre)}::{echapper(enonce(intro, commande, k.get('fichiers'), k.get('ou', ''), k.get('montrer', ())))}{{={echapper(s)} " + " ".join("~" + echapper(x) for x in l) + "}"


def quelle_commande(titre, question, bonne, autres, verifier, **k):
    """Chaque proposition est exécutée : seule la bonne doit satisfaire verifier(sortie, contenu des fichiers)."""
    a = {x: k[x] for x in CLES if x in k}
    r = executer(bonne, **a)
    assert verifier(r[0], r[3]), (titre, bonne, r)
    for c in autres:
        r = executer(c, **a)
        assert not verifier(r[0], r[3]), (titre, c, "donne aussi le résultat")
    return f"::{echapper(titre)}::{echapper(question)}{{={echapper(bonne)} " + " ".join("~" + echapper(c) for c in autres) + "}"


def choix(titre, question, bonne, leurres):
    """Question de cours, sans commande à exécuter."""
    return f"::{echapper(titre)}::{echapper(question)}{{={echapper(bonne)} " + " ".join("~" + echapper(x) for x in leurres) + "}"


def vf(titre, texte, valeur, retour):
    return f"::{echapper(titre)}::{echapper(texte)}{{{'T' if valeur else 'F'}#{echapper(retour)}#{echapper('Exact. ' + retour)}}}"


QUE = "Qu'affiche la dernière commande ?"
C = {"comptages.txt": COMPTAGES}
F = {"sequences.fasta": FASTA}
S = {n: "" for n in SOUCHES}
CSV = {"souches.csv": SOUCHES_CSV}


def niveau1():
    """Séances 1 et 2 : le système d'exploitation, GNU/Linux, l'installation et les systèmes de fichiers."""
    q = []
    q.append(choix("Le rôle du système", "Quel est le rôle d'un système d'exploitation ?",
                   "Faire le lien entre le matériel de l'ordinateur et les applications de l'utilisateur",
                   ["Écrire les programmes à la place de l'utilisateur", "Protéger l'ordinateur contre les virus, et seulement cela", "Afficher les pages web"]))
    q.append(choix("Le noyau", "Laquelle de ces tâches n'est PAS assurée par le noyau ?",
                   "Corriger l'orthographe d'un document", ["Répartir le temps de processeur entre les processus", "Attribuer la mémoire à chaque processus", "Piloter les périphériques"]))
    q.append(choix("Noyau et shell", "Dans un système Linux, qu'est-ce que le shell ?",
                   "L'interpréteur qui lit les commandes tapées et lance les programmes correspondants",
                   ["Le noyau, qui gère la mémoire et les processeurs", "Le dossier qui contient les fichiers de l'utilisateur", "Une interface graphique"]))
    q.append(vf("Logiciel libre", "Un logiciel libre donne le droit de l'exécuter, d'étudier et de modifier son code source, et de le redistribuer, modifié ou non.", True,
                "Vrai : ce sont les quatre libertés du logiciel libre. Linux est distribué sous la licence libre GPL."))
    q.append(choix("GNU et Linux", "Qui a lancé le projet GNU, et en quelle année ?", "Richard Stallman, en 1983",
                   ["Linus Torvalds, en 1991", "Linus Torvalds, en 1983", "Richard Stallman, en 1991"]))
    q.append(choix("Les systèmes de fichiers", "Quel système de fichiers est propre à Linux ?", "ext4", ["ntfs", "fat", "iso 9660"]))
    q.append(choix("L'arborescence", "Où se trouvent les fichiers de configuration du système ?", "/etc", ["/home", "/tmp", "/dev"]))
    q.append(choix("df et du", "Quelle commande affiche la place libre de chaque système de fichiers et son point de montage ?", "df -h",
                   ["du -sh", "ls -l", "mount -a"]))
    return "Le système d'exploitation, GNU/Linux, l'installation et les systèmes de fichiers", q


def niveau2():
    """Séance 3 : se déplacer et manipuler des fichiers, méta-caractères."""
    q = []
    q.append(qcm("Se déplacer", "Le répertoire personnel de Léa est /home/lea. Elle tape les commandes suivantes. " + QUE,
                 "cd projet_microbio ; cd donnees ; cd .. ; pwd", ["/home/lea/projet_microbio/donnees", "/home/lea", "/projet_microbio", "/home/lea/donnees"],
                 dossiers=["projet_microbio/donnees"]))
    r = executer("mkdir projet/donnees")
    assert r[2] != 0 and "No such file" in r[1]
    q.append(choix("Créer un sous-répertoire", "Dans un répertoire vide, Léa tape :\nlea@pc:~$ mkdir projet/donnees\nQue se passe-t-il ?",
                   "Une erreur : le répertoire projet n'existe pas (il faudrait mkdir -p)", ["Les répertoires projet et donnees sont créés",
                   "Un fichier nommé projet/donnees est créé", "Le répertoire donnees est créé dans le répertoire courant"]))
    q.append(qcm("Renommer", "Le répertoire ne contient que notes.txt. " + QUE, "mv notes.txt journal.txt ; ls",
                 ["notes.txt", "journal.txt notes.txt", "notes.txt journal.txt", "Une erreur"], fichiers={"notes.txt": "souche E. coli K-12\n"}))
    q.append(qcm("Copier", "Le répertoire contient notes.txt et un répertoire resultats vide. " + QUE, "cp notes.txt resultats/ ; ls resultats",
                 ["resultats", "Rien : resultats est vide", "Une erreur", "notes.txt resultats"], fichiers={"notes.txt": "x\n"}, dossiers=["resultats"]))
    q.append(vf("Supprimer", "Un fichier supprimé avec rm part dans la corbeille : on peut le récupérer.", False,
                "Faux : rm supprime définitivement, sans corbeille. rm * vide tout le répertoire courant : vérifie avant avec ls."))
    q.append(qcm("Le méta-caractère ?", "Le répertoire contient souche1.fasta, souche2.fasta, souche12.fasta, gelA.png, gelB.png et notes.txt. echo affiche les noms que le shell a substitués au modèle. " + QUE,
                 "echo souche?.fasta", ["souche1.fasta souche2.fasta souche12.fasta", "souche12.fasta", "souche?.fasta", "souche1.fasta"], fichiers=S))
    q.append(num("Le méta-caractère *", "Même répertoire. " + QUE, "ls *.fasta | wc -l", fichiers=S))
    q.append(qcm("Les crochets", "Même répertoire. " + QUE, "echo gel[AB].png", ["gelA.png", "gel[AB].png", "gelAB.png", "Une erreur"], fichiers=S))
    return "Se déplacer et manipuler des fichiers", q


def niveau3():
    """Séances 4 et 5 : utilisateurs, droits d'accès, processus."""
    q = []
    q.append(choix("Lire ls -l", "ls -l affiche : -rw-r--r-- 1 lea lea 1200 oct 19 12:39 comptages.txt. Que signifie -rw-r--r-- ?",
                   "Un fichier ordinaire : le propriétaire peut le lire et le modifier, le groupe et les autres peuvent seulement le lire",
                   ["Un répertoire que tout le monde peut modifier", "Un fichier que seul le propriétaire peut lire", "Un programme exécutable par tous"]))
    q.append(qcm("Retirer un droit", "comptages.txt a les droits -rw-r--r--. " + QUE, "chmod u-w comptages.txt ; ls -l comptages.txt | cut -c 1-10",
                 ["-rw-r--r--", "-rw-r-----", "--w-r--r--", "-r--r-----"], fichiers=C))
    q.append(qcm("Rendre exécutable", "bonjour.sh a les droits -rw-r--r--. " + QUE, "chmod u+x bonjour.sh ; ls -l bonjour.sh | cut -c 1-10",
                 ["-rwxrwxrwx", "-rw-r--r-x", "-rw-r--r--", "xrw-r--r--"], fichiers={"bonjour.sh": "echo Bonjour\n"}))
    q.append(qcm("Affecter des droits", "liste.txt a les droits -rw-r--r--. " + QUE, "chmod u=rw,g=r,o= liste.txt ; ls -l liste.txt | cut -c 1-10",
                 ["-rw-r--r--", "-rw-rw----", "-rwxr-----", "-r--r-----"], fichiers={"liste.txt": "x\n"}))
    q.append(qcm("Le masque", "Dans un répertoire vide. " + QUE, "umask 027 ; touch f ; ls -l f | cut -c 1-10",
                 ["-rw-r--r--", "-rwxr-x---", "----w-rwx", "-rw-rw-rw-"]))
    q.append(choix("Préemptif", "Pourquoi dit-on que Linux est un système multitâche préemptif ?",
                   "Il peut interrompre n'importe quel programme à tout moment pour donner le processeur à un autre",
                   ["Il attend que chaque application lui rende la main", "Il n'exécute qu'un programme à la fois", "Il réserve le processeur à l'administrateur"]))
    q.append(choix("PID et PPID", "Dans ps -ef, que désigne la colonne PPID ?", "Le numéro du processus père, celui qui a lancé le processus",
                   ["Le numéro du processus lui-même", "La priorité du processus", "Le terminal sur lequel il s'exécute"]))
    q.append(choix("Arrêter un processus", "Léa lance sleep 300 &. ps indique le PID 4321 pour sleep. Que fait kill -9 4321 ?",
                   "Il force l'arrêt du processus (signal 9, SIGKILL)", ["Il demande poliment l'arrêt (signal 15), que le processus peut refuser",
                   "Il suspend le processus pendant 9 secondes", "Il arrête les 9 derniers processus lancés"]))
    return "Utilisateurs, droits d'accès et processus", q


def niveau4():
    """Séance 6 : le shell, ses variables et l'enchaînement des commandes."""
    q = []
    q.append(qcm("Une variable", "Dans un terminal, Léa tape les commandes suivantes. " + QUE, "projet=donnees ; echo $projet",
                 ["projet", "$projet", "projet=donnees", "Une erreur"]))
    r = executer("projet = donnees")
    assert r[2] != 0 and "command not found" in r[1]
    q.append(choix("Pas d'espace autour de =", "Léa tape projet = donnees (avec des espaces). Que se passe-t-il ?",
                   "Une erreur : le shell cherche une commande nommée projet", ["La variable projet vaut donnees", "La variable projet vaut « = donnees »", "Rien"]))
    q.append(qcm("La variable HOME", "Le répertoire personnel de Léa est /home/lea. " + QUE, "cd / ; cd $HOME ; pwd", ["/", "$HOME", "/home", "/root"]))
    q.append(vf("Modifier PATH", "La commande PATH=\"$HOME/bin\" ajoute $HOME/bin à la liste des répertoires où le shell cherche les commandes.", False,
                "Faux : elle remplace toute la liste, et des commandes comme ls deviennent introuvables (il faut alors rouvrir le terminal). Pour ajouter un répertoire : PATH=\"$PATH:$HOME/bin\"."))
    q.append(qcm("&& et ||", "Le répertoire ne contient pas de répertoire tmp. Après le message d'erreur de cd, qu'affiche la commande ?", "cd tmp || echo absent",
                 ["tmp", "Rien d'autre", "absent tmp", "present"]))
    q.append(qcm("&& enchaîne si tout va bien", "Dans un répertoire vide. " + QUE, "mkdir test && cd test && pwd",
                 ["/home/lea", "test", "/test", "Une erreur"]))
    q.append(num("Les guillemets", "notes.txt contient trois lignes : « souche E coli K12 », « E coli isolée en 2023 » et « S aureus ». " + QUE,
                 "grep -c \"E coli\" notes.txt", fichiers={"notes.txt": "souche E coli K12\nE coli isolée en 2023\nS aureus\n"}))
    q.append(choix("Un alias permanent", "Léa a créé alias ll='ls -l'. Comment le garder pour ses prochaines sessions ?",
                   "En ajoutant la ligne alias ll='ls -l' à son fichier ~/.bashrc (~/.zshrc sous macOS)",
                   ["Il est gardé automatiquement", "En tapant save alias", "En le copiant dans /tmp"]))
    return "Le shell : variables, alias et enchaînements", q


def niveau5():
    """Séance 7 : traitement de fichiers texte avec wc, awk et sed."""
    q = []
    q.append(num("Compter les lignes", "comptages.txt est le fichier de la séance (une ligne d'en-tête, puis un échantillon par ligne). " + QUE,
                 "wc -l < comptages.txt", fichiers=C, montrer=["comptages.txt"]))
    q.append(qcm("Une colonne avec awk", "Même fichier. " + QUE, "awk 'NR==3 {print $3}' comptages.txt", ["E2", "LB", "45", "E_coli"], fichiers=C))
    q.append(num("Le nombre de lignes avec awk", "Même fichier. " + QUE, "awk 'END {print NR}' comptages.txt", fichiers=C))
    q.append(num("Additionner une colonne", "Même fichier. " + QUE, "awk 'NR>1 {s = s + $4} END {print s}' comptages.txt", fichiers=C))
    q.append(num("Les boîtes comptables", "Une boîte est comptable entre 30 et 300 colonies. Même fichier. " + QUE,
                 "awk '$4>=30 && $4<=300' comptages.txt | wc -l", fichiers=C))
    q.append(num("Changer de séparateur", "souches.csv utilise le point-virgule comme séparateur. " + QUE,
                 "awk -F \";\" '$3==\"negatif\"' souches.csv | wc -l", fichiers=CSV, montrer=["souches.csv"]))
    q.append(qcm("Remplacer avec sed", "comptages.txt est le fichier de la séance. " + QUE, "sed -n '2p' comptages.txt | sed 's/_/ /g'",
                 ["E1 LB E_coli 230", "E1 LB E coli", "echantillon milieu espece colonies", "E1_LB_E_coli_230"], fichiers=C))
    q.append(num("Garder les séquences", "sequences.fasta contient 3 séquences, chacune sur une ligne après sa ligne de titre >. " + QUE,
                 "sed '/^>/d' sequences.fasta | wc -l", fichiers=F, montrer=["sequences.fasta"]))
    return "Traitement de fichiers texte : wc, awk et sed", q


def evaluation():
    """Évaluation finale (30 min) : douze questions nouvelles, une par grande notion du cours, absentes des banques des séances."""
    q = []
    q.append(choix("Le noyau", "Qu'est-ce que le noyau d'un système d'exploitation ?",
                   "La partie centrale, qui gère la mémoire, les processus et les périphériques",
                   ["L'interface graphique du système", "Le premier logiciel installé par l'utilisateur", "Le dossier personnel de l'administrateur"]))
    q.append(choix("Les fichiers temporaires", "Dans quel répertoire se trouvent les fichiers temporaires ?", "/tmp", ["/etc", "/home", "/bin"]))
    q.append(qcm("Remonter de deux niveaux", "Le répertoire personnel de Léa est /home/lea. " + QUE, "cd projet/donnees ; cd ../.. ; pwd",
                 ["/home/lea/projet", "/home", "/", "/home/lea/projet/donnees"], dossiers=["projet/donnees"]))
    q.append(num("Un seul caractère", "Le répertoire contient a1.txt, a2.txt, a10.txt et b1.txt. " + QUE, "ls a?.txt | wc -l",
                 fichiers={"a1.txt": "", "a2.txt": "", "a10.txt": "", "b1.txt": ""}))
    q.append(qcm("Copier sous un autre nom", "Le répertoire ne contient que notes.txt. " + QUE, "cp notes.txt sauvegarde.txt ; echo *",
                 ["sauvegarde.txt", "notes.txt", "notes.txt notes.txt", "Une erreur"], fichiers={"notes.txt": "x\n"}))
    q.append(qcm("Retirer la lecture", "comptages.txt a les droits -rw-r--r--. " + QUE, "chmod go-r comptages.txt ; ls -l comptages.txt | cut -c 1-10",
                 ["-rw-r--r--", "-r--------", "-rw-r-----", "----r--r--"], fichiers=C))
    q.append(qcm("Droits d'un répertoire", "Dans un répertoire vide. " + QUE, "mkdir d ; chmod u=rwx,g=rx,o= d ; ls -ld d | cut -c 1-10",
                 ["drwxr-xr-x", "-rwxr-x---", "drwx------", "drwxrwx---"]))
    q.append(choix("Le PID", "Dans la liste affichée par ps -ef, que désigne la colonne PID ?", "Le numéro du processus",
                   ["Le numéro du processus père", "Le nom de l'utilisateur", "La mémoire utilisée"]))
    q.append(qcm("|| deux fois", "Dans un répertoire vide, Léa tape deux fois de suite la même commande. Après le message d'erreur de mkdir, qu'affiche la seconde ?",
                 "mkdir test || echo échec ; mkdir test || echo échec", ["Rien d'autre", "test", "échec échec", "créé"]))
    q.append(num("Valeurs distinctes", "comptages.txt est le fichier de la séance 3 (une ligne d'en-tête). Attention à l'en-tête. " + QUE,
                 "awk '{print $2}' comptages.txt | sort | uniq | wc -l", fichiers=C, montrer=["comptages.txt"]))
    q.append(num("Total par milieu", "Même fichier. " + QUE, "awk 'NR>1 && $2==\"MH\" {s = s + $4} END {print s}' comptages.txt", fichiers=C))
    q.append(qcm("Afficher une ligne et remplacer", "Même fichier. " + QUE, "sed -n '3p' comptages.txt | sed 's/E2/Echantillon 2/'",
                 ["E2 LB S_aureus 45", "Echantillon 2 LB E_coli 230", "Echantillon 2", "E1 LB E_coli 230"], fichiers=C))
    return "Évaluation finale", q


if __name__ == "__main__":
    # cours de 4 h : une banque par séance, puis l'évaluation (importée au niveau 5)
    banques = (("linux_niveau1", "Le système, l'arborescence et les fichiers", lambda: niveau1()[1] + niveau2()[1]),
               ("linux_niveau2", "Utilisateurs, droits d'accès et processus", lambda: niveau3()[1]),
               ("linux_niveau3", "Le shell et le traitement de fichiers texte", lambda: niveau4()[1] + niveau5()[1]),
               ("linux_evaluation", "Évaluation finale (30 minutes)", lambda: evaluation()[1]))
    for nom, theme, f in banques:
        qs = f()
        lignes = [f"// M1 de microbiologie — Système d'exploitation et Linux (4 h) — {theme}",
                  "// Réponses obtenues en exécutant chaque commande avec bash (generer_banques_linux.py).",
                  f"$CATEGORY: Master/Linux/{theme}", ""]
        with open(os.path.join(ICI, f"{nom}.gift"), "w", encoding="utf-8") as fd:
            fd.write("\n".join(lignes + [q + "\n" for q in qs]))
        print(f"{nom}.gift : {len(qs)} questions")
