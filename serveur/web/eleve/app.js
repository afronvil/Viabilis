// Viabilis classe — application élève.
import {tx, adopterLangue} from "../commun/langues.js";
import {appliquerTheme, banniere, plante, bravo} from "../commun/visuels.js";
import {$, el, now, api, echelleUI, listeIdees, NOM_MODE, boutonEcouter, dicteeLocaleDisponible, boutonDicter, texteIdee} from "../commun/etat.js";

// lecture à voix haute : seulement si l'enseignant l'a activée et qu'une voix est installée sur l'appareil
const ecoute = (texte, etiquette) => moi?.lecture?.active ? boutonEcouter(texte, moi.lecture.langue, etiquette) : null;
const MESSAGES_GROUPE = {
  atelier: tx("Aujourd'hui, ton enseignant travaille avec toi au début de la séance."),
  defi: tx("Aujourd'hui, un défi t'attend : cherche en autonomie, tu en es capable."),
};

// comment l'élève a cherché (demandé avant de vérifier) et ce qui l'a aidé (demandé en fin de séance)
const DEMARCHES = [["hasard", "🎲", tx("J'ai essayé des idées au hasard")], ["ordre", "🔢", tx("J'ai cherché dans un ordre, pour n'en oublier aucune")],
  ["transformer", "🔄", tx("Je suis parti d'une idée et je l'ai transformée")], ["aide", "💡", tx("Je me suis aidé d'un coup de pouce ou de l'IA")], ["autre", "✏️", tx("Autrement")]];
const AIDES = [["idees", "🧠", tx("mes propres idées")], ["pouce", "👍", tx("un coup de pouce")], ["ia", "🤖", tx("l'IA")], ["verification", "✅", tx("la vérification")],
  ["camarade", "👫", tx("un camarade")], ["enseignant", "🧑‍🏫", tx("mon enseignant")], ["rien", "🤷", tx("rien de particulier")]];
const pref = k => !!moi?.preferences?.[k];
// illustrations : réglées par l'enseignant pour la classe (Réglages), d'après la discipline de la séance et le public
const visuels = () => moi?.config?.visuels !== false;
const ecole = () => visuels() && (moi?.config?.public || "ecole") === "ecole";
// école : la plante grandit avec chaque idée écrite ; elle fleurit quand le nombre d'idées attendu est atteint
const titreIdees = (titre, n) => ecole()
  ? el("div", {class: "compteur-idees"}, plante(n, moi.config.minIdees || 3), el("div", {}, el("h2", {}, titre),
      el("p", {class: "small muted"}, !n ? tx("Écris une idée : ta plante va pousser.")
        : n >= (moi.config.minIdees || 3) ? tx`Ta plante a fleuri : ${n} idées ! Chaque nouvelle idée la fait encore grandir.`
        : tx`Ta plante a ${n} feuille${n > 1 ? "s" : ""} : chaque idée la fait grandir.`)))
  : el("h2", {}, titre);
const img = (emoji, texte) => pref("images") ? `${emoji} ${texte}` : texte;     // choix illustrés pour les plus jeunes ou les lecteurs fragiles
let DICTEE = {};             // langue -> la dictée sur l'appareil est-elle possible ?
const dictee = champ => {
  const lg = moi?.lecture?.langue || "fr-FR";
  if (!moi?.lecture?.dictee) return null;
  if (DICTEE[lg] === undefined) { DICTEE[lg] = false; dicteeLocaleDisponible(lg).then(ok => { DICTEE[lg] = ok; if (ok && L && moi) redessinerSansPerdreLaSaisie(); }); }
  return DICTEE[lg] ? boutonDicter(champ, lg) : null;
};
let PARCOURS = false, DEMARCHE = null;     // affichage du parcours ; démarche en cours de saisie avant une vérification

const CLE = "viabilis-eleve", CLE_SEANCE = "viabilis-seance";
let session = null;          // {jeton, pseudo}
let moi = null;              // réponse de /api/eleve/moi pour la séance choisie
let L = null;                // séance en cours, état local
let CHOIX = null;            // numéro de la séance choisie par l'élève
let CLASSE = null;           // étape de connexion : {code, nom, pseudos, codePersonnel}
let focusIdee = false;
const q = () => "?seance=" + L.num;                     // tous les appels portent sur la séance choisie

function lireSession() { try { return JSON.parse(localStorage.getItem(CLE)); } catch { return null; } }
function ecrireSession(s) { try { s ? localStorage.setItem(CLE, JSON.stringify(s)) : localStorage.removeItem(CLE); } catch {} }
function lireChoix() { try { return Number(sessionStorage.getItem(CLE_SEANCE)) || null; } catch { return null; } }
function ecrireChoix(n) { try { n ? sessionStorage.setItem(CLE_SEANCE, String(n)) : sessionStorage.removeItem(CLE_SEANCE); } catch {} }

async function charger() {
  try { moi = await api("eleve/moi" + (CHOIX ? "?seance=" + CHOIX : ""), {jeton: session.jeton}); }
  catch (e) { if (e.statut === 401) { ecrireSession(null); session = null; } moi = null; }
  if (moi && adopterLangue(moi.config?.langue)) return;          // la langue de la classe, choisie par l'enseignant
  appliquerPreferences();
  rendre();
}
function choisir(n) { CHOIX = n; ecrireChoix(n); L = null; EXOS = null; VERIF = null; moi = null; message(tx("Chargement…"), tx("Ouverture de la séance.")); charger(); }
function deconnecter() { ecrireSession(null); ecrireChoix(null); session = null; moi = null; L = null; CHOIX = null; CLASSE = null; rendre(); }

function rendre() {
  if (!session) return ecranConnexion();
  if (!moi) return message(tx("Connexion…"), tx("Récupération de vos séances."));
  appliquerTheme(visuels(), moi.config?.discipline, moi.config?.public);
  $("#sous-titre").textContent = `${moi.pseudo} · ${moi.classe}`;
  const ouv = moi.ouvertes || [];
  if (!ouv.length) { L = null; return message(tx("En attente de la séance"), tx("Votre enseignant n'a pas encore ouvert de séance. Cette page se met à jour toute seule.")); }
  if (CHOIX && !ouv.some(o => o.seance === CHOIX)) { CHOIX = null; ecrireChoix(null); L = null; }
  if (!CHOIX) { if (ouv.length === 1) return choisir(ouv[0].seance); return ecranSeances(); }
  const c = moi.config;
  if (c.seance !== CHOIX) return charger();
  if (!L || L.num !== c.seance) {
    const deja = moi.seances[String(c.seance)];
    L = deja ? {...deja, num: c.seance} : {num: c.seance, phase: "charge", tache: c.tache, debut: null, chargeDebut: null, chargeFin: null, compris: null,
      ideesAvant: [], ideesApres: [], echanges: [], premiereDemande: null, ideesAvantAide: null, bloque: false};
    L.echanges ||= []; L.ideesAvant ||= []; L.ideesApres ||= [];
    VERIF = moi.derniereVerification ? {...moi.derniereVerification, num: c.seance} : null;
  }
  seance();
}

/* ---------------------------------------------------------------- affichage, messages, parcours, galerie */
function appliquerPreferences() {
  for (const k of ["grand", "facile", "images"]) document.body.classList.toggle("pref-" + k, pref(k));
}
function carteAffichage() {
  const etat = el("span", {class: "small muted", "aria-live": "polite"});
  const caseP = (k, texte) => { const i = el("input", {type: "checkbox", id: "pref-" + k, checked: pref(k)});
    i.addEventListener("change", async () => {
      try { moi.preferences = await api("eleve/preferences", {methode: "PUT", jeton: session.jeton, corps: {...(moi.preferences || {}), [k]: i.checked}}); appliquerPreferences(); L ? redessinerSansPerdreLaSaisie() : rendre(); }
      catch (e) { etat.textContent = e.message; }
    });
    return el("label", {for: "pref-" + k, class: "row", style: "gap:8px;font-weight:600"}, i, texte); };
  return el("details", {class: "card"}, el("summary", {}, tx("Affichage")),
    caseP("grand", tx("Texte plus grand")), caseP("facile", tx("Lecture facilitée (lettres et lignes plus espacées)")), caseP("images", tx("Images dans les choix")), etat);
}
function carteMessages() {
  const msgs = moi.messages || [];
  if (!msgs.length) return null;
  return msgs.map(m => el("div", {class: "notice ok", role: "status"},
    el("div", {class: "row", style: "justify-content:space-between"}, el("p", {style: "font-weight:700"}, tx("Message de ton enseignant")), ecoute(m.texte)),
    el("p", {}, m.texte),
    el("button", {onclick: async () => { try { await api(`eleve/messages/${m.id}/lu`, {methode: "POST", jeton: session.jeton, corps: {}}); } catch {} moi.messages = msgs.filter(x => x !== m); L ? seance() : rendre(); }}, tx("J'ai lu"))));
}
/** Les essais successifs d'une séance : idées justes (ou idées écrites, sans vérification) et exercices. */
function essaisDe(p) {
  const tous = [...(p.historique || []), p.actuel].filter(Boolean);
  const mesure = x => x.justes != null ? x.justes : null;
  const ligne = tous.map(x => tx`Essai ${x.essai} : ` + (x.justes != null ? tx`${x.justes} idée${x.justes > 1 ? "s" : ""} juste${x.justes > 1 ? "s" : ""}` : tx`${x.idees} idée${x.idees > 1 ? "s" : ""}`)
    + (x.exercices != null ? tx`, exercices ${Math.round(100 * x.exercices)} %` : "")).join(" → ");
  const a = mesure(tous[0]), b = mesure(tous[tous.length - 1]);
  const progres = tous.length > 1 && a != null && b != null && b > a ? tx`Tu as progressé : ${b - a} idée${b - a > 1 ? "s" : ""} juste${b - a > 1 ? "s" : ""} de plus qu'au premier essai.` : null;
  return {ligne, progres};
}
function carteParcours() {
  const ps = (moi.parcours || []).slice().reverse();
  if (!ps.length) return null;
  return el("div", {class: "card"}, el("h2", {}, tx("Mon parcours")),
    el("p", {class: "small muted"}, tx("Ce que tu as fait à chaque séance, essai après essai. Tu te compares seulement à toi-même.")),
    el("ol", {class: "ideas"}, ps.map(p => { const {ligne, progres} = essaisDe(p);
      return el("li", {style: "flex-direction:column;align-items:stretch;gap:4px"},
        el("span", {}, el("b", {}, tx`Séance ${p.numero ?? p.seance}`), " · ", p.titre || ""),
        el("span", {class: "small"}, ligne || tx("Pas encore commencée.")),
        progres ? el("span", {class: "pill ok"}, progres) : null,
        (p.galerie || []).length ? el("details", {}, el("summary", {class: "small"}, tx`Les idées de la classe (${p.galerie.length})`), listeGalerie(p.galerie)) : null); })));
}
function listeGalerie(textes) { return el("ul", {class: "ideas"}, textes.map(t => el("li", {style: "align-items:center"}, el("span", {}, t), ecoute(t)))); }

/* ---------------------------------------------------------------- choix de la séance */
function ecranSeances() {
  $("#titre").textContent = tx("Mes séances");
  const etat = o => !o.phase ? tx("à commencer") : o.definitif ? tx("terminée définitivement") : o.phase === "envoye" ? tx`terminée · ${o.idees} idée${o.idees > 1 ? "s" : ""}` + (o.essais > 1 ? tx` · ${o.essais} essais` : "") : tx("en cours");
  const action = o => !o.phase ? tx("Commencer") : o.definitif ? tx("Voir la correction") : o.phase === "envoye" ? tx("Revoir et s'améliorer") : tx("Continuer");
  $("#vue").replaceChildren(...[carteCode(), carteHorsLigne(), ...(carteMessages() || []),
    el("p", {class: "muted"}, tx("Choisissez une séance. Sur une séance terminée, vous pouvez reprendre votre travail pour l'améliorer.")),
    ...moi.ouvertes.slice().reverse().map(o => el("div", {class: "card"},
      el("div", {class: "row", style: "justify-content:space-between"}, el("h2", {}, tx`Séance ${o.numero ?? o.seance}`), el("span", {class: "pill " + (o.phase === "envoye" ? "ok" : "")}, etat(o))),
      el("p", {}, o.titre || ""),
      el("div", {class: "row"}, el("button", {class: "primary", onclick: () => choisir(o.seance)}, action(o)), ecoute(o.titre)))),
    carteParcours(), carteAffichage(),
    el("button", {class: "ghost small", onclick: deconnecter}, tx("Changer d'élève sur cet appareil"))].filter(Boolean));
}

let NOUVEAU_CODE = null;
function carteCode() {
  if (!NOUVEAU_CODE) return null;
  return el("div", {class: "notice ok", role: "status"},
    el("p", {style: "font-weight:700"}, tx`Votre code personnel : ${NOUVEAU_CODE}`),
    el("p", {class: "small"}, tx("Notez-le dans votre cahier. Avec votre pseudonyme et ce code, vous retrouverez votre travail sur n'importe quelle tablette.")),
    el("button", {onclick: () => { NOUVEAU_CODE = null; rendre(); }}, tx("C'est noté")));
}
/** Hors ligne (clé USB) : le travail reste sur cet ordinateur jusqu'à ce que l'étudiant l'exporte pour son enseignant. */
function carteHorsLigne() {
  if (!moi?.horsLigne) return null;
  const etat = el("span", {class: "small", "aria-live": "polite"});
  const exporter = async () => {
    try {
      const t = await api("eleve/export", {jeton: session.jeton});
      const nom = `viabilis_${t.classe}_${moi.pseudo.replace(/[^\w-]+/g, "_")}_${t.exporte.slice(0, 10)}.json`;
      const a = el("a", {href: URL.createObjectURL(new Blob([JSON.stringify(t)], {type: "application/json"})), download: nom});
      document.body.append(a); a.click(); a.remove();
      etat.textContent = tx`Fichier ${nom} enregistré dans vos téléchargements : remettez-le à votre enseignant.`;
    } catch (e) { etat.textContent = e.message; }
  };
  return el("div", {class: "notice", role: "note"},
    el("p", {style: "font-weight:700"}, tx("Mode hors ligne")),
    el("p", {class: "small"}, tx("Vous travaillez sur cet ordinateur, sans IA. Votre travail est enregistré ici ; pour que votre enseignant le voie, exportez-le et remettez-lui le fichier (vous pouvez exporter autant de fois que vous voulez : le dernier fichier compte).")),
    el("div", {class: "row"}, el("button", {class: "primary", onclick: exporter}, tx("Exporter mon travail")), etat));
}
function message(titre, texte) {
  $("#titre").textContent = titre;
  $("#vue").replaceChildren(...[carteCode(), el("div", {class: "card"}, el("p", {}, texte))].filter(Boolean));
}

/* ---------------------------------------------------------------- connexion : code de la classe, puis pseudonyme dans la liste */
// la page se recharge dans la langue de la classe : l'étape « code de la classe » est gardée pour ne pas le redemander
function garderClasseEtChangerDeLangue() {
  return adopterLangue(CLASSE.langue, () => { try { sessionStorage.setItem("viabilis-classe", JSON.stringify(CLASSE)); } catch {} });
}
function ecranConnexion() {
  $("#sous-titre").textContent = "";
  const err = el("p", {class: "small", role: "alert"});
  if (!CLASSE && HORS_LIGNE) {
    api("eleve/classe", {methode: "POST", corps: {code: HORS_LIGNE.code}}).then(r => { CLASSE = {...r, code: HORS_LIGNE.code}; if (!garderClasseEtChangerDeLangue()) rendre(); }).catch(e => message(tx("Mode hors ligne"), e.message));
    return message(tx("Mode hors ligne"), tx("Ouverture de la classe…"));
  }
  if (!CLASSE) {
    $("#titre").textContent = tx("Rejoindre la classe");
    const code = el("input", {type: "text", id: "code", maxlength: "6", autocomplete: "off", autocapitalize: "characters", placeholder: tx("Par exemple : K7M2QX")});
    const go = async () => {
      err.textContent = "";
      try { CLASSE = {...await api("eleve/classe", {methode: "POST", corps: {code: code.value}}), code: code.value.trim().toUpperCase()}; if (!garderClasseEtChangerDeLangue()) rendre(); }
      catch (e) { err.textContent = e.message; }
    };
    code.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    $("#vue").replaceChildren(el("div", {class: "card"}, el("div", {class: "field"}, el("label", {for: "code"}, tx("Code de la classe")), code),
      el("button", {class: "primary", onclick: go}, tx("Continuer")), err));
    return;
  }
  $("#titre").textContent = CLASSE.nom;
  const entrer = async (pseudo, pin, nouveau) => {
    err.textContent = "";
    try {
      const r = await api("eleve/connexion", {methode: "POST", corps: {code: CLASSE.code, pseudo, pin, nouveau}});
      session = {jeton: r.jeton, pseudo: r.pseudo}; ecrireSession(session);
      NOUVEAU_CODE = !r.retour && CLASSE.codePersonnel ? r.pin : null;   // le code n'est utile que si l'enseignant l'exige
      CHOIX = null; ecrireChoix(null); CLASSE = null;
      await charger();
    } catch (e) { err.textContent = e.message; }
  };
  let choisi = null;
  const pin = el("input", {type: "text", id: "pin", maxlength: "4", inputmode: "numeric", autocomplete: "off", placeholder: tx("4 chiffres")});
  const zonePin = el("div", {class: "field", hidden: true}, el("label", {for: "pin"}, tx("Votre code personnel")), pin,
    el("button", {class: "primary", onclick: () => entrer(choisi, pin.value, false)}, tx("Entrer")));
  const liste = CLASSE.pseudos.length ? el("div", {class: "pseudos", role: "list"}, CLASSE.pseudos.map(p => el("button", {role: "listitem", onclick: () => {
    if (!CLASSE.codePersonnel) return entrer(p, "", false);
    choisi = p; zonePin.hidden = false; zonePin.querySelector("label").textContent = tx`Code personnel de ${p}`; pin.focus();
  }}, p))) : el("p", {class: "small muted"}, tx("Personne n'a encore rejoint la classe."));
  const nouveau = el("input", {type: "text", id: "pseudo", maxlength: "24", autocomplete: "off", placeholder: tx("Par exemple : Panda 7")});
  $("#vue").replaceChildren(
    el("div", {class: "card"}, el("h2", {}, tx("Qui êtes-vous ?")), el("p", {class: "small muted"}, tx("Touchez votre pseudonyme pour retrouver votre travail.")), liste, zonePin, err),
    el("div", {class: "card"}, el("h2", {}, tx("Première fois ?")),
      el("div", {class: "field"}, el("label", {for: "pseudo"}, tx("Choisissez un pseudonyme")), nouveau,
        el("p", {class: "small muted"}, tx("Pas votre vrai nom : votre enseignant vous reconnaîtra par ce pseudonyme."))),
      el("button", {class: "primary", onclick: () => {
        if (CLASSE.pseudos.some(p => p.toLowerCase() === nouveau.value.trim().toLowerCase())) { err.textContent = tx("Ce pseudonyme existe déjà : si c'est le vôtre, touchez-le dans la liste."); return; }
        entrer(nouveau.value, "", true);
      }}, tx("Créer mon pseudonyme"))),
    ...(HORS_LIGNE ? [] : [el("button", {class: "ghost small", onclick: () => { CLASSE = null; rendre(); }}, tx("Changer de classe"))]));
}

async function sauver() {
  const etat = $("#etat");
  try {
    const r = await api("eleve/seance/" + L.num, {methode: "PUT", jeton: session.jeton, corps: L});
    if (r.ordre) { L.ordre = r.ordre; L.mode = r.mode; }
    if (etat) etat.textContent = tx("Enregistré");
  } catch (e) { if (etat) etat.textContent = e.message; }
}
async function passer(phase) { L.phase = phase; await sauver(); seance(); }
async function reprendre() {
  try { await api("eleve/reprendre" + q(), {methode: "POST", jeton: session.jeton, corps: {}}); }
  catch (e) { const etat = $("#etat"); if (etat) etat.textContent = e.message; return; }
  L = null; EXOS = null; await charger();                // la séance repart de l'état préparé par le serveur
}

/* ---------------------------------------------------------------- fin définitive et correction */
let FIN_DEMANDEE = null, CORRECTION = null;          // séance dont la fin définitive attend confirmation ; correction reçue {num, ...}
async function terminerDefinitivement() {
  const etat = $("#etat");
  if (etat) etat.textContent = tx("Correction en cours…");
  try {
    const r = await api("eleve/terminer" + q(), {methode: "POST", jeton: session.jeton, corps: {}});
    CORRECTION = {...r, num: L.num}; L.definitif = r.definitif; FIN_DEMANDEE = null;
    seance(); window.scrollTo(0, 0);
  } catch (e) { if (etat) etat.textContent = e.message; }
}
const STATUT_IDEE = {juste: ["ok", tx("✓ juste")], a_revoir: ["warn", tx("à revoir")], doublon: ["", tx("déjà trouvée")]};
function carteCorrection() {
  if (!CORRECTION || CORRECTION.num !== L.num) {
    api("eleve/correction" + q(), {jeton: session.jeton}).then(r => { CORRECTION = {...r, num: L.num}; seance(); })
      .catch(e => { const etat = $("#etat"); if (etat) etat.textContent = e.message; });
    return [el("div", {class: "card"}, el("p", {class: "muted"}, tx("Chargement de la correction…")))];
  }
  const C = CORRECTION, cartes = [];
  const v = C.idees;
  cartes.push(el("div", {class: "card"}, el("h2", {}, tx("Vos idées")),
    v ? el("ol", {class: "ideas"}, v.idees.map((t, k) => { const r = v.retours[k] || {}, [cl, lib] = STATUT_IDEE[r.statut] || ["", ""];
          return el("li", {style: "flex-direction:column;align-items:stretch"},
            el("div", {class: "row", style: "justify-content:space-between;align-items:flex-start"}, texteIdee(t), lib ? el("span", {class: "pill " + cl}, lib) : null),
            r.retour && r.statut !== "juste" ? el("p", {class: "small"}, r.retour) : null); }))
      : el("p", {class: "small muted"}, C.message || tx("Pas d'idée à corriger dans cette séance.")),
    v?.bilan ? el("p", {class: "small"}, v.bilan) : null));
  if ((C.exercices || []).length) {
    const justes = C.exercices.filter(x => x.juste).length;
    cartes.push(el("div", {class: "card"}, el("h2", {}, tx`Vos exercices : ${justes} sur ${C.exercices.length} justes`),
      el("ol", {class: "ideas"}, C.exercices.map(x => el("li", {style: "flex-direction:column;align-items:stretch;gap:6px"},
        ...enonce(x.texte),
        el("div", {class: "row", style: "justify-content:space-between;align-items:flex-start"},
          el("p", {class: "small"}, el("b", {}, tx("Votre réponse : ")), x.reponse ?? tx("pas de réponse")),
          el("span", {class: "pill " + (x.juste ? "ok" : x.score > 0 ? "warn" : "ko")}, x.juste ? tx("✓ juste") : x.score > 0 ? tx`partiellement juste (${Math.round(x.score * 100)} %)` : tx("✗ faux"))),
        x.juste ? null : el("p", {class: "small"}, el("b", {}, tx("Bonne réponse : ")), x.attendu || "–"),
        x.retour ? el("p", {class: "small"}, x.retour) : null,
        x.retourGeneral ? el("p", {class: "small muted"}, x.retourGeneral) : null)))));
  }
  return cartes;
}

function seance() {
  const c = moi.config;
  $("#titre").textContent = tx("Séance ") + (c.numero ?? c.seance);
  const blocs = [carteCode(), ...(carteMessages() || [])].filter(Boolean);
  if ((moi.ouvertes || []).length > 1) blocs.push(el("div", {}, el("button", {class: "ghost small", onclick: () => { CHOIX = null; ecrireChoix(null); L = null; rendre(); }}, tx("← Mes séances"))));
  if (c.evaluation && L.phase !== "envoye") blocs.push(el("div", {class: "notice", role: "status"}, el("p", {style: "font-weight:700"}, tx("Évaluation")),
    el("p", {class: "small"}, tx("Sans IA ni coup de pouce. Une seule réponse par exercice ; vos réponses sont enregistrées au fur et à mesure."))));
  if (MESSAGES_GROUPE[moi.groupe] && L.phase !== "envoye" && !c.evaluation) blocs.push(el("div", {class: "notice ok", role: "status"}, el("p", {}, MESSAGES_GROUPE[moi.groupe])));
  if ((L.essais || 1) > 1 && L.phase !== "envoye") blocs.push(el("div", {class: "notice", role: "status"}, el("p", {}, tx`Essai n° ${L.essais} : complétez ou corrigez vos idées, vous pouvez à nouveau les faire vérifier.`)));
  blocs.push(el("div", {class: "card"}, visuels() ? banniere(c.discipline, c.public) : null,
    el("div", {class: "row", style: "justify-content:space-between"}, el("p", {class: "eyebrow"}, tx("La tâche")), ecoute(c.tache)),
    el("p", {style: "white-space:pre-wrap"}, c.tache || tx("(consigne non renseignée)"))));
  if (L.phase === "charge") {
    blocs.push(el("div", {class: "card"}, el("h2", {}, tx("Avant de commencer")),
      echelleUI(tx("Cette tâche me paraît…"), DIFFICULTE(), L.chargeDebut, x => { L.chargeDebut = x; seance(); }),
      el("button", {class: "primary", disabled: L.chargeDebut == null, onclick: async () => {
        L.debut = now();
        if (c.exercices?.actifs && c.exercices.placement === "avant") { L.suite = "tache"; return passer("exercices"); }
        await commencerTache(); }}, tx("Commencer"))));
  } else if (L.phase === "reflexion") {
    blocs.push(carteCoupsDePouce());
    const autonome = L.ordre === "autonomie";
    blocs.push(el("div", {class: "card"},
      titreIdees(autonome ? tx("Aujourd'hui, vous travaillez en autonomie") : tx("D'abord, vos idées"), L.ideesAvant.length),
      el("p", {class: "small muted"}, autonome ? tx("Écrivez vos idées, puis terminez la séance.") : tx`Écrivez au moins ${c.minIdees} idée${c.minIdees > 1 ? "s" : ""} avant d'ouvrir l'IA. Si vous êtes vraiment bloqué, dites-le.`),
      idees(L.ideesAvant, "avant", 0, true), saisieIdee(t => L.ideesAvant.push({t: now(), texte: t})), carteVerif(),
      el("div", {class: "row"},
        autonome ? el("button", {class: "primary", onclick: finirTache}, tx("Terminer"))
          : el("button", {class: "primary", disabled: L.ideesAvant.length < c.minIdees, onclick: () => { L.ideesAvantAide = L.ideesAvant.length; passer("ia"); }}, tx("Ouvrir l'IA")),
        autonome ? null : el("button", {onclick: () => { L.bloque = true; L.ideesAvantAide = L.ideesAvant.length; passer("ia"); }}, tx("Je suis bloqué")))));
  } else if (L.phase === "ia") {
    blocs.push(carteCoupsDePouce());
    blocs.push(el("div", {class: "grid2"}, carteIA(), el("div", {class: "card"},
      titreIdees(tx("Mes idées"), L.ideesAvant.length + L.ideesApres.length),
      L.ideesAvant.length ? el("p", {class: "small muted"}, tx("Avant l'IA :")) : null, idees(L.ideesAvant, "avant", 0, true),
      el("p", {class: "small muted"}, tx("Depuis l'IA :")), idees(L.ideesApres, tx("après"), L.ideesAvant.length, true),
      saisieIdee(t => L.ideesApres.push({t: now(), texte: t})), carteVerif(),
      el("button", {class: "primary", disabled: !(L.ideesAvant.length + L.ideesApres.length), onclick: finirTache}, tx("J'ai terminé")))));
  } else if (L.phase === "exercices") {
    blocs.push(...ecranExercices());
  } else if (L.phase === "fin") {
    blocs.push(el("div", {class: "card"}, el("h2", {}, tx("Pour finir")),
      echelleUI(tx("Finalement, la tâche m'a paru…"), DIFFICULTE(), L.chargeFin, x => { L.chargeFin = x; seance(); }),
      echelleUI(tx("J'ai compris ce qu'il fallait apprendre…"), [["😕", tx("pas du tout")], ["🤔", tx("un peu")], ["😐", tx("moyennement")], ["🙂", tx("bien")], ["😀", tx("très bien")]].map(([e, t]) => img(e, t)), L.compris, x => { L.compris = x; seance(); }),
      el("div", {class: "field", role: "group", "aria-labelledby": "q-aides"}, el("p", {id: "q-aides", style: "font-weight:700"}, tx("Qu'est-ce qui t'a aidé ? (plusieurs choix possibles, facultatif)")),
        el("div", {class: "row"}, AIDES.map(([k, e, t]) => el("button", {"aria-pressed": String((L.aides || []).includes(k)),
          onclick: () => { L.aides = (L.aides || []).includes(k) ? L.aides.filter(x => x !== k) : [...(L.aides || []), k]; seance(); }}, img(e, t))))),
      el("button", {class: "primary", disabled: L.chargeFin == null || L.compris == null, onclick: async () => { L.fin = now(); await passer("envoye"); charger(); }}, tx("Envoyer"))));
  } else if (L.phase === "envoye" && L.definitif) {
    blocs.push(el("div", {class: "notice ok", role: "status"}, el("p", {style: "font-weight:700"}, tx("Séance terminée définitivement")),
      el("p", {class: "small"}, tx("Voici votre correction. Relisez vos erreurs : c'est ainsi qu'on progresse."))));
    blocs.push(...carteCorrection());
  } else if (L.phase === "envoye") {
    blocs.push(el("div", {class: "card"}, visuels() ? el("div", {class: "row", style: "gap:14px"}, bravo(c.public), el("h2", {}, tx("Merci, c'est envoyé")))
      : el("h2", {}, tx("Merci, c'est envoyé")),
      el("p", {}, tx`${L.ideesAvant.length + L.ideesApres.length} idées enregistrées` + ((L.essais || 1) > 1 ? tx` (essai n° ${L.essais}).` : ".")),
      idees([...L.ideesAvant, ...L.ideesApres], "", 0),
      (() => { const p = (moi.parcours || []).find(x => x.seance === L.num); const pr = p && essaisDe(p).progres; return pr ? el("p", {class: "pill ok"}, pr) : null; })(),
      el("p", {class: "small muted"}, tx("Cette séance est encore ouverte : vous pouvez reprendre votre travail pour l'améliorer, en ajoutant des idées, en corrigeant celles à revoir et en refaisant les exercices ratés.")),
      c.evaluation ? null : el("div", {class: "row"}, el("button", {class: "primary", onclick: reprendre}, tx("Reprendre pour m'améliorer"))),
      FIN_DEMANDEE === L.num
        ? el("div", {class: "notice warn", role: "alert"},
            el("p", {style: "font-weight:700"}, tx("Terminer définitivement ?")),
            el("p", {class: "small"}, tx("Vous ne pourrez plus modifier cette séance ni la reprendre. Vous verrez ensuite la correction : vos idées et vos exercices, avec vos erreurs.")),
            el("div", {class: "row"}, el("button", {class: "primary", onclick: terminerDefinitivement}, tx("Oui, terminer et voir la correction")),
              el("button", {class: "ghost", onclick: () => { FIN_DEMANDEE = null; seance(); }}, tx("Annuler"))))
        : el("div", {class: "row"}, el("button", {onclick: () => { FIN_DEMANDEE = L.num; seance(); }}, tx("Terminer définitivement et voir la correction")))));
    const gal = (moi.parcours || []).find(x => x.seance === L.num)?.galerie || [];
    if (gal.length) blocs.push(el("div", {class: "card"}, el("h2", {}, tx("Des idées de la classe")),
      el("p", {class: "small muted"}, tx("Ton enseignant a choisi ces idées, sans les noms. L'une d'elles te donne-t-elle une nouvelle idée ? Tu peux reprendre ta séance pour l'ajouter, avec tes mots.")),
      listeGalerie(gal)));
  }
  blocs.push(el("p", {class: "small muted", id: "etat", "aria-live": "polite"}));
  blocs.push(el("div", {class: "row"}, el("button", {class: "ghost small", "aria-expanded": String(PARCOURS), onclick: () => { PARCOURS = !PARCOURS; seance(); }}, PARCOURS ? tx("Masquer mon parcours") : tx("Mon parcours"))));
  if (PARCOURS) blocs.push(carteParcours());
  blocs.push(carteHorsLigne());
  blocs.push(carteAffichage());
  if (moi.codePersonnel) blocs.push(el("details", {class: "small muted"}, el("summary", {}, tx("Mon code personnel")), el("p", {}, tx`Pseudonyme : ${moi.pseudo} · code : ${moi.pin || "–"}`)));
  blocs.push(el("button", {class: "ghost small", onclick: deconnecter}, tx("Changer d'élève sur cet appareil")));
  $("#vue").replaceChildren(...blocs.filter(Boolean));    // une carte absente (pas de coup de pouce…) n'est pas affichée
  if (focusIdee) { focusIdee = false; $("textarea[data-nouvelle]")?.focus(); }
}
const DIFFICULTE = () => [["😀", tx("très facile")], ["🙂", tx("facile")], ["😐", tx("moyenne")], ["😟", tx("difficile")], ["😣", tx("très difficile")]].map(([e, t]) => img(e, t));
/* ---------------------------------------------------------------- coups de pouce gradués */
function carteCoupsDePouce() {
  const cp = moi.coupsDePouce || {total: 0, vus: []};
  if (!cp.total || moi.config.evaluation) return null;
  const reste = cp.total - cp.vus.length;
  const etat = el("p", {class: "small", "aria-live": "polite"});
  const b = el("button", {disabled: !reste, onclick: async () => {
    b.disabled = true;
    try {
      if (L.ideesAvantAide == null) L.ideesAvantAide = L.ideesAvant.length + L.ideesApres.length;   // un coup de pouce est une aide
      await sauver();
      const r = await api("eleve/indice" + q(), {methode: "POST", jeton: session.jeton, corps: {}});
      moi.coupsDePouce = r; seance();
    } catch (e) { etat.textContent = e.message; b.disabled = false; }
  }}, reste ? tx`Voir un coup de pouce (${cp.vus.length + 1} sur ${cp.total})` : tx("Tous les coups de pouce sont affichés"));
  return el("div", {class: "card"},
    el("div", {class: "row", style: "justify-content:space-between"}, el("h2", {}, tx("Besoin d'un coup de pouce ?")), b),
    cp.vus.length ? el("ol", {class: "ideas"}, cp.vus.map(t => el("li", {style: "align-items:center"}, el("span", {}, t), ecoute(t)))) :
      el("p", {class: "small muted"}, tx("Cherchez d'abord seul. Si vous bloquez, ouvrez un coup de pouce : ils vont du plus léger au plus précis.")),
    etat);
}

/* ---------------------------------------------------------------- vérification des idées */
let VERIF = null;            // dernier retour reçu pour la séance en cours : {num, idees, retours, bilan, restantes}
const ICONE = {juste: tx("✓ juste"), a_revoir: tx("à revoir"), doublon: tx("déjà trouvée")};
let EDITION = null;          // idée en cours de modification ou de retrait : {liste, k, retrait}
function idees(liste, tag, decalage, modifiable = false) {
  if (!liste.length) return el("p", {class: "small muted"}, tx("Aucune idée pour l'instant."));
  const v = VERIF && VERIF.num === L.num ? VERIF : null;
  return el("ol", {class: "ideas"}, liste.map((i, k) => {
    const pos = !v ? -1 : v.idees[decalage + k] === i.texte ? decalage + k : v.idees.indexOf(i.texte);   // même position qu'au serveur
    const r = pos >= 0 ? v.retours[pos] : null;
    const ici = modifiable && EDITION && EDITION.liste === liste && EDITION.k === k;
    if (ici && !EDITION.retrait) return el("li", {style: "flex-direction:column;align-items:stretch"}, editeurIdee(liste, k));
    return el("li", {style: "flex-direction:column;align-items:stretch"},
      el("div", {class: "row", style: "justify-content:space-between;align-items:flex-start"}, texteIdee(i.texte),
        el("span", {class: "tag"}, r ? el("span", {class: "pill " + (r.statut === "juste" ? "ok" : r.statut === "doublon" ? "" : "warn")}, ICONE[r.statut]) : (i.modifiee ? tx`${tag} · modifiée` : tag))),
      r && r.statut !== "juste" ? el("div", {class: "row", style: "justify-content:space-between"}, el("p", {class: "small"}, r.retour), ecoute(r.retour)) : null,
      !modifiable ? null : ici
        ? el("div", {class: "row"}, el("span", {class: "small"}, tx("Retirer cette idée ?")),
            el("button", {class: "danger small", onclick: () => retirerIdee(liste, k)}, tx("Retirer")),
            el("button", {class: "ghost small", onclick: () => { EDITION = null; seance(); }}, tx("Annuler")))
        : el("div", {class: "row"},
            el("button", {class: "ghost small", onclick: () => { EDITION = {liste, k}; seance(); }}, tx("Modifier")),
            el("button", {class: "ghost small", onclick: () => { EDITION = {liste, k, retrait: true}; seance(); }}, tx("Retirer"))));
  }));
}
/** Modifier une idée : l'ancienne version est gardée dans la trace (i.avant), pour l'enseignant et la recherche. */
function editeurIdee(liste, k) {
  const i = liste[k], code = !!moi?.config?.saisieCode;
  const ta = el("textarea", {rows: code ? "12" : moi?.config?.public === "superieur" ? "5" : "2", class: code ? "code" : "", spellcheck: code ? "false" : "true",
    "aria-label": tx("Modifier l'idée")});
  ta.value = i.texte;
  const garder = () => {
    const t = code ? ta.value.replace(/\s+$/, "").slice(0, 4000) : ta.value.trim().slice(0, 1500);
    if (!t.trim() || t === i.texte) { EDITION = null; return seance(); }
    i.avant = [...(i.avant || []), {texte: i.texte, t: i.modifiee || i.t}].slice(-10);
    i.texte = t; i.modifiee = now();
    EDITION = null; seance(); sauver();
  };
  if (code) ta.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); garder(); return; }
    if (e.key === "Tab" && !e.shiftKey) { e.preventDefault(); const a = ta.selectionStart, b = ta.selectionEnd; ta.value = ta.value.slice(0, a) + "    " + ta.value.slice(b); ta.selectionStart = ta.selectionEnd = a + 4; }
  });
  setTimeout(() => ta.focus(), 0);
  return el("div", {class: "field"}, ta, el("div", {class: "row"},
    el("button", {class: "primary small", onclick: garder}, tx("Enregistrer la modification")),
    el("button", {class: "ghost small", onclick: () => { EDITION = null; seance(); }}, tx("Annuler"))),
    el("p", {class: "small muted"}, tx("Une idée modifiée devra être vérifiée à nouveau.")));
}
/** Retirer une idée : elle quitte la liste mais reste dans la trace (ideesRetirees). */
function retirerIdee(liste, k) {
  const [i] = liste.splice(k, 1);
  L.ideesRetirees = [...(L.ideesRetirees || []), {...i, retiree: now(), depuis: liste === L.ideesApres ? "apres" : "avant"}];
  EDITION = null; seance(); sauver();
}
function carteVerif() {
  const v = moi.config.verification;
  if (!v || v.mode === "aucune" || moi.config.evaluation || L.ordre === "autonomie" && v.mode === "ia") return null;
  const n = L.ideesAvant.length + L.ideesApres.length;
  const restantes = VERIF && VERIF.num === L.num ? VERIF.restantes : null;
  const etat = el("p", {class: "small", "aria-live": "polite"}, VERIF && VERIF.num === L.num ? VERIF.bilan : "");
  const essai = L.essais || 1, dejaDit = (L.demarches || []).some(d => d.essai === essai);
  const verifier = async () => {
    b.disabled = true; etat.textContent = tx("Vérification…");
    try {
      await sauver();
      const r = await api("eleve/verifier" + q(), {methode: "POST", jeton: session.jeton, corps: {}});
      VERIF = {...r, num: L.num}; seance();
    } catch (e) { etat.textContent = e.message; b.disabled = false; }
  };
  // avant la première vérification de chaque essai : « Comment as-tu cherché ? » (une touche suffit)
  const b = el("button", {disabled: !n || restantes === 0, onclick: () => { if (dejaDit) return verifier(); DEMARCHE = {essai, choix: null, texte: ""}; seance(); }}, tx("Vérifier mes idées"));
  const conseil = VERIF && VERIF.num === L.num && VERIF.conseil;
  const demande = DEMARCHE && DEMARCHE.essai === essai && !dejaDit ? (() => {
    const precision = el("input", {type: "text", maxlength: "300", placeholder: tx("Si tu veux, explique en quelques mots"), "aria-label": tx("Ma façon de chercher")});
    precision.value = DEMARCHE.texte; precision.addEventListener("input", () => { DEMARCHE.texte = precision.value; });
    return el("div", {class: "field", role: "group", "aria-labelledby": "q-demarche"},
      el("p", {id: "q-demarche", style: "font-weight:700"}, tx("Avant de vérifier : comment as-tu cherché ?")),
      el("div", {class: "field"}, DEMARCHES.map(([k, e, t]) => el("button", {"aria-pressed": String(DEMARCHE.choix === k), style: "text-align:left", onclick: () => { DEMARCHE.choix = k; seance(); }}, img(e, t)))),
      el("div", {class: "row"}, precision, dictee(precision)),
      el("button", {class: "primary", disabled: !DEMARCHE.choix, onclick: () => { L.demarches = [...(L.demarches || []), {...DEMARCHE}]; DEMARCHE = null; verifier(); }}, tx("Vérifier maintenant")));
  })() : null;
  return el("div", {class: "notice"}, el("div", {class: "row", style: "justify-content:space-between"}, demande ? null : b,
    el("span", {class: "small muted"}, restantes == null ? tx`${v.maximum} vérification${v.maximum > 1 ? "s" : ""} possible${v.maximum > 1 ? "s" : ""}` : tx`${restantes} vérification${restantes > 1 ? "s" : ""} restante${restantes > 1 ? "s" : ""}`)),
    demande, etat,
    conseil ? el("div", {class: "row", style: "justify-content:space-between;align-items:flex-start"}, el("p", {}, el("b", {}, tx("💡 Pour chercher : ")), conseil), ecoute(conseil)) : null);
}

async function commencerTache() {
  L.phase = "reflexion"; await sauver();                         // le serveur fixe l'ordre et le rôle de l'IA
  if (L.ordre === "ia") { L.ideesAvantAide = 0; L.phase = "ia"; await sauver(); }
  seance();
}
function finirTache() {
  const ex = moi.config.exercices;
  if (ex?.actifs && ex.placement === "apres") { L.suite = "fin"; return passer("exercices"); }
  passer("fin");
}

/* ---------------------------------------------------------------- exercices */
let EXOS = null, chargementExos = false;
const fini = x => moi?.config?.evaluation ? x.tentatives >= 1 : x.tentatives >= 2 || (x.score != null && x.score >= 1);
async function chargerExos() {
  if (chargementExos) return; chargementExos = true;
  try { EXOS = (await api("eleve/exercices" + q(), {jeton: session.jeton})).map(x => ({...x, t0: Date.now()})); }
  catch (e) { EXOS = []; }
  EXOS.seance = L.num; chargementExos = false; seance();
}
function ecranExercices() {
  if (!EXOS || EXOS.seance !== L.num) {
    if (!chargementExos) chargerExos();
    return [el("div", {class: "card"}, el("p", {class: "muted"}, tx("Chargement des exercices…")))];
  }
  const tous = EXOS.every(fini);
  const suite = async () => { if (L.suite === "tache") { L.suite = null; await commencerTache(); } else { L.suite = null; passer("fin"); } };
  return [el("div", {class: "card"}, el("h2", {}, tx("Exercices")),
      el("p", {class: "small muted"}, !EXOS.length ? tx("Pas d'exercice pour cette séance.") : moi.config.evaluation
        ? tx("Évaluation : une seule réponse par exercice, vérifiez avant de valider. Les corrections vous seront données par votre enseignant.") : tx("Deux essais par exercice. Prenez le temps de réfléchir."))),
    ...EXOS.map((x, i) => carteExo(x, i)),
    el("button", {class: "primary", disabled: !tous, onclick: suite}, tous ? tx("Continuer") : tx("Terminez les exercices pour continuer"))];
}
/** Énoncé d'exercice : la question, puis le programme éventuel (lignes suivantes) en police à chasse fixe. */
function enonce(t) {
  const i = String(t).indexOf("\n");
  if (i < 0) return [el("p", {style: "white-space:pre-wrap"}, t)];
  return [el("p", {}, t.slice(0, i)), el("pre", {class: "code", style: "background:var(--soft);padding:10px 12px;border-radius:10px"}, t.slice(i + 1))];
}
function carteExo(x, i) {
  const fin = fini(x);
  const champs = [];
  const nom = "exo" + x.id;
  if (x.type === "choix_unique" || x.type === "choix_multiple") {
    const multi = x.type === "choix_multiple";
    x.saisie ??= multi ? [] : null;
    champs.push(el("div", {class: "field", role: multi ? "group" : "radiogroup", "aria-label": tx("Choix")}, x.choix.map(ch => {
      const coche = multi ? x.saisie.includes(ch.id) : x.saisie === ch.id;
      const inp = el("input", {type: multi ? "checkbox" : "radio", name: nom, id: `${nom}-${ch.id}`, checked: coche, disabled: fin});
      inp.addEventListener("change", () => { if (multi) { x.saisie = inp.checked ? [...x.saisie, ch.id] : x.saisie.filter(v => v !== ch.id); } else x.saisie = ch.id; });
      return el("label", {for: `${nom}-${ch.id}`, class: "row", style: "font-weight:600;gap:8px;padding:8px 10px;border:1px solid var(--line);border-radius:10px"}, inp, ch.texte);
    })));
  } else if (x.type === "vrai_faux") {
    champs.push(el("div", {class: "row"}, ["vrai", "faux"].map(v => el("button", {"aria-pressed": String(x.saisie === v), disabled: fin, onclick: () => { x.saisie = v; seance(); }}, v === "vrai" ? tx("Vrai") : tx("Faux")))));
  } else if (x.type === "reponse_courte" || x.type === "numerique") {
    const inp = el("input", {type: "text", id: nom, inputmode: x.type === "numerique" ? "decimal" : "text", autocomplete: "off", disabled: fin, "aria-label": tx("Votre réponse")});
    inp.value = x.saisie ?? ""; inp.addEventListener("input", () => { x.saisie = inp.value; });
    champs.push(inp);
  } else if (x.type === "appariement") {
    x.saisie ??= {};
    champs.push(el("div", {class: "field"}, x.gauches.map((g, k) => {
      const sel = el("select", {id: `${nom}-${k}`, disabled: fin}, el("option", {value: ""}, tx("Choisir…")), x.droites.map(d => el("option", {value: d, selected: x.saisie[g] === d}, d)));
      sel.addEventListener("change", () => { x.saisie[g] = sel.value; });
      return el("div", {class: "row", style: "justify-content:space-between"}, el("label", {for: `${nom}-${k}`}, g), el("div", {style: "min-width:160px"}, sel));
    })));
  }
  const res = x.resultat;
  const retour = res?.enregistre || (fin && moi.config.evaluation) ? el("p", {class: "small muted", role: "status"}, tx("Réponse enregistrée."))
    : res ? el("div", {class: "notice " + (res.juste ? "ok" : res.fini ? "ko" : "warn"), role: "status"},
    el("p", {style: "font-weight:700"}, res.juste ? tx("Juste !") : res.score > 0 ? tx`Partiellement juste (${Math.round(res.score * 100)} %)` : res.fini ? tx("Ce n'est pas la bonne réponse.") : tx("Pas encore : réessayez une fois.")),
    res.retour ? el("p", {class: "small"}, res.retour) : null,
    res.attendu ? el("p", {class: "small"}, tx("Réponse attendue : ") + res.attendu) : null,
    res.retourGeneral ? el("p", {class: "small muted"}, res.retourGeneral) : null)
    : fin ? el("p", {class: "small muted"}, x.score >= 1 ? tx("Réussi.") : tx("Terminé.")) : null;
  const valider = el("button", {class: "primary", disabled: fin, onclick: async () => {
    valider.disabled = true;
    try {
      const r = await api(`eleve/exercices/${x.id}/reponse` + q(), {methode: "POST", jeton: session.jeton, corps: {reponse: x.saisie, duree: Math.round((Date.now() - x.t0) / 1000)}});
      x.resultat = r; x.tentatives = r.tentatives; x.score = Math.max(x.score ?? 0, r.score); x.t0 = Date.now();
    } catch (e) { x.resultat = {juste: false, fini: false, score: 0, retour: e.message}; }
    seance();
  }}, tx("Valider"));
  const aLire = () => [x.texte, ...(x.choix || []).map((ch, k) => tx`Choix ${k + 1} : ${ch.texte}`), ...(x.gauches || [])].join(". ");
  return el("div", {class: "card"}, el("div", {class: "row", style: "justify-content:space-between"}, el("p", {class: "eyebrow"}, tx`Exercice ${i + 1}`), ecoute(aLire)),
    ...enonce(x.texte), ...champs, retour, fin ? null : el("div", {class: "row"}, valider));
}

function saisieIdee(ajouter) {
  if (moi?.config?.saisieCode) return saisieCode(ajouter);
  const sup = moi?.config?.public === "superieur";        // dans le supérieur, une idée peut être une démonstration
  const ta = el("textarea", {rows: sup ? "5" : "2", placeholder: sup ? tx("Une idée par envoi, avec sa justification") : tx("Une idée par envoi"), "aria-label": tx("Nouvelle idée"), "data-nouvelle": true});
  const go = () => { const t = ta.value.trim(); if (!t) return; ajouter(t.slice(0, 1500)); focusIdee = true; seance(); sauver(); };
  ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); } });
  return el("div", {class: "field"}, ta, el("div", {class: "row"}, el("button", {onclick: go}, tx("Ajouter l'idée")), dictee(ta)));
}
/** Saisie d'un programme : police à chasse fixe, Tab indente, Entrée passe à la ligne, Ctrl+Entrée (ou ⌘+Entrée) ajoute l'idée. */
function saisieCode(ajouter) {
  const ta = el("textarea", {rows: "12", class: "code", spellcheck: "false", autocapitalize: "off", autocomplete: "off",
    placeholder: tx("Colle ton programme, testé, avec sa sortie en commentaire (# …).\nCtrl+Entrée ou le bouton pour l'ajouter."), "aria-label": tx("Nouvelle idée"), "data-nouvelle": true});
  const go = () => { const t = ta.value.replace(/\s+$/, ""); if (!t.trim()) return; ajouter(t.slice(0, 4000)); focusIdee = true; seance(); sauver(); };
  ta.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); go(); return; }
    if (e.key === "Tab" && !e.shiftKey) {                       // indentation de 4 espaces, comme en Python
      e.preventDefault();
      const a = ta.selectionStart, b = ta.selectionEnd;
      ta.value = ta.value.slice(0, a) + "    " + ta.value.slice(b); ta.selectionStart = ta.selectionEnd = a + 4;
    }
  });
  return el("div", {class: "field"}, ta, el("div", {class: "row"}, el("button", {onclick: go}, tx("Ajouter le programme")),
    el("span", {class: "small muted"}, tx("Tab : indenter · Ctrl+Entrée : ajouter"))));
}
function carteIA() {
  const mode = L.mode || "questionner";
  const zone = el("div", {class: "chat", "aria-live": "polite"}, L.echanges.map(e => el("div", {class: "msg " + (e.role === "ia" ? "ia" : "el")}, e.texte)));
  const ta = el("textarea", {rows: "2", placeholder: mode === "questionner" ? tx("Expliquez votre idée ou votre difficulté") : tx("Posez votre question"), "aria-label": tx("Message à l'IA")});
  const envoyer = el("button", {class: "primary"}, tx("Envoyer"));
  envoyer.onclick = async () => {
    const msg = ta.value.trim(); if (!msg) return;
    if (L.premiereDemande == null) { L.premiereDemande = Math.round((Date.now() - Date.parse(L.debut)) / 1000); if (L.ideesAvantAide == null) L.ideesAvantAide = L.ideesAvant.length; }
    L.echanges.push({role: "el", texte: msg.slice(0, 1000), t: now()}); ta.value = "";
    const bulle = el("div", {class: "msg ia"}, tx("Réflexion…"));
    zone.append(el("div", {class: "msg el"}, msg), bulle); zone.scrollTop = zone.scrollHeight;
    envoyer.disabled = true;
    try {
      await sauver();
      const r = await api("eleve/ia" + q(), {methode: "POST", jeton: session.jeton, corps: {echanges: L.echanges}});
      L.echanges.push({role: "ia", texte: r.texte, t: now()}); bulle.textContent = r.texte; await sauver();
    } catch (e) { bulle.textContent = e.message; }
    finally { envoyer.disabled = false; zone.scrollTop = zone.scrollHeight; }
  };
  return el("div", {class: "card"}, el("h2", {}, mode === "questionner" ? tx("L'IA vous pose des questions") : tx("L'IA vous donne un coup de pouce")),
    el("p", {class: "small muted"}, NOM_MODE[mode] + (mode === "questionner" ? tx(" : elle ne donne pas de réponse.") : tx(" : un élément à la fois, à vous de continuer."))),
    zone, ta, el("div", {class: "row"}, envoyer, dictee(ta), ecoute(() => [...L.echanges].reverse().find(e => e.role === "ia")?.texte || tx("L'IA n'a pas encore répondu."), tx("Écouter la dernière réponse"))));
}

// démarrage + rafraîchissement doux (la séance peut être ouverte ou réglée pendant que l'élève attend)
function redessinerSansPerdreLaSaisie() {
  const saisie = document.querySelector("textarea[data-nouvelle]")?.value;
  seance();
  const ta = document.querySelector("textarea[data-nouvelle]"); if (ta && saisie) ta.value = saisie;
}
if ("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged", () => { if (L && moi) redessinerSansPerdreLaSaisie(); });   // les voix arrivent après le chargement
let HORS_LIGNE = null;       // {code, nom} quand Viabilis tourne sur l'ordinateur de l'étudiant (clé USB)
session = lireSession();
CHOIX = lireChoix();
try { CLASSE = JSON.parse(sessionStorage.getItem("viabilis-classe")); sessionStorage.removeItem("viabilis-classe"); } catch {}
api("hors-ligne").then(d => { HORS_LIGNE = d; if (!session) rendre(); }).catch(() => {});
if (session) charger(); else rendre();
setInterval(async () => {
  if (!session || !moi) return;
  if (!L) return charger();                              // liste des séances ou attente : on rafraîchit
  // dans une séance : on ne redessine que si quelque chose de visible a changé (sans perdre la saisie en cours)
  try {
    const neuf = await api("eleve/moi?seance=" + L.num, {jeton: session.jeton});
    const cle = m => JSON.stringify([m.config.verification, m.config.ouverte, (m.ouvertes || []).map(o => o.seance), (m.messages || []).map(x => x.id)]);
    const change = cle(moi) !== cle(neuf);
    moi = {...neuf};
    if (change) {
      const saisie = document.querySelector("textarea[data-nouvelle]")?.value;
      if (!neuf.config.ouverte) { L = null; CHOIX = null; ecrireChoix(null); rendre(); } else seance();
      const ta = document.querySelector("textarea[data-nouvelle]"); if (ta && saisie) ta.value = saisie;
    }
  } catch {}
}, 15000);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("../sw.js", {scope: "../"}).catch(() => {});
