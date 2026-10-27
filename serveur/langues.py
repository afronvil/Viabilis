# -*- coding: utf-8 -*-
"""Langues des messages du serveur (français, anglais, catalan ; italien, espagnol et allemand dans langues_autres.py).

Chaque message est écrit en français dans le code ; T(langue, message, **valeurs) donne sa traduction,
puis remplace les {champs}. Un message absent du dictionnaire reste en français.
Les textes des séances et des banques d'exercices ne sont pas traduits : ils restent ceux de l'enseignant."""
import re

from langues_autres import AUTRES, AUTRES_TEXTES

LANGUES = ("fr", "en", "ca", "it", "es", "de")
AUTRES_LANGUES = {"it": 0, "es": 1, "de": 2}           # rang dans AUTRES et AUTRES_TEXTES
# pour les consignes données à l'IA (rédigées en français) : la langue dans laquelle elle doit répondre
NOM_POUR_IA = {"fr": "en français", "en": "en anglais", "ca": "en catalan", "it": "en italien", "es": "en espagnol", "de": "en allemand"}

_D = {
    # ---- connexion, classe, droits
    "Ce serveur n'est pas en mode hors ligne.": ("This server is not in offline mode.", "Aquest servidor no és en mode fora de línia."),
    "Mode hors ligne : la page enseignant n'est pas disponible sur cet ordinateur.": (
        "Offline mode: the teacher page is not available on this computer.", "Mode fora de línia: la pàgina docent no està disponible en aquest ordinador."),
    "Mot de passe incorrect.": ("Wrong password.", "Contrasenya incorrecta."),
    "Session enseignant requise.": ("Teacher session required.", "Cal una sessió docent."),
    "Code de classe inconnu.": ("Unknown class code.", "Codi de classe desconegut."),
    # ---- banques d'exercices (.gift)
    "Banque introuvable.": ("Bank not found.", "Banc no trobat."),
    "Donnez un nom à la banque.": ("Give the bank a name.", "Doneu un nom al banc."),
    "Aucune question reconnue : vérifiez le format GIFT.": ("No question recognised: check the GIFT format.", "Cap pregunta reconeguda: comproveu el format GIFT."),
    "Une de vos banques porte déjà ce nom : choisissez-en un autre.": ("One of your banks already has this name: choose another one.", "Un dels vostres bancs ja té aquest nom: trieu-ne un altre."),
    # ---- documents PDF des séances
    "Le fichier n'est pas un PDF.": ("The file is not a PDF.", "El fitxer no és un PDF."),
    "PDF trop volumineux : {mo} Mo au plus.": ("PDF too large: {mo} MB at most.", "PDF massa gran: {mo} MB com a màxim."),
    "Document introuvable.": ("Document not found.", "Document no trobat."),
    "Aucun document pour cette séance.": ("No document for this session.", "Cap document per a aquesta sessió."),
    "Aucun texte lisible dans ce PDF (document scanné ?) : écrivez la consigne vous-même.": (
        "No readable text in this PDF (scanned document?): write the task yourself.", "Cap text llegible en aquest PDF (document escanejat?): escriviu la consigna vosaltres mateixos."),
    "L'IA n'a pas pu préparer la séance : {exc}.": ("The AI could not prepare the session: {exc}.", "La IA no ha pogut preparar la sessió: {exc}."),
    "Pseudonyme : 1 à 24 lettres, chiffres ou espaces.": ("Nickname: 1 to 24 letters, digits or spaces.", "Pseudònim: d'1 a 24 lletres, xifres o espais."),
    "Ce pseudonyme existe déjà. Si c'est le vôtre, touchez-le dans la liste ; sinon, choisissez-en un autre.": (
        "This nickname already exists. If it is yours, tap it in the list; otherwise, choose another one.",
        "Aquest pseudònim ja existeix. Si és el teu, toca'l a la llista; si no, tria'n un altre."),
    "Trop d'essais : demandez votre code personnel à votre enseignant.": (
        "Too many attempts: ask your teacher for your personal code.", "Massa intents: demana el teu codi personal al teu docent."),
    "Ce pseudonyme existe déjà. Si c'est le vôtre, entrez votre code personnel ; sinon, choisissez-en un autre.": (
        "This nickname already exists. If it is yours, enter your personal code; otherwise, choose another one.",
        "Aquest pseudònim ja existeix. Si és el teu, introdueix el teu codi personal; si no, tria'n un altre."),
    "Code personnel incorrect.": ("Wrong personal code.", "Codi personal incorrecte."),
    "Reconnectez-vous avec le code de la classe.": ("Log in again with the class code.", "Torna a connectar-te amb el codi de la classe."),
    "Ressource inconnue.": ("Unknown resource.", "Recurs desconegut."),
    "Requête invalide : {exc}": ("Invalid request: {exc}", "Petició no vàlida: {exc}"),
    "Classe inconnue.": ("Unknown class.", "Classe desconeguda."),
    "Séance introuvable pour cet élève.": ("Session not found for this student.", "No s'ha trobat la sessió per a aquest alumne."),
    "Import impossible : {exc}.": ("Import failed: {exc}.", "No s'ha pogut importar: {exc}."),
    "Séance inconnue.": ("Unknown session.", "Sessió desconeguda."),
    "Message vide.": ("Empty message.", "Missatge buit."),
    "Élève inconnu.": ("Unknown student.", "Alumne desconegut."),
    "Réponse de l'IA introuvable.": ("AI answer not found.", "No s'ha trobat la resposta de la IA."),
    "Tables de viabilité absentes du serveur.": ("Viability tables missing from the server.", "Falten les taules de viabilitat al servidor."),
    "Fichier vide.": ("Empty file.", "Fitxer buit."),
    # ---- séance de l'élève
    "Vous avez terminé définitivement cette séance : elle ne peut plus être modifiée.": (
        "You have finished this session for good: it can no longer be changed.", "Has acabat definitivament aquesta sessió: ja no es pot modificar."),
    "Une évaluation ne se reprend pas.": ("An assessment cannot be redone.", "Una avaluació no es pot reprendre."),
    "Cette séance n'est plus ouverte.": ("This session is no longer open.", "Aquesta sessió ja no és oberta."),
    "Pendant une évaluation, la vérification n'est pas disponible : votre enseignant corrigera.": (
        "During an assessment, checking is not available: your teacher will correct.",
        "Durant una avaluació, la comprovació no està disponible: el teu docent corregirà."),
    "Hors ligne, la vérification par l'IA n'est pas disponible.": ("Offline, checking by the AI is not available.", "Fora de línia, la comprovació per la IA no està disponible."),
    "Pendant une évaluation, pas d'IA ni de coup de pouce.": ("During an assessment, no AI and no hints.", "Durant una avaluació, ni IA ni pistes."),
    "Aucune séance ouverte.": ("No open session.", "Cap sessió oberta."),
    "Exercice inconnu pour cette séance.": ("Unknown exercise for this session.", "Exercici desconegut per a aquesta sessió."),
    "Exercice supprimé.": ("Exercise deleted.", "Exercici suprimit."),
    "Exercice déjà terminé.": ("Exercise already finished.", "Exercici ja acabat."),
    "Cette séance n'a pas encore été commencée.": ("This session has not been started yet.", "Aquesta sessió encara no s'ha començat."),
    "Commencez la séance avant de demander un coup de pouce.": ("Start the session before asking for a hint.", "Comença la sessió abans de demanar una pista."),
    "Il n'y a plus de coup de pouce : essayez avec ce que vous avez déjà.": (
        "There are no more hints: try with what you already have.", "No queden més pistes: prova-ho amb el que ja tens."),
    "La vérification n'est pas proposée pour cette séance.": ("Checking is not offered for this session.", "La comprovació no està disponible en aquesta sessió."),
    "Écrivez d'abord des idées.": ("Write some ideas first.", "Primer escriu algunes idees."),
    "Vous avez déjà vérifié {n} fois : relisez les retours et améliorez vos idées.": (
        "You have already checked {n} times: read the feedback again and improve your ideas.",
        "Ja has comprovat {n} vegades: rellegeix els retorns i millora les teves idees."),
    "La vérification n'a pas abouti. Réessayez dans un moment.": ("The checking did not succeed. Try again in a moment.", "La comprovació no ha funcionat. Torna-ho a provar d'aquí a una estona."),
    "Terminez d'abord la séance (« J'ai terminé »), puis vous pourrez la terminer définitivement.": (
        "First finish the session (\"I've finished\"), then you can finish it for good.",
        "Primer acaba la sessió («He acabat»), i després la podràs acabar definitivament."),
    "Vos idées ne sont pas corrigées automatiquement dans cette séance : votre enseignant les lira.": (
        "Your ideas are not corrected automatically in this session: your teacher will read them.",
        "Les teves idees no es corregeixen automàticament en aquesta sessió: el teu docent les llegirà."),
    "Hors ligne, vos idées ne peuvent pas être corrigées par l'IA : votre enseignant les lira après l'import.": (
        "Offline, your ideas cannot be corrected by the AI: your teacher will read them after the import.",
        "Fora de línia, la IA no pot corregir les teves idees: el teu docent les llegirà després de la importació."),
    "La correction n'a pas abouti. Réessayez dans un moment : votre séance n'est pas encore terminée définitivement.": (
        "The correction did not succeed. Try again in a moment: your session is not finished for good yet.",
        "La correcció no ha funcionat. Torna-ho a provar d'aquí a una estona: la teva sessió encara no està acabada definitivament."),
    "La correction est disponible quand la séance est terminée définitivement.": (
        "The correction is available once the session is finished for good.", "La correcció està disponible quan la sessió està acabada definitivament."),
    "Commencez la séance avant d'utiliser l'IA.": ("Start the session before using the AI.", "Comença la sessió abans de fer servir la IA."),
    "Aujourd'hui, vous travaillez sans l'IA.": ("Today, you work without the AI.", "Avui treballes sense la IA."),
    "Écrivez d'abord vos idées.": ("Write your ideas first.", "Primer escriu les teves idees."),
    "Nombre de questions à l'IA atteint pour cette séance.": ("Number of questions to the AI reached for this session.", "S'ha arribat al nombre de preguntes a la IA per a aquesta sessió."),
    "La clé d'API de l'IA est refusée : prévenez votre enseignant.": ("The AI's API key is refused: tell your teacher.", "La clau d'API de la IA és rebutjada: avisa el teu docent."),
    "L'IA n'a pas répondu. Réessayez dans un moment.": ("The AI did not answer. Try again in a moment.", "La IA no ha respost. Torna-ho a provar d'aquí a una estona."),
    "Je ne vais pas te donner de solution : c'est à toi de la trouver. Dis-moi plutôt comment tu cherches : quel calcul as-tu essayé, et qu'as-tu obtenu ?": (
        "I won't give you a solution: it's up to you to find it. Tell me instead how you are searching: which calculation did you try, and what did you get?",
        "No et donaré cap solució: et toca a tu trobar-la. Explica'm més aviat com busques: quin càlcul has provat i què n'has obtingut?"),
    # ---- exercices
    "Entrez un nombre.": ("Enter a number.", "Introdueix un nombre."),
    "pas de réponse": ("no answer", "cap resposta"),
    "Vrai": ("True", "Cert"),
    "Faux": ("False", "Fals"),
    "{v} (à {tol} près)": ("{v} (to within {tol})", "{v} (amb una tolerància de {tol})"),
    "Question {n} « {titre} » : texte libre, ignorée.": ("Question {n} \"{titre}\": free text, ignored.", "Pregunta {n} «{titre}»: text lliure, ignorada."),
    "Question {n} « {titre} » : format non reconnu ({exc}), ignorée.": (
        "Question {n} \"{titre}\": unrecognised format ({exc}), ignored.", "Pregunta {n} «{titre}»: format no reconegut ({exc}), ignorada."),
    "« {titre} » : contient une image, non importée ; le texte seul est gardé.": (
        "\"{titre}\": contains an image, not imported; only the text is kept.", "«{titre}»: conté una imatge, no importada; només es conserva el text."),
    "« {titre} » : type « {t} » non pris en charge, ignorée.": ("\"{titre}\": type \"{t}\" not supported, ignored.", "«{titre}»: tipus «{t}» no admès, ignorada."),
    "« {titre} » : aucune bonne réponse trouvée, ignorée.": ("\"{titre}\": no correct answer found, ignored.", "«{titre}»: no s'ha trobat cap resposta correcta, ignorada."),
    "Fichier XML illisible : {exc}": ("Unreadable XML file: {exc}", "Fitxer XML il·legible: {exc}"),
    # ---- vérification par calculs (verification.py)
    "Je ne reconnais pas un calcul. Écris-le avec des nombres et les signes +, −, × ou ÷.": (
        "I don't recognise a calculation. Write it with numbers and the signs +, −, × or ÷.",
        "No hi reconec cap càlcul. Escriu-lo amb nombres i els signes +, −, × o ÷."),
    "Tu utilises {n}, qui n'est pas autorisé ici. Avec quels nombres peux-tu remplacer ?": (
        "You use {n}, which is not allowed here. Which numbers could you use instead?",
        "Fas servir {n}, que aquí no està permès. Amb quins nombres el pots substituir?"),
    "Tu utilises {n} plusieurs fois : chaque nombre ne peut servir qu'une fois. Comment faire autrement ?": (
        "You use {n} several times: each number can only be used once. How else could you do it?",
        "Fas servir {n} diverses vegades: cada nombre només es pot fer servir una vegada. Com ho pots fer d'una altra manera?"),
    "Ce calcul vaut {v} : c'est trop. Que pourrais-tu changer pour obtenir {c} ?": (
        "This calculation equals {v}: that's too much. What could you change to get {c}?",
        "Aquest càlcul val {v}: és massa. Què podries canviar per obtenir {c}?"),
    "Ce calcul vaut {v} : ce n'est pas assez. Que pourrais-tu changer pour obtenir {c} ?": (
        "This calculation equals {v}: that's not enough. What could you change to get {c}?",
        "Aquest càlcul val {v}: no n'hi ha prou. Què podries canviar per obtenir {c}?"),
    "Juste, mais tu as déjà trouvé cette solution, peut-être dans un autre ordre.": (
        "Correct, but you have already found this solution, maybe in another order.",
        "Correcte, però ja has trobat aquesta solució, potser en un altre ordre."),
    "Juste : ce calcul vaut bien {c}.": ("Correct: this calculation does equal {c}.", "Correcte: aquest càlcul val {c}."),
    "Bravo : tu as trouvé {n} solutions différentes, c'est complet.": (
        "Well done: you found {n} different solutions, that's all of them.", "Molt bé: has trobat {n} solucions diferents, ja les tens totes."),
    "Tu as trouvé {n} solution différente. Il en existe d'autres : comment pourrais-tu ranger ta recherche pour n'en oublier aucune ?": (
        "You found {n} different solution. There are others: how could you organise your search so as not to miss any?",
        "Has trobat {n} solució diferent. N'hi ha d'altres: com podries ordenar la teva recerca per no oblidar-ne cap?"),
    "Tu as trouvé {n} solutions différentes. Il en existe d'autres : comment pourrais-tu ranger ta recherche pour n'en oublier aucune ?": (
        "You found {n} different solutions. There are others: how could you organise your search so as not to miss any?",
        "Has trobat {n} solucions diferents. N'hi ha d'altres: com podries ordenar la teva recerca per no oblidar-ne cap?"),
    "Tu as {n} idée juste et différente.": ("You have {n} correct and different idea.", "Tens {n} idea correcta i diferent."),
    "Tu as {n} idées justes et différentes.": ("You have {n} correct and different ideas.", "Tens {n} idees correctes i diferents."),
    "Range tes solutions dans un ordre (par exemple du plus grand nombre utilisé au plus petit) : tu verras mieux celles qui manquent.": (
        "Put your solutions in order (for example from the largest number used to the smallest): you will see better which ones are missing.",
        "Ordena les teves solucions (per exemple del nombre més gran utilitzat al més petit): veuràs millor les que falten."),
    "Tes solutions additionnent {k} nombres. As-tu essayé avec {m} nombres ?": (
        "Your solutions add {k} numbers. Have you tried with {m} numbers?", "Les teves solucions sumen {k} nombres. Has provat amb {m} nombres?"),
    "Avec {k} nombres, il existe d'autres solutions : change un nombre et compense avec un autre.": (
        "With {k} numbers, there are other solutions: change one number and make up for it with another.",
        "Amb {k} nombres, hi ha altres solucions: canvia un nombre i compensa-ho amb un altre."),
    "Dans tes solutions justes, le {g} est utilisé : {deja}. As-tu cherché des solutions où le {g} est utilisé {fois} ?": (
        "In your correct solutions, {g} is used: {deja}. Have you looked for solutions where {g} is used {fois}?",
        "En les teves solucions correctes, el {g} s'utilitza: {deja}. Has buscat solucions on el {g} s'utilitzi {fois}?"),
    "Quand le {g} est utilisé {fois}, il te manque encore des solutions. Essaie de découper un des autres nombres en plus petits.": (
        "When {g} is used {fois}, you are still missing some solutions. Try splitting one of the other numbers into smaller ones.",
        "Quan el {g} s'utilitza {fois}, encara et falten solucions. Prova de descompondre un dels altres nombres en de més petits."),
    "zéro fois": ("zero times", "cap vegada"), "une fois": ("once", "una vegada"), "deux fois": ("twice", "dues vegades"),
    "trois fois": ("three times", "tres vegades"), "{k} fois": ("{k} times", "{k} vegades"),
    "Relis la consigne et vérifie ton idée.": ("Read the instructions again and check your idea.", "Rellegeix la consigna i comprova la teva idea."),
    # ---- explications d'erreurs d'exercices par l'IA
    "Hors ligne, l'IA ne peut pas expliquer les erreurs : relisez le commentaire de l'exercice.": ("Offline, the AI cannot explain mistakes: read the exercise comment again.", "Fora de línia, la IA no pot explicar els errors: rellegeix el comentari de l'exercici."),
    "Votre enseignant n'a pas activé les explications de l'IA pour les exercices.": ("Your teacher has not turned on AI explanations for the exercises.", "El teu docent no ha activat les explicacions de la IA per als exercicis."),
    "Répondez d'abord à l'exercice.": ("Answer the exercise first.", "Respon primer l'exercici."),
    "Cette réponse est juste : il n'y a pas d'erreur à expliquer.": ("This answer is correct: there is no mistake to explain.", "Aquesta resposta és correcta: no hi ha cap error per explicar."),
    "Touchez d'abord « Comprendre mon erreur ».": ("First tap “Understand my mistake”.", "Toca primer «Entendre el meu error»."),
    "La remédiation est terminée pour cette réponse : réessayez l'exercice.": ("The remediation is over for this answer: try the exercise again.", "La remediació s'ha acabat per a aquesta resposta: torna a provar l'exercici."),
    "Relis l'énoncé mot par mot et compare-le à ta réponse : où se trouve la différence ? Pense à la règle que tu as apprise sur cette notion, puis réessaie.": ("Read the question word by word and compare it with your answer: where is the difference? Think of the rule you learned about this, then try again.", "Rellegeix l'enunciat paraula per paraula i compara'l amb la teva resposta: on és la diferència? Pensa en la regla que has après sobre aquesta noció i torna-ho a provar."),
}


# textes longs (mails), repérés par un nom : (français, anglais, catalan)
_TEXTES = {
    "MAIL_CONFIRMER": (
        "Bonjour,\n\nPour confirmer votre adresse et activer votre compte enseignant Viabilis, ouvrez ce lien (valable 48 heures) :\n\n{lien}\n\n"
        "Si vous n'avez pas demandé ce compte, ignorez ce mail : rien ne sera créé.\n\nViabilis",
        "Hello,\n\nTo confirm your address and activate your Viabilis teacher account, open this link (valid for 48 hours):\n\n{lien}\n\n"
        "If you did not ask for this account, ignore this email: nothing will be created.\n\nViabilis",
        "Bon dia,\n\nPer confirmar la vostra adreça i activar el vostre compte docent de Viabilis, obriu aquest enllaç (vàlid durant 48 hores):\n\n{lien}\n\n"
        "Si no heu demanat aquest compte, no feu cas d'aquest correu: no es crearà res.\n\nViabilis"),
    "MAIL_OUBLI": (
        "Bonjour,\n\nPour choisir un nouveau mot de passe Viabilis, ouvrez ce lien (valable une heure) :\n\n{lien}\n\n"
        "Si vous n'avez rien demandé, ignorez ce mail : votre mot de passe actuel reste valable.\n\nViabilis",
        "Hello,\n\nTo choose a new Viabilis password, open this link (valid for one hour):\n\n{lien}\n\n"
        "If you did not ask for anything, ignore this email: your current password remains valid.\n\nViabilis",
        "Bon dia,\n\nPer triar una contrasenya nova de Viabilis, obriu aquest enllaç (vàlid durant una hora):\n\n{lien}\n\n"
        "Si no heu demanat res, no feu cas d'aquest correu: la vostra contrasenya actual continua sent vàlida.\n\nViabilis"),
    "MAIL_DEJA": (
        "Bonjour,\n\nQuelqu'un a demandé à créer un compte Viabilis avec votre adresse, mais vous en avez déjà un. "
        "Si vous avez oublié votre mot de passe, ouvrez ce lien (valable une heure) pour en choisir un nouveau :\n\n{lien}\n\n"
        "Sinon, ignorez ce mail.\n\nViabilis",
        "Hello,\n\nSomeone asked to create a Viabilis account with your address, but you already have one. "
        "If you forgot your password, open this link (valid for one hour) to choose a new one:\n\n{lien}\n\nOtherwise, ignore this email.\n\nViabilis",
        "Bon dia,\n\nAlgú ha demanat crear un compte de Viabilis amb la vostra adreça, però ja en teniu un. "
        "Si heu oblidat la contrasenya, obriu aquest enllaç (vàlid durant una hora) per triar-ne una de nova:\n\n{lien}\n\n"
        "Si no, no feu cas d'aquest correu.\n\nViabilis"),
}
_TEXTES.update({
    "MAIL_DEMANDE": ("Bonjour,\n\nUne nouvelle demande de compte enseignant Viabilis attend votre décision.\n\n"
                     "Nom : {nom}\nAdresse (confirmée) : {email}\nPrésentation : {presentation}\n\n"
                     "Pour valider ou refuser, connectez-vous à Viabilis : carte « Comptes enseignants », sous vos classes.\n{lien}\n\nViabilis", "", ""),
    "MAIL_VALIDE": ("Bonjour,\n\nVotre compte enseignant Viabilis est ouvert. Connectez-vous avec votre adresse et votre mot de passe :\n\n{lien}\n\n"
                    "Vous ne verrez que vos propres classes.\n\nViabilis",
                    "Hello,\n\nYour Viabilis teacher account is open. Log in with your address and your password:\n\n{lien}\n\nYou will only see your own classes.\n\nViabilis",
                    "Bon dia,\n\nEl vostre compte docent de Viabilis és obert. Inicieu la sessió amb la vostra adreça i la vostra contrasenya:\n\n{lien}\n\n"
                    "Només veureu les vostres classes.\n\nViabilis"),
    "MAIL_REFUSE": ("Bonjour,\n\nVotre demande de compte Viabilis n'a pas été retenue. Pour toute question, répondez à l'administratrice de la plateforme.\n\nViabilis",
                    "Hello,\n\nYour Viabilis account request was not accepted. For any question, contact the platform administrator.\n\nViabilis",
                    "Bon dia,\n\nLa vostra sol·licitud de compte de Viabilis no s'ha acceptat. Per a qualsevol pregunta, adreceu-vos a l'administradora de la plataforma.\n\nViabilis"),
})
_D.update({
    "Indiquez votre nom : l'administratrice en a besoin pour valider votre demande.": (
        "Enter your name: the administrator needs it to approve your request.", "Indiqueu el vostre nom: l'administradora el necessita per validar la sol·licitud."),
    "Adresse confirmée. Votre demande est transmise à l'administratrice : vous recevrez un mail dès qu'elle l'aura validée.": (
        "Address confirmed. Your request has been sent to the administrator: you will receive an email as soon as she has approved it.",
        "Adreça confirmada. La vostra sol·licitud s'ha enviat a l'administradora: rebreu un correu quan l'hagi validada."),
    "Votre demande de compte attend la validation de l'administratrice : vous recevrez un mail.": (
        "Your account request is waiting for the administrator's approval: you will receive an email.",
        "La vostra sol·licitud de compte espera la validació de l'administradora: rebreu un correu."),
    "Réservé à l'administratrice.": ("Reserved for the administrator.", "Reservat a l'administradora."),
    "Compte inconnu.": ("Unknown account.", "Compte desconegut."),
    "Ce compte a déjà servi : suspendez-le plutôt.": ("This account has already been used: suspend it instead.", "Aquest compte ja s'ha fet servir: suspeneu-lo."),
    "Viabilis : votre compte est ouvert": ("Viabilis: your account is open", "Viabilis: el vostre compte és obert"),
    "Viabilis : votre demande de compte": ("Viabilis: your account request", "Viabilis: la vostra sol·licitud de compte"),
})
_D.update({
    "Si cette adresse peut recevoir un compte, un mail vient de lui être envoyé. Pensez à regarder dans les indésirables.": (
        "If this address can receive an account, an email has just been sent to it. Remember to check your spam folder.",
        "Si aquesta adreça pot rebre un compte, s'hi acaba d'enviar un correu. Mireu també el correu brossa."),
    "Adresse refusée : seules les adresses {domaines} peuvent créer un compte.": (
        "Address refused: only {domaines} addresses can create an account.", "Adreça rebutjada: només les adreces {domaines} poden crear un compte."),
    "Le mot de passe doit faire au moins 10 caractères.": ("The password must be at least 10 characters long.", "La contrasenya ha de tenir almenys 10 caràcters."),
    "Trop de demandes : réessayez dans une heure.": ("Too many requests: try again in an hour.", "Massa peticions: torneu-ho a provar d'aquí a una hora."),
    "Viabilis : vous avez déjà un compte": ("Viabilis: you already have an account", "Viabilis: ja teniu un compte"),
    "Viabilis : confirmez votre adresse": ("Viabilis: confirm your address", "Viabilis: confirmeu la vostra adreça"),
    "Viabilis : nouveau mot de passe": ("Viabilis: new password", "Viabilis: contrasenya nova"),
    "Ce lien n'est plus valable. Recommencez l'inscription pour en recevoir un nouveau.": (
        "This link is no longer valid. Sign up again to receive a new one.", "Aquest enllaç ja no és vàlid. Torneu a fer la inscripció per rebre'n un de nou."),
    "Adresse confirmée. Vous pouvez vous connecter.": ("Address confirmed. You can log in.", "Adreça confirmada. Ja podeu iniciar la sessió."),
    "Trop d'essais : attendez un quart d'heure, ou utilisez « Mot de passe oublié ».": (
        "Too many attempts: wait a quarter of an hour, or use \"Forgot password\".", "Massa intents: espereu un quart d'hora, o feu servir «He oblidat la contrasenya»."),
    "Adresse ou mot de passe incorrect.": ("Wrong address or password.", "Adreça o contrasenya incorrectes."),
    "Confirmez d'abord votre adresse : ouvrez le lien reçu par mail.": ("First confirm your address: open the link you received by email.",
                                                                        "Primer confirmeu la vostra adreça: obriu l'enllaç que heu rebut per correu."),
    "Ce lien n'est plus valable. Demandez-en un nouveau avec « Mot de passe oublié ».": (
        "This link is no longer valid. Ask for a new one with \"Forgot password\".", "Aquest enllaç ja no és vàlid. Demaneu-ne un de nou amb «He oblidat la contrasenya»."),
    "Mot de passe changé. Vous pouvez vous connecter.": ("Password changed. You can log in.", "Contrasenya canviada. Ja podeu iniciar la sessió."),
})


def T(langue, message, **valeurs):
    """Message traduit dans `langue` (fr, en, ca), avec ses {champs} remplis."""
    if message in _TEXTES:
        k = AUTRES_LANGUES.get(langue)
        if k is not None:                                  # italien, espagnol, allemand ; sinon le français
            message = (AUTRES_TEXTES.get(message) or ("", "", ""))[k] or _TEXTES[message][0]
        else:
            message = _TEXTES[message][{"en": 1, "ca": 2}.get(langue, 0)]
    elif langue in ("en", "ca") and message in _D:
        message = _D[message][0 if langue == "en" else 1]
    elif langue in AUTRES_LANGUES and message in AUTRES:
        message = AUTRES[message][AUTRES_LANGUES[langue]]
    return message.format(**valeurs) if valeurs else message


def langue_valide(l):
    return l if l in LANGUES else "fr"


def _motif(modele):
    vus, morceaux = set(), []
    for texte, champ in re.findall(r"([^{]*)(?:\{(\w+)\})?", modele):
        morceaux.append(re.escape(texte))
        if champ:
            morceaux.append(f"(?P={champ})" if champ in vus else f"(?P<{champ}>.+?)")
            vus.add(champ)
    return re.compile("".join(morceaux), re.S)


_MOTIFS = [(m, _motif(m)) for m in _D if "{" in m]


def traduire_texte(langue, texte):
    """Traduit un message déjà rempli en français (par exemple « 12 (à 0,5 près) ») en retrouvant son modèle."""
    if langue not in LANGUES[1:] or not isinstance(texte, str) or not texte:
        return texte
    if texte in _D:
        return T(langue, texte)
    for modele, rx in _MOTIFS:
        m = rx.fullmatch(texte)
        if m:
            return T(langue, modele, **m.groupdict())
    return texte
