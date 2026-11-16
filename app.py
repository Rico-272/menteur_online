import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

places = {"J1": None, "J2": None}
mains = {
    "J1": {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0},
    "J2": {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
}

# Variables d'état du jeu du Menteur
etat = {
    "tour": "J1",               # Qui doit jouer ("J1" ou "J2")
    "tas": [],                  # Liste des cartes posées au milieu
    "carte_annoncee": None,     # L'enseigne de la 1ère carte posée face visible
    "dernier_poseur": None,     # Qui a posé la dernière carte face cachée
    "carte_visuelle": "dos",    # Ce qui s'affiche au centre ("coeur", ..., ou "dos")
    "partie_terminee": False
}

cartes_autorisees = ["coeur", "carreau", "trefle", "pique"]
noms_fr = {"coeur": "Cœur ♥", "carreau": "Carreau ♦", "trefle": "Trèfle ♣", "pique": "Pique ♠"}

@app.get("/")
async def afficher_page():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

def total_cartes(role: str) -> int:
    return sum(mains[role].values())

def reinitialiser_partie():
    paquet = ["coeur"] * 16 + ["carreau"] * 16 + ["trefle"] * 16 + ["pique"] * 16
    random.shuffle(paquet)
    
    for role, cartes_j in [("J1", paquet[:32]), ("J2", paquet[32:])]:
        mains[role] = {
            "coeur": cartes_j.count("coeur"),
            "carreau": cartes_j.count("carreau"),
            "trefle": cartes_j.count("trefle"),
            "pique": cartes_j.count("pique")
        }
    
    etat["tour"] = "J1"
    etat["tas"] = []
    etat["carte_annoncee"] = None
    etat["dernier_poseur"] = None
    etat["carte_visuelle"] = "dos"
    etat["partie_terminee"] = False

async def envoyer_etat_complet(message_info: str = ""):
    """Envoie à chaque joueur sa main privée et l'état public de la table."""
    nb_joueurs = sum(1 for v in places.values() if v is not None)
    
    for role in ["J1", "J2"]:
        ws = places[role]
        if ws is not None:
            autre = "J2" if role == "J1" else "J1"
            # On peut cliquer sur "Menteur" uniquement s'il y a au moins 2 cartes dans le tas (donc une carte face cachée)
            peut_crier_menteur = (
                nb_joueurs == 2 
                and not etat["partie_terminee"]
                and etat["tour"] == role 
                and len(etat["tas"]) >= 2
            )
            
            donnees = {
                "type": "mise_a_jour",
                "nb_joueurs": nb_joueurs,
                "mon_role": role,
                "ma_main": mains[role],
                "cartes_adversaire": total_cartes(autre),
                "tour": etat["tour"],
                "carte_visuelle": etat["carte_visuelle"],
                "carte_annoncee": etat["carte_annoncee"],
                "taille_tas": len(etat["tas"]),
                "peut_crier_menteur": peut_crier_menteur,
                "partie_terminee": etat["partie_terminee"],
                "message": message_info
            }
            try:
                await ws.send_text(json.dumps(donnees))
            except Exception:
                pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    mon_role = None
    if places["J1"] is None:
        places["J1"] = websocket
        mon_role = "J1"
    elif places["J2"] is None:
        places["J2"] = websocket
        mon_role = "J2"
    else:
        await websocket.send_text(json.dumps({
            "type": "complet",
            "message": "La salle est pleine (Joueur 1 et Joueur 2 sont déjà connectés)."
        }))
        await websocket.close()
        return

    nb_joueurs = sum(1 for v in places.values() if v is not None)
    if nb_joueurs == 2:
        reinitialiser_partie()
        await envoyer_etat_complet("La partie commence ! Joueur 1 pose la 1ère carte face visible.")
    else:
        await envoyer_etat_complet("En attente du Joueur 2...")

    try:
        while True:
            texte = await websocket.receive_text()
            data = json.loads(texte)
            action = data.get("action")

            if places["J1"] is None or places["J2"] is None:
                continue

            # Relancer une partie après une victoire
            if action == "rejouer" and etat["partie_terminee"]:
                reinitialiser_partie()
                await envoyer_etat_complet("Nouvelle partie ! Joueur 1 pose la 1ère carte face visible.")
                continue

            # Vérifier que c'est bien le tour du joueur et que la partie n'est pas finie
            if etat["partie_terminee"] or etat["tour"] != mon_role:
                continue

            autre_role = "J2" if mon_role == "J1" else "J1"
            nom_moi = "Joueur 1" if mon_role == "J1" else "Joueur 2"
            nom_autre = "Joueur 2" if mon_role == "J1" else "Joueur 1"

            # ACTION 1 : Poser une carte
            if action == "jouer_carte":
                carte = data.get("valeur")
                if carte in cartes_autorisees and mains[mon_role][carte] > 0:
                    # Si l'adversaire avait 0 carte et qu'on ne l'a pas accusé de menteur, il gagne !
                    if total_cartes(autre_role) == 0:
                        etat["partie_terminee"] = True
                        await envoyer_etat_complet(f"🏆 {nom_autre} n'a plus de cartes et remporte la partie !")
                        continue

                    mains[mon_role][carte] -= 1
                    etat["tas"].append(carte)
                    etat["dernier_poseur"] = mon_role

                    # Si c'est la 1ère carte du tour : elle est posée FACE VISIBLE et fixe l'annonce
                    if len(etat["tas"]) == 1:
                        etat["carte_annoncee"] = carte
                        etat["carte_visuelle"] = carte
                        msg = f"{nom_moi} lance le tour avec {noms_fr[carte]} (face visible)."
                    # Sinon : la carte est posée FACE CACHÉE
                    else:
                        etat["carte_visuelle"] = "dos"
                        msg = f"{nom_moi} pose une carte face cachée (Annonce : {noms_fr[etat['carte_annoncee']]})."

                    # Vérification immédiate si le joueur vient de vider sa main sur la 1ère carte
                    if total_cartes(mon_role) == 0 and len(etat["tas"]) == 1:
                        etat["partie_terminee"] = True
                        await envoyer_etat_complet(f"🏆 {nom_moi} a posé sa dernière carte et gagne la partie !")
                    else:
                        etat["tour"] = autre_role
                        await envoyer_etat_complet(msg)

            # ACTION 2 : Cliquer sur "Menteur !"
            elif action == "menteur" and len(etat["tas"]) >= 2:
                derniere_carte = etat["tas"][-1]
                carte_attendue = etat["carte_annoncee"]
                nb_tas = len(etat["tas"])

                # Règle : si la carte posée est la MÊME que celle annoncée -> celui qui clique récupère tout
                if derniere_carte == carte_attendue:
                    perdant = mon_role
                    nom_perdant = nom_moi
                    verdict = f"Pas de mensonge ! C'était bien un {noms_fr[derniere_carte]}."
                # Sinon (il a menti) -> l'autre (celui qui a posé la carte) récupère tout
                else:
                    perdant = autre_role
                    nom_perdant = nom_autre
                    verdict = f"Menteur démasqué ! C'était un {noms_fr[derniere_carte]} au lieu de {noms_fr[carte_attendue]}."

                # Transfert de toutes les cartes du tas vers la main de celui qui ramasse
                for c in etat["tas"]:
                    mains[perdant][c] += 1

                # Réinitialisation du tas et celui qui a ramassé recommence le tour
                etat["tas"] = []
                etat["carte_annoncee"] = None
                etat["carte_visuelle"] = "dos"
                etat["tour"] = perdant

                # Si l'autre joueur avait 0 carte et a réussi son bluff, il gagne la partie !
                if total_cartes(autre_role) == 0 and perdant == mon_role:
                    etat["partie_terminee"] = True
                    await envoyer_etat_complet(f"{verdict} 🏆 {nom_autre} n'a plus de cartes et gagne !")
                else:
                    await envoyer_etat_complet(f"{verdict} {nom_perdant} ramasse les {nb_tas} cartes et recommence le tour.")

    except WebSocketDisconnect:
        if places[mon_role] == websocket:
            places[mon_role] = None
            etat["tas"] = []
            etat["carte_annoncee"] = None
            etat["carte_visuelle"] = "dos"
            etat["partie_terminee"] = False
            mains["J1"] = {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
            mains["J2"] = {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
            await envoyer_etat_complet("L'autre joueur s'est déconnecté.")
