# Déploiement Render

Le Dockerfile à la racine lance le site Node et le backend Python dans le même
service. `backend/Dockerfile` est destiné à AWS Lambda et ne démarre pas le site.

Après avoir publié ces fichiers sur la branche déployée, configurez Render :

- Language : **Docker**.
- Root Directory : vide (racine du dépôt Git).
- Dockerfile Path : **./Dockerfile**.
- Docker Build Context Directory : **.**.
- Docker Command : vide (utiliser le CMD de l’image).
- Health Check Path : **/api/health**.

Render fournit `PORT` et `RENDER_EXTERNAL_URL`. Le site écoute sur `0.0.0.0` ;
le backend reste privé sur `127.0.0.1`. Pour un domaine personnalisé, définissez
`PUBLIC_ORIGIN=https://votre-domaine`.

Variables pour activer Bedrock : `AWS_REGION=us-east-1`, `BEDROCK_MODEL_ID`
et une **nouvelle** clé dans `AWS_BEARER_TOKEN_BEDROCK` (secret Render).
Sans modèle configuré, le moteur utilise son explication déterministe.
Ne publiez jamais `.env` : il est exclu de Git et du contexte Docker.

L’audit local sous `/tmp/alphaforge-audit` est temporaire et ne survit pas aux
redémarrages de l’instance. Un stockage persistant doit être configuré si sa
conservation est nécessaire. Aucun déploiement distant n’est effectué par ces fichiers.
