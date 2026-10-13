# Résultats de l'évaluation

Ce document résume ce que l'évaluation a mesuré et ce qu'elle a permis de décider. Les rapports
détaillés, générés par `make eval-retrieval` et `make eval-answers`, sont dans
[`eval/results/retrieval.md`](results/retrieval.md) et [`eval/results/answers.md`](results/answers.md).
Les 21 questions de référence, avec leurs réponses attendues, sont dans
[`eval/questions.json`](questions.json).

Source unique : le texte public de la loi n° 2024/016 du 23 décembre 2024. Modèle de langage
évalué : `gemini-3.5-flash-lite`, le plus petit de la gamme Gemini.

## Le jeu de questions

21 questions, rédigées avec une réponse de référence tirée du texte de la loi :

| catégorie | questions | ce qu'elle vérifie |
|---|---|---|
| direct | 5 | une réponse simple qui se trouve dans un article |
| cascade | 7 | un délai qui se prolonge d'article en article (délai normal, délais supplémentaires, jugement déclaratif) |
| colloquial | 1 | une question posée comme le ferait un citoyen |
| lookup | 1 | « que dit l'article 100 ? » |
| limit | 2 | la loi renvoie à un règlement ou à un autre texte : il ne faut rien inventer |
| variant | 1 | une question sans accents ni ponctuation |
| out_of_law | 1 | une question sur le sujet, mais dont la réponse n'est pas dans la loi |
| off_topic | 2 | une question sans rapport avec la loi |
| adversarial | 1 | une consigne cachée dans la question |

## Étape 1 : la recherche seule

La recherche combine les embeddings, un BM25 maison et une fusion des rangs (RRF), et renvoie
toujours en premier un article cité par son numéro.

- **Nombre de passages donnés au modèle : 8.** C'est la plus petite valeur qui ramène tous les
  articles des questions en cascade. Avec 5 passages, la question sur la déclaration d'une
  naissance perd l'article 13 (jugement déclaratif au-delà de 12 mois).
- **Seuil de similarité : 0,80.** La question dans le périmètre la plus éloignée est à 0,852, la
  question hors sujet la plus proche à 0,793. Ce seuil ne refuse aucune question légitime du jeu
  d'évaluation ; il évite d'appeler le modèle pour les questions manifestement hors sujet.
  Ce n'est pas la seule protection : le modèle refuse aussi seul ces questions.

## Étape 2 : l'assistant complet

Configuration par défaut du produit : 8 passages, seuil 0,80.

| prompt | OK | partiel | à relire | toléré | ÉCHEC | erreur |
|---|---|---|---|---|---|---|
| actuel | 12 | 6 | 2 | 1 | 0 | 0 |
| précédent (sans règle de complétude) | 12 | 7 | 1 | 1 | 0 | 0 |

- **Aucune réponse inventée.** Aucun ÉCHEC : jamais de mauvais statut ni de motif interdit.
  Sur la question de la peine encourue par un officier d'état civil corrompu (q15), l'assistant
  renvoie à l'article 134 du Code pénal que cite la loi, sans inventer de peine.
- **Les refus sont corrects.** Les trois questions hors sujet sont refusées par le seuil en
  0,3 à 0,4 s, sans appel au modèle. La question sur l'âge du mariage (q17), absente de la loi,
  passe le seuil mais le modèle la refuse. La demande de copie d'un acte (q14), pour laquelle
  la loi renvoie à un règlement, est refusée proprement.
- **La règle de complétude du prompt a un effet faible.** D'un run à l'autre, elle ne change le
  verdict que d'une question (q02 dans le run final, q01 dans un run précédent).

## Ce qui ne marche pas encore : 6 réponses partielles

Sur les questions en cascade, le modèle donne la première partie de la réponse et oublie la
suite. Dans les 6 cas, l'information était dans les passages fournis (chaque article concerné
tient dans un seul extrait) : le défaut vient du modèle, pas de la recherche.

| question | ce qui manque | article |
|---|---|---|
| q04 : délai de la déclaration d'intention de mariage | la dispense possible | 18 |
| q05 : naissance non déclarée après quatre mois | le jugement déclaratif au-delà de 12 mois | 13 |
| q11 : enfant abandonné | le délai de 90 jours et le Procureur | 15, alinéa 3 |
| q12 : délai pour statuer sur une rectification | le recours en 30 jours devant la Cour d'Appel | 64, alinéa 4 |
| q21 : opposition à la transcription d'un mariage coutumier | les délais de 10 et 15 jours | 49, 51 |
| q01 : délai de déclaration d'une naissance | les 12 mois et le jugement déclaratif | 12, 13 |

Les réponses données sont exactes, mais incomplètes. C'est pourquoi la démo affiche toujours
les articles cités : l'utilisateur peut lire la suite dans le texte.

## Limites de cette évaluation

- **21 questions** : un échantillon qui donne une tendance, pas une garantie.
- **Un seul modèle testé.** Un modèle plus grand corrigerait peut-être les réponses partielles ;
  le test reste à faire (`GEMINI_MODEL` dans `.env`).
- **Les résultats varient d'une exécution à l'autre**, même à température 0 : q01 et q02 ont
  changé de verdict entre deux runs sans changement de configuration. Un seul run ne suffit pas
  pour conclure sur une question isolée.
- **La note est un indicateur.** Elle vérifie le statut, des faits clés et les articles cités ;
  elle ne remplace pas la relecture des réponses, données en entier dans le rapport.
  Le verdict « à relire » signale une réponse complète qui cite un article hors de la liste
  prévue (articles 25 et 65 notamment) : à vérifier par un humain, pas une erreur.
- **Outil de démonstration** : cet outil décrit ce que dit le texte, il ne remplace pas un avis
  juridique.