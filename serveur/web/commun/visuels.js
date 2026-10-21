// Viabilis — illustrations de la page élève, adaptées à la discipline et au niveau de la classe.
// Dessins en SVG écrits ici (aucune image extérieure) ; leurs couleurs viennent des thèmes de style.css (.theme-…),
// en clair comme en sombre. Tout est décoratif (aria-hidden) : rien d'utile n'est dit seulement par une image.
//   école, collège : bannière illustrée et couleurs vives ; à l'école, une plante grandit avec les idées.
//   lycée, supérieur : bannière au trait, discrète.

/** Thème d'après le nom de la discipline (champ « discipline » des modèles de séances, ou celle de la classe). */
export function themeDe(discipline) {
  const d = String(discipline || "").toLowerCase();
  const regles = [
    [/galois|alg[eè]bre|anneau|corps fini/, "algebre"], [/math|calcul|g[eé]om[eé]trie|nombre/, "maths"],
    [/linux|syst[eè]me d'exploitation|terminal|shell/, "terminal"], [/python|programm|informatique|algorithm|code/, "code"],
    [/cr[eé]ole/, "creole"], [/anglais|english|espagnol|allemand|catalan|langue vivante/, "langues"],
    [/fran[cç]ais|lecture|[eé]criture|litt[eé]rature|grammaire/, "francais"], [/histoire/, "histoire"],
    [/g[eé]ographie/, "geographie"], [/science|biolog|physique|chimie|svt|vivant/, "sciences"],
  ];
  return (regles.find(([re]) => re.test(d)) || [null, "general"])[1];
}

/** Style d'après le public : illustré (école, collège) ou au trait (lycée, supérieur). */
export const styleDe = pub => (pub === "lycee" || pub === "superieur") ? "trait" : "illustre";

/** Applique le thème à la page (classes du body) ; sans visuels, retire tout. */
export function appliquerTheme(actif, discipline, pub) {
  const b = document.body;
  [...b.classList].filter(c => /^(theme|public|style)-/.test(c)).forEach(c => b.classList.remove(c));
  b.classList.toggle("visuels", !!actif);
  if (!actif) return;
  b.classList.add("theme-" + themeDe(discipline), "public-" + (pub || "ecole"), "style-" + styleDe(pub));
}

function svg(code, classe, vue = "0 0 640 110", cadrage = "xMidYMid meet") {
  const t = document.createElement("div");
  t.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vue}" class="${classe}" aria-hidden="true" focusable="false" preserveAspectRatio="${cadrage}">${code}</svg>`;
  return t.firstElementChild;
}
// petits motifs réutilisés : points, étoiles
const points = (l, c = "v3") => l.map(([x, y, r]) => `<circle class="${c}" cx="${x}" cy="${y}" r="${r || 4}"/>`).join("");
const etoile = (x, y, r, c = "v2") => {
  const p = Array.from({length: 10}, (_, i) => { const a = Math.PI / 5 * i - Math.PI / 2, q = i % 2 ? r * 0.45 : r; return `${(x + q * Math.cos(a)).toFixed(1)},${(y + q * Math.sin(a)).toFixed(1)}`; });
  return `<polygon class="${c}" points="${p.join(" ")}"/>`;
};
const texte = (x, y, t, taille, c = "v1", rot = 0) =>
  `<text class="${c} txt" x="${x}" y="${y}" font-size="${taille}" transform="rotate(${rot} ${x} ${y})">${t}</text>`;
const bulle = (x, y, w, h, t, c = "v1") =>
  `<g><rect class="${c}" x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}"/><polygon class="${c}" points="${x + 18},${y + h - 2} ${x + 30},${y + h - 2} ${x + 14},${y + h + 12}"/>` +
  `<text class="sur txt" x="${x + w / 2}" y="${y + h / 2 + 6}" font-size="17" text-anchor="middle">${t}</text></g>`;

const DESSINS = {
  maths: () =>
    `<circle class="v1" cx="70" cy="58" r="30"/><polygon class="v2" points="150,88 186,24 222,88"/><rect class="v3" x="262" y="30" width="54" height="54" rx="6" transform="rotate(12 289 57)"/>` +
    texte(350, 70, "3 + 4 = ?", 34) + texte(530, 50, "×", 40, "v2") + texte(580, 92, "÷", 38, "v3") + texte(500, 98, "½", 30, "v1") +
    points([[120, 22], [240, 18], [330, 100], [470, 24], [620, 30]]),
  algebre: () =>
    `<circle class="v1" cx="96" cy="55" r="40" fill="none"/>` +
    Array.from({length: 5}, (_, k) => { const a = 2 * Math.PI * k / 5; return `<circle class="v2" cx="${(96 + 40 * Math.cos(a)).toFixed(1)}" cy="${(55 - 40 * Math.sin(a)).toFixed(1)}" r="6"/>`; }).join("") +
    `<line class="v3 ligne" x1="40" y1="55" x2="152" y2="55"/><line class="v3 ligne" x1="96" y1="5" x2="96" y2="105"/>` +
    texte(190, 50, "x⁵ − 1", 30) + texte(190, 92, "ℚ(ζ₅) ⊃ ℚ", 26, "v3") + texte(410, 66, "Gal(K/ℚ) ≅ ℤ/4ℤ", 26, "v2"),
  terminal: () =>
    `<rect class="v1" x="40" y="12" width="330" height="88" rx="10"/><rect class="sur" x="40" y="12" width="330" height="20" rx="10" opacity=".25"/>` +
    points([[58, 22, 4], [72, 22, 4], [86, 22, 4]], "v2") +
    texte(56, 60, "$ ls -l", 20, "sur") + texte(56, 88, "$ cd donnees", 20, "sur") + `<rect class="v2" x="200" y="74" width="12" height="18"/>` +
    `<path class="v3" d="M420 40 h40 l10 10 h60 v46 h-110 z"/><path class="v2" d="M500 22 h34 l8 8 h50 v38 h-92 z"/>` +
    `<line class="v1 ligne" x1="440" y1="96" x2="440" y2="104"/>`,
  code: () =>
    `<rect class="v1" x="40" y="12" width="300" height="88" rx="10"/>` +
    `<rect class="v2" x="60" y="32" width="90" height="10" rx="5"/><rect class="sur" x="160" y="32" width="120" height="10" rx="5" opacity=".7"/>` +
    `<rect class="v3" x="84" y="54" width="70" height="10" rx="5"/><rect class="sur" x="164" y="54" width="90" height="10" rx="5" opacity=".7"/>` +
    `<rect class="v2" x="84" y="76" width="140" height="10" rx="5"/>` +
    Array.from({length: 11}, (_, k) => { const x = 400 + k * 20, y1 = 55 + 32 * Math.sin(k * 0.75), y2 = 55 - 32 * Math.sin(k * 0.75);
      return `<line class="v3 ligne" x1="${x}" y1="${y1.toFixed(1)}" x2="${x}" y2="${y2.toFixed(1)}"/><circle class="v1" cx="${x}" cy="${y1.toFixed(1)}" r="6"/><circle class="v2" cx="${x}" cy="${y2.toFixed(1)}" r="6"/>`; }).join(""),
  creole: () =>
    `<circle class="v2" cx="580" cy="34" r="22"/>` +
    `<g transform="rotate(-28 95 70)"><ellipse class="v1" cx="95" cy="70" rx="70" ry="22"/><line class="sur ligne" x1="31" y1="70" x2="159" y2="70"/><line class="sur ligne" x1="39" y1="70" x2="49" y2="53"/><line class="sur ligne" x1="39" y1="70" x2="49" y2="87"/><line class="sur ligne" x1="55" y1="70" x2="65" y2="53"/><line class="sur ligne" x1="55" y1="70" x2="65" y2="87"/><line class="sur ligne" x1="71" y1="70" x2="81" y2="53"/><line class="sur ligne" x1="71" y1="70" x2="81" y2="87"/><line class="sur ligne" x1="87" y1="70" x2="97" y2="53"/><line class="sur ligne" x1="87" y1="70" x2="97" y2="87"/><line class="sur ligne" x1="103" y1="70" x2="113" y2="53"/><line class="sur ligne" x1="103" y1="70" x2="113" y2="87"/><line class="sur ligne" x1="119" y1="70" x2="129" y2="53"/><line class="sur ligne" x1="119" y1="70" x2="129" y2="87"/></g><g transform="rotate(-8 170 82)"><ellipse class="v3" cx="170" cy="82" rx="56" ry="18"/><line class="sur ligne" x1="120" y1="82" x2="220" y2="82"/><line class="sur ligne" x1="128" y1="82" x2="138" y2="69"/><line class="sur ligne" x1="128" y1="82" x2="138" y2="95"/><line class="sur ligne" x1="144" y1="82" x2="154" y2="69"/><line class="sur ligne" x1="144" y1="82" x2="154" y2="95"/><line class="sur ligne" x1="160" y1="82" x2="170" y2="69"/><line class="sur ligne" x1="160" y1="82" x2="170" y2="95"/><line class="sur ligne" x1="176" y1="82" x2="186" y2="69"/><line class="sur ligne" x1="176" y1="82" x2="186" y2="95"/><line class="sur ligne" x1="192" y1="82" x2="202" y2="69"/><line class="sur ligne" x1="192" y1="82" x2="202" y2="95"/></g>` +
    bulle(250, 18, 150, 40, "Bonjou !", "v3") + bulle(420, 56, 120, 38, "Mèsi !", "v1") + points([[240, 92], [600, 92], [560, 100]], "v2"),
  langues: () =>
    bulle(30, 20, 130, 40, "Hello!", "v1") + bulle(190, 54, 120, 38, "Hola", "v2") + bulle(340, 18, 140, 40, "Bon dia", "v3") + bulle(500, 54, 120, 38, "Hallo", "v1") +
    points([[180, 24], [330, 100], [490, 22], [630, 30]], "v2"),
  francais: () =>
    `<path class="v1" d="M60 30 Q130 14 200 30 V100 Q130 84 60 100 Z"/><path class="v2" d="M200 30 Q270 14 340 30 V100 Q270 84 200 100 Z"/>` +
    `<line class="sur ligne" x1="80" y1="50" x2="180" y2="44"/><line class="sur ligne" x1="80" y1="66" x2="180" y2="60"/><line class="sur ligne" x1="220" y1="44" x2="320" y2="50"/><line class="sur ligne" x1="220" y1="60" x2="320" y2="66"/>` +
    texte(380, 78, "A", 52, "v3") + texte(430, 70, "b", 40, "v1", -8) + texte(470, 86, "c", 44, "v2", 6) +
    `<path class="v3" d="M560 100 C565 60 590 25 625 10 C610 45 590 75 566 102 Z"/>`,
  histoire: () =>
    `<polygon class="v1" points="40,40 150,14 260,40"/><rect class="v1" x="40" y="40" width="220" height="8"/>` +
    [60, 110, 160, 210].map(x => `<rect class="v2" x="${x}" y="52" width="22" height="44" rx="3"/>`).join("") + `<rect class="v1" x="36" y="96" width="228" height="10"/>` +
    `<line class="v3 ligne" x1="300" y1="70" x2="600" y2="70"/>` + points([[330, 70, 9], [420, 70, 9], [510, 70, 9], [590, 70, 9]], "v1") +
    texte(312, 50, "-52", 16, "v3") + texte(404, 50, "800", 16, "v3") + texte(490, 50, "1789", 16, "v3") + texte(570, 50, "1945", 16, "v3"),
  geographie: () =>
    `<circle class="v1" cx="90" cy="55" r="44"/><ellipse class="sur ligne" cx="90" cy="55" rx="18" ry="44" fill="none"/><line class="sur ligne" x1="46" y1="55" x2="134" y2="55"/>` +
    `<path class="v3" d="M70 30 q14 -8 26 4 q-4 14 -18 12 z M92 66 q16 -6 22 8 q-10 12 -22 2 z"/>` +
    `<polygon class="v2" points="200,104 260,40 300,80 340,30 410,104"/><polygon class="sur" points="330,42 340,30 350,44" opacity=".8"/>` +
    `<g transform="translate(540 55)"><circle class="v3" r="36" opacity=".25"/><polygon class="v1" points="0,-34 7,0 0,34 -7,0"/><polygon class="v2" points="-34,0 0,-7 34,0 0,7"/>` + texte(-6, -40, "N", 14, "v1") + `</g>`,
  sciences: () =>
    `<path class="v1" d="M70 14 h40 v28 l34 56 a6 6 0 0 1 -5 9 h-98 a6 6 0 0 1 -5 -9 l34 -56 z"/>` + points([[80, 84, 6], [100, 72, 4], [112, 90, 5]], "sur") +
    `<path class="v3" d="M220 100 C220 50 260 22 320 18 C316 70 280 100 220 100 Z"/><line class="sur ligne" x1="226" y1="96" x2="300" y2="34"/>` +
    `<circle class="v2" cx="430" cy="48" r="28" fill="none" stroke-width="10"/><line class="v2 ligne epais" x1="452" y1="68" x2="490" y2="100"/>` +
    points([[560, 30, 10], [596, 52, 7], [570, 80, 8]], "v1"),
  general: () =>
    `<circle class="v2" cx="90" cy="46" r="30"/><rect class="v1" x="78" y="74" width="24" height="22" rx="4"/>` +
    etoile(220, 40, 20, "v3") + etoile(300, 80, 14, "v1") + etoile(560, 36, 18, "v2") +
    `<path class="v3" d="M380 30 h40 a12 12 0 1 1 20 0 h40 v30 a12 12 0 1 0 0 20 v30 h-100 z"/>`,
};

/** Bannière illustrée de la discipline (en tête de la carte « La tâche »). */
export function banniere(discipline, pub) {
  const cle = themeDe(discipline);
  return svg((DESSINS[cle] || DESSINS.general)(), "banniere " + styleDe(pub));   // fond : couleur de la bannière (style.css), sur toute la largeur
}

/** École : une plante qui pousse avec les idées ; une fleur quand l'objectif est atteint, une de plus tous les deux au-delà. */
export function plante(n, objectif) {
  objectif = Math.max(1, objectif || 3);
  const feuilles = Math.min(n, 9), haut = 24 + Math.min(n, 9) * 7;
  let code = `<circle class="halo" cx="60" cy="64" r="58"/><path class="pot" d="M38 102 h44 l-6 22 h-32 z"/><rect class="pot" x="34" y="96" width="52" height="9" rx="3"/>`;
  code += `<path class="tige" d="M60 97 C ${n % 2 ? 66 : 54} ${97 - haut / 2}, 60 ${97 - haut + 10}, 60 ${97 - haut}" fill="none"/>`;
  for (let i = 0; i < feuilles; i++) {
    const y = 84 - i * 7.2, d = i % 2 ? 1 : -1;
    code += `<path class="feuille" d="M60 ${y} q ${d * 18} -16 ${d * 32} -6 q ${-d * 13} 13 ${-d * 32} 6 z"/>`;
  }
  const fleurs = n >= objectif ? 1 + Math.floor((n - objectif) / 2) : 0;
  for (let f = 0; f < Math.min(fleurs, 3); f++) {
    const cx = 60 + [0, -20, 20][f], cy = 97 - haut - [0, -18, -26][f];
    code += Array.from({length: 6}, (_, k) => `<circle class="petale" cx="${(cx + 7 * Math.cos(k * Math.PI / 3)).toFixed(1)}" cy="${(cy + 7 * Math.sin(k * Math.PI / 3)).toFixed(1)}" r="5.5"/>`).join("") +
      `<circle class="coeur" cx="${cx}" cy="${cy}" r="4.5"/>`;
  }
  if (!n) code += `<circle class="graine" cx="60" cy="94" r="5"/>`;
  return svg(code, "plante" + (n ? " pousse" : ""), "0 0 120 126");
}

/** Fin de séance : bouquet d'étoiles (école, collège) ou simple marque de réussite (lycée, supérieur). */
export function bravo(pub) {
  if (styleDe(pub) === "trait")
    return svg(`<circle class="v1 ligne" cx="40" cy="40" r="30" fill="none"/><path class="v3 ligne epais" d="M26 41 l10 10 l20 -22" fill="none"/>`, "bravo trait", "0 0 80 80");
  return svg(etoile(60, 60, 34, "v2") + etoile(22, 26, 12, "v1") + etoile(104, 22, 14, "v3") + etoile(108, 96, 10, "v1") + etoile(16, 98, 9, "v3") +
    points([[44, 10, 4], [86, 112, 4], [118, 58, 3]], "v1"), "bravo", "0 0 124 124");
}
