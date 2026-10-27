# Lance tous les tests de Viabilis, chacun contre un serveur neuf réglé comme l'indique l'en-tête du test.
#   python3 developpement/tests/lancer_tests.py            (tous les tests)
#   python3 developpement/tests/lancer_tests.py langues    (seulement test_langues.py)
# Les bases et les mails de test vont dans un dossier temporaire ; la base viabilis.sqlite3 n'est jamais touchée.
import glob, os, re, shlex, subprocess, sys, tempfile, time, urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
SERVEUR = os.path.normpath(os.path.join(ICI, "..", "..", "serveur"))
TMP = tempfile.mkdtemp(prefix="viabilis_tests_")
filtre = sys.argv[1:]
res = []
for t in sorted(glob.glob(os.path.join(ICI, "test_*.py"))):
    nom = os.path.basename(t)
    if filtre and not any(f in nom for f in filtre):
        continue
    tete = open(t, encoding="utf-8").read(3000)
    m = re.search(r"#\s*((?:[A-Z_]+=\S+\s+)*)python3 serveur\.py\s+--port (\d+)([^\n]*)", tete)
    base, mails = os.path.join(TMP, nom + ".sqlite3"), os.path.join(TMP, nom + "_mails")
    os.makedirs(mails, exist_ok=True)
    env = {**os.environ}
    srv = None
    if m:                                         # test qui parle à un serveur : on le lance comme l'indique l'en-tête
        for kv in m.group(1).split():
            k, v = kv.split("=", 1)
            env[k] = mails if k == "VIABILIS_MAIL_DOSSIER" else v
        port, args = m.group(2), shlex.split(m.group(3))
        if "--base" in args:
            args[args.index("--base") + 1] = base
        else:
            args += ["--base", base]
        srv = subprocess.Popen([sys.executable, "serveur.py", "--port", port, "--sans-navigateur"] + args, cwd=SERVEUR, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
    try:
        p = subprocess.run([sys.executable, t] + ([m.group(2), base, mails] if m else []), cwd=SERVEUR, env=env,
                           capture_output=True, text=True, timeout=900)
        res.append((nom, p.returncode, ((p.stdout + p.stderr).strip().splitlines() or [""])[-1]))
    finally:
        if srv:
            srv.terminate()
            srv.wait()
for nom, rc, der in res:
    print("OK   " if rc == 0 else "ÉCHEC", nom, "·", der[:120])
print(f"{sum(rc == 0 for _, rc, _ in res)} / {len(res)} suites réussies")
sys.exit(0 if all(rc == 0 for _, rc, _ in res) else 1)
