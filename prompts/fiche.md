# Consigne : fiche d'une vidéo

À donner à un modèle (Claude Code, l'API, une autre IA) avec une transcription `chaines/<nom>/transcripts/<id>.md`. La fiche va dans `chaines/<nom>/fiches/<id>.md`, même identifiant.

Le but : garder tout ce que l'auteur affirme de précis, avec la minute où il le dit, et rien de ce qu'il ne dit pas.

## Règles

- **Une source par affirmation** : lien horodaté repris de la transcription, sous la forme `[mm:ss](https://www.youtube.com/watch?v=<id>&t=<s>s)`. Sans source, ne pas l'écrire.
- **Ses mots, pas des connaissances générales** sur le sujet. Si un terme a un sens courant différent du sien, donner le sien.
- **Chiffres tels qu'il les dit** : prix, durées, pourcentages, heures (avec le fuseau s'il le donne). Un chiffre absent reste absent ; ne pas estimer.
- **Contradictions** : citer les deux passages, ne pas trancher.
- **Mots mal transcrits** : les signaler dans « Limites » avec la correction probable (« busy » = bullish).
- **Concision** : une fiche se lit en deux minutes. Pas de résumé du blabla, de la pub ou des remerciements.

## Modèle

```markdown
# <titre de la vidéo>
https://www.youtube.com/watch?v=<id> · <durée> min · <catégorie> · <sous-titres YouTube | Whisper>

## En bref
Deux à quatre phrases : de quoi parle la vidéo et ce qu'elle apporte de neuf.

## Règles énoncées
1. Règle, condition, ordre des étapes, avec sources.
   - Précision ou exception.

## Définitions
- Terme : définition dans ses mots (source).

## Exemples concrets
Ce qu'il montre ou raconte : date, contexte, chiffres, résultat. Dire quand une date ou un chiffre manque.

## Limites
- Ce qui reste flou, non chiffré, contradictoire, ou dépend d'un écran qu'on ne voit pas.
- Mots mal transcrits.
```

Adapter les sections au sujet de la chaîne. Pour une chaîne de trading, remplacer « Exemples concrets » par deux sections : « Entrées, stops, objectifs, gestion » puis « Trades et exemples concrets » (date, instrument, sens, entrée, stop, sortie, résultat annoncé).
