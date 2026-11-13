# Menteur — Duel en ligne

Jeu multijoueur réel à deux personnes : entrée par pseudo, joueurs connectés, défis acceptés ou refusés, cartes sans numéros dessinées en CSS, table, main et bouton Menteur. Les symboles des types sont du texte, sans images de cartes.

## Installation sur Render
1. Décompresse cette archive et ajoute tous les fichiers dans un nouveau dépôt GitHub, en conservant les dossiers.
2. Pour ajouter ton fond, crée le dossier static puis ajoute ton image sous le nom exact bg_table.jpg. Aucun fond personnel n’est fourni ; la table verte reste utilisable sans image.
3. Dans Render, choisis New puis Blueprint et connecte ton dépôt. Le fichier render.yaml prépare le service et sa commande de démarrage.
4. Lance le déploiement puis ouvre l’adresse fournie par Render.
5. Partage cette même adresse avec un ami : chacun choisit un pseudo différent, puis l’un défie l’autre et celui-ci accepte.

## Règles de cette version
Le paquet comprend 32 cartes : huit cartes de chacun des quatre types. Chaque joueur reçoit 16 cartes. À son tour, on pose de 1 à 3 cartes face cachée et on annonce un type. Le type reste imposé pendant toute la pile. L’adversaire peut contester immédiatement la dernière pose ou jouer, ce qui accepte implicitement la pose précédente. Si une des cartes révélées n’est pas du type annoncé, le poseur ramasse la pile ; sinon, le contestataire ramasse. Celui qui ramasse commence la pile suivante et choisit son type. Une main vide gagne lorsque la dernière pose est acceptée ou lorsqu’une contestation prouve son honnêteté.

## Fonctionnement et limites
Le serveur contrôle les mains, les tours et les contestations ; il n’envoie jamais la main adverse au navigateur. Les pseudos ne sont pas des comptes et n’ont pas de mot de passe. Une déconnexion termine le duel en faveur de l’autre joueur.
Les parties et présences vivent dans la mémoire d’un unique processus : conserver un seul service, un seul worker et une seule instance. Un redémarrage efface les duels ; pas de reprise ni d’historique. Le salon accepte au maximum 100 connexions inscrites et cette version ne comprend pas de dispositif anti-abus avancé. L’hébergement et les téléchargements des polices et du client temps réel nécessitent Internet.

Le déploiement Render doit être effectué par le propriétaire : aucune publication automatique n’est faite depuis cette conversation. Le fonctionnement en ligne doit être vérifié après déploiement avec deux navigateurs distincts.
