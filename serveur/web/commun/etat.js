// Viabilis classe — module commun : similarité des idées, estimation de l'état (C, A, D, M),
// ruptures et recommandation. Identique au prototype pilote ; aucune donnée ne sort du navigateur.

import {tx, LANGUE} from "./langues.js";
export {tx};

export const NOM_ORDRE = {reflexion: tx("Réflexion d'abord"), ia: tx("IA d'abord"), adaptatif: tx("Adaptatif (selon la charge déclarée)"), autonomie: tx("IA retirée")};
export const NOM_MODE = {questionner: tx("IA qui questionne"), elements: tx("IA qui donne des éléments")};
export const NOM_VARIANTE = {accessible: tx("variante accessible"), standard: tx("tâche standard"), exigeante: tx("variante exigeante")};
const ORDRE_VARIANTES = ["accessible", "standard", "exigeante"];

const VIDES = new Set("les des une un le la de du et a au aux en pour par sur avec dans ce ces cet cette son sa ses leur leurs qui que quoi ne pas plus est sont etre faire on il elle ils elles nous vous je tu me te se mon ma mes ton ta tes y d l qu c s n j m t peut peuvent tres comme ou mais donc car si aussi bien tout tous toute toutes".split(" "));

export function mots(t) {
  const calc = String(t).toLowerCase().replace(/€|euros?/g, "").replace(/\s+/g, "").replace(/[×x]/g, "*").replace(/−/g, "-").replace(/:/g, "/");
  if (/\d/.test(calc) && /^[\d+\-*/().,=]+$/.test(calc)) {   // un calcul : même jeton si mêmes termes (l'ordre d'une somme ne compte pas)
    const expr = calc.split("=").find(c => /[+\-*/]/.test(c)) || calc;
    return new Set(["calc:" + (/^[\d.,+]+$/.test(expr) ? expr.split("+").sort().join("+") : expr)]);
  }
  return new Set(String(t).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]+/g, " ").split(/\s+/)
    .filter(w => w.length >= 3 && !VIDES.has(w)).map(w => w.replace(/(s|x)$/, "")));
}
export function jaccard(a, b) {
  const A = a instanceof Set ? a : mots(a), B = b instanceof Set ? b : mots(b);
  if (!A.size || !B.size) return 0;
  let n = 0; for (const w of A) if (B.has(w)) n++;
  return n / (A.size + B.size - n);
}
export function distinctes(textes) {
  const reps = [];
  for (const t of textes) { const m = mots(t); if (!m.size) continue; if (!reps.some(r => jaccard(r, m) >= 0.5)) reps.push(m); }
  return reps.length;
}
// Nombre de solutions qu'on peut raisonnablement attendre en une séance : au-delà, trouver 8 solutions vaut la note maximale
// (sur « Payer 20 € », 29 solutions existent : en trouver 5 est un bon résultat, pas une maîtrise insuffisante).
export const ATTENDU_MAX_SEANCE = 8;
/** Niveau de difficulté effectif d'une séance pour un élève : niveau de la tâche (1 à 5), −1 en variante accessible, +1 en exigeante. */
export function niveauEffectif(cfg, n, variante) {
  const t = (cfg.archives || {})[n] || (n === cfg.seance ? cfg : null);
  return (t?.niveauTache ?? cfg.niveauTache ?? 3) + ({accessible: -1, exigeante: 1}[variante] || 0);
}
export const echelle = x => x == null ? null : 0.1 + 0.2 * (x - 1);   // 1..5 -> 0,1..0,9
const moy = xs => { const v = xs.filter(x => x != null && !isNaN(x)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };

/** Aide reçue pendant une séance, traduite dans les commandes du modèle (s : éléments de réponse, φ : questions, r : réflexion d'abord).
    Correspondance approximative : IA qui donne des éléments → s = 0,6 ; IA qui questionne → φ = 0,6 ; chaque coup de pouce → s + 0,2. */
export function commandeObservee(s) {
  const ia = (s?.echanges || []).some(e => e.role === "ia"), pouces = s?.indicesVus || 0;
  let et = 0, phi = 0;
  if (ia && s.ordre !== "autonomie") { if (s.mode === "elements") { et = 0.6; phi = 0.2; } else phi = 0.6; }
  return [Math.min(1, et + 0.2 * pouces), phi, s?.ordre === "ia" ? 0 : 1];
}
export function brut(s, autres, noteEns) {
  const avant = (s.ideesAvant || []).map(i => i.texte), apres = (s.ideesApres || []).map(i => i.texte), toutes = avant.concat(apres);
  const phrasesIA = (s.echanges || []).filter(e => e.role === "ia").flatMap(e => e.texte.split(/[.?!\n]+/)).filter(p => mots(p).size >= 2).map(mots);
  const reprises = apres.filter(t => phrasesIA.some(p => jaccard(t, p) >= 0.4)).length;
  const reprise = apres.length ? reprises / apres.length : 0;
  const autresIdees = autres.map(mots);
  const originales = toutes.filter(t => !autresIdees.some(o => jaccard(t, o) >= 0.5)).length;
  const originalite = toutes.length ? originales / toutes.length : null;
  const nDist = distinctes(toutes);
  // part des idées écrites avant toute aide (au moins 3 attendues) : écrire 3 idées puis tout tirer de l'IA ne vaut plus 1
  const autonomie = Math.min(1, (s.ideesAvantAide ?? avant.length) / Math.max(3, toutes.length));
  const exos = (s.exercices || []).filter(x => x.score != null);
  const scoreExos = exos.length ? moy(exos.map(x => x.score)) : null;          // meilleure tentative
  const premierEssai = exos.length ? moy(exos.map(x => x.premierScore ?? x.score)) : null;
  let C = moy([echelle(s.chargeDebut), echelle(s.chargeFin)]); if (C != null && s.bloque) C = Math.min(1, C + 0.1);
  if (premierEssai != null) C = C == null ? 0.2 + 0.6 * (1 - premierEssai) : 0.7 * C + 0.3 * (1 - premierEssai);   // échecs au premier essai : signe de charge
  const A = toutes.length || s.premiereDemande != null ? 0.5 * (1 - reprise) + 0.5 * autonomie : null;
  const D = toutes.length ? 0.4 * Math.min(1, nDist / 5) + 0.3 * (originalite ?? 0) + 0.3 * (1 - reprise) : null;
  const verif = s.verification;
  // réussite à la dernière vérification, sans pénaliser les essais : part des solutions trouvées quand leur nombre est connu,
  // sinon la meilleure des deux mesures (part d'idées justes, ou 5 idées justes et plus = 1)
  const tauxJuste = !verif || !verif.idees?.length ? null : verif.attendu ? Math.min(1, verif.justes / Math.min(verif.attendu, ATTENDU_MAX_SEANCE))
    : Math.max(verif.justes / verif.idees.length, Math.min(1, verif.justes / 5));
  const M = moy([echelle(s.compris), noteEns == null ? null : noteEns / 4, scoreExos, tauxJuste]);
  return {C, A, D, M, reprise, originalite, nDist, nAvant: avant.length, nApres: apres.length, scoreExos, nExos: exos.length,
          niveauExos: exos.length ? moy(exos.map(x => x.niveau)) : null, tauxJuste, nVerifs: verif?.nombre ?? 0,
          indicesVus: s.indicesVus ?? 0, variante: s.variante ?? null};
}

/** traces : {idEleve: {pseudo, seances: {n: trace}}} ; notes : {idEleve: {n: 0..4}} */
export function ideesDesAutres(traces, uid, n) {
  return Object.entries(traces).filter(([u]) => u !== uid).flatMap(([, d]) => {
    const x = d.seances?.[n]; return x ? [...(x.ideesAvant || []), ...(x.ideesApres || [])].map(i => i.texte) : [];
  });
}
export function etatEleve(traces, notes, uid) {
  const doc = traces[uid]; if (!doc) return null;
  const nums = Object.keys(doc.seances || {}).map(Number).sort((a, b) => a - b);
  const etat = {C: null, A: null, D: null, M: null}; let dernier = null; const serie = [], trajet = [];
  for (const n of nums) {
    const b = brut(doc.seances[n], ideesDesAutres(traces, uid, n), notes[uid]?.[n]);
    for (const k of ["C", "A", "D", "M"]) if (b[k] != null) etat[k] = etat[k] == null ? b[k] : 0.4 * etat[k] + 0.6 * b[k];
    dernier = {n, ...b};
    serie.push(dernier);
    trajet.push({n, ...etat, variante: b.variante, u: commandeObservee(doc.seances[n])});   // état estimé après la séance n
  }
  return {etat, dernier, nums, serie, trajet, preferences: doc.preferences || {}};
}
export function ruptures(e, cfg) {
  const r = [];
  const t = (v, cond, nom) => { if (v == null) return; if (cond(v, 0)) r.push({nom, niv: "ko"}); else if (cond(v, 0.1)) r.push({nom, niv: "warn"}); };
  t(e.C, (v, m) => v > 0.85 - m, "surcharge");
  t(e.C, (v, m) => v < 0.2 + m, "ennui");
  t(e.A, (v, m) => v < 0.3 + m, "dépendance");
  t(e.D, (v, m) => v < 0.25 + m, "rigidité");
  t(e.M, (v, m) => v < cfg.seuilMaitrise + m, "maîtrise insuffisante");
  return r;
}
/** Les deux dernières séances (valeurs brutes, non lissées) confirment-elles une maîtrise insuffisante, ou une tâche trop facile ? */
function tendances(est, cfg) {
  const deux = (est?.serie || []).slice(-2);
  const solide = Math.max(cfg.seuilMaitrise, 0.7);
  const tropFacile = deux.length === 2 && deux.every(b => b.C != null && b.C < 0.35 && b.M != null && b.M >= solide);
  return {insuffisante: deux.length === 2 && deux.every(b => b.M != null && b.M < cfg.seuilMaitrise), tropFacile,
          // palier : le niveau effectif réellement réussi (le plus bas des deux séances faciles)
          palier: tropFacile ? Math.min(...deux.map(b => niveauEffectif(cfg, b.n, b.variante))) : null,
          // lecture facilitée ou images : une consigne plus exigeante est souvent plus longue ; l'enseignant décide
          lecteurFragile: !!(est?.preferences?.facile || est?.preferences?.images)};
}
/** niveau : niveau d'exercices de référence (1 à 5) ou null ; variante : variante de référence ou null (variantes inactives) ;
    est : résultat d'etatEleve, pour tenir compte des deux dernières séances. */
export function recommandation(e, cfg, niveau = null, variante = null, est = null) {
  const t = tendances(est, cfg);
  const r = recommandationBase(e, cfg, niveau, t);
  if (variante == null || e.C == null) return {...r, variante};
  const i = ORDRE_VARIANTES.indexOf(variante);
  // on redescend d'un cran si la charge est trop forte OU si la maîtrise est insuffisante deux séances de suite ;
  // on ne monte qu'après deux séances faciles et réussies (une seule séance facile ne suffit plus)
  const plusAccessible = (e.C >= cfg.seuilCharge && (e.M == null || e.M < cfg.seuilMaitrise)) || t.insuffisante;
  const aLAise = !plusAccessible && t.tropFacile && e.M != null && e.M >= Math.max(cfg.seuilMaitrise, 0.7);
  const plusExigeante = aLAise && !t.lecteurFragile;
  const v = plusAccessible ? ORDRE_VARIANTES[Math.max(0, i - 1)] : plusExigeante ? ORDRE_VARIANTES[Math.min(2, i + 1)] : variante;
  let texte = v === variante ? r.texte : r.texte.replace(/\.$/, "") + (plusAccessible
    ? (t.insuffisante && e.C < cfg.seuilCharge ? tx(" ; maîtrise insuffisante deux séances de suite : proposer une tâche plus accessible.") : tx(" ; proposer une tâche plus accessible."))
    : tx` ; deux séances faciles et réussies au niveau ${t.palier} : variante plus exigeante, tant que la tâche reste à ce niveau.`);
  if (aLAise && t.lecteurFragile && i < 2) texte = texte.replace(/\.$/, "") + tx(" ; à l'aise deux séances de suite, mais il lit avec l'affichage facilité : à vous de juger d'une tâche plus exigeante.");
  // palier : niveau validé ; le serveur ne donne la variante exigeante que si la nouvelle tâche n'est pas déjà plus difficile
  return {...r, variante: v, texte, palier: plusExigeante ? t.palier : null};
}
function recommandationBase(e, cfg, niveau = null, t = {}) {
  if (e.C == null) return {ordre: null, mode: null, retrait: false, niveau, texte: tx("Pas encore de trace : suivre la règle de la classe.")};
  const plus = n => n == null ? null : Math.min(5, n + 1), moins = n => n == null ? null : Math.max(1, n - 1);
  const maitriseSolide = e.M != null && e.M >= Math.max(cfg.seuilMaitrise, 0.6);
  if (e.C >= cfg.seuilCharge) {
    const baisse = niveau != null && niveau > 1 && (e.M == null || e.M < cfg.seuilMaitrise);
    return {ordre: "ia", mode: "elements", retrait: false, niveau: baisse ? moins(niveau) : niveau,
      texte: tx("Charge élevée : l'aide vient d'abord, avec des éléments de réponse") + (baisse ? tx(", et des exercices d'un niveau plus accessible.") : ".")};
  }
  if (t.insuffisante && niveau != null && niveau > 1)
    return {ordre: "reflexion", mode: "questionner", retrait: false, niveau: moins(niveau),
      texte: tx("Maîtrise insuffisante deux séances de suite : réflexion d'abord, une IA qui questionne, et des exercices d'un niveau plus accessible.")};
  if (e.A != null && e.A >= cfg.retraitAgentivite && maitriseSolide) {
    const hausse = niveau != null && niveau < 5 && e.C < 0.3;
    return {ordre: "reflexion", mode: "questionner", retrait: true, niveau: hausse ? plus(niveau) : niveau,
      texte: e.C < 0.3 ? (hausse ? tx("Autonome et peu chargé : retirer l'IA et passer au niveau d'exercices supérieur.") : tx("Autonome et peu chargé : retirer l'IA et relever l'exigence de la tâche.")) : tx("Autonome : retirer l'IA.")};
  }
  const hausse = niveau != null && niveau < 5 && e.C < 0.3 && e.M != null && e.M >= 0.8;
  if (e.A != null && e.A >= cfg.retraitAgentivite)        // autonome mais maîtrise fragile : on garde une IA qui questionne
    return {ordre: "reflexion", mode: "questionner", retrait: false, niveau, texte: tx("Autonome, mais maîtrise encore fragile : réflexion d'abord, et garder une IA qui questionne.")};
  if (e.D != null && e.D < 0.35) return {ordre: "reflexion", mode: "questionner", retrait: false, niveau: hausse ? plus(niveau) : niveau, texte: tx("Pensée divergente basse : réflexion d'abord, puis une IA qui questionne.")};
  return {ordre: "reflexion", mode: "questionner", retrait: false, niveau: hausse ? plus(niveau) : niveau,
    texte: tx("Réflexion d'abord, puis une IA qui questionne") + (hausse ? tx(", et des exercices du niveau supérieur.") : ".")};
}

/* ---------- numéro affiché d'une séance ----------
   Une séance garde son identifiant interne (n) même quand des séances plus anciennes sont effacées ;
   on affiche son rang parmi les séances qui existent encore (la 1re séance restante s'appelle « Séance 1 »). */
export const numeroSeance = (cfg, n) => n - (cfg?.supprimees || []).filter(x => x < n).length;
export const prochainNumero = cfg => (cfg?.seance || 0) - (cfg?.supprimees || []).length + 1;

/* ---------- petits outils d'interface partagés ---------- */
export const $ = (s, r = document) => r.querySelector(s);
export function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, ""); else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}
export const fr = (v, n = 2) => (v == null || isNaN(v)) ? "–" : v.toFixed(n).replace(".", ",");
export const now = () => new Date().toISOString();
export function echelleUI(question, libelles, val, choisir) {
  const id = "q" + Math.random().toString(36).slice(2, 7);
  return el("div", {class: "field", role: "group", "aria-labelledby": id}, el("p", {id, style: "font-weight:700"}, question),
    el("div", {class: "scale"}, libelles.map((lib, i) => el("button", {"aria-pressed": String(val === i + 1), onclick: () => choisir(i + 1)}, lib))));
}
/** Texte d'une idée : un programme (plusieurs lignes) garde son indentation, en police à chasse fixe. */
export function texteIdee(t) {
  return /\n/.test(String(t)) ? el("pre", {class: "code"}, t) : el("span", {class: "texte-idee"}, t);
}
export function listeIdees(liste, tag) {
  if (!liste.length) return el("p", {class: "small muted"}, tx("Aucune idée pour l'instant."));
  return el("ol", {class: "ideas"}, liste.map(i => el("li", {style: (i.avant || []).length ? "flex-direction:column;align-items:stretch" : ""},
    el("div", {class: "row", style: "justify-content:space-between;align-items:flex-start"}, texteIdee(i.texte), el("span", {class: "tag"}, i.modifiee ? tx`${tag} · modifiée` : tag)),
    (i.avant || []).length ? el("details", {class: "small muted"}, el("summary", {}, tx`Version${i.avant.length > 1 ? "s" : ""} précédente${i.avant.length > 1 ? "s" : ""} (${i.avant.length})`),
      el("ol", {}, i.avant.map(x => el("li", {}, texteIdee(x.texte))))) : null)));
}
export async function api(chemin, {methode = "GET", corps, jeton} = {}) {
  const r = await fetch("/api/" + chemin, {method: methode, headers: {"Content-Type": "application/json", "X-Viabilis-Langue": LANGUE, ...(jeton ? {Authorization: "Bearer " + jeton} : {})},
    body: corps === undefined ? undefined : JSON.stringify(corps)});
  const d = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw Object.assign(new Error(d?.erreur || tx("Erreur ") + r.status), {statut: r.status});
  return d;
}

/* ---------- groupes de besoin ---------- */
export const GROUPES = {
  atelier: {nom: tx("Atelier dirigé"), aide: tx("avec vous en début de séance ; l'aide vient d'abord"), reglage: {ordre: "ia", mode: "elements", retrait: false, variante: "accessible"}},
  accompagne: {nom: tx("Travail accompagné"), aide: tx("réflexion d'abord, puis une IA qui questionne"), reglage: {ordre: "reflexion", mode: "questionner", retrait: false, variante: "standard"}},
  defi: {nom: tx("Défi en autonomie"), aide: tx("variante exigeante, sans IA"), reglage: {ordre: "reflexion", mode: "questionner", retrait: true, variante: "exigeante"}},
};
/** Groupe proposé pour la séance suivante, avec la raison. v : statut de viabilité (ou null). */
export function groupeSuggere(e, v, cfg) {
  if (e.C == null) return {groupe: "accompagne", raison: tx("pas encore de trace")};
  const ko = ruptures(e, cfg).filter(x => x.niv === "ko").map(x => x.nom);
  const solide = e.M != null && e.M >= Math.max(cfg.seuilMaitrise, 0.6);
  if (v && (v.statut === "hors_noyau" || v.statut === "hors_bassin")) {
    const ou = v.statut === "hors_noyau" ? tx("hors du noyau de viabilité") : tx("hors du bassin de capture");
    // sortie par l'ennui (charge très faible, sans surcharge ni dépendance) : un défi, pas un atelier dirigé
    if (e.C < 0.3 && !ko.includes("surcharge") && !ko.includes("dépendance"))
      return solide ? {groupe: "defi", raison: ou + tx(" par l'ennui : relever le défi")} : {groupe: "accompagne", raison: ou + tx(" par l'ennui, maîtrise à consolider")};
    return {groupe: "atelier", raison: ou};
  }
  if (ko.includes("surcharge") || ko.includes("dépendance")) return {groupe: "atelier", raison: tx("rupture : ") + ko.filter(x => x === "surcharge" || x === "dépendance").map(x => tx(x)).join(", ")};
  if (e.C >= cfg.seuilCharge && (e.M == null || e.M < cfg.seuilMaitrise)) return {groupe: "atelier", raison: tx("charge élevée et maîtrise insuffisante")};
  const maitriseSolide = solide;                                                         // un défi suppose une maîtrise solide
  if (v?.statut === "auto_soutenu" && e.C < 0.6 && maitriseSolide) return {groupe: "defi", raison: tx("peut continuer sans aide (auto-soutenu) et maîtrise solide")};
  if (e.A != null && e.A >= cfg.retraitAgentivite && e.C < 0.5 && maitriseSolide) return {groupe: "defi", raison: tx("autonome, peu chargé, maîtrise solide")};
  if (e.M != null && e.M >= 0.8 && e.C < 0.3) return {groupe: "defi", raison: tx("maîtrise élevée et charge faible")};
  if (ko.includes("ennui")) return {groupe: "defi", raison: tx("risque d'ennui")};
  return {groupe: "accompagne", raison: tx("dans le domaine")};
}

/* ---------- lecture à voix haute (voix de l'appareil uniquement : rien n'est envoyé à un service extérieur) ---------- */
const parle = () => typeof window !== "undefined" && "speechSynthesis" in window;
function voixLocale(langue) {
  if (!parle()) return null;
  const base = langue.slice(0, 2).toLowerCase();
  const voix = speechSynthesis.getVoices().filter(v => v.localService && (v.lang || "").toLowerCase().replace("_", "-").startsWith(base));
  return voix.find(v => v.lang.replace("_", "-") === langue) || voix[0] || null;
}
export const lectureDisponible = langue => !!voixLocale(langue);
export function lire(texte, langue) {
  const v = voixLocale(langue); if (!v || !texte) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(String(texte).replace(/____/g, "blanc"));
  u.voice = v; u.lang = v.lang; u.rate = 0.9;
  speechSynthesis.speak(u);
}
/** Bouton « Écouter » ; null si aucune voix locale n'est disponible dans cette langue. */
export function boutonEcouter(texte, langue, etiquette = tx("Écouter")) {
  if (!lectureDisponible(langue)) return null;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("width", "18"); svg.setAttribute("height", "18"); svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = '<path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/><path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>';
  return el("button", {class: "ghost ecouter", type: "button", "aria-label": etiquette, onclick: () => lire(typeof texte === "function" ? texte() : texte, langue)}, svg, " " + etiquette);
}

/* ---------- dictée vocale : seulement si l'appareil reconnaît la parole SANS envoyer la voix à un service extérieur ----------
   Les navigateurs qui transcrivent sur leurs serveurs (comportement par défaut de la reconnaissance vocale) sont exclus :
   on exige la reconnaissance « sur l'appareil » (SpeechRecognition.available avec processLocally), sinon pas de bouton. */
const Reco = () => typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
export async function dicteeLocaleDisponible(langue) {
  const R = Reco();
  if (!R || typeof R.available !== "function") return false;
  try { return (await R.available({langs: [langue], processLocally: true})) === "available"; } catch { return false; }
}
export function boutonDicter(champ, langue) {
  const R = Reco();
  let r = null;
  const b = el("button", {type: "button", class: "ecouter", "aria-pressed": "false"}, tx("🎤 Dicter"));
  const stop = () => { r = null; b.setAttribute("aria-pressed", "false"); b.textContent = tx("🎤 Dicter"); };
  b.addEventListener("click", () => {
    if (r) { r.stop(); return; }
    r = new R(); r.lang = langue; r.processLocally = true; r.interimResults = false; r.maxAlternatives = 1;
    r.onresult = e => { const t = e.results[0][0].transcript; champ.value = (champ.value ? champ.value.trimEnd() + " " : "") + t; champ.dispatchEvent(new Event("input")); };
    r.onend = stop; r.onerror = stop;
    b.setAttribute("aria-pressed", "true"); b.textContent = tx("⏹ Arrêter");
    try { r.start(); } catch { stop(); }
  });
  return b;
}
