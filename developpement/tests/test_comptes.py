# Comptes enseignants : demande avec un mail confirmé, validation par l'administratrice, chacun ne voit que ses classes, mot de passe oublié.
#   VIABILIS_ADMIN=anne@exemple.fr VIABILIS_MAIL_DOSSIER=/tmp/mails23 VIABILIS_IA=fausse python3 serveur.py --port 8817 --base /tmp/t23.sqlite3
# Arguments : port, base, dossier des mails (ceux de la ligne ci-dessus par défaut).
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import email, glob, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
PORT = sys.argv[1] if len(sys.argv) > 1 else "8817"
BASE = sys.argv[2] if len(sys.argv) > 2 else "/tmp/t23.sqlite3"
MAILS = sys.argv[3] if len(sys.argv) > 3 else "/tmp/mails23"
B = f"http://127.0.0.1:{PORT}/api/"
n_ok = 0
def r(m, p, c=None, j=None):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(q) as x:
            return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
def ok(cond, msg):
    global n_ok
    assert cond, msg
    n_ok += 1
    print("OK  ", msg)
def dernier_mail(dest, avant):
    for _ in range(50):
        for f in sorted(glob.glob(os.path.join(MAILS, "*.eml")), reverse=True):
            m = email.message_from_bytes(open(f, "rb").read())
            if f not in avant and m["To"] == dest:
                return m["Subject"], m.get_payload(decode=True).decode()
        time.sleep(0.1)
    raise AssertionError("aucun mail pour " + dest)
def deja():
    return set(glob.glob(os.path.join(MAILS, "*.eml")))
lien = lambda texte, nom: re.search(nom + r"=([\w-]+)", texte).group(1)

ok(r("GET", "enseignant/mode")[1] == {"comptes": True, "domaines": [], "validation": True}, "le serveur annonce des comptes validés par l'administratrice")
ok(r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[0] == 401, "l'ancien mot de passe unique ne sert plus")
os.environ["VIABILIS_DOMAINES"] = "exemple.fr,*.academie.fr"           # limite facultative des adresses (vérifiée sans serveur)
sys.path.insert(0, SERVEUR)
import comptes
ok(comptes.email_valide("a@exemple.fr") and comptes.email_valide("b@lycee.academie.fr") and not comptes.email_valide("etu@etudiant.exemple.fr")
   and not comptes.email_valide("x@ailleurs.com"), "domaines facultatifs : domaine exact, sous-domaines seulement avec *.")
del os.environ["VIABILIS_DOMAINES"]
ok(r("POST", "enseignant/inscription", {"email": "pas-une-adresse", "motdepasse": "unmotdepasse-long", "nom": "X"})[0] == 400, "adresse mal formée refusée")
ok(r("POST", "enseignant/inscription", {"email": "etudiant@gmail.com", "motdepasse": "unmotdepasse-long"})[0] == 400, "une demande sans nom est refusée")
ok(r("POST", "enseignant/inscription", {"email": "anne@exemple.fr", "motdepasse": "court"})[0] == 400, "mot de passe trop court refusé")

# classe créée avant les comptes : elle reviendra à VIABILIS_PROPRIETAIRE
with sqlite3.connect(BASE) as c:
    c.execute("INSERT INTO classes (code, nom, config, cree) VALUES ('ANCIEN', 'Classe d''avant', '{}', '2026-01-01T00:00:00')")

av = deja()
s, d = r("POST", "enseignant/inscription", {"email": "Anne@Exemple.fr", "motdepasse": "anne-mot-de-passe"})
ok(s == 200 and "mail" in d["message"], "inscription : réponse neutre")
sujet, texte = dernier_mail("anne@exemple.fr", av)
ok("confirmez" in sujet and "/enseignant/?confirmer=" in texte, "mail de confirmation reçu, avec le lien")
jc = lien(texte, "confirmer")
ok(r("POST", "enseignant/connexion", {"email": "anne@exemple.fr", "motdepasse": "anne-mot-de-passe"})[0] == 403, "pas de connexion avant la confirmation")
ok(r("POST", "enseignant/confirmer", {"jeton": jc})[0] == 200, "adresse confirmée par le lien")
ok(r("POST", "enseignant/confirmer", {"jeton": jc})[0] == 400, "le lien ne sert qu'une fois")
ok(r("POST", "enseignant/connexion", {"email": "anne@exemple.fr", "motdepasse": "mauvais-mot-de-passe"})[0] == 401, "mauvais mot de passe refusé")
s, d = r("POST", "enseignant/connexion", {"email": "anne@exemple.fr", "motdepasse": "anne-mot-de-passe"})
ok(s == 200 and d["email"] == "anne@exemple.fr", "connexion avec l'adresse et le mot de passe")
JA = d["jeton"]
ok(d["admin"] is True, "l'administratrice est reconnue (son compte s'ouvre sans validation)")
ok([x["code"] for x in r("GET", "classes", j=JA)[1]] == ["ANCIEN"], "les classes d'avant les comptes reviennent à l'administratrice")
ca = r("POST", "classes", {"nom": "Classe d'Anne"}, JA)[1]["code"]

av = deja()
r("POST", "enseignant/inscription", {"email": "bruno@etudiant.univ.fr", "motdepasse": "bruno-mot-de-passe", "nom": "Bruno Martin",
                                     "presentation": "Étudiant de M1, je veux essayer la plateforme."})
_, texte = dernier_mail("bruno@etudiant.univ.fr", av)
av = deja()
s, d = r("POST", "enseignant/confirmer", {"jeton": lien(texte, "confirmer")})
ok(s == 200 and "administratrice" in d["message"], "un étudiant peut demander un compte ; après confirmation, sa demande part chez l'administratrice")
sujet, texte = dernier_mail("anne@exemple.fr", av)
ok("Bruno Martin" in sujet and "bruno@etudiant.univ.fr" in texte and "essayer la plateforme" in texte, "l'administratrice reçoit la demande par mail (nom, adresse, présentation)")
ok(r("POST", "enseignant/connexion", {"email": "bruno@etudiant.univ.fr", "motdepasse": "bruno-mot-de-passe"})[0] == 403, "pas de connexion avant la validation")
liste = r("GET", "enseignant/comptes", j=JA)[1]
ok([(x["email"], x["valide"]) for x in liste] == [("bruno@etudiant.univ.fr", 0), ("anne@exemple.fr", 1)], "l'administratrice voit la demande en attente")
idb = liste[0]["id"]
av = deja()
ok(r("POST", f"enseignant/comptes/{idb}/valider", {}, JA)[0] == 200, "elle valide la demande")
sujet, texte = dernier_mail("bruno@etudiant.univ.fr", av)
ok("ouvert" in sujet, "la personne est prévenue par mail")
JB = r("POST", "enseignant/connexion", {"email": "bruno@etudiant.univ.fr", "motdepasse": "bruno-mot-de-passe"})[1]["jeton"]
ok(r("GET", "enseignant/comptes", j=JB)[0] == 403, "seule l'administratrice gère les comptes")
ok(r("GET", "classes", j=JB)[1] == [], "un nouveau compte ne voit aucune classe d'un collègue")
cb = r("POST", "classes", {"nom": "Classe de Bruno"}, JB)[1]["code"]
ok([x["code"] for x in r("GET", "classes", j=JB)[1]] == [cb], "il voit sa propre classe")
ok(r("GET", f"classes/{ca}/config", j=JB)[0] == 404, "la classe d'un collègue est introuvable (réglages)")
ok(r("GET", f"classes/{ca}/traces", j=JB)[0] == 404, "… ni ses traces")
ok(r("DELETE", f"classes/{ca}", j=JB)[0] == 404, "… et elle ne peut pas être supprimée")
ok(sorted(x["code"] for x in r("GET", "classes", j=JA)[1]) == sorted(["ANCIEN", ca]), "Anne ne voit pas la classe de Bruno")

av = deja()
r("POST", "enseignant/inscription", {"email": "carla@ailleurs.org", "motdepasse": "carla-mot-de-passe", "nom": "Carla"})
_, texte = dernier_mail("carla@ailleurs.org", av)
r("POST", "enseignant/confirmer", {"jeton": lien(texte, "confirmer")})
idc = [x["id"] for x in r("GET", "enseignant/comptes", j=JA)[1] if x["email"] == "carla@ailleurs.org"][0]
av = deja()
ok(r("POST", f"enseignant/comptes/{idc}/refuser", {}, JA)[0] == 200, "elle peut refuser une demande")
ok("demande" in dernier_mail("carla@ailleurs.org", av)[0], "la personne refusée est prévenue")
ok(r("POST", "enseignant/connexion", {"email": "carla@ailleurs.org", "motdepasse": "carla-mot-de-passe"})[0] == 401, "la demande refusée est effacée")
ok(r("POST", f"enseignant/comptes/{idb}/refuser", {}, JA)[0] == 409, "un compte qui a servi ne se refuse pas (il se suspend)")

av = deja()
s, d = r("POST", "enseignant/inscription", {"email": "anne@exemple.fr", "motdepasse": "autre-mot-de-passe"})
_, texte = dernier_mail("anne@exemple.fr", av)
ok(s == 200 and "reinitialiser=" in texte, "réinscription d'une adresse existante : même réponse, un mail l'apprend à la propriétaire")
ok(r("POST", "enseignant/connexion", {"email": "anne@exemple.fr", "motdepasse": "autre-mot-de-passe"})[0] == 401, "… sans changer son mot de passe")
ok(r("POST", "enseignant/oubli", {"email": "personne@exemple.fr"})[0] == 200, "oubli pour une adresse inconnue : même réponse")
av = deja()
r("POST", "enseignant/oubli", {"email": "anne@exemple.fr"})
_, texte = dernier_mail("anne@exemple.fr", av)
jr = lien(texte, "reinitialiser")
ok(r("POST", "enseignant/reinitialiser", {"jeton": jr, "motdepasse": "nouveau-mot-de-passe"})[0] == 200, "nouveau mot de passe choisi par le lien")
ok(r("GET", "classes", j=JA)[0] == 401, "les sessions ouvertes avec l'ancien mot de passe sont fermées")
ok(r("POST", "enseignant/connexion", {"email": "anne@exemple.fr", "motdepasse": "nouveau-mot-de-passe"})[0] == 200, "connexion avec le nouveau mot de passe")
ok(r("POST", "enseignant/reinitialiser", {"jeton": jr, "motdepasse": "encore-un-autre"})[0] == 400, "le lien de réinitialisation ne sert qu'une fois")
JB2 = r("POST", "enseignant/connexion", {"email": "bruno@etudiant.univ.fr", "motdepasse": "bruno-mot-de-passe"})[1]["jeton"]
r("POST", "enseignant/deconnexion", {}, JB2)
ok(r("GET", "classes", j=JB2)[0] == 401, "déconnexion")
JA = r("POST", "enseignant/connexion", {"email": "anne@exemple.fr", "motdepasse": "nouveau-mot-de-passe"})[1]["jeton"]
r("POST", f"enseignant/comptes/{idb}/suspendre", {}, JA)
ok(r("GET", "classes", j=JB)[0] == 401, "un compte suspendu est aussitôt déconnecté")
ok(r("POST", "enseignant/connexion", {"email": "bruno@etudiant.univ.fr", "motdepasse": "bruno-mot-de-passe"})[0] == 403, "… et ne peut plus se connecter")
codes = [r("POST", "enseignant/connexion", {"email": "inconnu@exemple.fr", "motdepasse": "faux-faux-faux"})[0] for _ in range(9)]
ok(codes[-1] == 429, "trop d'essais de mot de passe : connexion bloquée un moment")
print(f"test_comptes : {n_ok} vérifications réussies")
