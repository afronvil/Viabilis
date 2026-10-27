# Test des modèles qui raisonnent (gpt-oss-120b d'Albert…) : effort de raisonnement et place laissée à la réponse.
# Sans serveur : python3 developpement/tests/test_raisonnement.py
import os as _os, sys as _sys
SERVEUR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "serveur"))   # le code testé
_sys.path.insert(0, SERVEUR)
import serveur as S
N = 0
def ok(cond, msg):
    global N
    print(("OK   " if cond else "ÉCHEC ") + msg)
    assert cond, msg
    N += 1
_os.environ.pop("VIABILIS_IA_RAISONNEMENT", None)
tours = [{"role": "user", "content": "Bonjour"}]
c = S.corps_compatible("gpt-oss-120b", "Consignes", tours, 300)
ok(c["reasoning_effort"] == "low" and c["max_tokens"] == 2300, "gpt-oss-120b : raisonnement court et place pour réfléchir puis répondre")
ok(c["messages"][0] == {"role": "system", "content": "Consignes"} and c["messages"][1:] == tours, "consignes et échanges transmis")
c = S.corps_compatible("mistral-small-3-2-24b-instruct-2506", "Consignes", tours, 300)
ok("reasoning_effort" not in c and c["max_tokens"] == 300, "modèle sans raisonnement : requête inchangée")
ok(S.effort_raisonnement("openai/gpt-oss-20b") == "low" and S.effort_raisonnement("deepseek-r1") == "low"
   and S.effort_raisonnement("gemma-4-31b-it") is None and S.effort_raisonnement("gpt-4o-mini") is None, "modèles qui raisonnent reconnus par leur nom")
_os.environ["VIABILIS_IA_RAISONNEMENT"] = "medium"
ok(S.corps_compatible("gpt-oss-120b", "C", tours, 300)["max_tokens"] == 4300, "VIABILIS_IA_RAISONNEMENT=medium : plus de place")
_os.environ["VIABILIS_IA_RAISONNEMENT"] = "aucun"
ok("reasoning_effort" not in S.corps_compatible("gpt-oss-120b", "C", tours, 300), "VIABILIS_IA_RAISONNEMENT=aucun : désactivé")
_os.environ.pop("VIABILIS_IA_RAISONNEMENT")
# réponse d'une API compatible : raisonnement écrit entre balises, ou réponse vide
import io, json, urllib.error, urllib.request
def fausse_api(reponse):
    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return lambda req, timeout=60: R(json.dumps(reponse).encode())
_os.environ.update(VIABILIS_IA="openai", VIABILIS_IA_CLE="essai", VIABILIS_IA_MODELE="gpt-oss-120b")
vraie = urllib.request.urlopen
try:
    urllib.request.urlopen = fausse_api({"choices": [{"message": {"content": "<think>je réfléchis</think> Quelle règle as-tu utilisée ?"}, "finish_reason": "stop"}]})
    ok(S.appeler_ia("C", tours) == "Quelle règle as-tu utilisée ?", "raisonnement entre balises retiré de la réponse")
    urllib.request.urlopen = fausse_api({"choices": [{"message": {"content": None, "reasoning_content": "…"}, "finish_reason": "length"}]})
    try:
        S.appeler_ia("C", tours); vide = False
    except ValueError as e:
        vide = "length" in str(e)
    ok(vide, "réponse vide signalée avec sa cause (raisonnement trop long)")
    envois = []
    def refuse_puis_accepte(req, timeout=60):
        envois.append(json.loads(req.data))
        if len(envois) == 1:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"detail": "unknown field reasoning_effort"}'))
        return fausse_api({"choices": [{"message": {"content": "Relis ta retenue."}, "finish_reason": "stop"}]})(req)
    urllib.request.urlopen = refuse_puis_accepte
    ok(S.appeler_ia("C", tours) == "Relis ta retenue." and "reasoning_effort" in envois[0] and "reasoning_effort" not in envois[1]
       and envois[1]["max_tokens"] == envois[0]["max_tokens"], "reasoning_effort refusé : nouvel essai sans ce champ, même place")
finally:
    urllib.request.urlopen = vraie
print(f"test_raisonnement : {N} vérifications réussies")
