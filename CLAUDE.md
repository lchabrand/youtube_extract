# Pour Claude Code

Outil d'extraction des transcriptions d'une chaîne YouTube, décrit dans `README.md`. Python 3.9, bibliothèque standard seulement : ne pas ajouter de dépendance.

- Le code est dans `ytx/`, lancé avec `python3 -m ytx <commande> <chaine>`. Une chaîne = un dossier `chaines/<nom>/` avec son `chaine.json` ; tout ce que le pipeline écrit va dans ce dossier.
- Rien de spécifique à une chaîne dans `ytx/` : ce qui varie va dans `chaine.json` (clés et valeurs par défaut : `DEFAUTS` dans `ytx/projet.py`).
- Le pipeline se reprend où il s'est arrêté : une étape saute ce qui existe déjà. Garder cette propriété.
- YouTube bloque (HTTP 429) les clients trop rapides : ne pas raccourcir les pauses par défaut.
- Fiches et synthèse : suivre `prompts/fiche.md` et `prompts/synthese.md`. Chaque affirmation garde sa source horodatée ; rien ne vient de connaissances générales.
- Messages à l'écran et documentation en français ; commentaires et docstrings du code en anglais.
