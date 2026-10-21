#!/bin/sh
# Viabilis hors ligne (macOS : double-cliquez sur ce fichier) : lance la page de l'étudiant avec le kit de la classe. Voir LISEZMOI.txt.
cd "$(dirname "$0")" || exit 1
KIT=kit.json
[ -f "$KIT" ] || KIT=$(ls viabilis_kit_*.json 2>/dev/null | head -n 1)
if [ -z "$KIT" ] || [ ! -f "$KIT" ]; then
  echo "Kit introuvable : copiez dans ce dossier le fichier téléchargé par votre enseignant (kit.json)."
  printf "Appuyez sur Entrée pour fermer. "; read -r _; exit 1
fi
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "Python 3 est nécessaire : acceptez l'installation des outils de développement proposée par macOS, ou installez Python depuis python.org, puis relancez."
  printf "Appuyez sur Entrée pour fermer. "; read -r _; exit 1
fi
exec "$PY" ../serveur/serveur.py --hors-ligne "$KIT" --port 8765
