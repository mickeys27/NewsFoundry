# NewsFoundry

## Besoins fonctionnels

- L'utilisateur peut se connecter.
- L’utilisateur peut voir la liste de ses discussions passées.
- L’utilisateur peut démarrer une nouvelle discussion ou reprendre une ancienne discussion.
- Un utilisateur n’est pas autorisé à accéder aux discussions d’un autre utilisateur.
- Le LLM répond aux messages envoyés par l’utilisateur.
- L'utilisateur peut faire générer une revue de presse à partir d'une discussion.
- L'application doit afficher des messages d'erreur à l'utilisateur final en cas d'erreur.

## Prérequis

- Docker
- Python 3.13
- uv
- Node.js 22.19

## Installation

1. Cloner le repository
2. Démarrer le backend aved les instructions du fichier `backend/README.md`
3. Initialiser un projet Next.js dans un dossier `frontend/`

## Choix technologiques

### Frontend

**Next.js**

### Backend

- **Python** pour bénéficier de son écosystème de librairies IA
- **FastAPI** pour le développement de l'API
- Connection avec des **JWT**
- **SQLModel** comme ORM : fait pour bien marcher avec FastAPI.
  - Branché à une base de données **PostgreSQL**
- **PydanticAI** comme client qui s'intégrera aussi bien avec les autres outils de la stack backend
- Attention à la **sécurité des données**. On ne veut pas qu’un utilisateur puisse accéder aux chats d’un autre utilisateur ou les modifier.
  - Le produit aura rapidement beaucoup d’utilisateurs professionnels il est donc crucial de garantir le fonctionnement correct de cette fonctionnalité par l'**implémentation de tests automatisés qui s'exécutent par une Github Action**.
- Pour les sources de news, on utilisera l’API [**WorldNewsAPI**](https://worldnewsapi.com/).
- Pour déployer on mettra le frontend sur **Vercel** et le backend sur **Railway**.

### Documentation

Une documentation claire devra être rédigée et ajoutée dans un dossier `docs/`.

Elle devra inclure des suggestions d'amélioration concernant la qualité et la performance de la partie IA du système. Chaque recommandation doit être illustrée par une une métrique ou un exemple, une proposition d’implémentation réalisable, ainsi qu'un objectif mesurable.


Par ailleurs, pour faciliter la maintenance du projet à long terme, le code du projet devra être clair et bien structuré, accompagné de commentaires qui expliquent les sections de code complexes.

### Deploiement

L'url de l'application déployée devra être ajouté dans la documentation.

#### Frontend

Déployer le frontend sur [Vercel](https://vercel.com/dashboard).

#### Backend

Déployer le backend sur [Railway](https://railway.com/dashboard).

> Un Dockerfile est déjà présent pour faciliter le déploiement. Il faudra simplement référencer `backend/` comme "Root Directory" après avoir connecté le repository.
> La base de donnée postgres peut être créée via Railway dans le même projet que le backend.
