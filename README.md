# youtube_extract

Récupère les transcriptions d'une chaîne YouTube entière, en local, pour les analyser ensuite (par exemple avec Claude) :

1. liste toutes les vidéos des onglets de la chaîne ;
2. les classe par catégorie d'après leur titre, et écarte ce qui ne vous intéresse pas ;
3. télécharge les sous-titres YouTube, lentement pour ne pas être bloqué ;
4. transcrit avec Whisper, sur votre machine, les vidéos qui n'en ont pas ; repère et refait les transcriptions qui bouclent ;
5. écrit une transcription lisible par vidéo, horodatée chaque minute, avec des liens vers le bon moment ;
6. en option sur macOS : lit le texte affiché à l'écran (graphiques, diapositives, code).

Ensuite, `prompts/` contient les consignes pour tirer de ces transcriptions une fiche par vidéo, puis une synthèse de la chaîne où chaque règle garde sa source horodatée.

## Installation

Python 3.9 ou plus, sans dépendance Python. Trois outils en ligne de commande :

```bash
brew install yt-dlp ffmpeg whisper-cpp
```

Sous Linux : `pip install yt-dlp`, `ffmpeg` par le gestionnaire de paquets, et [whisper.cpp](https://github.com/ggml-org/whisper.cpp) compilé avec `whisper-cli` dans le `PATH`.

Puis les modèles Whisper (environ 550 Mo, dans `modeles/`) :

```bash
python3 -m ytx modeles
```

Pour les mettre ailleurs, définir `YTX_MODELES=/chemin/du/dossier`.

## Utilisation

Toutes les commandes se lancent depuis le dossier du dépôt.

```bash
python3 -m ytx nouvelle machaine @NomDeLaChaine
```

```bash
python3 -m ytx lister machaine
```

Regarder les titres dans `chaines/machaine/data/listing.tsv`, ajuster les catégories dans `chaines/machaine/chaine.json`, puis vérifier le classement :

```bash
python3 -m ytx selectionner machaine
```

Les vidéos gardées sont dans `data/selection.tsv`, les autres dans `data/exclues.tsv`. Recommencer jusqu'à ce que le tri convienne, puis tout lancer :

```bash
python3 -m ytx tout machaine
```

Comptez plusieurs heures pour une grosse chaîne : les pauses entre requêtes évitent le blocage de YouTube. Tout se reprend là où ça s'est arrêté, il suffit de relancer la commande. Pour voir où on en est :

```bash
python3 -m ytx statut machaine
```

Les transcriptions sont dans `chaines/machaine/transcripts/<id>.md`.

Pour essayer sur quelques vidéos seulement : `python3 -m ytx tout machaine --limite 3`.

### Les étapes une par une

| Commande | Ce qu'elle fait | Écrit dans `chaines/<nom>/` |
|---|---|---|
| `lister` | liste les vidéos des onglets | `data/listing.tsv` |
| `selectionner` | classe les titres | `data/selection.tsv`, `data/exclues.tsv` |
| `sous-titres` | sous-titres YouTube, manuels ou automatiques | `data/raw/`, `data/info/` |
| `whisper` | transcrit les vidéos sans sous-titres | `data/whisper/` |
| `verifier-whisper` | repère les transcriptions qui bouclent | `data/whisper_bad.tsv` |
| `refaire-whisper` | les refait avec détection de voix (ancien résultat gardé) | `data/whisper/`, `data/whisper_old/` |
| `transcriptions` | une transcription lisible par vidéo | `transcripts/` |
| `images` | macOS : vidéo sans le son, texte à l'écran toutes les 10 s | `data/ocr/<id>.jsonl` |
| `statut` | compte ce qui est fait à chaque étape | |

`tout` enchaîne `lister` (si le listing n'existe pas encore, ou avec `--relister`), `selectionner`, `sous-titres`, `whisper`, `verifier-whisper`, `refaire-whisper`, `transcriptions`. `images` est à part : il télécharge les vidéos (plusieurs Go) et les efface après lecture, sauf avec `--garder-videos`.

## Configuration : `chaine.json`

Voir `chaines/exemple/chaine.json`.

| Clé | Rôle |
|---|---|
| `sources` | une ou plusieurs chaînes : `@handle`, identifiant `UC…`, URL de chaîne, ou URL de playlist |
| `onglets` | `videos`, `streams`, `shorts` |
| `langue` | langue des vidéos : sous-titres et Whisper (`en`, `fr`…) |
| `duree_min_s` | vidéos plus courtes écartées (les shorts) |
| `categories` | liste ordonnée de `{"nom", "motif"}` ; `motif` est une expression régulière cherchée dans le titre, sans tenir compte de la casse. La première qui correspond gagne. Avec `"exclure": true`, les titres qui correspondent sont écartés. L'ordre sert aussi de priorité pour `images`. |
| `defaut` | catégorie des titres qu'aucun motif ne reconnaît ; `null` pour les écarter |
| `forcer` | `{"<id>": "<catégorie>"}` pour corriger une vidéo mal classée, `null` pour l'écarter |
| `cookies_navigateur` | `"chrome"`, `"firefox"`, `"safari"`… si YouTube bloque ou demande une connexion (passé à `yt-dlp --cookies-from-browser`) |
| `pause_*`, `passages_sous_titres` | rythme des requêtes ; garder les valeurs par défaut sauf raison précise |
| `ocr_toutes_les_s`, `garder_videos` | réglages de `images` |

## Fiches et synthèse

Le pipeline s'arrête aux transcriptions. Pour la suite, donner à un modèle :

- `prompts/fiche.md` avec une transcription : une fiche par vidéo dans `chaines/<nom>/fiches/<id>.md` ;
- `prompts/synthese.md` avec toutes les fiches : `chaines/<nom>/REGLES.md`.

Avec Claude Code ouvert dans ce dossier, il suffit de demander « fais les fiches de la chaîne machaine en suivant prompts/fiche.md ».

## Ce qui n'est pas publié

`.gitignore` exclut les dossiers de chaînes (sauf l'exemple), les modèles et les binaires compilés : les transcriptions et les vidéos appartiennent à leurs auteurs, et pèsent lourd.

## Avertissement

Outil d'étude personnelle. Respecter les conditions d'utilisation de YouTube et les droits des auteurs : ne pas republier leurs transcriptions ni leurs vidéos.
