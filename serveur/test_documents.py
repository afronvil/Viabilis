# Séance créée à partir d'un document PDF : dépôt, lecture du texte, brouillon par l'IA, document montré aux élèves, droits d'accès.
#   VIABILIS_MDP_ENSEIGNANT=motdepasse-test VIABILIS_IA=fausse python3 serveur.py --port 8834 --base /tmp/t34.sqlite3
import base64, json, os, sys, urllib.request, urllib.error
import pdf_texte
PORT = sys.argv[1] if len(sys.argv) > 1 else "8834"
B = f"http://127.0.0.1:{PORT}/api/"
n_ok = 0


def r(m, p, c=None, j=None, brut=False):
    q = urllib.request.Request(B + p, method=m, data=json.dumps(c).encode() if c is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + j} if j else {})})
    try:
        with urllib.request.urlopen(q) as x:
            corps = x.read()
            return x.status, (corps if brut else json.loads(corps)), x.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), None


def ok(cond, msg):
    global n_ok
    assert cond, msg
    n_ok += 1
    print("OK  ", msg)


def pdf_minimal(lignes):
    """Petit PDF valide, texte en Helvetica (police standard), pour ne dépendre d'aucun fichier."""
    contenu = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({l}) Tj 0 -16 Td" for l in lignes) + " ET"
    objets = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
              f"<< /Length {len(contenu)} >>\nstream\n{contenu}\nendstream",
              "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    sortie, positions = "%PDF-1.4\n", []
    for k, o in enumerate(objets, 1):
        positions.append(len(sortie.encode("latin-1")))
        sortie += f"{k} 0 obj\n{o}\nendobj\n"
    xref = len(sortie.encode("latin-1"))
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n" + "".join(f"{p:010d} 00000 n \n" for p in positions)
    sortie += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return sortie.encode("latin-1")


LIGNES = ["Chapitre 2 : la photosynthese.", "Les plantes vertes captent la lumiere grace a la chlorophylle.",
          "Elles transforment le dioxyde de carbone et l'eau en glucose et en dioxygene."] * 4
PDF = pdf_minimal(LIGNES)
texte = pdf_texte._Lecteur(PDF).texte()
ok("chlorophylle" in texte and "photosynthese" in texte, "lecteur intégré : texte d'un PDF simple")
ok(pdf_texte.extraire(b"pas un pdf") == "", "lecteur : un fichier illisible donne un texte vide")
exemple = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "Sticef", "qcm-linux-microbio", "qcm-linux.pdf")

J = r("POST", "enseignant/connexion", {"motdepasse": "motdepasse-test"})[1]["jeton"]
code = r("POST", "classes", {"nom": "Documents"}, J)[1]["code"]
autre = r("POST", "classes", {"nom": "Autre classe"}, J)[1]["code"]
b64 = lambda b: base64.b64encode(b).decode()

s, d, _ = r("POST", f"classes/{code}/documents", {"nom": "notes.txt", "contenu": b64(b"Bonjour")}, J)
ok(s == 400, "un fichier qui n'est pas un PDF est refusé")
s, d, _ = r("POST", f"classes/{code}/documents", {"nom": "photosynthese.pdf", "contenu": b64(PDF)}, J)
ok(s == 201 and d["caracteres"] > 200 and d["taille"] == len(PDF), f"PDF déposé, texte lu ({d.get('caracteres')} caractères)")
doc = d["id"]
ok([x["id"] for x in r("GET", f"classes/{code}/documents", j=J)[1]] == [doc], "liste des documents de la classe")
ok(r("GET", f"classes/{autre}/documents/{doc}", j=J)[0] == 404, "le document d'une classe n'existe pas pour une autre classe")
s, contenu, typ = r("GET", f"classes/{code}/documents/{doc}", j=J, brut=True)
ok(s == 200 and contenu == PDF and typ == "application/pdf", "l'enseignant relit le PDF déposé")

s, br, _ = r("POST", f"classes/{code}/documents/{doc}/brouillon", {"souhait": "1 h, CM2"}, J)
ok(s == 200 and br["tache"] and len(br["indices"]) == 3 and br["verification"]["mode"] == "ia", "brouillon de séance (IA factice)")

cfg = r("GET", f"classes/{code}/config", j=J)[1]
cfg.update({k: v for k, v in br.items() if k != "titre"}, seance=1, ouvertes=[], ouverte=False, document=doc)
cfg = r("PUT", f"classes/{code}/config", cfg, J)[1]
ok(cfg["document"] == doc and cfg["ouvertes"] == [] and cfg["archives"]["1"]["document"] == doc, "séance 1 créée fermée, avec son document")
e = r("POST", "eleve/connexion", {"code": code, "pseudo": "Lou"})[1]["jeton"]
ok(r("GET", "eleve/document?seance=1", j=e)[0] == 404, "séance fermée : le document n'est pas accessible")
cfg = r("PUT", f"classes/{code}/config", {**cfg, "ouvertes": [1], "ouverte": True}, J)[1]
moi = r("GET", "eleve/moi", j=e)[1]
ok(moi["config"]["document"] == {"id": doc, "nom": "photosynthese.pdf"}, "l'élève voit le nom du document de la séance")
s, contenu, typ = r("GET", "eleve/document?seance=1", j=e, brut=True)
ok(s == 200 and contenu == PDF and typ == "application/pdf", "l'élève ouvre le document de la séance ouverte")
ok(r("GET", "eleve/document?seance=1")[0] in (401, 403), "sans jeton : refusé")
e2 = r("POST", "eleve/connexion", {"code": autre, "pseudo": "Max"})[1]["jeton"]
ok(r("GET", "eleve/document?seance=1", j=e2)[0] == 404, "un élève d'une autre classe ne lit pas le document")

cfg = r("PUT", f"classes/{code}/config", {**cfg, "seance": 2, "ouvertes": [1, 2], "ouverte": True, "tache": "Séance sans document", "document": 0}, J)[1]
ok(cfg["archives"]["1"]["document"] == doc and cfg["document"] == 0, "la séance 1 garde son document quand la séance 2 n'en a pas")
ok(r("GET", "eleve/moi?seance=2", j=e)[1]["config"]["document"] is None, "séance 2 : pas de document")
kit = r("GET", f"classes/{code}/kit", j=J)[1]
ok(all(not c.get("document") for c in [kit["classe"]["config"]] + list(kit["classe"]["config"]["archives"].values())), "le kit hors ligne ne référence aucun document")

ok(r("DELETE", f"classes/{code}/documents/{doc}", j=J)[0] == 200, "document effacé")
ok(r("GET", "eleve/document?seance=1", j=e)[0] == 404 and r("GET", "eleve/moi?seance=1", j=e)[1]["config"]["document"] is None, "après effacement : plus de document pour l'élève")

s, d, _ = r("POST", f"classes/{code}/documents", {"nom": "vide.pdf", "contenu": b64(pdf_minimal(["x"]))}, J)
ok(r("POST", f"classes/{code}/documents/{d['id']}/brouillon", {}, J)[0] == 422, "PDF presque sans texte : pas de brouillon, message clair")
if os.path.exists(exemple):
    t = pdf_texte._Lecteur(open(exemple, "rb").read()).texte()
    ok("système d’exploitation" in t.lower() or "systeme" in t.lower(), "lecteur intégré : un vrai PDF produit par LaTeX")
print(f"test_documents : {n_ok} vérifications réussies")
