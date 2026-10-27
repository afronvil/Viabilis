// Service worker : met en cache l'interface (pas les données) pour une ouverture rapide et l'installation sur l'écran d'accueil.
const CACHE = "viabilis-v43";
const FICHIERS = ["eleve/", "eleve/index.html", "eleve/app.js", "eleve/manifest.webmanifest",
  "enseignant/", "enseignant/index.html", "enseignant/app.js", "enseignant/manifest.webmanifest",
  "commun/etat.js", "commun/style.css", "commun/icone.svg", "commun/modeles.json", "commun/suites.js", "commun/langues.js", "commun/traductions.js", "commun/visuels.js"];
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(FICHIERS)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/") || e.request.method !== "GET") return;      // les données passent toujours par le réseau
  e.respondWith(fetch(e.request).then(r => { const copie = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copie)); return r; })
    .catch(() => caches.match(e.request)));
});
