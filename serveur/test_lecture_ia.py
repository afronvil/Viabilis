# Lecture des réponses de l'IA à la vérification : tolérante aux imperfections fréquentes des modèles (sans serveur).
#   python3 test_lecture_ia.py
import verification as V

ok = 0


def verif(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("OK  ", msg)


bon = '{"idees": [{"n": 1, "statut": "juste", "retour": "Bravo."}, {"n": 2, "statut": "a_revoir", "retour": "Vérifie."}], "bilan": "Bien.", "conseil": "Range."}'
cas = {
    "réponse correcte": bon,
    "texte autour": "Voici mon analyse :\n" + bon + "\nJ'espère que cela aide.",
    "bloc ```json": "```json\n" + bon + "\n```",
    "virgules en trop": bon.replace('"Bravo."}', '"Bravo.",}').replace('"Range."}', '"Range.",}'),
    "guillemets typographiques": bon.replace('"bilan"', '“bilan”'),
    "retour à la ligne dans une chaîne": bon.replace("Vérifie.", "Vérifie\nton calcul."),
    "accolades dans un retour (code)": bon.replace("Bravo.", "Bravo, mkdir -p a/{b,c} marche."),
}
for nom, t in cas.items():
    r = V.lire_reponse_ia(t, 2)
    verif([x["statut"] for x in r["retours"]] == ["juste", "a_revoir"], f"lu : {nom}")
coupe = '{"idees": [{"n": 1, "statut": "juste", "retour": "Bravo."}, {"n": 2, "statut": "a_revoir", "retour": "Vérifie ton cal'
r = V.lire_reponse_ia(coupe, 2)
verif(r["retours"][0]["statut"] == "juste" and r["retours"][1]["statut"] == "a_revoir", "réponse coupée : l'idée complète est gardée, l'autre est à revoir")
try:
    V.lire_reponse_ia("Je ne peux pas répondre.", 2)
    verif(False, "réponse sans JSON")
except ValueError:
    verif(True, "réponse sans JSON : erreur claire (le serveur refait un essai)")
print(f"test_lecture_ia : {ok} vérifications réussies")
