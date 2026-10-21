// Viabilis classe — propositions de séances suivantes, d'après la séance précédente et les résultats de chaque élève.
import {tx} from "./langues.js";
import {etatEleve, groupeSuggere, numeroSeance, niveauEffectif, ATTENDU_MAX_SEANCE} from "./etat.js";

export const GENRES = {
  consolider: {nom: tx("Consolider"), aide: tx("une tâche voisine, plus accessible")},
  prolonger: {nom: tx("Prolonger"), aide: tx("la suite logique, de difficulté proche")},
  approfondir: {nom: tx("Approfondir"), aide: tx("une tâche plus exigeante")},
  varier: {nom: tx("Varier"), aide: tx("une autre discipline, avec la même démarche de recherche")},
};
export const PROFILS = {difficulte: tx("en difficulté"), attendu: tx("au niveau attendu"), aise: tx("à l'aise"), absent: tx("pas de trace")};

/** Le modèle d'origine de la séance n : celui qui a été enregistré, sinon celui dont on reconnaît la consigne. */
export function modeleDeSeance(modeles, cfg, n) {
  if ((cfg.supprimees || []).includes(n)) return null;
  const a = (cfg.archives || {})[n] || (n === cfg.seance ? cfg : null);
  if (!a) return null;
  return modeles.find(m => m.id === a.modele) || modeles.find(m => m.tache === a.tache) || null;
}

/** Bilan de chaque élève sur la séance n, et ce qu'on lui propose pour la suivante (groupe, variante). */
export function bilanEleves(cfg, traces, notes, viab, n) {
  const tache = (cfg.archives || {})[n] || cfg;
  // nombre de solutions à trouver dans la variante de l'élève (comme le serveur : sinon celui de la tâche standard)
  const attenduDe = s => { const x = s?.variante && s.variante !== "standard" ? tache.variantes?.[s.variante]?.attendu : null; return (x ?? tache.verification?.attendu) || 0; };
  return Object.keys(traces).map(uid => {
    const s = traces[uid].seances?.[n], e = etatEleve(traces, notes, uid)?.etat || {}, attendu = attenduDe(s);
    const g = groupeSuggere(e, viab?.[uid], cfg);
    const v = s?.verification, reussite = v?.idees?.length ? v.justes / v.idees.length : null;
    const exos = (s?.exercices || []).filter(x => x.score != null), exo = exos.length ? exos.reduce((a, x) => a + x.score, 0) / exos.length : null;
    const completude = attendu && v ? Math.min(1, v.justes / Math.min(attendu, ATTENDU_MAX_SEANCE)) : null;
    // avec un nombre de solutions connu, on juge ce qui a été trouvé, pas les essais ratés en chemin
    const faible = (completude != null ? completude < 0.5 : reussite != null && reussite < 0.5) || (exo != null && exo < 0.5);
    let profil, raison = g.raison;
    if (!s) { profil = "absent"; raison = tx`n'a pas travaillé la séance ${numeroSeance(cfg, n)}`; }
    else if (g.groupe === "atelier" || faible) profil = "difficulte";
    else if (g.groupe === "defi" && (completude != null ? completude >= 0.6 : reussite == null || reussite >= 0.75)) profil = "aise";
    else profil = "attendu";
    if (s && reussite != null) raison += tx`, ${Math.round(100 * reussite)} % d'idées justes`;
    if (s && completude != null) raison += tx`, ${v.justes} solution${v.justes > 1 ? "s" : ""} sur ${attendu}`;
    if (s && exo != null) raison += tx`, exercices réussis à ${Math.round(100 * exo)} %`;
    const groupe = profil === "difficulte" ? (g.groupe === "atelier" ? "atelier" : "accompagne") : profil === "aise" ? "defi" : "accompagne";
    const variante = profil === "difficulte" ? "accessible" : profil === "aise" ? "exigeante" : "standard";
    // palier : niveau effectif réussi à cette séance ; la variante exigeante ne s'appliquera que si la tâche suivante reste à ce niveau
    return {uid, pseudo: traces[uid].pseudo, profil, groupe, variante, raison, fini: s?.phase === "envoye", D: e.D,
            palier: variante === "exigeante" && s ? niveauEffectif(cfg, n, s.variante) : null};
  }).sort((a, b) => a.pseudo.localeCompare(b.pseudo));
}

/** Quatre propositions au plus (consolider, prolonger, approfondir, et varier en classe polyvalente seulement), dont une conseillée selon la classe. */
export function proposerSuites(modeles, cfg, traces, notes, viab) {
  // la séance précédente = la plus récente qui existe encore (une séance effacée ne compte pas)
  const effacees = cfg.supprimees || [];
  let n = cfg.seance;
  while (n > 0 && effacees.includes(n)) n--;
  const prec = modeleDeSeance(modeles, cfg, n);
  const faits = new Map();                                   // modèle -> séance où il a déjà été fait
  for (let k = 1; k <= n; k++) { const m = modeleDeSeance(modeles, cfg, k); if (m && !faits.has(m.id)) faits.set(m.id, k); }
  const eleves = bilanEleves(cfg, traces, notes, viab, n);
  const actifs = eleves.filter(x => x.profil !== "absent");
  const nb = p => actifs.filter(x => x.profil === p).length;
  const Ds = actifs.map(x => x.D).filter(x => x != null), Dm = Ds.length ? Ds.reduce((a, x) => a + x, 0) / Ds.length : null;
  const conseil = !actifs.length ? "prolonger" : nb("difficulte") / actifs.length >= 0.4 ? "consolider" : nb("aise") / actifs.length >= 0.5 ? "approfondir" : "prolonger";
  const niv = prec?.niveauTache ?? cfg.niveauTache ?? 3;
  const pris = new Set(prec ? [prec.id] : []);
  const usage = d => [...faits.keys()].filter(id => modeles.find(x => x.id === id)?.discipline === d).length;
  // les suites déclarées par le modèle précédent sont réservées à leur rôle : un choix de repli ne les prend pas
  const declarees = new Set(Object.values(prec?.suites || {}).filter(Boolean));
  const choisir = (id, filtre, cible, tri = () => 0) => {
    let m = id && !pris.has(id) ? modeles.find(x => x.id === id) : null;
    if (!m) m = modeles.filter(x => !pris.has(x.id) && !declarees.has(x.id) && filtre(x))
      .sort((a, b) => tri(a, b) || (faits.has(a.id) - faits.has(b.id)) || Math.abs(a.niveauTache - cible) - Math.abs(b.niveauTache - cible))[0] || null;
    if (m) pris.add(m.id);
    return m;
  };
  // une classe suit sa discipline (choisie, ou celle de ses séances) : aucune proposition n'en sort, sauf en classe polyvalente
  const restreinte = cfg.discipline !== "*" && (cfg.disciplineClasse != null || cfg.public === "superieur");
  const discipline = cfg.disciplineClasse ?? prec?.discipline ?? (restreinte ? modeles.find(x => faits.has(x.id))?.discipline : null);
  const meme = x => !discipline || x.discipline === discipline;
  const pct = p => actifs.length ? tx`${nb(p)} élève${nb(p) > 1 ? "s" : ""} sur ${actifs.length}` : "";
  const titre = prec ? `« ${prec.titre} »` : tx`la séance ${numeroSeance(cfg, n)}`;
  const raisons = {
    consolider: actifs.length ? tx`${pct("difficulte")} en difficulté à ${titre}.` : tx`Pour revenir sur ${titre} sous un autre angle.`,
    prolonger: tx`La suite logique de ${titre}` + (actifs.length ? tx` ; ${pct("attendu")} au niveau attendu.` : "."),
    approfondir: actifs.length ? tx`${pct("aise")} à l'aise à ${titre}.` : tx`Pour aller plus loin que ${titre}.`,
    varier: Dm != null && Dm < 0.35 ? tx`Pensée divergente de la classe basse (moyenne ${Dm.toFixed(2).replace(".", ",")}) : un autre domaine peut relancer les idées.` : tx("Changer de discipline en gardant la même démarche : chercher plusieurs idées, les vérifier."),
  };
  const propositions = [];
  const ajouter = (genre, m) => { if (m) propositions.push({genre, modele: m, raison: raisons[genre], conseille: genre === conseil, dejaFaite: faits.get(m.id) ?? null}); };
  ajouter("consolider", choisir(prec?.suites?.consolider, x => meme(x) && x.niveauTache <= niv, niv - 1));
  ajouter("prolonger", choisir(prec?.suites?.prolonger, meme, niv));
  ajouter("approfondir", choisir(prec?.suites?.approfondir, x => meme(x) && x.niveauTache >= niv, niv + 1));
  if (!restreinte) ajouter("varier", choisir(null, x => !prec || x.discipline !== prec.discipline, niv, (a, b) => usage(a.discipline) - usage(b.discipline)));
  if (!propositions.some(p => p.conseille) && propositions.length) propositions[0].conseille = true;
  return {n, prec, eleves, conseil, propositions, Dm,
    resume: {difficulte: nb("difficulte"), attendu: nb("attendu"), aise: nb("aise"), absent: eleves.length - actifs.length},
    aReprendre: actifs.filter(x => x.profil === "difficulte" || !x.fini)};
}
