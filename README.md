# RAG état civil — loi n° 2024/016

Démo d'un assistant de questions-réponses **avec citations d'articles** sur la loi n° 2024/016 du
23 décembre 2024 portant organisation du système d'enregistrement des faits d'état civil au Cameroun.

> **Outil de démonstration, ne remplace pas un avis juridique.** Seul le texte publié au Journal
> Officiel fait foi.

**Projet indépendant** : il n'a aucun lien avec un organisme public ni avec un employeur. Il est
construit à partir du seul texte public de la loi, sans aucune donnée, code ni document interne.

État : en construction (étape 1 : squelette de l'application). Le moteur de recherche et la
génération arrivent aux étapes suivantes.

## Démarrage

Prérequis : [uv](https://docs.astral.sh/uv/) et Python 3.12.

```bash
cp .env.example .env
make install
make run        # http://127.0.0.1:5000
make check      # ruff + tests
```

## Structure

```
data/raw/           texte de la loi (transcription) et fiche de source
docs/               vérification de la transcription
src/rag_etat_civil/ application (config, web)
tests/              tests
```

## Licence

MIT, voir [LICENSE](LICENSE). Le texte de la loi est un acte officiel, voir `data/raw/SOURCE.md`.
