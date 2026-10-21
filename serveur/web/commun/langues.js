// Viabilis — langue de l'interface : français (langue du code), anglais, catalan.
// Les textes sont écrits en français dans le code et passent par tx :
//   tx("Texte")                 un texte simple
//   tx`Séance ${n} ouverte`     un gabarit : la clé est « Séance {} ouverte » ; la traduction place les valeurs avec {0}, {1}…
// Dans une traduction, {0|idea|ideas} choisit le singulier ou le pluriel selon la valeur 0 (un nombre, ou "s"/"" en français).
// Les consignes, les modèles de séances et les exercices ne sont pas traduits : ils restent ceux de l'enseignant.
import TRADUCTIONS from "./traductions.js";

export const LANGUES = {fr: "Français", en: "English", ca: "Català"};
const RANG = {en: 0, ca: 1};
const POUR_LES_DATES = {fr: "fr-FR", en: "en-GB", ca: "ca-ES"};
// élève et enseignant gardent chacun leur langue, même sur le même navigateur
const CLE = location.pathname.includes("/enseignant") ? "viabilis-langue-enseignant" : "viabilis-langue-eleve";

function langueDeDepart() {
  try { const l = localStorage.getItem(CLE); if (LANGUES[l]) return l; } catch {}
  const n = (navigator.language || "fr").slice(0, 2).toLowerCase();
  return LANGUES[n] ? n : "fr";
}
export const LANGUE = langueDeDepart();
export const LOCALE = POUR_LES_DATES[LANGUE];
document.documentElement.lang = LANGUE;

function remplir(modele, valeurs) {
  return modele.replace(/\{(\d+)(?:\|([^|}]*)\|([^}]*))?\}/g, (_, k, un, plusieurs) => {
    const v = valeurs[+k];
    if (un === undefined) return v == null ? "" : String(v);
    const nombre = typeof v === "number" ? v : /^\d+$/.test(String(v)) ? Number(v) : null;
    return (nombre != null ? nombre !== 1 : v !== "" && v != null && v !== false) ? plusieurs : un;
  });
}

/** Traduit un texte de l'interface (voir l'en-tête). Un texte inconnu reste en français. */
export function tx(textes, ...valeurs) {
  if (Array.isArray(textes) && textes.raw) {
    const trad = LANGUE !== "fr" && TRADUCTIONS[textes.join("{}")];
    if (trad) return remplir(trad[RANG[LANGUE]], valeurs);
    return textes.reduce((s, t, i) => s + (valeurs[i - 1] == null ? "" : String(valeurs[i - 1])) + t);
  }
  if (LANGUE === "fr" || typeof textes !== "string") return textes;
  const trad = TRADUCTIONS[textes];
  return trad ? trad[RANG[LANGUE]] : textes;
}

/** Adopte la langue choisie (par l'enseignant pour la classe, ou pour sa propre page).
    Renvoie vrai si la page se recharge pour l'afficher ; avantRechargement garde ce qui doit survivre. */
export function adopterLangue(l, avantRechargement) {
  if (!LANGUES[l]) return false;
  try { localStorage.setItem(CLE, l); } catch { return false; }        // sans stockage, pas de rechargement en boucle
  if (l === LANGUE) return false;
  if (avantRechargement) avantRechargement();
  location.reload();
  return true;
}

/** Menu de choix de la langue de la page (page enseignant). */
export function menuLangue() {
  const s = document.createElement("select");
  s.setAttribute("aria-label", tx("Langue de l'interface"));
  s.className = "langue";
  for (const [code, nom] of Object.entries(LANGUES)) {
    const o = document.createElement("option"); o.value = code; o.textContent = nom; o.selected = code === LANGUE; s.append(o);
  }
  s.addEventListener("change", () => adopterLangue(s.value));
  return s;
}

// textes fixes des pages HTML (titre, en-tête, onglets)
function traduirePage() {
  if (LANGUE === "fr") return;
  document.title = tx(document.title);
  const parcours = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = parcours.nextNode(); n; n = parcours.nextNode()) {
    const t = n.nodeValue.trim();
    if (t && TRADUCTIONS[t]) n.nodeValue = n.nodeValue.replace(t, tx(t));
  }
}
traduirePage();
