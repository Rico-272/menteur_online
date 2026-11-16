import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

places = {
    "J1": None,
    "J2": None
}

mains = {
    "J1": {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0},
    "J2": {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
}

carte_actuelle = "dos"
cartes_autorisees = ["coeur", "carreau", "trefle", "pique"]

# Variables ajoutées pour le jeu du Menteur
tas = []
carte_annoncee = None
tour_actuel = "J1"
partie_finie = False
noms_fr = {"coeur": "Cœur ♥", "carreau": "Carreau ♦", "trefle": "Trèfle ♣", "pique": "Pique ♠"}

@app.get("/")
async def afficher_page():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

def distribuer_64_cartes():
    global tas, carte_annoncee, tour_actuel, carte_actuelle, partie_finie
    paquet = ["coeur"] * 16 + ["carreau"] * 16 + ["trefle"] * 16 + ["pique"] * 16
    random.shuffle(paquet)
    
    main_j1 = paquet[:32]
    main_j2 = paquet[32:]
    
    for role, cartes_joueur in [("J1", main_j1), ("J2", main_j2)]:
        mains[role] = {
            "coeur": cartes_joueur.count("coeur"),
            "carreau": cartes_joueur.count("carreau"),
            "trefle": cartes_joueur.count("trefle"),
            "pique": cartes_joueur.count("pique")
        }
    tas = []
    carte_annoncee = None
    tour_actuel = "J1"
    carte_actuelle = "dos"
    partie_finie = False

async def envoyer_main(role: str):
    ws = places[role]
    if ws is not None:
        try:
            await ws.send_text(json.dumps({
                "type": "maj_main",
                "main": mains[role]
            }))
        except Exception:
            pass

async def diffuser_aux_joueurs(donnees: dict):
    message = json.dumps(donnees)
    for role in ["J1", "J2"]:
        ws = places[role]
        if ws is not None:
            try:
                await ws.send_text(message)
            except Exception:
                pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global carte_actuelle, tas, carte_annoncee, tour_actuel, partie_finie
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
            "message": "La partie est complète (Joueur 1 et Joueur 2 sont déjà connectés)."
        }))
        await websocket.close()
        return

    nb_joueurs = sum(1 for v in places.values() if v is not None)
    await websocket.send_text(json.dumps({
        "type": "attribution",
        "role": mon_role,
        "carte": carte_actuelle
    }))

    if nb_joueurs == 2:
        distribuer_64_cartes()
        await envoyer_main("J1")
        await envoyer_main("J2")

    await diffuser_aux_joueurs({
        "type": "statut_salle",
        "nb_joueurs": nb_joueurs,
        "tour": tour_actuel
    })

    try:
        while True:
            texte = await websocket.receive_text()
            data = json.loads(texte)
            action = data.get("action")

            if places["J1"] is None or places["J2"] is None:
                continue

            autre_role = "J2" if mon_role == "J1" else "J1"
            nom_joueur = "Joueur 1" if mon_role == "J1" else "Joueur 2"
            nom_autre = "Joueur 2" if mon_role == "J1" else "Joueur 1"

            # Action 1 : Jouer une carte
            if action == "jouer_carte" and not partie_finie and tour_actuel == mon_role:
                nouvelle_carte = data.get("valeur")
                if nouvelle_carte in cartes_autorisees and mains[mon_role][nouvelle_carte] > 0:
                    # Si l'autre avait 0 carte et qu'on ne l'a pas accusé de menteur, il gagne
                    if sum(mains[autre_role].values()) == 0:
                        partie_finie = True
                        await diffuser_aux_joueurs({
                            "type": "carte",
                            "valeur": carte_actuelle,
                            "par": f"VICTOIRE : {nom_autre} n'a plus de carte !",
                            "tour": tour_actuel,
                            "annonce": None,
                            "taille_tas": len(tas),
                            "partie_finie": True
                        })
                        continue

                    mains[mon_role][nouvelle_carte] -= 1
                    tas.append(nouvelle_carte)
                    await envoyer_main(mon_role)

                    # 1ère carte du tour : face visible + fixe l'annonce
                    if len(tas) == 1:
                        carte_annoncee = nouvelle_carte
                        carte_actuelle = nouvelle_carte
                        texte_info = f"{nom_joueur} ouvre avec {noms_fr[nouvelle_carte]} (face visible)"
                    # Cartes suivantes : face cachée
                    else:
                        carte_actuelle = "dos"
                        texte_info = f"{nom_joueur} pose face cachée (Annonce : {noms_fr[carte_annoncee]})"

                    # Victoire si 0 carte dès la 1ère pose
                    if sum(mains[mon_role].values()) == 0 and len(tas) == 1:
                        partie_finie = True
                        await diffuser_aux_joueurs({
                            "type": "carte",
                            "valeur": carte_actuelle,
                            "par": f"VICTOIRE : {nom_joueur} n'a plus de carte !",
                            "tour": tour_actuel,
                            "annonce": None,
                            "taille_tas": len(tas),
                            "partie_finie": True
                        })
                    else:
                        tour_actuel = autre_role
                        await diffuser_aux_joueurs({
                            "type": "carte",
                            "valeur": carte_actuelle,
                            "par": texte_info,
                            "tour": tour_actuel,
                            "annonce": carte_annoncee,
                            "taille_tas": len(tas),
                            "partie_finie": False
                        })

            # Action 2 : Cliquer sur Menteur !
            elif action == "menteur" and not partie_finie and tour_actuel == mon_role and len(tas) >= 2:
                derniere_carte = tas[-1]
                nb_ramasse = len(tas)

                # Si c'est la même carte que celle annoncée -> celui qui clique récupère tout
                if derniere_carte == carte_annoncee:
                    perdant = mon_role
                    nom_perdant = nom_joueur
                    verdict = f"Faux ! C'était bien un {noms_fr[derniere_carte]}."
                # Sinon -> l'autre récupère tout
                else:
                    perdant = autre_role
                    nom_perdant = nom_autre
                    verdict = f"Menteur ! C'était un {noms_fr[derniere_carte]}."

                for c in tas:
                    mains[perdant][c] += 1

                tas = []
                carte_annoncee = None
                carte_actuelle = "dos"
                tour_actuel = perdant

                await envoyer_main("J1")
                await envoyer_main("J2")

                if sum(mains[autre_role].values()) == 0 and perdant == mon_role:
                    partie_finie = True
                    msg_final = f"{verdict} VICTOIRE : {nom_autre} n'a plus de carte !"
                else:
                    msg_final = f"{verdict} {nom_perdant} ramasse {nb_ramasse} carte(s) et recommence."

                await diffuser_aux_joueurs({
                    "type": "carte",
                    "valeur": "dos",
                    "par": msg_final,
                    "tour": tour_actuel,
                    "annonce": None,
                    "taille_tas": 0,
                    "partie_finie": partie_finie
                })

            # Action 3 : Rejouer
            elif action == "rejouer" and partie_finie:
                distribuer_64_cartes()
                await envoyer_main("J1")
                await envoyer_main("J2")
                await diffuser_aux_joueurs({
                    "type": "carte",
                    "valeur": "dos",
                    "par": "Nouvelle partie ! Joueur 1 commence.",
                    "tour": "J1",
                    "annonce": None,
                    "taille_tas": 0,
                    "partie_finie": False
                })

    except WebSocketDisconnect:
        if places[mon_role] == websocket:
            places[mon_role] = None
            carte_actuelle = "dos"
            tas = []
            carte_annoncee = None
            tour_actuel = "J1"
            partie_finie = False
            mains["J1"] = {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
            mains["J2"] = {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
            
            nb_restants = sum(1 for v in places.values() if v is not None)
            await diffuser_aux_joueurs({
                "type": "statut_salle",
                "nb_joueurs": nb_restants,
                "tour": "J1"
            })
