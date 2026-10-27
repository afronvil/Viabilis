// Viabilis classe — application enseignant.
import {tx, LANGUE, LANGUES, LOCALE, menuLangue} from "../commun/langues.js";
import {$, el, fr, api, ouvrirPdf, listeIdees, etatEleve, ruptures, recommandation, brut, ideesDesAutres, distinctes, jaccard, mots, NOM_ORDRE, NOM_MODE, NOM_VARIANTE, GROUPES, groupeSuggere, numeroSeance, prochainNumero, niveauEffectif} from "../commun/etat.js";
const N = n => numeroSeance(S.config, n);          // numéro affiché (rang parmi les séances qui existent encore)
import {proposerSuites, GENRES, PROFILS, modeleDeSeance} from "../commun/suites.js";

const S = {jeton: null, classes: [], code: null, config: null, traces: {}, notes: {}, onglet: "classe", detail: null, confirmer: null, exos: null, importMsg: null, viab: {}, brouillon: null, seanceEditee: null, modeles: null, modele: null, modeleChoisi: null, suite: false, suiteChoisie: null, messages: [], signalements: [], galerieChoix: null, documents: null, pdfEtat: null, banques: null, gift: null};
const PUBLICS = {ecole: tx("École élémentaire"), college: tx("Collège"), lycee: tx("Lycée"), superieur: tx("Enseignement supérieur")};
const DEFAUT = {seance: 0, ouverte: false, tache: "", public: "ecole", ordre: "adaptatif", mode: "questionner", minIdees: 3, seuilCharge: 0.7, retraitAgentivite: 0.8, seuilMaitrise: 0.5, eleves: {},
  exercices: {actifs: false, nombre: 3, placement: "avant", niveau: 2, choix: "niveau"}, niveauTache: 3,
  verification: {mode: "aucune", cible: 10, nombres: "", attendu: 0, criteres: "", maximum: 3, uneFois: false},
  groupes: {}, lecture: {active: true, langue: "fr-FR"}, langue: "fr",
  indices: [], variantes: {actives: false, accessible: {consigne: "", indices: [], cible: null, attendu: null}, exigeante: {consigne: "", indices: [], cible: null, attendu: null}}};
/** Minuscule pour l'insérer dans une phrase, sauf en allemand (les noms y prennent une majuscule). */
const minuscule = t => LANGUE === "de" ? t : t.toLowerCase();
const NOM_TYPE = {choix_unique: tx("choix unique"), choix_multiple: tx("choix multiple"), vrai_faux: tx("vrai ou faux"), reponse_courte: tx("réponse courte"), numerique: tx("numérique"), appariement: "appariement"};


try { S.jeton = sessionStorage.getItem("viabilis-enseignant"); S.email = sessionStorage.getItem("viabilis-email"); S.admin = !!sessionStorage.getItem("viabilis-admin"); } catch {}
const appel = (chemin, opts = {}) => api(chemin, {...opts, jeton: S.jeton}).catch(e => { if (e.statut === 401) { S.jeton = null; rendre(); } throw e; });

function toast(t) { const n = el("div", {class: "notice warn", role: "status"}, t); $("#vue").prepend(n); setTimeout(() => n.remove(), 4000); }

async function chargerClasse() {
  if (!S.code) return;
  try {
    const [cfg, traces, notes, messages, signalements] = await Promise.all([appel(`classes/${S.code}/config`), appel(`classes/${S.code}/traces`), appel(`classes/${S.code}/notes`),
      appel(`classes/${S.code}/messages`), appel(`classes/${S.code}/signalements`)]);
    S.config = {...DEFAUT, ...cfg}; S.traces = traces; S.notes = notes; S.messages = messages; S.signalements = signalements;
  } catch (e) { if (e.statut !== 401) toast(e.message); }
  rendre();
  chargerViabilite();
}
// Viabilité (expérimental) : le serveur situe l'état estimé de chaque élève dans les tables du modèle
async function chargerViabilite() {
  const c = S.config, eleves = {};
  for (const u of Object.keys(S.traces)) {
    const est = etatEleve(S.traces, S.notes, u), e = est?.etat;
    if (!e || [e.C, e.A, e.M, e.D].some(v => v == null)) continue;
    const perso = c.eleves?.[u] || {}, decalage = {accessible: -1, exigeante: 1}[varianteDe(c, perso)] || 0;
    // trajet : état estimé après chaque séance et aide reçue, pour comparer les prévisions du modèle à ce qui s'est passé
    const trajet = (est.trajet || []).filter(p => [p.C, p.A, p.M, p.D].every(v => v != null)).slice(-8)
      .map(p => ({t: p.n - 1, niveau: Math.min(5, Math.max(1, niveauEffectif(c, p.n, p.variante))), C: p.C, A: p.A, M: p.M, D: p.D, u: p.u}));
    const zone = c.exercices?.actifs && c.exercices.choix === "adaptatif" ? S.traces[u]?.zpdes?.zone : null;   // choix adaptatif : niveau le plus haut ouvert
    eleves[u] = {...e, niveau: (zone?.length ? Math.max(...zone) : niveauDe(c, perso)) ?? Math.min(5, Math.max(1, (c.niveauTache ?? 3) + decalage)), trajet};
  }
  if (!Object.keys(eleves).length) { S.viab = {}; return; }
  try { S.viab = await appel(`classes/${S.code}/viabilite`, {methode: "POST", corps: {seance: Math.max(1, c.seance || 1), eleves}}); }
  catch (e) { S.viab = {erreur: e.message}; }
  if (S.onglet === "classe" && !S.detail) rendre();
}
/** Marge dans le noyau (modèle complet, tables) : > 0 correction nécessaire ; < 0 marge avant la frontière, et sa direction. */
const MENACES = [[tx("de la surcharge"), 0, 1], [tx("de l'ennui"), 0, -1], [tx("de la dépendance à l'aide"), 1, -1], [tx("d'une maîtrise qui baisse"), 2, -1], [tx("de la rigidité (peu d'idées nouvelles)"), 3, -1]];
const LEVIERS = [[tx("alléger la tâche (variante accessible, éléments de réponse)"), 0, -1], [tx("relever le défi (tâche plus riche, variante exigeante)"), 0, 1],
  [tx("laisser chercher seul d'abord (réflexion avant l'IA)"), 1, 1], [tx("consolider (coups de pouce, exercices)"), 2, 1], [tx("ouvrir la recherche (questions, idées des autres)"), 3, 1]];
function dominante(vec, table) {
  if (!vec) return null;
  let best = null;
  for (const [nom, i, signe] of table) { const v = vec[i] * signe; if (v > 0 && (!best || v > best[1])) best = [nom, v]; }
  return best?.[0] ?? null;
}
function ligneTension(m) {
  const b = m?.bassin;
  if (!b || b.tension == null) return el("p", {class: "small"}, el("b", {}, tx("Marge : ")), tx("correction hors de portée du modèle."));
  if (b.tension > 0) return el("p", {class: "small"}, el("span", {class: "pill ko"}, tx`Hors du noyau sans aide (écart ${fr(b.tension)})`), tx(" Sans aide, l'élève sort de la zone viable à la prochaine séance. Correction minimale : "),
    el("b", {}, dominante(b.vecteur, LEVIERS) || tx("à préciser")), ".");
  const marge = -b.tension, niv = marge < 0.05 ? "warn" : marge < 0.15 ? "" : "ok";
  const menace = dominante(b.vecteur, MENACES);
  return el("p", {class: "small"}, el("span", {class: "pill " + niv}, marge >= 0.3 ? tx("Marge large") : tx`Marge ${fr(marge)}`),
    marge >= 0.3 ? tx(" Aucune frontière proche.") : tx` Sans aide, la frontière la plus proche est ${menace ? tx("celle ") + menace : tx("à préciser")}${marge < 0.05 ? tx(" : à surveiller dès maintenant") : ""}.`);
}
/** Prédiction démentie : le modèle prévoyait autre chose que ce qui a été observé (ennui durable, difficulté non déclarée… ou modèle à recalibrer). */
function lignePrediction(p) {
  const d = p?.comparaisons?.slice(-1)[0];
  if (!d || !d.dementie) return null;
  const i = ["charge", "agentivité", "maîtrise", "pensée divergente"].indexOf(d.variable);
  const n = p.dementiesDeSuite;
  return el("p", {class: "small"}, el("span", {class: "pill warn"}, tx`Prédiction démentie${n > 1 ? tx` (${n} séances de suite)` : ""}`), " ",
    d.retourNonRealise ? tx("Le retour dans le domaine prévu sans aide n'a pas eu lieu. ") : "",
    tx`Le modèle prévoyait une ${tx(d.variable)} de ${fr(d.prevu[i])} ; estimée : ${fr(d.observe[i])}. `,
    el("span", {class: "muted"}, n > 1 ? tx("Un écart qui dure : à vérifier avec l'élève (ennui durable, difficulté non déclarée…), et un signe que le modèle est à recalibrer.") : tx("À vérifier avec l'élève.")));
}
/** Multiplicateurs de viabilité de l'article (section 5.6) : nature de l'aide, exigence qui la motive, prix des seuils. */
const SEUILS = {surcharge: "surcharge", ennui: "ennui", dependance: tx("dépendance")};
function ligneMultiplicateurs(v) {
  const mu = v.multiplicateurs; if (!mu) return null;
  const a = mu.anticipateurs, my = mu.myopes, nature = v.natureAide;
  const pill = nature === "sauvegarde" ? el("span", {class: "pill ko"}, tx("Intervention de sauvegarde"))
    : nature === "progression" ? el("span", {class: "pill ok"}, tx("Intervention de progression"))
    : mu.sauvegarde ? el("span", {class: "pill warn"}, tx("Sans aide, sortie du domaine d'ici 10 séances")) : null;
  const sens = nature === "sauvegarde" ? tx(" L'aide prévient un décrochage.") : nature === "progression" ? tx(" Aucune sortie n'est imminente : l'aide rapproche l'élève de l'autonomie.") : "";
  const exigence = a.aucuneAideSuffisante ? tx("aucune aide constante ne le garde dans le domaine sur 10 séances.")
    : a.cout === 0 ? tx("aucune aide n'est nécessaire.")
    : tx`l'exigence qui motive l'aide est la ${SEUILS[a.contrainte]} ; aide minimale constante : éléments de réponse ${fr(a.aide[0])}, questions ${fr(a.aide[1])}.`;
  const prix = my ? Object.entries(my.prix).filter(([, p]) => p > 0) : [];
  if (!pill && my && !prix.length && a.cout === 0)          // rien à signaler : une seule ligne
    return el("p", {class: "small muted"}, tx("Multiplicateurs de viabilité : aucune aide nécessaire, ni à la prochaine séance ni sur 10 séances."));
  return el("div", {class: "field", style: "gap:2px"},
    el("p", {class: "small"}, pill, pill ? " " : "", sens, tx(" Sur 10 séances, "), exigence),
    el("p", {class: "small muted"}, my == null ? tx("Prochaine séance : aucune aide ne garde l'élève dans le domaine.")
      : prix.length ? tx`Prix des seuils à la prochaine séance : ${prix.map(([n, p]) => `${SEUILS[n]} ${fr(p, 3)}`).join(" · ")} (ce que coûterait, en aide, un seuil relevé d'un cran).`
      : tx("Prochaine séance : aucun seuil menacé (prix nuls).")));
}
function blocViabilite(u) {
  if (S.viab?.erreur) return null;
  const v = S.viab?.[u];
  if (!v) return el("p", {class: "small muted"}, tx("Viabilité : estimation incomplète pour l'instant."));
  const statuts = {
    auto_soutenu: ["ok", tx("Auto-soutenu : peut continuer sans aide")],
    dans_bassin: ["ok", tx`Dans le bassin de capture : autonomie possible en ${v.seancesVersAutonomie} séance${v.seancesVersAutonomie > 1 ? "s" : ""} environ`],
    hors_bassin: ["warn", tx("Hors du bassin de capture : l'autonomie n'est plus atteignable dans cette situation")],
    hors_noyau: ["ko", tx("Hors du noyau : rupture probable, même avec de l'aide")]};
  const m = v.marge;
  // hors du noyau parce qu'une contrainte est violée MAINTENANT, mais retour prévu sans aide : ce n'est pas une rupture inévitable
  const [niv, txt] = v.statut === "hors_noyau" && m && !m.dansDomaine
    ? (m.retourSpontane ? ["warn", tx("Hors du domaine pour l'instant : retour prévu sans aide à la prochaine séance")] : ["ko", tx("Hors du domaine, sans retour spontané : une correction est nécessaire")])
    : statuts[v.statut];
  const a = v.aide;
  const ordre = a ? (a.reflexion >= 1 ? tx("réflexion d'abord") : a.reflexion > 0 ? tx("réflexion en milieu de séance") : tx("IA d'abord")) : "";
  const aide = !a ? tx("aucune aide ne garantit de rester dans le domaine") : (a.etayage === 0 && a.questions === 0) ? tx("aucune aide nécessaire")
    : [a.etayage ? tx`éléments de réponse ${fr(a.etayage, 1)}` : null, a.questions ? tx`questions ${fr(a.questions, 1)}` : null].filter(Boolean).join(tx(" et ")) + ", " + ordre;
  return el("div", {class: "field", style: "gap:4px"}, el("details", {class: "small"}, el("summary", {}, el("span", {class: "pill " + niv}, txt)),
    el("p", {class: "small"}, v.fenetre === 0 ? tx("Fenêtre d'intervention : déjà dépassée.") : v.fenetre == null ? tx("Fenêtre d'intervention : aucune sortie prévue sur 20 séances sans aide.") : tx`Fenêtre d'intervention : ${v.fenetre} séance${v.fenetre > 1 ? "s" : ""} sans aide avant qu'il soit trop tard.`),
    el("p", {class: "small"}, tx`Aide minimale (${v.nature === "capture" ? tx("loi de capture") : v.nature === "sauvegarde" ? tx("sauvegarde") : tx("aucune")}) : ${aide}.`),
    (v.statut === "hors_noyau" || v.statut === "hors_bassin") ? el("p", {class: "small"}, el("b", {}, tx("Piste : ")), tx("selon le modèle, l'aide de l'IA ne suffit plus ; rendre la tâche plus accessible ou intervenir en personne.")) : null,
    el("p", {class: "small muted"}, tx("Marge : où l'élève va sans aide, comparé au noyau du modèle complet (avec la maîtrise attendue). Elle donne un compte à rebours avant le décrochage.")),
    el("p", {class: "small muted"}, tx("Multiplicateurs de viabilité (article, section 5.6, modèle réduit charge – agentivité – maîtrise) : plus petite aide qui garde l'élève dans le domaine, à la prochaine séance et sur 10 séances ; le prix d'un seuil est la dérivée du coût de cette aide par rapport au seuil. Une intervention est « de sauvegarde » si, sans aide, l'élève sortirait du domaine dans les 10 séances, « de progression » sinon.")),
    m ? el("p", {class: "small muted"}, tx`Maîtrise attendue à ce stade de la séquence : ${fr(m.maitriseAttendue)} (elle monte jusqu'à 0,6 en fin de séquence).`) : null,
    el("p", {class: "small muted"}, tx("Expérimental : modèle non calibré et état estimé grossièrement. À lire comme une alerte, pas comme un diagnostic."))), ligneMultiplicateurs(v), m ? ligneTension(m) : null, lignePrediction(v.prediction));
}
async function majConfig(patch) {
  try { S.config = await appel(`classes/${S.code}/config`, {methode: "PUT", corps: {...S.config, ...patch}}); }
  catch (e) { toast(tx("Réglage non enregistré : ") + e.message); }
  rendre();
}

function rendre() {
  $("#tabs").hidden = !(S.jeton && S.code);
  if (!S.jeton) return ecranConnexion();
  if (!S.code) return ecranClasses();
  if (!S.config) return;
  const c = S.config;
  const ouv = c.ouvertes || [];
  $("#titre").textContent = ouv.length ? tx`Séance${ouv.length > 1 ? "s" : ""} ouverte${ouv.length > 1 ? "s" : ""} : ${ouv.map(N).join(", ")}` : (c.seance ? tx("Aucune séance ouverte") : tx("Aucune séance"));
  $("#sous-titre").textContent = tx`${(S.classes.find(x => x.code === S.code) || {}).nom || ""} · code de la classe : ${S.code}`;
  if (S.onglet === "reglages") return ongletReglages();
  if (S.onglet === "donnees") return ongletDonnees();
  if (S.onglet === "exercices") return ongletExercices();
  if (S.onglet === "groupes") return ongletGroupes();
  if (S.detail) return detailEleve(S.detail);
  ongletClasse();
}
function ecranConnexion() {
  $("#titre").textContent = tx("Espace enseignant"); $("#sous-titre").textContent = "";
  if (S.comptes === undefined) { api("enseignant/mode").then(m => { S.comptes = m.comptes ? m : null; rendre(); }).catch(() => { S.comptes = null; rendre(); }); return; }
  if (S.comptes) return ecranComptes();
  const mdp = el("input", {type: "password", id: "mdp", autocomplete: "current-password"});
  const err = el("p", {class: "small", role: "alert"});
  const go = async () => {
    try { const r = await api("enseignant/connexion", {methode: "POST", corps: {motdepasse: mdp.value}}); ouvrirSession(r); await listerClasses(); }
    catch (e) { err.textContent = e.message; }
  };
  mdp.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  $("#vue").replaceChildren(el("div", {class: "card"}, el("div", {class: "field"}, el("label", {for: "mdp"}, tx("Mot de passe")), mdp), el("button", {class: "primary", onclick: go}, tx("Se connecter")), err));
}
function ouvrirSession(r) {
  S.jeton = r.jeton; S.email = r.email || null; S.admin = !!r.admin; S.comptesListe = null;
  try {
    sessionStorage.setItem("viabilis-enseignant", r.jeton); r.email ? sessionStorage.setItem("viabilis-email", r.email) : sessionStorage.removeItem("viabilis-email");
    r.admin ? sessionStorage.setItem("viabilis-admin", "1") : sessionStorage.removeItem("viabilis-admin");
  } catch {}
}
async function deconnecter() {
  try { await api("enseignant/deconnexion", {methode: "POST", corps: {}, jeton: S.jeton}); } catch {}
  try { ["viabilis-enseignant", "viabilis-email", "viabilis-admin"].forEach(k => sessionStorage.removeItem(k)); } catch {}
  Object.assign(S, {jeton: null, email: null, admin: false, comptesListe: null, code: null, config: null, classes: [], detail: null}); $("#tabs").hidden = true; rendre();
}

/* ---------------------------------------------------------------- comptes : adresse confirmée par mail, mot de passe */
// écrans : connexion, inscription, oubli (demande d'un lien), nouveau (mot de passe choisi depuis le lien reçu)
function ecranComptes() {
  const etape = S.etapeCompte || "connexion";
  const msg = el("p", {class: "small", role: "alert"}, S.messageCompte || "");
  S.messageCompte = null;
  const champ = (id, label, attrs) => el("div", {class: "field"}, el("label", {for: id}, label), el("input", {id, ...attrs}));
  const aller = e => { S.etapeCompte = e; rendre(); };
  const lien = (texte, e) => el("button", {class: "ghost small", onclick: () => aller(e)}, texte);
  const valeur = id => $("#" + id).value;
  const envoyer = async (route, corps, suite) => {
    msg.textContent = "";
    try { const r = await api("enseignant/" + route, {methode: "POST", corps}); suite(r); }
    catch (e) { msg.textContent = e.message; }
  };
  const deux = () => valeur("c-mdp") === valeur("c-mdp2") || (msg.textContent = tx("Les deux mots de passe sont différents."), false);
  const domaines = S.comptes.domaines.map(d => "@" + d.replace(/^\*\./, "….")).join(", ");
  const intro = [S.comptes.validation ? tx("Votre demande sera examinée par l'administratrice de la plateforme. Vous recevrez d'abord un mail pour confirmer votre adresse, puis un second quand votre compte sera ouvert. Vous ne verrez que vos propres classes.")
                   : tx("Un lien de confirmation vous sera envoyé : le compte ne sert qu'une fois l'adresse confirmée. Vous ne verrez que vos propres classes."),
                 domaines ? " " + tx`Adresses acceptées : ${domaines}.` : ""].join("");
  let carte;
  if (etape === "connexion") {
    const go = () => envoyer("connexion", {email: valeur("c-email"), motdepasse: valeur("c-mdp")}, async r => { ouvrirSession(r); await listerClasses(); });
    carte = [el("h2", {}, tx("Se connecter")), champ("c-email", tx("Adresse électronique"), {type: "email", autocomplete: "username"}),
      champ("c-mdp", tx("Mot de passe"), {type: "password", autocomplete: "current-password", onkeydown: e => { if (e.key === "Enter") go(); }}),
      el("button", {class: "primary", onclick: go}, tx("Se connecter")), msg,
      el("div", {class: "row"}, lien(tx("Créer un compte"), "inscription"), lien(tx("Mot de passe oublié ?"), "oubli"))];
  } else if (etape === "inscription") {
    carte = [el("h2", {}, tx("Créer un compte enseignant")),
      el("p", {class: "small muted"}, intro),
      champ("c-nom", tx("Nom et prénom"), {type: "text", autocomplete: "name", maxlength: "80"}),
      champ("c-email", tx("Adresse électronique"), {type: "email", autocomplete: "username"}),
      el("div", {class: "field"}, el("label", {for: "c-presentation"}, tx("Qui êtes-vous ? (établissement, discipline, ce que vous voulez essayer)")),
        el("textarea", {id: "c-presentation", rows: "3", maxlength: "500"})),
      champ("c-mdp", tx("Mot de passe (10 caractères au moins)"), {type: "password", autocomplete: "new-password", minlength: "10"}),
      champ("c-mdp2", tx("Le même mot de passe, une seconde fois"), {type: "password", autocomplete: "new-password"}),
      el("button", {class: "primary", onclick: () => deux() && envoyer("inscription", {email: valeur("c-email"), motdepasse: valeur("c-mdp"), nom: valeur("c-nom"), presentation: valeur("c-presentation")},
        r => { S.messageCompte = r.message; aller("connexion"); })}, tx("Créer le compte")), msg, lien(tx("← J'ai déjà un compte"), "connexion")];
  } else if (etape === "oubli") {
    carte = [el("h2", {}, tx("Mot de passe oublié")), el("p", {class: "small muted"}, tx("Vous recevrez un lien pour choisir un nouveau mot de passe.")),
      champ("c-email", tx("Adresse électronique"), {type: "email", autocomplete: "username"}),
      el("button", {class: "primary", onclick: () => envoyer("oubli", {email: valeur("c-email")}, r => { S.messageCompte = r.message; aller("connexion"); })}, tx("Recevoir un lien")),
      msg, lien(tx("← Se connecter"), "connexion")];
  } else {
    carte = [el("h2", {}, tx("Nouveau mot de passe")),
      champ("c-mdp", tx("Mot de passe (10 caractères au moins)"), {type: "password", autocomplete: "new-password", minlength: "10"}),
      champ("c-mdp2", tx("Le même mot de passe, une seconde fois"), {type: "password", autocomplete: "new-password"}),
      el("button", {class: "primary", onclick: () => deux() && envoyer("reinitialiser", {jeton: S.jetonLien, motdepasse: valeur("c-mdp")},
        r => { S.jetonLien = null; S.messageCompte = r.message; aller("connexion"); })}, tx("Enregistrer le mot de passe")), msg];
  }
  $("#vue").replaceChildren(el("div", {class: "card"}, ...carte));
}
// lien reçu par mail : ?confirmer=… ou ?reinitialiser=… ; le jeton est aussitôt retiré de l'adresse
function lireLienRecu() {
  const q = new URLSearchParams(location.search), conf = q.get("confirmer"), reinit = q.get("reinitialiser");
  if (!conf && !reinit) return;
  history.replaceState(null, "", location.pathname);
  if (reinit) { S.jetonLien = reinit; S.etapeCompte = "nouveau"; return; }
  api("enseignant/confirmer", {methode: "POST", corps: {jeton: conf}}).then(r => { S.messageCompte = r.message; }, e => { S.messageCompte = e.message; })
    .finally(() => { S.etapeCompte = "connexion"; rendre(); });
}
/** Administratrice : demandes de compte à valider, comptes ouverts (à suspendre si besoin). */
function carteComptes() {
  if (!S.comptesListe && !S.comptesEnCours) {        // chargée une fois par visite de l'écran (null : à recharger)
    S.comptesEnCours = true;
    appel("enseignant/comptes").then(l => { S.comptesListe = l; }, () => { S.comptesListe = []; }).finally(() => { S.comptesEnCours = false; rendre(); });
  }
  const liste = S.comptesListe || [];
  const agir = async (id, action) => { try { await appel(`enseignant/comptes/${id}/${action}`, {methode: "POST", corps: {}}); S.comptesListe = null; rendre(); } catch (e) { toast(e.message); } };
  const ligne = x => el("div", {class: "card", style: "gap:6px"},
    el("div", {class: "row", style: "justify-content:space-between"}, el("b", {}, x.nom || x.email), el("span", {class: "pill " + (x.valide ? "ok" : "warn")}, x.valide ? tx("ouvert") : tx("en attente"))),
    el("p", {class: "small"}, x.email + " · " + tx`demandé le ${new Date(x.cree).toLocaleDateString(LOCALE)}` + (x.valide ? " · " + tx`${x.classes} classe${x.classes > 1 ? "s" : ""}` : "")),
    x.presentation ? el("p", {class: "small muted"}, x.presentation) : null,
    x.email === S.email ? null : el("div", {class: "row"}, x.valide ? el("button", {class: "ghost small", onclick: () => agir(x.id, "suspendre")}, tx("Suspendre"))
      : [el("button", {class: "primary small", onclick: () => agir(x.id, "valider")}, tx("Valider")),
         x.classes ? el("span", {class: "small muted"}, tx("compte suspendu")) : el("button", {class: "ghost small", onclick: () => agir(x.id, "refuser")}, tx("Refuser"))]));
  const attente = liste.filter(x => !x.valide).length;
  return el("div", {class: "card"}, el("h2", {}, tx("Comptes enseignants") + (attente ? tx` · ${attente} demande${attente > 1 ? "s" : ""} en attente` : "")),
    el("p", {class: "small muted"}, tx("Chaque demande vous est aussi envoyée par mail. Valider ouvre l'accès et prévient la personne ; refuser efface la demande. Une personne n'a jamais accès aux classes des autres.")),
    !S.comptesListe ? el("p", {class: "small muted"}, tx("Chargement…")) : liste.length ? liste.map(ligne) : el("p", {class: "small muted"}, tx("Aucune demande pour l'instant.")));
}
async function listerClasses() { try { S.classes = await appel("classes"); } catch {} rendre(); }
function ecranClasses() {
  $("#titre").textContent = tx("Mes classes"); $("#sous-titre").textContent = S.email || "";
  const nom = el("input", {type: "text", id: "nom", maxlength: "80", placeholder: tx("Par exemple : 4e B, sciences")});
  $("#vue").replaceChildren(el("div", {class: "wrap"},
    S.classes.length ? el("div", {class: "grid2"}, S.classes.map(k => el("div", {class: "card"}, el("h2", {}, k.nom), el("p", {class: "small muted"}, tx("Code : ") + k.code),
      el("button", {class: "primary", onclick: () => { S.code = k.code; S.onglet = "classe"; S.detail = null; S.exos = null; S.importMsg = null; S.brouillon = null; chargerClasse(); }}, tx("Ouvrir"))))) : el("p", {class: "muted"}, tx("Aucune classe pour l'instant.")),
    el("div", {class: "card"}, el("h2", {}, tx("Nouvelle classe")), el("label", {for: "nom"}, tx("Nom")), nom,
      el("button", {onclick: async () => { try { const r = await appel("classes", {methode: "POST", corps: {nom: nom.value, langue: LANGUE}}); S.classes.unshift({...r}); rendre(); } catch (e) { toast(e.message); } }}, tx("Créer la classe")),
      el("p", {class: "small muted"}, tx("Un code à six caractères est créé : les élèves le saisissent avec un pseudonyme, sans compte ni adresse."))),
    S.admin ? carteComptes() : null,
    el("button", {class: "ghost", onclick: deconnecter}, tx("Se déconnecter"))));
}

/* ---------------------------------------------------------------- séances : plusieurs peuvent rester ouvertes */
function carteSeances(c) {
  const ouv = c.ouvertes || [], effacees = c.supprimees || [];
  const nums = Array.from({length: c.seance || 0}, (_, i) => i + 1).filter(n => !effacees.includes(n)).reverse();
  const nbEleves = n => Object.values(S.traces).filter(d => d.seances?.[n]?.phase || d.seances?.[n]?.ideesAvant).length;
  const modifier = n => { S.seanceEditee = n; S.onglet = "reglages"; S.detail = null;
    document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-selected", String(x.dataset.tab === "reglages"))); rendre(); window.scrollTo(0, 0); };
  const effacer = async n => {
    try { const r = await appel(`classes/${S.code}/seances/${n}`, {methode: "DELETE"}); S.config = {...DEFAUT, ...r.config}; S.confirmer = null;
      toast(tx`Séance ${N(n)} effacée` + (r.elevesConcernes ? tx`, avec les traces de ${r.elevesConcernes} élève${r.elevesConcernes > 1 ? "s" : ""}.` : ".")); await chargerClasse(); }
    catch (e) { toast(e.message); }
  };
  const envoyer = (seance, liste) => majConfig({seance, ouvertes: liste, ouverte: liste.includes(seance)});   // « ouverte » reste cohérent
  const basculer = n => envoyer(c.seance, ouv.includes(n) ? ouv.filter(x => x !== n) : [...ouv, n].sort((a, b) => a - b));
  const nouvelle = () => {
    if (c.seance) { S.suite = true; S.suiteChoisie = null; rendre(); return; }      // propositions d'après la séance précédente
    if (!c.tache) { S.onglet = "reglages"; rendre(); toast(tx("Saisissez d'abord la consigne de la nouvelle séance dans Réglages.")); return; }
    envoyer((c.seance || 0) + 1, [...ouv, (c.seance || 0) + 1]);
  };
  const titre = n => (c.archives || {})[n]?.tache || (n === c.seance ? c.tache : "");
  return el("div", {class: "card"},
    el("div", {class: "row", style: "justify-content:space-between"}, el("h2", {}, tx("Séances")),
      S.suite ? null : el("button", {class: "primary", onclick: nouvelle}, tx`Créer la séance ${prochainNumero(c)}`)),
    nums.length ? el("ol", {class: "ideas"}, nums.map(n => el("li", {style: "flex-direction:column;align-items:stretch;gap:8px"},
      el("div", {class: "row", style: "justify-content:space-between"},
        el("span", {}, el("b", {}, tx`Séance ${N(n)}`), " · ", titre(n) || el("span", {class: "muted"}, tx("consigne non renseignée"))),
        el("span", {class: "pill " + (ouv.includes(n) ? "ok" : "")}, ouv.includes(n) ? tx("ouverte") : tx("fermée"))),
      S.confirmer === "seance" + n
        ? el("div", {class: "notice ko row"}, el("span", {}, tx`Effacer définitivement la séance ${N(n)}` + (nbEleves(n) ? tx` et le travail de ${nbEleves(n)} élève${nbEleves(n) > 1 ? "s" : ""} (idées, exercices, vérifications) ?` : " ?")),
            el("button", {class: "danger", onclick: () => effacer(n)}, tx("Effacer")), el("button", {class: "ghost", onclick: () => { S.confirmer = null; rendre(); }}, tx("Annuler")))
        : el("div", {class: "row"},
            el("button", {class: "ghost", onclick: () => basculer(n)}, ouv.includes(n) ? tx("Fermer") : tx("Rouvrir")),
            el("button", {class: "ghost", onclick: () => modifier(n)}, tx("Modifier")),
            el("button", {class: "danger", onclick: () => { S.confirmer = "seance" + n; rendre(); }}, tx("Effacer")))))) :
      el("p", {class: "small muted"}, tx("Aucune séance pour l'instant : saisissez une consigne dans Réglages, puis créez la séance 1.")),
    el("p", {class: "small muted"}, tx`Les élèves choisissent parmi les séances ouvertes ; sur une séance terminée, ils peuvent reprendre pour s'améliorer. Les réglages de la tâche (onglet Réglages) s'appliquent à la séance ${N(c.seance || 1)} ; les séances précédentes gardent leur consigne. Règle de classe : ${NOM_ORDRE[c.ordre]} · ${NOM_MODE[c.mode]} · ${c.minIdees} idées avant l'IA.`));
}

function barre(lbl, v, couleur) { return [el("span", {}, lbl), el("div", {class: "bar", role: "img", "aria-label": `${lbl} ${fr(v)}`}, el("i", {style: `width:${v == null ? 0 : Math.round(v * 100)}%;background:${couleur}`})), el("span", {class: "small"}, fr(v))]; }
const niveauDe = (c, perso) => c.exercices?.actifs ? (perso.niveau ?? c.exercices.niveau) : null;
// la recommandation part du niveau des exercices réellement passés (sinon, un clic sur « Appliquer » la ferait glisser à chaque fois)
const niveauReference = (c, perso, est) => { const n = niveauDe(c, perso); if (n == null) return null; const fait = est?.dernier?.niveauExos; return fait != null ? Math.round(fait) : n; };
const recoAppliquee = (c, perso, reco) => perso.ordre === reco.ordre && perso.mode === reco.mode && !!perso.retrait === reco.retrait
  && (reco.niveau == null || (perso.niveau ?? c.exercices?.niveau) === reco.niveau)
  && (reco.variante == null || (perso.variante ?? "standard") === reco.variante);
const varianteDe = (c, perso) => c.variantes?.actives ? (perso.variante ?? "standard") : null;
// comme pour le niveau, la recommandation part de la variante réellement travaillée à la dernière séance
const varianteReference = (c, perso, est) => { const v = varianteDe(c, perso); if (v == null) return null; return est?.dernier?.variante ?? v; };
function appliquer(u, reco) {
  const patch = {...(S.config.eleves || {})};
  const palier = p => p.variante === "exigeante" ? (p.palier ?? S.config.eleves?.[u]?.palier ?? null) : null;
  if (reco) patch[u] = {ordre: reco.ordre, mode: reco.mode, retrait: reco.retrait, niveau: reco.niveau, variante: reco.variante, palier: palier(reco)}; else delete patch[u];
  majConfig({eleves: patch, origine: reco ? "recommandation" : "manuel"});
}
function ongletClasse() {
  const c = S.config, uids = Object.keys(S.traces), n = c.seance;
  const tete = [carteSeances(c), carteSuites(c)].filter(Boolean);
  if (!uids.length) {
    $("#vue").replaceChildren(el("div", {class: "wrap"}, tete, el("div", {class: "card"}, el("h2", {}, tx("Aucun élève pour l'instant")),
      el("p", {}, tx`Donnez aux élèves l'adresse de l'application élève et le code ${S.code}. Ils choisissent un pseudonyme ; leurs traces apparaissent ici.`))));
    return;
  }
  const idees = uids.flatMap(u => { const s = S.traces[u].seances?.[n]; return s ? [...(s.ideesAvant || []), ...(s.ideesApres || [])].map(i => i.texte) : []; });
  const actifs = uids.filter(u => S.traces[u].seances?.[n]), finis = actifs.filter(u => S.traces[u].seances[n].phase === "envoye");
  const kpis = el("div", {class: "kpis"},
    el("div", {class: "kpi"}, el("span", {class: "small muted"}, tx("Élèves dans la séance")), el("b", {}, actifs.length), el("span", {class: "small muted"}, tx`${finis.length} ont terminé`)),
    el("div", {class: "kpi"}, el("span", {class: "small muted"}, tx("Idées de la classe")), el("b", {}, idees.length), el("span", {class: "small muted"}, tx`${distinctes(idees)} distinctes`)),
    el("div", {class: "kpi"}, el("span", {class: "small muted"}, tx("Diversité")), el("b", {}, idees.length ? fr(distinctes(idees) / idees.length) : "–"), el("span", {class: "small muted"}, tx("part d'idées distinctes"))));
  const cartes = uids.map(u => {
    const doc = S.traces[u], est = etatEleve(S.traces, S.notes, u), e = est?.etat || {}, perso = c.eleves?.[u] || {};
    const niv = niveauDe(c, perso), rup = ruptures(e, c), reco = recommandation(e, c, niveauReference(c, perso, est), varianteReference(c, perso, est), est);
    // la séance à montrer : celle, encore ouverte, sur laquelle l'élève travaille ; sinon la plus récente
    const enCours = (c.ouvertes || []).slice().reverse().find(k => doc.seances?.[k] && doc.seances[k].phase !== "envoye");
    const nAff = enCours ?? n, s = doc.seances?.[nAff];
    const statut = !s ? el("span", {class: "pill"}, tx`séance ${N(nAff)} : pas commencée`) : s.phase === "envoye" ? el("span", {class: "pill ok"}, tx`séance ${N(nAff)} terminée` + (s.essais > 1 ? tx` (${s.essais} essais)` : ""))
      : el("span", {class: "pill"}, tx`séance ${N(nAff)}, ` + (s.essais > 1 ? tx`essai ${s.essais}, ` : "") + tx("en cours : ") + ({charge: "accueil", reflexion: tx("réflexion"), ia: tx("avec l'IA"), fin: "bilan", exercices: "exercices"}[s.phase || "exercices"] || s.phase));
    const applique = recoAppliquee(c, perso, reco);
    const exosN = s?.exercices?.filter(x => x.score != null) || [];
    return el("div", {class: "card"},
      el("div", {class: "row", style: "justify-content:space-between"}, el("h3", {}, doc.pseudo), statut),
      el("div", {class: "bars"}, barre(tx("Charge"), e.C, "var(--blue)"), barre(tx("Agentivité"), e.A, "var(--accent)"), barre(tx("Pensée div."), e.D, "var(--green)"), barre(tx("Maîtrise"), e.M, "var(--violet)")),
      el("div", {class: "row"}, rup.length ? rup.map(x => el("span", {class: "pill " + x.niv}, (x.niv === "ko" ? tx("rupture : ") : tx("menace : ")) + tx(x.nom))) : el("span", {class: "pill ok"}, tx("dans le domaine"))),
      el("p", {class: "small"}, el("b", {}, tx("Recommandation : ")), reco.texte),
      blocViabilite(u),
      el("p", {class: "small muted"}, tx("Réglage actuel : ") + (perso.retrait ? tx("IA retirée") : `${NOM_ORDRE[perso.ordre || c.ordre]}, ${NOM_MODE[perso.mode || c.mode]}`)
        + (niv != null ? tx` · exercices niveau ${niv}` : "") + (c.variantes?.actives ? ` · ${NOM_VARIANTE[perso.variante ?? "standard"]}` + (perso.variante === "exigeante" && perso.palier ? tx` (si la tâche reste au niveau ${perso.palier})` : "") : "")),
      s?.indicesVus ? el("p", {class: "small"}, tx`Coups de pouce ouverts : ${s.indicesVus}`) : null,
      ligneDemarche(s),
      S.messages.some(m => m.eleve === u && !m.lu) ? el("p", {class: "small muted"}, tx("✉ Message pas encore lu")) : null,
      s?.verification ? el("p", {class: "small"}, tx`Idées vérifiées : ${s.verification.justes}/${s.verification.idees?.length ?? 0} justes (${s.verification.nombre} vérification${s.verification.nombre > 1 ? "s" : ""})`) : null,
      exosN.length ? el("p", {class: "small"}, tx`Exercices de la séance : ${Math.round(100 * exosN.reduce((a, x) => a + x.score, 0) / exosN.length)} % de réussite, ${exosN.filter(x => (x.premierScore ?? x.score) >= 1).length}/${exosN.length} au premier essai`) : null,
      el("div", {class: "row"},
        reco.ordre ? el("button", {disabled: applique, onclick: () => appliquer(u, reco)}, applique ? tx("Recommandation appliquée") : tx("Appliquer")) : null,
        Object.keys(perso).length ? el("button", {class: "ghost", onclick: () => appliquer(u, null)}, tx("Règle de la classe")) : null,
        el("button", {class: "ghost", onclick: () => { S.detail = u; rendre(); }}, tx("Détail"))));
  });
  const tout = el("button", {onclick: () => { const patch = {...(c.eleves || {})}; for (const u of uids) { const est = etatEleve(S.traces, S.notes, u), r = recommandation(est?.etat || {}, c, niveauReference(c, c.eleves?.[u] || {}, est), varianteReference(c, c.eleves?.[u] || {}, est), est); if (r.ordre) patch[u] = {ordre: r.ordre, mode: r.mode, retrait: r.retrait, niveau: r.niveau, variante: r.variante, palier: r.variante === "exigeante" ? (r.palier ?? c.eleves?.[u]?.palier ?? null) : null}; } majConfig({eleves: patch, origine: "toutes_recommandations"}); }}, tx("Appliquer toutes les recommandations"));
  $("#vue").replaceChildren(el("div", {class: "wrap"}, tete, kpis, carteGalerie(c), el("div", {class: "row", style: "justify-content:space-between"}, el("h2", {}, tx("Élèves")), tout), el("div", {class: "grid2"}, cartes),
    el("details", {class: "card"}, el("summary", {}, tx("Comment l'état est-il estimé ?")),
      el("p", {class: "small"}, tx("Charge : difficultés déclarées en début et en fin de séance (de 0,1 à 0,9), plus 0,1 si l'élève s'est déclaré bloqué. Agentivité : pour moitié la part d'idées non reprises de l'IA, pour moitié le nombre d'idées produites avant toute aide. Pensée divergente : idées distinctes, originalité dans la classe, absence de reprise. Maîtrise : compréhension déclarée et votre appréciation. Lissage entre séances : 60 % pour la dernière. Seuils de rupture du modèle : surcharge au-dessus de 0,85, ennui sous 0,2, dépendance sous 0,3, rigidité sous 0,25.")),
      el("p", {class: "small muted"}, tx("Ces indicateurs sont des estimations grossières : ils aident à regarder un élève, ils ne le mesurent pas.")))));
}
const NOM_DEMARCHE = {hasard: tx("au hasard"), ordre: tx("dans un ordre"), transformer: tx("en transformant une idée"), aide: tx("avec un coup de pouce ou l'IA"), autre: "autrement"};
const NOM_AIDE = {idees: tx("ses propres idées"), pouce: tx("un coup de pouce"), ia: tx("l'IA"), verification: tx("la vérification"), camarade: tx("un camarade"), enseignant: tx("vous"), rien: tx("rien de particulier")};
/** Galerie : l'enseignant choisit des idées originales de la séance, montrées sans nom aux élèves qui ont terminé. */
function carteGalerie(c) {
  const n = c.seance; if (!n) return null;
  const parEleve = Object.entries(S.traces).map(([u, d]) => { const s = d.seances?.[n]; if (!s) return [];
    const v = s.verification; return [...(s.ideesAvant || []), ...(s.ideesApres || [])].map(i => ({u, texte: i.texte, juste: v ? v.retours?.[v.idees.indexOf(i.texte)]?.statut === "juste" : null})); }).flat();
  if (!parEleve.length) return null;
  // une idée par formulation ; originalité = part des autres élèves qui n'ont rien écrit de semblable
  const cle = t => { const m = [...mots(t)]; return m.length ? m.sort().join(" ") : String(t).toLowerCase().replace(/\s+/g, ""); };
  const semblable = (a, b) => cle(a) === cle(b) || (mots(a).size > 0 && jaccard(a, b) >= 0.5);
  const auteurs = new Set(parEleve.map(x => x.u)), vues = new Map();
  for (const x of parEleve) {
    const k = cle(x.texte); if (vues.has(k)) continue;
    const proches = new Set(parEleve.filter(y => y.u !== x.u && semblable(x.texte, y.texte)).map(y => y.u));
    vues.set(k, {...x, originalite: 1 - proches.size / Math.max(1, auteurs.size - 1)});
  }
  const idees = [...vues.values()].sort((a, b) => (b.juste === true) - (a.juste === true) || b.originalite - a.originalite);
  const publiees = (c.galerie || {})[n] || [];
  S.galerieChoix ??= new Set(publiees);
  const publier = async liste => { await majConfig({galerie: {...(c.galerie || {}), [n]: liste}}); S.galerieChoix = null; toast(liste.length ? tx`Galerie publiée : ${liste.length} idée${liste.length > 1 ? "s" : ""}.` : tx("Galerie retirée.")); };
  return el("details", {class: "card"}, el("summary", {}, tx`Galerie d'idées de la séance ${N(n)}` + (publiees.length ? tx` · ${publiees.length} publiée${publiees.length > 1 ? "s" : ""}` : "")),
    el("p", {class: "small muted"}, tx("Choisissez jusqu'à 12 idées à montrer à la classe, sans les noms. Les élèves les voient après avoir terminé la séance, pour relancer leurs propres idées. Les plus originales (les moins proches de celles des autres) sont en haut. Relisez-les : une idée ne doit pas permettre de reconnaître son auteur.")),
    c.verification?.mode === "calcul" ? el("p", {class: "small notice warn"}, tx("Tâche vérifiée par calculs : montrer des solutions permet de les recopier lors d'une reprise. Préférez publier quand la séance est fermée, ou choisir peu d'idées.")) : null,
    el("ul", {class: "ideas"}, idees.slice(0, 40).map(x => { const id = "gal-" + Math.random().toString(36).slice(2, 8);
      const i = el("input", {type: "checkbox", id, checked: S.galerieChoix.has(x.texte)});
      i.addEventListener("change", () => { i.checked ? S.galerieChoix.add(x.texte) : S.galerieChoix.delete(x.texte); });
      return el("li", {}, el("label", {for: id, class: "row", style: "gap:8px;font-weight:400"}, i, x.texte),
        el("span", {class: "tag"}, (x.juste === true ? tx("juste · ") : x.juste === false ? tx("à revoir · ") : "") + tx`originalité ${fr(x.originalite)}`)); })),
    el("div", {class: "row"}, el("button", {class: "primary", onclick: () => publier([...S.galerieChoix].slice(0, 12))}, tx("Publier la galerie")),
      publiees.length ? el("button", {class: "ghost", onclick: () => publier([])}, tx("Retirer la galerie")) : null));
}
function ligneDemarche(s) {
  const d = (s?.demarches || []).slice(-1)[0], a = s?.aides || [];
  if (!d && !a.length) return null;
  return el("p", {class: "small"}, d ? [el("b", {}, tx("A cherché : ")), NOM_DEMARCHE[d.choix] + (d.texte ? ` (« ${d.texte} »)` : "")] : null,
    d && a.length ? " · " : null, a.length ? [el("b", {}, tx("Aidé par : ")), a.map(x => NOM_AIDE[x]).join(", ")] : null);
}
function carteMessage(u) {
  const ta = el("textarea", {id: "message", rows: "2", maxlength: "500", placeholder: tx("Par exemple : Bravo pour ta méthode ! La prochaine fois, essaie d'abord sans l'IA.")});
  const envoyer = async () => {
    if (!ta.value.trim()) return;
    try { await appel(`classes/${S.code}/messages`, {methode: "POST", corps: {eleve: u, texte: ta.value.trim(), seance: S.config.seance || null}}); S.messages = await appel(`classes/${S.code}/messages`); toast(tx("Message envoyé : l'élève le verra au début de sa prochaine séance.")); rendre(); }
    catch (e) { toast(e.message); }
  };
  const miens = S.messages.filter(m => m.eleve === u);
  return el("div", {class: "card"}, el("h2", {}, tx("Un mot pour l'élève")),
    el("label", {for: "message"}, tx("Message affiché au début de sa prochaine séance")), ta, el("div", {class: "row"}, el("button", {class: "primary", onclick: envoyer}, tx("Envoyer"))),
    miens.length ? el("ul", {class: "ideas"}, miens.map(m => el("li", {}, el("span", {}, m.texte),
      el("span", {class: "row", style: "gap:6px"}, el("span", {class: "pill " + (m.lu ? "ok" : "")}, m.lu ? "lu" : tx("pas encore lu")),
        el("button", {class: "ghost small", onclick: async () => { try { await appel(`classes/${S.code}/messages/${m.id}`, {methode: "DELETE"}); S.messages = S.messages.filter(x => x !== m); rendre(); } catch (e) { toast(e.message); } }}, tx("Retirer")))))) : null,
    el("p", {class: "small muted"}, tx("Un retour humain, court et précis, compte plus que celui de l'IA : dites ce qui a bien marché et une seule chose à essayer.")));
}
const MOTIFS = [tx("donne la réponse"), "erreur", tx("inadaptée au niveau"), tx("hors sujet"), "autre"];
function echangesIA(u, n, echanges) {
  const sig = k => S.signalements.find(x => x.eleve === u && x.seance === n && x.indice === k);
  const signaler = async (k, motif) => {
    try { await appel(`classes/${S.code}/signalements`, {methode: "POST", corps: {eleve: u, seance: n, indice: k, motif}}); S.signalements = await appel(`classes/${S.code}/signalements`); rendre(); }
    catch (e) { toast(e.message); }
  };
  const bloquees = S.signalements.filter(x => x.eleve === u && x.seance === n && x.auteur === "auto").length;
  return el("details", {}, el("summary", {}, tx`Échanges avec l'IA (${echanges.length})` + (bloquees ? tx` · ${bloquees} réponse${bloquees > 1 ? "s" : ""} bloquée${bloquees > 1 ? "s" : ""}` : "")),
    el("div", {class: "chat"}, echanges.map((e, k) => e.role !== "ia" ? el("div", {class: "msg el"}, e.texte) : el("div", {class: "msg ia"}, e.texte,
      el("div", {class: "row", style: "margin-top:6px"}, sig(k)
        ? [el("span", {class: "pill warn"}, tx("signalée : ") + sig(k).motif), el("button", {class: "ghost small", onclick: () => signaler(k, "")}, tx("Retirer"))]
        : (() => { const sel = el("select", {"aria-label": tx("Motif du signalement")}, el("option", {value: ""}, tx("Signaler…")), MOTIFS.map(m => el("option", {value: m}, m)));
            sel.addEventListener("change", () => sel.value && signaler(k, sel.value)); return sel; })())))),
    bloquees ? el("p", {class: "small muted"}, tx("Les réponses bloquées contenaient une solution : l'élève a reçu à la place une question sur sa démarche. Elles figurent dans l'export des échanges (onglet Données).")) : null);
}
function detailEleve(u) {
  const doc = S.traces[u]; if (!doc) { S.detail = null; return ongletClasse(); }
  const nums = Object.keys(doc.seances || {}).map(Number).sort((a, b) => b - a);
  const zp = doc.zpdes;      // choix adaptatif des exercices : zone de niveaux ouverts et progrès récent
  const carteZone = zp && zp.zone.length ? el("div", {class: "card"}, el("h3", {}, tx("Exercices : choix adaptatif")),
    el("p", {class: "small"}, tx`Niveaux ouverts : ${zp.zone.join(", ")}` + (Object.keys(zp.reussite).length ? " · " + tx("réussite récente au premier essai : ") +
      Object.entries(zp.reussite).map(([k, v]) => tx`niveau ${k} ${Math.round(v * 100)} %`).join(", ") : "")),
    el("p", {class: "small muted"}, tx("Les prochains exercices sont tirés de préférence dans les niveaux ouverts où l'élève progresse le plus.")) ) : null;
  const blocs = nums.map(n => {
    const s = doc.seances[n], note = S.notes[u]?.[n];
    return el("div", {class: "card"},
      el("div", {class: "row", style: "justify-content:space-between"}, el("h3", {}, tx`Séance ${N(n)}` + (s.essais > 1 ? tx` · ${s.essais} essais` : "")), el("span", {class: "pill"}, `${NOM_ORDRE[s.ordre] || "–"} · ${NOM_MODE[s.mode] || "–"}`)),
      s.definitif ? el("div", {class: "notice row", style: "justify-content:space-between"},
        el("span", {class: "small"}, tx`Terminée définitivement par l'élève le ${new Date(s.definitif).toLocaleString(LOCALE, {dateStyle: "short", timeStyle: "short"})} : il voit sa correction.`),
        el("button", {class: "ghost small", onclick: async () => { try { await appel(`classes/${S.code}/eleves/${u}/seances/${n}/rouvrir`, {methode: "POST", corps: {}}); toast(tx("L'élève peut de nouveau modifier ou reprendre cette séance.")); await chargerClasse(); } catch (e) { toast(e.message); } }}, tx("Autoriser à reprendre"))) : null,
      s.variante && s.variante !== "standard" ? el("p", {class: "small"}, el("b", {}, NOM_VARIANTE[s.variante] + " : "), s.tache || "") : null,
      s.indicesVus ? el("p", {class: "small"}, tx`Coups de pouce ouverts : ${s.indicesVus}`) : null,
      el("p", {class: "small muted"}, tx`Difficulté déclarée : ${s.chargeDebut ?? "–"}/5 au début, ${s.chargeFin ?? "–"}/5 à la fin · compréhension ${s.compris ?? "–"}/5 · ${s.bloque ? tx("s'est déclaré bloqué · ") : ""}${s.premiereDemande != null ? tx("première demande à l'IA après ") + Math.round(s.premiereDemande / 60) + tx(" min") : tx("aucune demande à l'IA")}`),
      s.verification ? el("details", {}, el("summary", {}, tx`Dernière vérification des idées : ${s.verification.justes}/${s.verification.idees.length} justes`),
        el("ol", {class: "ideas"}, s.verification.idees.map((t, k) => el("li", {style: "flex-direction:column;align-items:stretch"},
          el("div", {class: "row", style: "justify-content:space-between"}, el("span", {}, t), el("span", {class: "tag"}, {juste: "juste", a_revoir: tx("à revoir"), doublon: "doublon"}[s.verification.retours[k]?.statut] || "")),
          el("p", {class: "small muted"}, s.verification.retours[k]?.retour || "")))),
        el("p", {class: "small"}, s.verification.bilan || "")) : null,
      el("p", {class: "small", style: "font-weight:700"}, tx("Idées avant l'IA")), listeIdees(s.ideesAvant || [], tx("avant")),
      el("p", {class: "small", style: "font-weight:700"}, tx("Idées après l'IA")), listeIdees(s.ideesApres || [], tx("après")),
      (s.ideesRetirees || []).length ? el("details", {class: "small"}, el("summary", {}, tx`Idées retirées par l'élève (${s.ideesRetirees.length})`), listeIdees(s.ideesRetirees, tx("retirée"))) : null,
      (s.exercices || []).length ? el("div", {class: "field"}, el("p", {class: "small", style: "font-weight:700"}, tx("Exercices")),
        el("ol", {class: "ideas"}, s.exercices.map(x => el("li", {}, el("span", {}, tx`${x.titre || tx("Exercice")} (niveau ${x.niveau ?? "–"})`),
          el("span", {class: "tag"}, x.score == null ? tx("non fait") : tx`${Math.round(x.score * 100)} % · ${x.tentatives} essai${x.tentatives > 1 ? "s" : ""} · ${x.duree ?? 0} s`))))) : null,
      ligneDemarche(s),
      (s.historique || []).length ? el("p", {class: "small"}, el("b", {}, tx("Essais : ")), [...s.historique, {essai: s.essais, justes: s.verification?.justes, idees: (s.ideesAvant || []).length + (s.ideesApres || []).length}]
        .map(x => tx`essai ${x.essai} : ` + (x.justes != null ? tx`${x.justes} juste${x.justes > 1 ? "s" : ""}` : tx`${x.idees} idée${x.idees > 1 ? "s" : ""}`)).join(" → ")) : null,
      (s.echanges || []).length ? echangesIA(u, n, s.echanges) : null,
      el("div", {class: "field"}, el("p", {style: "font-weight:700"}, tx("Votre appréciation de la maîtrise")),
        el("div", {class: "scale"}, [tx("non atteint"), tx("fragile"), tx("en cours"), tx("atteint"), tx("dépassé")].map((lib, i) => el("button", {"aria-pressed": String(note === i), onclick: () => noter(u, n, i)}, lib)))));
  });
  const supprimer = S.confirmer === u
    ? el("div", {class: "notice ko row"}, el("span", {}, tx("Supprimer définitivement cet élève et toutes ses traces ?")), el("button", {class: "danger", onclick: () => effacerEleve(u)}, tx("Supprimer")), el("button", {class: "ghost", onclick: () => { S.confirmer = null; rendre(); }}, tx("Annuler")))
    : el("button", {class: "danger", onclick: () => { S.confirmer = u; rendre(); }}, tx("Supprimer les données de cet élève"));
  $("#vue").replaceChildren(el("div", {class: "wrap"}, el("div", {class: "row"}, el("button", {class: "ghost", onclick: () => { S.detail = null; S.confirmer = null; rendre(); }}, tx("← Classe")), el("h2", {}, doc.pseudo),
    el("span", {class: "pill"}, tx`code personnel : ${doc.pin || "–"}`)), carteMessage(u), carteZone, ...blocs, supprimer));
}
async function noter(u, n, v) {
  const notes = JSON.parse(JSON.stringify(S.notes)); (notes[u] ||= {})[n] = v; S.notes = notes; rendre();
  try { S.notes = await appel(`classes/${S.code}/notes`, {methode: "PUT", corps: notes}); } catch { toast(tx("Note non enregistrée.")); }
}
async function effacerEleve(u) {
  try { await appel(`classes/${S.code}/eleves/${u}`, {methode: "DELETE"}); S.detail = null; S.confirmer = null; await chargerClasse(); }
  catch (e) { toast(e.message); }
}
function ongletReglages() {
  const n = S.seanceEditee ?? S.config.seance;
  if (S.seanceEditee != null && S.seanceEditee !== S.config.seance) return reglagesSeance(n);
  const c = S.modele && S.modele.seance === n ? {...S.config, ...S.modele.reglages} : S.config;
  const tache = el("textarea", {id: "tache", rows: "3"}); tache.value = c.tache || "";
  const curseur = (id, lbl, min, max, pas, val, aide) => { const i = el("input", {type: "range", id, min, max, step: pas, value: val}); const o = el("output", {}, fr(+val)); i.addEventListener("input", () => o.textContent = fr(+i.value));
    return el("div", {class: "field"}, el("label", {for: id, class: "row", style: "justify-content:space-between"}, lbl, o), i, el("p", {class: "small muted"}, aide)); };
  const choix = (id, lbl, val, opts) => el("div", {class: "field"}, el("label", {for: id}, lbl), el("select", {id}, Object.entries(opts).map(([k, t]) => el("option", {value: k, selected: k === val}, t))));
  const {autonomie, ...ordres} = NOM_ORDRE;
  const lire = () => ({tache: $("#tache").value.trim(), saisieCode: $("#saisie-code").checked, evaluation: $("#seance-evaluation").checked, langue: $("#langue").value, visuels: $("#visuels").checked, public: $("#public").value, discipline: $("#discipline").value, ordre: $("#ordre").value, mode: $("#mode").value, minIdees: +$("#minIdees").value,
      seuilCharge: +$("#seuilCharge").value, retraitAgentivite: +$("#retraitAgentivite").value, seuilMaitrise: +$("#seuilMaitrise").value, niveauTache: +$("#niveauTache").value,
      modele: c.modele || "", indices: lireIndices("std"), variantes: lireVariantes(), lecture: {active: $("#lecture-active").checked, langue: $("#lecture-langue").value, dictee: $("#lecture-dictee").checked},
      verification: {mode: $("#v-mode").value, cible: +String($("#v-cible").value).replace(",", "."), nombres: $("#v-nombres").value, attendu: +$("#v-attendu").value || 0,
        criteres: $("#v-criteres").value, maximum: +$("#v-maximum").value, uneFois: $("#v-unefois").checked}});
  const fermee = c.seance && !(c.ouvertes || []).includes(c.seance);
  const ouvrir = async () => { await majConfig({...lire(), ouvertes: [...(c.ouvertes || []), c.seance].sort((a, b) => a - b), ouverte: true}); S.modele = null; toast(tx`Séance ${N(c.seance)} enregistrée et ouverte aux élèves.`); };
  $("#vue").replaceChildren(el("div", {class: "wrap"},
    c.seance ? el("div", {class: "notice"}, el("p", {}, tx`La tâche, les variantes et la vérification ci-dessous sont celles de la séance ${N(c.seance)}, la plus récente. Pour une séance précédente, utilisez « Modifier » dans la carte Séances (onglet Classe).`)) : null,
    fermee ? el("div", {class: "notice warn"}, el("p", {}, tx`La séance ${N(c.seance)} est fermée : les élèves ne la voient pas encore. Relisez la consigne et les réglages ci-dessous, puis ouvrez-la.`),
      el("button", {class: "primary", onclick: ouvrir}, tx`Enregistrer et ouvrir la séance ${N(c.seance)} aux élèves`)) : null,
    carteModeles(n, true),
    carteNouvelle(c),
    carteGift(c),
    el("div", {class: "card"}, el("h2", {}, tx("La tâche")), el("label", {for: "tache"}, tx("Consigne affichée aux élèves")), tache, caseCode(c),
      champsIndices("std", c.indices), c.seance ? ligneDocument(c, v => majConfig({...lire(), document: v})) : null),
    carteVariantes(c),
    el("div", {class: "card"}, el("h2", {}, tx("Règle de la classe")),
      choix("langue", tx("Langue de la classe"), c.langue || "fr", LANGUES),
      el("p", {class: "small muted"}, tx("Les élèves voient leur application dans cette langue, et l'IA (tuteur et vérification) leur répond dans cette langue. Les consignes, les modèles de séances et les exercices restent tels que vous les avez écrits.")),
      choix("public", tx("Public de la classe"), c.public || "ecole", PUBLICS),
      el("label", {for: "visuels", class: "row", style: "gap:8px;font-weight:600"}, el("input", {type: "checkbox", id: "visuels", checked: c.visuels !== false}),
        tx("Illustrations adaptées au niveau et à la discipline, sur la page des élèves")),
      el("p", {class: "small muted"}, tx("Couleurs et dessins d'après la discipline de la séance : vifs à l'école et au collège (à l'école, une plante grandit avec les idées), discrets au lycée et dans le supérieur.")),
      choix("discipline", tx("Discipline de la classe"), c.discipline || "", {"": tx`Celle de ses séances${disciplineDe({...c, discipline: ""}) ? " (" + disciplineDe({...c, discipline: ""}) + ")" : ""}`,
        ...Object.fromEntries([...new Set((S.modeles || []).map(m => m.discipline))].sort((a, b) => a.localeCompare(b)).map(d => [d, d])), "*": tx("Toutes les disciplines (classe polyvalente)")}),
      el("p", {class: "small muted"}, tx("La classe ne voit que les modèles de séances et les suites proposées de sa discipline. « Toutes les disciplines » convient à une classe polyvalente (école) : les suites proposent alors aussi de varier de discipline.")),
      el("p", {class: "small muted"}, tx("Règle le ton et l'exigence de l'IA (tuteur et vérification des idées) et les modèles de séances proposés. Dans le supérieur, l'IA vérifie la rigueur des justifications.")),
      choix("ordre", tx("Ordre dans la séance"), c.ordre, ordres), choix("mode", tx("Rôle de l'IA"), c.mode, NOM_MODE),
      curseur("minIdees", tx("Idées à écrire avant d'ouvrir l'IA"), 0, 6, 1, c.minIdees, tx("En réflexion d'abord. L'élève peut toujours se déclarer bloqué.")),
      curseur("seuilCharge", tx("Seuil de charge"), 0.5, 0.85, 0.05, c.seuilCharge, tx("Au-dessus, l'aide vient d'abord. « Difficile » correspond à 0,7.")),
      curseur("retraitAgentivite", tx("Agentivité de retrait"), 0.4, 1, 0.05, c.retraitAgentivite, tx("Au-dessus, on recommande de retirer l'IA.")),
      curseur("seuilMaitrise", tx("Maîtrise attendue"), 0.2, 0.9, 0.05, c.seuilMaitrise, tx("Sous ce niveau, la maîtrise est signalée comme insuffisante."))),
    carteVerification(c),
    carteLecture(c),
    el("div", {class: "card"}, el("h2", {}, tx("Viabilité (expérimental)")),
      el("div", {class: "field"}, el("label", {for: "niveauTache"}, tx("Difficulté de la tâche ouverte pour le modèle")),
        el("select", {id: "niveauTache"}, [1, 2, 3, 4, 5].map(n => el("option", {value: n, selected: n === (c.niveauTache ?? 3)}, tx`Niveau ${n}` + ["", tx(" (très accessible)"), tx(" (accessible)"), tx(" (moyen)"), tx(" (exigeant)"), tx(" (très exigeant)")][n]))),
        el("p", {class: "small muted"}, tx("Sert à situer les élèves dans les tables du modèle de viabilité quand les exercices ne sont pas activés ; sinon, c'est le niveau d'exercices de chaque élève qui est utilisé.")))),
    el("button", {class: "primary", onclick: async () => { await majConfig(lire()); S.modele = null; toast(tx("Réglages enregistrés.")); }}, tx("Enregistrer les réglages"))));
}
/** Modifier une séance précédente : seulement sa tâche (consigne, coups de pouce, variantes, vérification). */
function reglagesSeance(n) {
  const c = S.config, arch = (c.archives || {})[n] || {};
  const src = {...c, ...arch, ...(S.modele && S.modele.seance === n ? S.modele.reglages : {})};
  const tache = el("textarea", {id: "tache", rows: "3"}); tache.value = src.tache || "";
  const lire = () => ({...arch, modele: src.modele || "", saisieCode: $("#saisie-code").checked, evaluation: $("#seance-evaluation").checked, tache: $("#tache").value.trim(), indices: lireIndices("std"), variantes: lireVariantes(),
      verification: {mode: $("#v-mode").value, cible: +String($("#v-cible").value).replace(",", "."), nombres: $("#v-nombres").value, attendu: +$("#v-attendu").value || 0,
        criteres: $("#v-criteres").value, maximum: +$("#v-maximum").value, uneFois: $("#v-unefois").checked},
      lecture: {active: $("#lecture-active").checked, langue: $("#lecture-langue").value, dictee: $("#lecture-dictee").checked}});
  const enregistrer = async () => {
    await majConfig({archives: {...(c.archives || {}), [n]: lire()}});
    S.modele = null; toast(tx`Séance ${N(n)} modifiée.`);
  };
  const retour = () => { S.seanceEditee = null; S.modele = null; S.onglet = "classe"; document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-selected", String(x.dataset.tab === "classe"))); rendre(); };
  $("#vue").replaceChildren(el("div", {class: "wrap"},
    el("div", {class: "notice warn"}, el("p", {style: "font-weight:700"}, tx`Vous modifiez la séance ${N(n)}`),
      el("p", {class: "small"}, tx("Les changements sont visibles tout de suite par les élèves, y compris ceux qui ont déjà commencé cette séance. Leurs idées et leurs résultats sont conservés. La règle de la classe et la viabilité se règlent pour toute la classe, depuis l'onglet Réglages.")),
      el("button", {class: "ghost", onclick: retour}, tx("← Retour à la classe"))),
    carteModeles(n, false),
    el("div", {class: "card"}, el("h2", {}, tx`La tâche de la séance ${N(n)}`), el("label", {for: "tache"}, tx("Consigne affichée aux élèves")), tache, caseCode(src), champsIndices("std", src.indices),
      ligneDocument(src, v => majConfig({archives: {...(c.archives || {}), [n]: {...lire(), document: v}}}))),
    carteVariantes(src),
    carteVerification(src),
    carteLecture(src),
    el("button", {class: "primary", onclick: enregistrer}, tx`Enregistrer la séance ${N(n)}`)));
}
/** Bibliothèque de séances prêtes à l'emploi (commun/modeles.json) : l'enseignant choisit, relit, puis enregistre. */
async function chargerModeles() {
  try { const r = await fetch("../commun/modeles.json", {cache: "no-cache"}); S.modeles = (await r.json()).modeles; } catch { S.modeles = []; }
  rendre();
}
function reglagesDuModele(m, c) {
  const v = nom => ({consigne: m.variantes?.[nom]?.consigne || "", indices: m.variantes?.[nom]?.indices || [],
    cible: m.variantes?.[nom]?.cible ?? null, attendu: m.variantes?.[nom]?.attendu ?? null});
  const niveauEx = Number((m.exercices || "").match(/\(niveau (\d)\)/)?.[1]) || null;   // « dossier/banque.gift (niveau 2) »
  return {modele: m.id, saisieCode: !!m.saisieCode, evaluation: !!m.evaluation, tache: m.tache, indices: m.indices || [], niveauTache: m.niveauTache ?? 3,
    verification: {...DEFAUT.verification, ...m.verification, attendu: m.verification?.attendu || 0, cible: m.verification?.cible ?? DEFAUT.verification.cible},
    variantes: {actives: !!m.variantes, accessible: v("accessible"), exigeante: v("exigeante")},
    // lectureActive: false → pas de voix pour cette langue (le créole, par exemple) : la lecture à voix haute est coupée
    lecture: {...(c.lecture || DEFAUT.lecture), langue: m.lecture || "fr-FR", ...(m.lectureActive === false ? {active: false} : {})},
    ...(niveauEx ? {exercices: {...(c.exercices || DEFAUT.exercices), niveau: niveauEx}} : {})};
}
/** Discipline de la classe : celle choisie dans « Règle de la classe », sinon celle de ses séances ; null = toutes (classe polyvalente,
    ou classe sans séance tirée d'un modèle). Une classe ne voit alors que les modèles et les suites de sa discipline. */
function disciplineDe(c) {
  if (c.discipline === "*") return null;
  if (c.discipline) return c.discipline;
  const ids = Object.values(c.archives || {}).map(a => a.modele);
  if (c.seance && !(c.supprimees || []).includes(c.seance)) ids.push(c.modele);
  return (S.modeles || []).find(m => ids.includes(m.id))?.discipline || null;
}
/** Modèles de séances de la classe : ceux de son public (tous si aucun ne correspond), puis ceux de sa discipline. */
function modelesDuPublic(c) {
  const l0 = (S.modeles || []).filter(m => (m.public || "ecole") === (c.public || "ecole")), l = l0.length ? l0 : (S.modeles || []);
  // la discipline au niveau de la classe ; si ce niveau n'en a pas (classe réglée sur un autre public), la discipline à tous les niveaux
  const d = disciplineDe(c);
  if (!d) return l;
  const auNiveau = l.filter(m => m.discipline === d), partout = (S.modeles || []).filter(m => m.discipline === d);
  return auNiveau.length ? auNiveau : partout.length ? partout : l;
}
function carteModeles(n, courante) {
  if (S.modeles == null) { chargerModeles(); return el("div", {class: "card"}, el("h2", {}, tx("Modèles de séances")), el("p", {class: "small muted"}, tx("Chargement…"))); }
  if (!S.modeles.length) return null;
  const c = S.config, liste = modelesDuPublic(c), effacees = c.supprimees || [];
  // sans choix de l'enseignant : la suite logique de la dernière séance qui existe encore, sinon la même discipline
  let der = c.seance || 0; while (der > 0 && effacees.includes(der)) der--;
  const derModele = der ? modeleDeSeance(liste, c, der) : null;
  const parDefaut = (derModele && (liste.find(x => x.id === derModele.suites?.prolonger) || liste.find(x => x.discipline === derModele.discipline && x.id !== derModele.id))) || liste[0];
  const vide = S.modeleChoisi === MODELE_VIDE;           // modèle vide : l'enseignant écrit toute la séance
  const m = vide ? {id: MODELE_VIDE, titre: tx("Séance vide"), discipline: tx("Modèle vide")} : (liste.find(x => x.id === S.modeleChoisi) || parDefaut);
  const disciplines = [...new Set(liste.map(x => x.discipline))];
  const sel = el("select", {id: "modele"}, el("optgroup", {label: tx("Modèle vide")}, el("option", {value: MODELE_VIDE, selected: vide}, tx("Séance vide : vous écrivez tout vous-même"))),
    disciplines.map(d => el("optgroup", {label: d},
      liste.filter(x => x.discipline === d).map(x => el("option", {value: x.id, selected: x.id === m.id}, x.titre)))));
  sel.addEventListener("change", () => { S.modeleChoisi = sel.value; rendre(); });
  const ver = m.verification || {};
  const nomVer = ver.mode === "calcul" ? tx`par calculs : chaque idée doit valoir ${String(ver.cible).replace(".", ",")}` + (ver.nombres ? tx`, avec ${ver.nombres}` : "") + (ver.uneFois ? tx(", chaque nombre une fois") : "") + (ver.attendu ? tx` ; ${ver.attendu} solutions à trouver` : "")
    : ver.mode === "ia" ? tx("par l'IA, selon des critères de réussite") : "aucune";
  const remplir = () => { S.modele = {seance: n, id: m.id, reglages: vide ? seanceVide() : reglagesDuModele(m, c)}; rendre(); window.scrollTo(0, 0); };
  const creer = vide ? () => creerSeanceFermee({}, tx`Séance ${prochainNumero(c)} créée, vide et fermée : écrivez la consigne et les réglages ci-dessous, enregistrez, puis ouvrez-la aux élèves.`) : async () => {
    const k = (c.seance || 0) + 1, ouv = c.ouvertes || [];
    await majConfig({...reglagesDuModele(m, c), seance: k, ouvertes: [...ouv, k], ouverte: true});
    S.modele = null; toast(tx`Séance ${N(k)} créée et ouverte : « ${m.titre} ».`);
  };
  const charge = S.modele && S.modele.seance === n ? (S.modele.id === MODELE_VIDE ? {titre: tx("Séance vide")} : S.modeles.find(x => x.id === S.modele.id)) : null;
  return el("div", {class: "card"}, el("h2", {}, tx("Modèles de séances")),
    charge ? el("div", {class: "notice warn"}, el("p", {}, tx`Modèle « ${charge.titre} » chargé dans les champs ci-dessous. Relisez et adaptez, puis enregistrez : rien n'est envoyé aux élèves avant.`),
      el("button", {class: "ghost", onclick: () => { S.modele = null; rendre(); }}, tx("Annuler le modèle"))) : null,
    el("p", {class: "small muted"}, tx`Des tâches ouvertes prêtes à l'emploi (${minuscule(PUBLICS[c.public || "ecole"])}) : consigne, coups de pouce, variantes et vérification déjà réglés. Le public se règle dans « Règle de la classe ».`),
    el("div", {class: "field"}, el("label", {for: "modele"}, tx("Choisir un modèle")), sel),
    vide ? el("details", {open: true}, el("summary", {}, m.titre),
      el("p", {}, tx("Aucune consigne : vous écrivez vous-même la consigne, les coups de pouce, les variantes et la vérification dans les cartes ci-dessous. La séance est créée fermée : ouvrez-la aux élèves quand elle est prête.")))
    : el("details", {open: true}, el("summary", {}, `${m.discipline} · ${m.titre}`),
      el("p", {class: "small"}, el("b", {}, tx("Objectif : ")), m.objectif),
      el("p", {}, m.tache),
      el("p", {class: "small"}, el("b", {}, tx("Coups de pouce : ")), (m.indices || []).join(" → ")),
      m.variantes ? el("p", {class: "small"}, el("b", {}, tx("Accessible : ")), m.variantes.accessible?.consigne || "") : null,
      m.variantes ? el("p", {class: "small"}, el("b", {}, tx("Exigeante : ")), m.variantes.exigeante?.consigne || "") : null,
      el("p", {class: "small"}, el("b", {}, tx("Vérification : ")), nomVer + "."),
      m.exercices ? el("p", {class: "small"}, el("b", {}, tx("Exercices conseillés : ")), m.exercices.split("/").pop(), tx` — à importer dans l'onglet Exercices (dossier serveur/exemples/${m.exercices.split(" ")[0].split("/").slice(0, -1).join("/")}).`) : null),
    el("div", {class: "row"},
      el("button", {class: courante && c.seance ? "ghost" : "primary", onclick: remplir}, n ? tx`Remplir la séance ${N(n)} avec ce modèle` : tx("Remplir les réglages avec ce modèle")),
      courante ? el("button", {class: "primary", onclick: creer}, tx`Créer la séance ${prochainNumero(c)} avec ce modèle`) : null),
    courante && c.seance ? el("p", {class: "small muted"}, vide ? tx`« Créer la séance ${prochainNumero(c)} » garde la séance ${N(c.seance)} telle quelle ; la nouvelle séance reste fermée jusqu'à ce que vous l'ouvriez.`
      : tx`« Créer la séance ${prochainNumero(c)} » garde la séance ${N(c.seance)} telle quelle et ouvre aussitôt la nouvelle séance aux élèves.`) : null);
}
/* ---------- nouvelle séance : vide (modèle vide), ou à partir d'un document PDF ---------- */
const MODELE_VIDE = "__vide";
const TAILLE_PDF = 10 * 1024 * 1024;
const seanceVide = () => ({tache: "", indices: [], variantes: JSON.parse(JSON.stringify(DEFAUT.variantes)), verification: {...DEFAUT.verification}, modele: "", saisieCode: false, evaluation: false, document: 0, niveauTache: 3});
function lireBase64(f) { return new Promise((ok, ko) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1] || ""); r.onerror = ko; r.readAsDataURL(f); }); }
async function chargerDocuments() { try { S.documents = await appel(`classes/${S.code}/documents`); } catch { S.documents = []; } rendre(); }
async function deposerPdf(f) {
  if (!f) throw new Error(tx("Choisissez d'abord un fichier PDF."));
  if (f.size > TAILLE_PDF) throw new Error(tx("PDF trop volumineux : 10 Mo au plus."));
  const d = await appel(`classes/${S.code}/documents`, {methode: "POST", corps: {nom: f.name, contenu: await lireBase64(f)}});
  S.documents = null;
  return d;
}
/** Crée la séance suivante, fermée, avec ces réglages de tâche : l'enseignant la relit dans Réglages, puis l'ouvre. */
async function creerSeanceFermee(reglages, message) {
  const c = S.config, k = (c.seance || 0) + 1;
  await majConfig({...seanceVide(), ...reglages, verification: {...DEFAUT.verification, ...(reglages.verification || {})}, seance: k, ouvertes: c.ouvertes || [], ouverte: false});
  S.modele = null; S.seanceEditee = null; S.suite = false; S.onglet = "reglages";
  document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-selected", String(x.dataset.tab === "reglages")));
  rendre(); window.scrollTo(0, 0); toast(message);
}
function carteNouvelle(c) {
  const k = prochainNumero(c);
  const depuisPdf = async () => {
    const f = $("#pdf-fichier").files[0], montrer = $("#pdf-eleves").checked, avecIA = $("#pdf-ia").checked, souhait = $("#pdf-souhait").value.trim();
    if (!montrer && !avecIA) return toast(tx("Cochez au moins une des deux cases : faire préparer la séance par l'IA, ou montrer le PDF aux élèves."));
    try {
      S.pdfEtat = tx("Envoi et lecture du PDF…"); rendre();
      const doc = await deposerPdf(f);
      let reglages = {}, note = "";
      if (avecIA) {
        S.pdfEtat = tx("L'IA prépare la séance à partir du PDF : cela peut prendre une minute…"); rendre();
        try { const {titre, ...b} = await appel(`classes/${S.code}/documents/${doc.id}/brouillon`, {methode: "POST", corps: {souhait}}); reglages = b; }
        catch (e) { note = " " + e.message; }
      }
      if (!montrer) await appel(`classes/${S.code}/documents/${doc.id}`, {methode: "DELETE"}).catch(() => {});
      S.pdfEtat = null;
      await creerSeanceFermee({...reglages, document: montrer ? doc.id : 0}, (avecIA && !note
        ? tx`Séance ${k} préparée à partir de « ${doc.nom} » et fermée : relisez et corrigez la consigne, les coups de pouce, les variantes et les critères ci-dessous, enregistrez, puis ouvrez-la aux élèves.`
        : tx`Séance ${k} créée avec « ${doc.nom} » et fermée : écrivez la consigne ci-dessous, enregistrez, puis ouvrez-la aux élèves.`) + note);
    } catch (e) { S.pdfEtat = null; rendre(); toast(e.message); }
  };
  return el("div", {class: "card"}, el("h2", {}, tx`Créer la séance ${k} à partir d'un PDF`),
    el("p", {class: "small muted"}, tx("La nouvelle séance est créée fermée : les élèves ne la voient qu'une fois ouverte, et les séances précédentes gardent leur consigne. Pour une séance vide ou un modèle, voyez la carte « Modèles de séances » ci-dessus.")),
    el("div", {class: "field"}, el("label", {for: "pdf-fichier"}, tx("Document PDF (10 Mo au plus)")), el("input", {type: "file", id: "pdf-fichier", accept: "application/pdf,.pdf"})),
    el("label", {for: "pdf-ia", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "pdf-ia", checked: true}),
      tx("L'IA prépare la consigne, les coups de pouce, les variantes et les critères de réussite à partir du PDF")),
    el("div", {class: "field"}, el("label", {for: "pdf-souhait"}, tx("Ce que vous attendez de la séance (facultatif)")),
      el("textarea", {id: "pdf-souhait", rows: "2", placeholder: tx("Par exemple : faire appliquer la notion du chapitre 2 à un cas nouveau, en 1 h 30.")})),
    el("label", {for: "pdf-eleves", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "pdf-eleves", checked: true}), tx("Les élèves peuvent ouvrir le PDF pendant la séance")),
    el("p", {class: "small muted"}, tx("Pour préparer la séance, le texte du PDF est envoyé au fournisseur d'IA de la plateforme. Un PDF scanné (des images, sans texte) ne peut pas être lu par l'IA : il peut seulement être montré aux élèves.")),
    S.pdfEtat ? el("p", {class: "notice", role: "status"}, S.pdfEtat) : null,
    el("button", {class: "primary", onclick: depuisPdf, disabled: !!S.pdfEtat}, tx`Créer la séance ${k} à partir du PDF`));
}
/** Document PDF d'une séance (src.document) : l'ouvrir, le retirer, ou en joindre un. ecrire(id) enregistre la séance avec ce document. */
function ligneDocument(src, ecrire) {
  if (S.documents == null) { chargerDocuments(); return null; }
  const id = src.document || 0, doc = S.documents.find(d => d.id === id);
  const retirer = async () => {
    await ecrire(0);
    const c = S.config, encore = c.document === id || Object.values(c.archives || {}).some(a => a.document === id);
    if (!encore) { await appel(`classes/${S.code}/documents/${id}`, {methode: "DELETE"}).catch(() => {}); S.documents = null; rendre(); }
  };
  const joindre = async () => {
    try { const d = await deposerPdf($("#doc-fichier").files[0]); await ecrire(d.id); toast(tx`« ${d.nom} » joint à la séance (réglages enregistrés).`); }
    catch (e) { toast(e.message); }
  };
  return el("div", {class: "field"}, el("label", {for: "doc-fichier"}, tx("Document PDF pour les élèves")),
    id && doc
      ? el("div", {class: "row"}, el("span", {}, "📄 " + doc.nom),
          el("button", {class: "ghost", onclick: () => ouvrirPdf(`classes/${S.code}/documents/${id}`, S.jeton, doc.nom).catch(e => toast(e.message))}, tx("Ouvrir")),
          el("button", {class: "ghost", onclick: retirer}, tx("Retirer")))
      : el("div", {class: "row"}, el("input", {type: "file", id: "doc-fichier", accept: "application/pdf,.pdf"}), el("button", {class: "ghost", onclick: joindre}, tx("Joindre"))),
    el("p", {class: "small muted"}, tx("Les élèves l'ouvrent depuis la carte « La tâche ». Joindre ou retirer un document enregistre aussi les réglages de la séance. Le document n'est pas copié dans le kit hors ligne.")));
}
/* ---------- séance à partir d'une banque d'exercices (.gift), modifiable et enregistrable sous un nouveau nom ---------- */
async function chargerBanques() { try { S.banques = await appel("banques"); } catch { S.banques = {mes: [], fournies: []}; } rendre(); }
function carteGift(c) {
  if (S.banques == null) { chargerBanques(); return null; }
  const G = S.gift || (S.gift = {contenu: "", nom: "", id: null, origine: "", verif: null});
  const k = prochainNumero(c);
  const vider = () => Object.assign(G, {contenu: "", nom: "", id: null, origine: "", verif: null});
  const charger = async v => {
    try {
      if (v.startsWith("m:")) { const b = await appel(`banques/${v.slice(2)}`); Object.assign(G, {contenu: b.contenu, nom: b.nom, id: b.id, origine: v, verif: null}); }
      else if (v.startsWith("f:")) { const b = await appel(`banques/fournie?chemin=${encodeURIComponent(v.slice(2))}`); Object.assign(G, {contenu: b.contenu, nom: b.nom + tx(" (copie)"), id: null, origine: v, verif: null}); }
      else vider();
    } catch (e) { toast(e.message); }
    rendre();
  };
  const ouvrirFichier = async f => { if (!f) return; Object.assign(G, {contenu: await lireFichier(f), nom: f.name.replace(/\.(gift|txt)$/i, ""), id: null, origine: "fichier", verif: null}); rendre(); };
  const verifier = async () => { try { G.verif = await appel("banques/verifier", {methode: "POST", corps: {contenu: G.contenu}}); } catch (e) { toast(e.message); } rendre(); };
  const enregistrer = async () => {
    // même nom que la banque ouverte : on la remplace ; nouveau nom : nouvelle banque, l'ancienne est gardée
    const meme = G.id && S.banques.mes.find(b => b.id === G.id)?.nom === G.nom.trim();
    try {
      const r = meme ? await appel(`banques/${G.id}`, {methode: "PUT", corps: {nom: G.nom, contenu: G.contenu}})
                     : await appel("banques", {methode: "POST", corps: {nom: G.nom, contenu: G.contenu}});
      Object.assign(G, {id: r.id, nom: r.nom, origine: "m:" + r.id, verif: r}); S.banques = null;
      toast(tx`Banque « ${r.nom} » enregistrée dans Viabilis (${r.questions} questions).`);
    } catch (e) { toast(e.message); }
    rendre();
  };
  const telechargerGift = () => G.contenu.trim() ? telecharger((G.nom.trim() || "banque") + ".gift", G.contenu, "text/plain;charset=utf-8") : toast(tx("Le fichier est vide."));
  const supprimer = async () => {
    try { await appel(`banques/${G.id}`, {methode: "DELETE"}); toast(tx`Banque « ${G.nom} » supprimée de Viabilis.`); vider(); S.banques = null; } catch (e) { toast(e.message); }
    rendre();
  };
  const creer = async () => {
    const niveau = +$("#gift-niveau").value, nom = G.nom.trim() || tx("banque");
    const source = `${nom} · ${new Date().toLocaleString(LOCALE, {dateStyle: "short", timeStyle: "short"})}`.slice(0, 120);
    try {
      const r = await appel(`classes/${S.code}/exercices/import`, {methode: "POST", corps: {contenu: G.contenu, format: "gift", niveau, source}});
      if (!r.importes) return toast(tx("Aucune question reconnue : vérifiez le format GIFT."));
      S.exos = null;
      await creerSeanceFermee({tache: tx("Après les exercices, écris tes idées : ce que tu as compris, une erreur que tu as faite ou évitée et pourquoi, et une question que tu te poses encore."),
        exercices: {...(c.exercices || DEFAUT.exercices), actifs: true, nombre: Math.min(20, r.importes), placement: "avant", niveau, choix: "niveau", source}},
        tx`Séance ${k} créée avec ${r.importes} exercices de « ${nom} », fermée : relisez la tâche ouverte ci-dessous (une consigne de départ est proposée), enregistrez, puis ouvrez-la aux élèves.`);
    } catch (e) { toast(e.message); }
  };
  const parDossier = {};
  for (const b of S.banques.fournies) (parDossier[b.dossier] ||= []).push(b);
  const sel = el("select", {id: "gift-source"},
    el("option", {value: "", selected: !G.origine || G.origine === "fichier"}, G.origine === "fichier" ? tx("— Fichier ouvert depuis l'ordinateur —") : tx("— Nouveau fichier vide —")),
    S.banques.mes.length ? el("optgroup", {label: tx("Mes banques")}, S.banques.mes.map(b => el("option", {value: "m:" + b.id, selected: G.origine === "m:" + b.id}, tx`${b.nom} (${b.questions} questions)`))) : null,
    Object.entries(parDossier).map(([d, l]) => el("optgroup", {label: tx`Fournies avec Viabilis : ${d}`}, l.map(b => el("option", {value: "f:" + b.chemin, selected: G.origine === "f:" + b.chemin}, b.nom)))));
  sel.addEventListener("change", () => charger(sel.value));
  const fichier = el("input", {type: "file", id: "gift-fichier", accept: ".gift,.txt,text/plain"});
  fichier.addEventListener("change", () => ouvrirFichier(fichier.files[0]));
  const zone = el("textarea", {id: "gift-contenu", rows: "14", spellcheck: "false", style: "font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px",
    placeholder: "::Titre::Énoncé de la question ?{=bonne réponse ~mauvaise réponse ~autre mauvaise réponse}"});
  zone.value = G.contenu;
  zone.addEventListener("input", () => { G.contenu = zone.value; });
  const nom = el("input", {id: "gift-nom", placeholder: tx("Par exemple : linux_revision_v2")});
  nom.value = G.nom;
  nom.addEventListener("input", () => { G.nom = nom.value; });
  const v = G.verif;
  return el("div", {class: "card"}, el("h2", {}, tx`Créer la séance ${k} à partir d'un fichier .gift`),
    el("p", {class: "small muted"}, tx("Choisissez une banque d'exercices au format GIFT (Moodle) : une des vôtres, une banque fournie avec Viabilis ou un fichier de votre ordinateur. Modifiez-la ici, enregistrez-la sous un nouveau nom si vous le souhaitez, puis créez la séance : ses questions deviennent les exercices de la séance, suivis d'une tâche ouverte.")),
    el("div", {class: "field"}, el("label", {for: "gift-source"}, tx("Banque d'exercices")), sel),
    el("div", {class: "field"}, el("label", {for: "gift-fichier"}, tx("Ou ouvrir un fichier .gift de l'ordinateur")), fichier),
    el("div", {class: "field"}, el("label", {for: "gift-contenu"}, tx("Contenu (format GIFT)")), zone),
    el("div", {class: "row"}, el("button", {class: "ghost", onclick: verifier}, tx("Vérifier le fichier"))),
    v ? el("div", {class: "notice" + (v.questions ? "" : " ko"), role: "status"}, el("p", {}, tx`${v.questions} question${v.questions > 1 ? "s" : ""} reconnue${v.questions > 1 ? "s" : ""}.`),
      v.avertissements?.length ? el("ul", {class: "small"}, v.avertissements.map(a => el("li", {}, a))) : null,
      v.titres?.length ? el("details", {}, el("summary", {}, tx("Questions reconnues")), el("ul", {class: "small"}, v.titres.map(t => el("li", {}, t)))) : null) : null,
    el("div", {class: "field"}, el("label", {for: "gift-nom"}, tx("Nom de la banque")), nom),
    el("p", {class: "small muted"}, tx("« Enregistrer dans Viabilis » : avec un nouveau nom, une nouvelle banque est créée et l'ancienne est gardée ; avec le même nom, votre banque est remplacée. Vos banques servent dans toutes vos classes. Les banques fournies avec Viabilis ne sont jamais modifiées.")),
    el("div", {class: "row"}, el("button", {class: "ghost", onclick: enregistrer}, tx("Enregistrer dans Viabilis")),
      el("button", {class: "ghost", onclick: telechargerGift}, tx("Télécharger le fichier .gift")),
      G.id ? el("button", {class: "danger", onclick: supprimer}, tx("Supprimer cette banque")) : null),
    el("div", {class: "field"}, el("label", {for: "gift-niveau"}, tx("Niveau donné à ces exercices")),
      el("select", {id: "gift-niveau"}, [1, 2, 3, 4, 5].map(n => el("option", {value: n, selected: n === ((c.exercices || DEFAUT.exercices).niveau ?? 2)}, tx("Niveau ") + n)))),
    el("p", {class: "small muted"}, tx("Les questions sont ajoutées à la banque de la classe (onglet Exercices). La séance ne tire que celles-ci, avant la tâche ouverte ; vous pouvez le changer dans l'onglet Exercices.")),
    el("button", {class: "primary", onclick: creer}, tx`Créer la séance ${k} avec ces exercices`));
}
function carteLecture(c) {
  return el("div", {class: "card"}, el("h2", {}, tx("Lecture à voix haute")),
      el("label", {for: "lecture-active", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "lecture-active", checked: (c.lecture || DEFAUT.lecture).active}), tx("Proposer le bouton « Écouter » aux élèves")),
      el("div", {class: "field"}, el("label", {for: "lecture-langue"}, tx("Langue de lecture")),
        el("select", {id: "lecture-langue"}, [["fr-FR", tx("français")], ["en-GB", tx("anglais (britannique)")], ["en-US", tx("anglais (américain)")], ["es-ES", tx("espagnol")], ["de-DE", tx("allemand")], ["it-IT", tx("italien")], ["ca-ES", tx("catalan")]]
          .map(([k, t]) => el("option", {value: k, selected: (c.lecture || DEFAUT.lecture).langue === k}, t)))),
      el("p", {class: "small muted"}, tx("Consigne, exercices, coups de pouce, réponses de l'IA et retours peuvent être écoutés. Seules les voix installées sur la tablette sont utilisées : aucun texte n'est envoyé à un service extérieur. Si aucune voix de cette langue n'est installée, le bouton n'apparaît pas.")),
      el("label", {for: "lecture-dictee", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "lecture-dictee", checked: !!(c.lecture || DEFAUT.lecture).dictee}), tx("Proposer la dictée vocale pour écrire les idées")),
      el("p", {class: "small muted"}, tx("Le bouton « Dicter » n'apparaît que si la tablette reconnaît la parole sur l'appareil, sans envoyer la voix à un service extérieur. Sur beaucoup d'appareils, ce n'est pas encore le cas : le bouton reste alors caché.")));
}
/** Créer la séance suivante : propositions d'après la séance précédente, avec une variante et un réglage d'IA par élève. */
function carteSuites(c) {
  if (!S.suite) return null;
  if (S.modeles == null) { chargerModeles(); return el("div", {class: "card"}, el("h2", {}, tx("Propositions pour la suite")), el("p", {class: "small muted"}, tx("Chargement…"))); }
  const P = proposerSuites(modelesDuPublic(c), {...c, disciplineClasse: disciplineDe(c)}, S.traces, S.notes, S.viab), k = (c.seance || 0) + 1, n = P.n;
  const fermer = () => { S.suite = false; S.suiteChoisie = null; rendre(); };
  const allerReglages = () => { S.suite = false; S.onglet = "reglages"; document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-selected", String(x.dataset.tab === "reglages"))); rendre(); window.scrollTo(0, 0); };
  if (!P.propositions.length) return el("div", {class: "card"}, el("h2", {}, tx`Créer la séance ${prochainNumero(c)}`), el("p", {}, tx("Aucun modèle à proposer.")),
    el("div", {class: "row"}, el("button", {class: "primary", onclick: allerReglages}, tx("Séance vide ou à partir d'un PDF (Réglages)")), el("button", {class: "ghost", onclick: fermer}, tx("Annuler"))));
  const p = P.propositions.find(x => x.modele.id === S.suiteChoisie) || P.propositions.find(x => x.conseille);
  const r = P.resume, actifs = r.difficulte + r.attendu + r.aise;
  const bilan = actifs
    ? tx`Séance ${N(n)}${P.prec ? ` (« ${P.prec.titre} »)` : ""} : ${actifs} élève${actifs > 1 ? "s" : ""} — ${r.difficulte} en difficulté, ${r.attendu} au niveau attendu, ${r.aise} à l'aise` + (r.absent ? tx` ; ${r.absent} sans trace.` : ".")
    : tx`Pas encore de trace d'élève à la séance ${N(n)} : les propositions suivent seulement la progression${P.prec ? tx` après « ${P.prec.titre} »` : ""}.`;
  const choix = P.propositions.map(x => el("button", {class: "suite" + (x === p ? " choisie" : ""), "aria-pressed": String(x === p), onclick: () => { S.suiteChoisie = x.modele.id; rendre(); }},
    el("span", {class: "row", style: "gap:6px"}, el("span", {class: "pill" + (x.conseille ? " ok" : "")}, GENRES[x.genre].nom + (x.conseille ? tx(" · conseillé") : "")),
      x.dejaFaite ? el("span", {class: "pill warn"}, tx`déjà faite en séance ${N(x.dejaFaite)}`) : null),
    el("b", {}, x.modele.titre), el("span", {class: "small muted"}, tx`${x.modele.discipline} · niveau ${x.modele.niveauTache} · ${GENRES[x.genre].aide}`),
    el("span", {class: "small"}, x.raison)));
  const NOMS = {accessible: tx("Variante accessible"), standard: tx("Tâche standard"), exigeante: tx("Variante exigeante")};
  const parVariante = ["accessible", "standard", "exigeante"].map(v => {
    const l = P.eleves.filter(x => x.variante === v);
    return l.length ? el("div", {}, el("p", {style: "font-weight:700;margin-bottom:4px"}, `${NOMS[v]} (${l.length})`),
      el("ul", {class: "small", style: "margin:0 0 8px;padding-left:18px"}, l.map(x => el("li", {}, el("b", {}, x.pseudo), ` — ${PROFILS[x.profil]} : ${x.raison} → ${minuscule(GROUPES[x.groupe].nom)}`)))) : null;
  });
  const repr = P.aReprendre.map(x => x.pseudo);
  const creer = async () => {
    const appliquer = $("#suite-appliquer").checked, garder = $("#suite-garder").checked;
    const eleves = {...(c.eleves || {})}, groupes = {...(c.groupes || {})};
    if (appliquer) for (const x of P.eleves) if (x.profil !== "absent") { eleves[x.uid] = {...(eleves[x.uid] || {}), ...GROUPES[x.groupe].reglage, variante: x.variante, palier: x.palier}; groupes[x.uid] = x.groupe; }
    const ouv = [...(c.ouvertes || []).filter(x => garder || x !== n), k];
    S.suite = false; S.suiteChoisie = null;
    await majConfig({...reglagesDuModele(p.modele, c), seance: k, ouvertes: ouv, ouverte: true, eleves, groupes, origine: "suite"});
    toast(tx`Séance ${N(k)} créée et ouverte : « ${p.modele.titre} »` + (garder ? tx`. La séance ${N(n)} reste ouverte.` : tx`. La séance ${N(n)} est fermée.`));
  };
  return el("div", {class: "card"}, el("h2", {}, tx`Créer la séance ${prochainNumero(c)} : propositions pour la suite`),
    el("p", {}, bilan),
    el("div", {class: "suites"}, choix),
    el("details", {open: true}, el("summary", {}, tx`« ${p.modele.titre} » : la consigne`), el("p", {}, p.modele.tache),
      el("p", {class: "small muted"}, p.modele.objectif + (p.modele.exercices ? tx` Exercices conseillés : ${p.modele.exercices}.` : ""))),
    P.eleves.length ? el("details", {open: true}, el("summary", {}, tx("Pour chaque élève")), parVariante,
      el("p", {class: "small muted"}, tx("Selon les traces de la séance précédente (état estimé, idées justes, exercices). La variante reste invisible pour l'élève. Vous pourrez tout changer ensuite, élève par élève, dans l'onglet Classe."))) : null,
    P.eleves.length ? el("label", {for: "suite-appliquer", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "suite-appliquer", checked: true}), tx("Appliquer à chaque élève la variante et le réglage d'IA proposés"))
      : el("input", {type: "checkbox", id: "suite-appliquer", hidden: true}),
    el("label", {for: "suite-garder", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "suite-garder", checked: repr.length > 0 || !actifs}),
      tx`Garder la séance ${N(n)} ouverte` + (repr.length ? tx` pour qu'ils la terminent ou la reprennent : ${repr.join(", ")}` : "")),
    el("div", {class: "row"}, el("button", {class: "primary", onclick: creer}, tx`Créer la séance ${prochainNumero(c)} : « ${p.modele.titre} »`),
      el("button", {class: "ghost", onclick: allerReglages}, tx("Séance vide, PDF ou autre modèle")),
      el("button", {class: "ghost", onclick: fermer}, tx("Annuler"))));
}
function caseCode(c) {
  return el("div", {class: "field"}, el("label", {for: "saisie-code", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "saisie-code", checked: !!c.saisieCode}), tx("Les idées sont des programmes (saisie de code)")),
    el("p", {class: "small muted"}, tx("Police à chasse fixe, indentation conservée, Entrée pour aller à la ligne et Ctrl+Entrée pour ajouter. Le tuteur IA ne donne jamais de programme complet ; la vérification déroule le code à la main, sans l'exécuter.")),
    el("label", {for: "seance-evaluation", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "seance-evaluation", checked: !!c.evaluation}), tx("Séance d'évaluation")),
    el("p", {class: "small muted"}, tx("Sans IA, sans coup de pouce ni vérification ; une seule réponse par exercice, sans correction affichée. Les scores apparaissent dans la fiche de chaque élève et dans l'export.")));
}
function champsIndices(cle, indices = []) {
  return el("div", {class: "field"}, el("p", {style: "font-weight:700"}, tx("Coups de pouce (facultatif, du plus léger au plus précis)")),
    [0, 1, 2].map(i => { const t = el("input", {type: "text", id: `ind-${cle}-${i}`, placeholder: [tx("1. Une piste générale"), tx("2. Une piste plus précise"), tx("3. Presque la méthode, sans la réponse")][i]}); t.value = indices[i] || ""; return t; }),
    el("p", {class: "small muted"}, tx("L'élève les ouvre un par un s'il bloque. Ne donnez jamais la réponse : ce sont des étapes pour chercher.")));
}
const lireIndices = cle => [0, 1, 2].map(i => $(`#ind-${cle}-${i}`)?.value.trim() || "").filter(Boolean);
function carteVariantes(c) {
  const va = c.variantes || DEFAUT.variantes;
  const actives = el("input", {type: "checkbox", id: "var-actives", checked: !!va.actives});
  const bloc = (nom, titre, aide) => {
    const x = va[nom] || {};
    const cons = el("textarea", {id: `var-${nom}-consigne`, rows: "2", placeholder: aide}); cons.value = x.consigne || "";
    const cible = el("input", {type: "text", id: `var-${nom}-cible`, inputmode: "decimal", placeholder: tx("comme la tâche standard")}); cible.value = x.cible == null ? "" : String(x.cible).replace(".", ",");
    const att = el("input", {type: "text", id: `var-${nom}-attendu`, inputmode: "numeric", placeholder: tx("comme la tâche standard")}); att.value = x.attendu ?? "";
    return el("details", {open: true}, el("summary", {}, titre),
      el("div", {class: "field", style: "margin-top:8px"}, el("label", {for: `var-${nom}-consigne`}, tx("Consigne")), cons),
      el("div", {class: "row"}, el("div", {class: "field", style: "flex:1;min-width:160px"}, el("label", {for: `var-${nom}-cible`}, tx("Résultat attendu (vérification par calculs)")), cible),
        el("div", {class: "field", style: "flex:1;min-width:160px"}, el("label", {for: `var-${nom}-attendu`}, tx("Nombre de solutions")), att)),
      champsIndices(nom, x.indices));
  };
  const corps = el("div", {class: "field"},
    bloc("accessible", tx("Variante accessible"), tx("Par exemple : avec 2, 3, 5 et 7, trouve des calculs qui donnent 12.")),
    bloc("exigeante", tx("Variante exigeante"), tx("Par exemple : avec 2, 3, 5 et 7, trouve des calculs qui donnent 100.")));
  const maj = () => { corps.hidden = !actives.checked; }; actives.addEventListener("change", maj); maj();
  return el("div", {class: "card"}, el("h2", {}, tx("Variantes de la tâche")),
    el("label", {for: "var-actives", class: "row", style: "gap:8px"}, actives, tx("Proposer une variante accessible et une variante exigeante")),
    el("p", {class: "small muted"}, tx("Même objectif pour toute la classe, difficulté adaptée. Chaque élève travaille la tâche standard, sauf si une variante lui est appliquée depuis l'onglet Classe (les recommandations la proposent). Les élèves ne voient pas le nom de leur variante. Les champs vides reprennent ceux de la tâche standard.")),
    corps);
}
function lireVariantes() {
  const lire = nom => ({consigne: $(`#var-${nom}-consigne`)?.value.trim() || "", indices: lireIndices(nom),
    cible: ($(`#var-${nom}-cible`)?.value || "").trim() || null, attendu: ($(`#var-${nom}-attendu`)?.value || "").trim() || null});
  return {actives: !!$("#var-actives")?.checked, accessible: lire("accessible"), exigeante: lire("exigeante")};
}
function carteVerification(c) {
  const v = c.verification || DEFAUT.verification;
  const mode = el("select", {id: "v-mode"}, [["aucune", tx("Pas de vérification")], ["calcul", tx("Calculs : chaque idée doit valoir un nombre")], ["ia", tx("IA : selon vos critères de réussite")]]
    .map(([k, t]) => el("option", {value: k, selected: v.mode === k}, t)));
  const champ = (id, lbl, val, aide, attrs = {}) => { const i = el("input", {type: "text", id, ...attrs}); i.value = val ?? "";
    return el("div", {class: "field", "data-mode": attrs["data-mode"] || ""}, el("label", {for: id}, lbl), i, aide ? el("p", {class: "small muted"}, aide) : null); };
  const crit = el("textarea", {id: "v-criteres", rows: "3", placeholder: tx("Par exemple : le problème contient une fraction, une question, et on peut le résoudre.")}); crit.value = v.criteres || "";
  const maxi = el("input", {type: "range", id: "v-maximum", min: 1, max: 10, step: 1, value: v.maximum}), maxo = el("output", {}, v.maximum);
  maxi.addEventListener("input", () => maxo.textContent = maxi.value);
  const blocCalcul = el("div", {class: "field"}, champ("v-cible", tx("Résultat attendu de chaque calcul"), String(v.cible).replace(".", ","), tx("Par exemple 10 pour « payer 10 € »."), {inputmode: "decimal"}),
    champ("v-nombres", tx("Nombres autorisés (facultatif)"), (v.nombres || "").replace(/ ; /g, " ; "), tx("Séparés par des points-virgules, par exemple 1 ; 2 ; 5 pour les pièces. Vide : tous les nombres.")),
    el("label", {for: "v-unefois", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "v-unefois", checked: !!v.uneFois}), tx("Chaque nombre ne peut servir qu'une fois dans un calcul")),
    champ("v-attendu", tx("Nombre de solutions différentes à trouver (facultatif)"), v.attendu || "", tx("Par exemple 10. L'élève saura s'il en manque, sans savoir lesquelles. Deux calculs qui ne diffèrent que par l'ordre des termes comptent pour une seule solution."), {inputmode: "numeric"}));
  const blocIA = el("div", {class: "field"}, el("label", {for: "v-criteres"}, tx("Critères de réussite")), crit,
    el("p", {class: "small muted"}, tx("L'IA juge chaque idée d'après ces critères, explique ce qui ne va pas et pose une question, sans jamais donner la réponse.")));
  const maj = () => { blocCalcul.hidden = mode.value !== "calcul"; blocIA.hidden = mode.value !== "ia"; };
  mode.addEventListener("change", maj); maj();
  return el("div", {class: "card"}, el("h2", {}, tx("Vérification des idées")),
    el("p", {class: "small muted"}, tx("L'élève peut faire vérifier les idées de la tâche ouverte et reçoit un retour pour chacune.")),
    el("div", {class: "field"}, el("label", {for: "v-mode"}, tx("Type de vérification")), mode), blocCalcul, blocIA,
    el("div", {class: "field"}, el("label", {for: "v-maximum", class: "row", style: "justify-content:space-between"}, tx("Vérifications par élève et par séance"), maxo), maxi,
      el("p", {class: "small muted"}, tx("Un petit nombre évite de corriger au hasard jusqu'à ce que tout soit juste."))));
}
function csvIndicateurs() {
  const tete = ["pseudo", "seance", "ordre", "mode", "charge_debut", "charge_fin", "compris", "note_enseignant", "bloque", "premiere_demande_s", "idees_avant", "idees_apres", "idees_distinctes", "reprise_ia", "originalite", "exercices", "score_exercices", "niveau_exercices", "verifications", "idees_justes", "variante", "coups_de_pouce", "C_estime", "A_estime", "D_estime", "M_estime"];
  const lignes = [tete.join(";")];
  for (const [u, doc] of Object.entries(S.traces)) for (const n of Object.keys(doc.seances || {}).map(Number).sort((a, b) => a - b)) {
    const s = doc.seances[n], b = brut(s, ideesDesAutres(S.traces, u, n), S.notes[u]?.[n]);
    lignes.push([doc.pseudo, n, s.ordre || "", s.mode || "", s.chargeDebut ?? "", s.chargeFin ?? "", s.compris ?? "", S.notes[u]?.[n] ?? "", s.bloque ? 1 : 0, s.premiereDemande ?? "",
      b.nAvant, b.nApres, b.nDist, fr(b.reprise, 3), fr(b.originalite, 3), b.nExos, fr(b.scoreExos, 3), fr(b.niveauExos, 1), b.nVerifs, fr(b.tauxJuste, 3), b.variante || "", b.indicesVus, fr(b.C, 3), fr(b.A, 3), fr(b.D, 3), fr(b.M, 3)].map(x => String(x).replace(/[;\n]/g, " ")).join(";"));
  }
  return "﻿" + lignes.join("\n");
}
/** Données pour calibrer le modèle (developpement/outils/calibrer.py) : par élève et par séance, l'état estimé de la séance (C, A, M, D, sans lissage),
    l'aide reçue traduite en commandes du modèle (s, φ, r) et le niveau de la tâche. Identifiants d'élèves seulement, pas de pseudonymes. */
function csvCalibration() {
  const c = S.config, tete = ["classe", "eleve", "seance", "rang", "niveau", "s", "phi", "r", "C", "A", "M", "D"];
  const lignes = [tete.join(";")];
  for (const u of Object.keys(S.traces)) {
    const est = etatEleve(S.traces, S.notes, u); if (!est) continue;
    est.serie.forEach((b, k) => { const u3 = est.trajet[k].u;
      lignes.push([S.code, u, b.n, k + 1, Math.min(5, Math.max(1, niveauEffectif(c, b.n, b.variante))), ...u3.map(x => fr(x, 2)), fr(b.C, 3), fr(b.A, 3), fr(b.M, 3), fr(b.D, 3)].join(";")); });
  }
  return lignes.join("\n") + "\n";
}
function telecharger(nom, texte, type = "text/csv") { const a = el("a", {href: URL.createObjectURL(new Blob([texte], {type})), download: nom}); document.body.append(a); a.click(); a.remove(); }
/** Mode hors ligne : kit de la classe pour la clé USB, puis import du travail rapporté par les étudiants. */
function carteHorsLigne() {
  const toutes = el("input", {type: "checkbox", id: "kit-toutes", checked: true});
  const kit = async () => {
    try { const k = await appel(`classes/${S.code}/kit?toutes=${toutes.checked ? 1 : 0}`); telecharger(`viabilis_kit_${S.code}.json`, JSON.stringify(k), "application/json"); }
    catch (e) { toast(e.message); }
  };
  const fichiers = el("input", {type: "file", id: "travaux-hl", accept: ".json,application/json", multiple: true});
  const fusion = el("input", {type: "checkbox", id: "hl-fusion"});
  const importer = async () => {
    const res = [];
    for (const f of fichiers.files) {
      try {
        const r = await appel(`classes/${S.code}/import-eleve`, {methode: "POST", corps: {travail: JSON.parse(await f.text()), fusionner: fusion.checked}});
        const n = r.importees.length;
        res.push({ok: true, texte: `${f.name} : ${r.eleve}` + (r.renomme ? tx(" (pseudonyme déjà pris : renommé)") : r.fusionne ? tx(" (rattaché à l'élève du même pseudonyme)") : "")
          + tx` · ${n} séance${n > 1 ? "s" : ""} importée${n > 1 ? "s" : ""}` + (r.gardees.length ? tx` · séance${r.gardees.length > 1 ? "s" : ""} ${r.gardees.map(N).join(", ")} gardée${r.gardees.length > 1 ? "s" : ""} : plus récente${r.gardees.length > 1 ? "s" : ""} dans la classe` : "")
          + (r.ignorees.length ? tx` · ${r.ignorees.length} séance${r.ignorees.length > 1 ? "s" : ""} effacée${r.ignorees.length > 1 ? "s" : ""} depuis, ignorée${r.ignorees.length > 1 ? "s" : ""}` : "")});
      } catch (e) { res.push({ok: false, texte: `${f.name} : ${e.message}`}); }
    }
    S.importHL = res; await chargerClasse();
  };
  return el("div", {class: "card"}, el("h2", {}, tx("Travail hors ligne (clé USB)")),
    el("p", {class: "small"}, tx("Pour un étudiant qui travaille sur son ordinateur sans accès au serveur de la classe. Le kit contient les séances et les exercices, sans les critères de réussite ni les données des autres élèves. Hors ligne, il n'y a pas d'IA : l'étudiant cherche seul, avec les coups de pouce et les exercices corrigés sur place.")),
    el("ol", {class: "small"}, el("li", {}, tx("Téléchargez le kit et copiez-le, nommé kit.json, dans le dossier hors_ligne de l'application, sur la clé USB.")),
      el("li", {}, tx("L'étudiant lance Viabilis depuis la clé (lanceur de son système : voir hors_ligne/LISEZMOI.txt), travaille, puis touche « Exporter mon travail ».")),
      el("li", {}, tx("Il vous remet le fichier exporté ; importez-le ici. Son travail rejoint le suivi de la classe."))),
    el("label", {for: "kit-toutes", class: "row", style: "gap:8px"}, toutes, tx("Ouvrir toutes les séances dans le kit (l'étudiant avance à son rythme)")),
    el("button", {class: "primary", onclick: kit}, tx("Télécharger le kit de la classe")),
    el("div", {class: "field"}, el("label", {for: "travaux-hl"}, tx("Importer le travail d'étudiants (un fichier par étudiant)")), fichiers),
    el("label", {for: "hl-fusion", class: "row", style: "gap:8px"}, fusion, tx("Si le pseudonyme existe déjà dans la classe, rattacher le travail à cet élève (sinon, un pseudonyme numéroté est créé)")),
    el("button", {onclick: importer}, tx("Importer")),
    (S.importHL || []).length ? el("ul", {class: "ideas"}, S.importHL.map(x => el("li", {class: "small" + (x.ok ? "" : " ko")}, x.texte))) : null);
}
function ongletDonnees() {
  const nb = Object.values(S.traces).reduce((a, d) => a + Object.keys(d.seances || {}).length, 0);
  const effacer = S.confirmer === "classe"
    ? el("div", {class: "notice ko row"}, el("span", {}, tx("Supprimer définitivement la classe, ses élèves et toutes leurs traces ?")),
        el("button", {class: "danger", onclick: async () => { try { await appel(`classes/${S.code}`, {methode: "DELETE"}); S.classes = S.classes.filter(k => k.code !== S.code); S.code = null; S.confirmer = null; rendre(); } catch (e) { toast(e.message); } }}, tx("Supprimer")),
        el("button", {class: "ghost", onclick: () => { S.confirmer = null; rendre(); }}, tx("Annuler")))
    : el("button", {class: "danger", onclick: () => { S.confirmer = "classe"; rendre(); }}, tx("Supprimer la classe et ses données"));
  $("#vue").replaceChildren(el("div", {class: "wrap"},
    el("div", {class: "card"}, el("h2", {}, tx("Export pour l'analyse")),
      el("p", {}, tx`${Object.keys(S.traces).length} élèves, ${nb} séances enregistrées.`),
      el("div", {class: "row"},
        el("button", {class: "primary", disabled: !nb, onclick: () => telecharger(`indicateurs_${S.code}.csv`, csvIndicateurs())}, tx("Indicateurs (CSV)")),
        el("button", {disabled: !nb, onclick: async () => { try { telecharger(`traces_${S.code}.csv`, await appel(`classes/${S.code}/export.csv`)); } catch (e) { toast(e.message); } }}, tx("Traces brutes (CSV)"))),
      el("p", {class: "small muted"}, tx("Une ligne par élève et par séance, pseudonymes seulement.")),
      el("div", {class: "row"},
        el("button", {onclick: async () => { try { telecharger(`echanges_ia_${S.code}.csv`, await appel(`classes/${S.code}/echanges_ia.csv`)); } catch (e) { toast(e.message); } }}, tx("Échanges avec l'IA (CSV)")),
        el("button", {onclick: async () => { try { telecharger(`journal_${S.code}.csv`, await appel(`classes/${S.code}/journal.csv`)); } catch (e) { toast(e.message); } }}, tx("Journal des décisions (CSV)"))),
      el("div", {class: "row"},
        el("button", {disabled: !nb, onclick: () => telecharger(`calibration_${S.code}.csv`, csvCalibration())}, tx("Données pour calibrer le modèle (CSV)"))),
      el("p", {class: "small muted"}, tx("Pour recalculer le noyau de viabilité avec des paramètres estimés sur vos classes : exportez ce fichier dans chaque classe réelle (pas les simulations), puis lancez developpement/outils/calibrer.py (voir developpement/NOTES_DEVELOPPEMENT.md, section 9 bis).")),
      el("p", {class: "small muted"}, tx("Le journal garde chaque changement de réglage d'un élève, avec son origine (recommandation appliquée, groupes, suite proposée ou choix manuel). Croisé avec les indicateurs, il sert à vérifier si les recommandations aident vraiment."))),
    carteHorsLigne(),
    el("div", {class: "card"}, el("h2", {}, tx("Qualité des réponses de l'IA")),
      el("p", {}, (() => { const auto = S.signalements.filter(x => x.auteur === "auto").length, ens = S.signalements.length - auto;
        return tx`${auto} réponse${auto > 1 ? "s" : ""} bloquée${auto > 1 ? "s" : ""} automatiquement (elles contenaient une solution) · ${ens} signalée${ens > 1 ? "s" : ""} par vous.`; })()),
      S.signalements.length ? el("ul", {class: "ideas"}, S.signalements.slice(0, 20).map(x => el("li", {style: "flex-direction:column;align-items:stretch"},
        el("span", {class: "small"}, el("b", {}, tx`${S.traces[x.eleve]?.pseudo || "?"} · séance ${N(x.seance)} · `), x.motif), el("span", {class: "small muted"}, x.texte)))) : null,
      el("p", {class: "small muted"}, tx("Signalez une réponse depuis la fiche d'un élève (« Détail », puis « Échanges avec l'IA »). Le blocage automatique ne fonctionne que pour les tâches vérifiées par calculs ; pour les autres, relisez les échanges."))),
    el("div", {class: "card"}, el("h2", {}, tx("Retour des élèves sur leur travail")),
      el("p", {class: "small"}, tx("Par défaut, un élève revient sur son travail en choisissant son pseudonyme dans la liste de la classe. C'est simple, mais un élève pourrait choisir le pseudonyme d'un camarade : surveillez ce moment en classe. Si besoin, exigez en plus le code personnel.")),
      el("label", {for: "code-perso", class: "row", style: "gap:8px"}, (() => { const i = el("input", {type: "checkbox", id: "code-perso", checked: !!S.config.codePersonnel});
        i.addEventListener("change", () => majConfig({codePersonnel: i.checked})); return i; })(), tx("Exiger le code personnel pour revenir sous un pseudonyme existant")),
      el("p", {class: "small muted"}, tx("Codes personnels (utiles seulement si l'option est cochée) :")),
      el("table", {class: "codes"}, el("tr", {}, el("th", {}, tx("Pseudonyme")), el("th", {}, tx("Code personnel"))),
        Object.values(S.traces).sort((a, b) => a.pseudo.localeCompare(b.pseudo)).map(d => el("tr", {}, el("td", {}, d.pseudo), el("td", {}, d.pin || "–")))),
      el("p", {class: "small muted"}, tx`Code de la classe : ${S.code}. Pour imprimer, utilisez le menu Imprimer du navigateur.`)),
    el("div", {class: "card"}, el("h2", {}, tx("Effacement")), el("p", {class: "small"}, tx("Pour répondre à une demande d'effacement, supprimez un élève depuis sa fiche, ou toute la classe ici. Les traces sont aussi supprimées automatiquement après la durée de conservation réglée sur le serveur.")), effacer),
    el("button", {class: "ghost", onclick: () => { S.code = null; S.config = null; rendre(); }}, tx("Changer de classe"))));
}

/* ---------------------------------------------------------------- groupes de besoin */
function propositions() {
  const c = S.config, out = {};
  for (const u of Object.keys(S.traces)) {
    const e = etatEleve(S.traces, S.notes, u)?.etat || {};
    out[u] = groupeSuggere(e, S.viab?.[u], c);
  }
  return out;
}
function ongletGroupes() {
  const c = S.config, props = propositions(), uids = Object.keys(S.traces);
  if (!S.brouillon) S.brouillon = Object.fromEntries(uids.map(u => [u, props[u].groupe]));
  for (const u of uids) if (!S.brouillon[u]) S.brouillon[u] = props[u].groupe;
  if (!uids.length) { $("#vue").replaceChildren(el("div", {class: "card"}, el("p", {}, tx("Aucun élève pour l'instant.")))); return; }
  const colonne = g => {
    const membres = uids.filter(u => S.brouillon[u] === g).sort((a, b) => S.traces[a].pseudo.localeCompare(S.traces[b].pseudo));
    return el("div", {class: "card"}, el("h2", {}, `${GROUPES[g].nom} (${membres.length})`), el("p", {class: "small muted"}, GROUPES[g].aide),
      membres.length ? el("ol", {class: "ideas"}, membres.map(u => {
        const sel = el("select", {"aria-label": tx("Groupe de ") + S.traces[u].pseudo}, Object.entries(GROUPES).map(([k, x]) => el("option", {value: k, selected: k === g}, x.nom)));
        sel.addEventListener("change", () => { S.brouillon[u] = sel.value; rendre(); });
        const deplace = props[u].groupe !== g;
        return el("li", {style: "flex-direction:column;align-items:stretch;gap:6px"},
          el("div", {class: "row", style: "justify-content:space-between"}, el("b", {}, S.traces[u].pseudo), (c.groupes || {})[u] === g ? el("span", {class: "tag"}, tx("déjà appliqué")) : null),
          el("p", {class: "small muted"}, deplace ? tx`Déplacé par vous (proposé : ${minuscule(GROUPES[props[u].groupe].nom)}, ${props[u].raison})` : props[u].raison),
          el("div", {style: "max-width:240px"}, sel));
      })) : el("p", {class: "small muted"}, tx("Personne dans ce groupe.")));
  };
  const appliquer = async () => {
    const eleves = {...(c.eleves || {})};
    for (const u of uids) {
      const r = GROUPES[S.brouillon[u]].reglage;
      eleves[u] = {...(eleves[u] || {}), ordre: r.ordre, mode: r.mode, retrait: r.retrait, ...(c.variantes?.actives ? {variante: r.variante} : {})};
    }
    await majConfig({eleves, groupes: {...S.brouillon}, origine: "groupes"});
    toast(tx("Groupes appliqués : ils valent pour la prochaine séance de chaque élève."));
  };
  $("#vue").replaceChildren(el("div", {class: "wrap"},
    el("div", {class: "card"}, el("h2", {}, tx("Groupes de besoin pour la prochaine séance")),
      el("p", {class: "small"}, tx("Proposés à partir de l'état estimé et de la viabilité de chaque élève. Déplacez un élève si vous le jugez utile, puis appliquez : chaque groupe reçoit ses réglages (ordre, rôle de l'IA, retrait, et variante si les variantes sont activées). Les groupes sont recalculés à chaque séance : aucun élève n'y est enfermé.")),
      el("div", {class: "row"}, el("button", {class: "primary", onclick: appliquer}, tx("Appliquer ces groupes")),
        el("button", {class: "ghost", onclick: () => { S.brouillon = null; rendre(); }}, tx("Revenir aux propositions")))),
    el("div", {class: "grid2"}, colonne("atelier"), colonne("accompagne"), colonne("defi")),
    el("p", {class: "small muted"}, tx("L'atelier dirigé suppose votre présence : prévoyez-le en début de séance, pendant que les autres groupes cherchent seuls."))));
}

async function chargerExos() { try { S.exos = await appel(`classes/${S.code}/exercices`); } catch (e) { S.exos = []; } rendre(); }
function lireFichier(f) { return new Promise((ok, ko) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = ko; r.readAsText(f, "utf-8"); }); }
function ongletExercices() {
  const c = S.config, ex = c.exercices || DEFAUT.exercices;
  if (!S.exos) { chargerExos(); $("#vue").replaceChildren(el("p", {class: "muted"}, tx("Chargement de la banque…"))); return; }
  const niveaux = [1, 2, 3, 4, 5];
  const selNiv = (id, val) => el("select", {id}, niveaux.map(n => el("option", {value: n, selected: n === val}, tx("Niveau ") + n)));
  // réglages de séance
  const actifs = el("input", {type: "checkbox", id: "ex-actifs", checked: ex.actifs});
  const nombre = el("input", {type: "range", id: "ex-nombre", min: 1, max: 20, step: 1, value: ex.nombre}), nbOut = el("output", {}, ex.nombre);
  nombre.addEventListener("input", () => nbOut.textContent = nombre.value);
  const placement = el("select", {id: "ex-placement"}, el("option", {value: "avant", selected: ex.placement === "avant"}, tx("Avant la tâche ouverte")), el("option", {value: "apres", selected: ex.placement === "apres"}, tx("Après la tâche ouverte")));
  const reglages = el("div", {class: "card"}, el("h2", {}, tx("Dans la séance")),
    el("label", {for: "ex-actifs", class: "row", style: "gap:8px"}, actifs, tx("Proposer des exercices aux élèves")),
    el("div", {class: "field"}, el("label", {for: "ex-nombre", class: "row", style: "justify-content:space-between"}, tx("Exercices par élève et par séance"), nbOut), nombre),
    el("div", {class: "field"}, el("label", {for: "ex-placement"}, tx("Moment")), placement),
    el("div", {class: "field"}, el("label", {for: "ex-choix"}, tx("Choix des exercices")),
      el("select", {id: "ex-choix"}, el("option", {value: "niveau", selected: ex.choix !== "adaptatif"}, tx("Au niveau fixé (classe ou élève)")),
        el("option", {value: "adaptatif", selected: ex.choix === "adaptatif"}, tx("Adaptatif : selon les progrès de chaque élève"))),
      el("p", {class: "small muted"}, tx("Adaptatif : à la manière de l'algorithme ZPDES, chaque élève a une zone de niveaux ouverts. Elle part du niveau ci-dessous, s'ouvre au niveau supérieur quand il réussit, se referme sur les niveaux maîtrisés et rouvre le niveau inférieur en cas d'échec. Les exercices sont tirés de préférence dans les niveaux où il progresse le plus."))),
    el("div", {class: "field"}, el("label", {for: "ex-niveau"}, tx("Niveau de la classe")), selNiv("ex-niveau", ex.niveau),
      el("p", {class: "small muted"}, tx("Chaque élève reçoit des exercices de ce niveau, sauf si un niveau individuel lui est appliqué depuis l'onglet Classe."))),
    ex.source ? el("label", {for: "ex-source", class: "row", style: "gap:8px"}, el("input", {type: "checkbox", id: "ex-source", checked: true}),
      tx`Seulement les questions de « ${ex.source} » (séance créée à partir d'un fichier .gift)`) : null,
    el("button", {class: "primary", onclick: async () => { await majConfig({exercices: {actifs: actifs.checked, nombre: +nombre.value, placement: placement.value, niveau: +$("#ex-niveau").value, choix: $("#ex-choix").value,
      source: ex.source && $("#ex-source")?.checked ? ex.source : ""}}); toast(tx("Réglages des exercices enregistrés.")); }}, tx("Enregistrer")));
  // import
  const fichier = el("input", {type: "file", id: "ex-fichier", accept: ".gift,.txt,.xml"});
  const colle = el("textarea", {id: "ex-texte", rows: "5", placeholder: tx("Ou collez ici le contenu d'un fichier GIFT ou Moodle XML")});
  const msg = S.importMsg ? el("div", {class: "notice " + (S.importMsg.importes ? "" : "warn"), role: "status"},
    el("p", {style: "font-weight:700"}, tx`${S.importMsg.importes} question${S.importMsg.importes > 1 ? "s" : ""} importée${S.importMsg.importes > 1 ? "s" : ""}.`),
    S.importMsg.avertissements.length ? el("ul", {class: "small"}, S.importMsg.avertissements.map(a => el("li", {}, a))) : null) : null;
  const importer = el("div", {class: "card"}, el("h2", {}, tx("Importer une banque")),
    el("p", {class: "small muted"}, tx("Formats GIFT (.gift, .txt) et Moodle XML (.xml), par exemple exportés depuis Éléa ou Moodle. Questions prises en charge : choix unique ou multiple, vrai ou faux, réponse courte, numérique, appariement. Les images ne sont pas importées.")),
    el("div", {class: "field"}, el("label", {for: "ex-fichier"}, tx("Fichier")), fichier), colle,
    el("div", {class: "field"}, el("label", {for: "ex-niveau-import"}, tx("Niveau des questions importées")), selNiv("ex-niveau-import", 2)),
    el("button", {class: "primary", onclick: async () => {
      let contenu = colle.value, source = tx("texte collé");
      if (fichier.files[0]) { contenu = await lireFichier(fichier.files[0]); source = fichier.files[0].name; }
      if (!contenu.trim()) { toast(tx("Choisissez un fichier ou collez un contenu.")); return; }
      try { S.importMsg = await appel(`classes/${S.code}/exercices/import`, {methode: "POST", corps: {contenu, niveau: +$("#ex-niveau-import").value, source}}); S.exos = null; }
      catch (e) { toast(e.message); }
      rendre(); }}, tx("Importer")), msg);
  // banque
  const parNiveau = niveaux.map(n => [n, S.exos.filter(x => x.niveau === n)]).filter(([, l]) => l.length);
  const banque = el("div", {class: "card"}, el("h2", {}, tx`Banque de la classe (${S.exos.length} question${S.exos.length > 1 ? "s" : ""})`),
    S.exos.length ? null : el("p", {class: "muted"}, tx("Aucune question pour l'instant.")),
    ...parNiveau.map(([n, l]) => el("details", {open: true}, el("summary", {}, tx`Niveau ${n} · ${l.length} question${l.length > 1 ? "s" : ""}`),
      el("ol", {class: "ideas", style: "margin-top:8px"}, l.map(x => {
        const niv = selNiv("niv-" + x.id, x.niveau); niv.setAttribute("aria-label", tx("Niveau de ") + x.titre);
        niv.addEventListener("change", async () => { await appel(`classes/${S.code}/exercices/${x.id}`, {methode: "PUT", corps: {niveau: +niv.value}}); S.exos = null; rendre(); });
        const act = el("input", {type: "checkbox", id: "act-" + x.id, checked: x.actif});
        act.addEventListener("change", async () => { await appel(`classes/${S.code}/exercices/${x.id}`, {methode: "PUT", corps: {actif: act.checked}}); x.actif = act.checked; });
        const suppr = S.confirmer === "exo" + x.id
          ? el("span", {class: "row"}, el("button", {class: "danger", onclick: async () => { await appel(`classes/${S.code}/exercices/${x.id}`, {methode: "DELETE"}); S.confirmer = null; S.exos = null; rendre(); }}, tx("Confirmer")),
              el("button", {class: "ghost", onclick: () => { S.confirmer = null; rendre(); }}, tx("Annuler")))
          : el("button", {class: "ghost", onclick: () => { S.confirmer = "exo" + x.id; rendre(); }}, tx("Supprimer"));
        return el("li", {style: "flex-direction:column;align-items:stretch"},
          el("div", {class: "row", style: "justify-content:space-between"}, el("b", {}, x.titre), el("span", {class: "tag"}, NOM_TYPE[x.type] || x.type)),
          el("p", {class: "small muted"}, x.texte),
          el("div", {class: "row"}, el("div", {style: "width:140px"}, niv), el("label", {for: "act-" + x.id, class: "row", style: "gap:6px"}, act, tx("proposée")), suppr));
      })))));
  $("#vue").replaceChildren(el("div", {class: "wrap"}, reglages, importer, banque));
}

document.querySelector("header").append(menuLangue());     // langue de cette page ; celle des élèves se règle par classe (Réglages)
document.querySelectorAll("#tabs button").forEach(b => b.addEventListener("click", () => { S.onglet = b.dataset.tab; S.detail = null; S.confirmer = null; S.seanceEditee = null;
  document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-selected", String(x === b))); rendre(); }));
lireLienRecu();
if (S.jeton) listerClasses(); else rendre();
setInterval(() => { if (S.jeton && S.code && S.onglet === "classe" && !S.detail) chargerClasse(); }, 10000);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("../sw.js", {scope: "../"}).catch(() => {});
