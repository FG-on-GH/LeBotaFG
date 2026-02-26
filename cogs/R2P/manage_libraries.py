# Sauvegarder les listes entre les redémarrages
import json
from pathlib import Path
# Pour le nettoyage du texte
import re
import unicodedata



# - - - Fonctions de sauvegarde - - - #

data_path=Path("./cogs/R2P/game_libraries.json")
player_libraries = {}
pretty_print_library = {}

def load_data():
    '''Charge la sauvegarde des noms d'affichage et des bibliothèque de joueurs si elle existe'''
    try:
        with open(data_path, "r") as f:
            data = json.load(f)
            # On recrée les ensembles (sets) à partir de la sauvegarde
            player_libraries = {k: set(v) for k, v in data.get("player_libraries", {}).items()}
            pretty_print_library = data.get("pretty_print_library", {})
    except FileNotFoundError:
        player_libraries = {}
        pretty_print_library = {}

def save_data():
    '''Enregistre la sauvegarde des noms d'affichage et des bibliothèque de joueurs dans game_libraries.json'''
    data = {
        "player_libraries": {k: list(v) for k, v in player_libraries.items()},
        "pretty_print_library": pretty_print_library
    }
    with open(data_path, "w") as f:
        json.dump(data, f)



def reg_name(name):
    '''Fonction pour régulariser les noms données par les utilisateurs lorsqu'ils cherchent à ajouter un jeu
    Retire les accents, la ponctuation, les espaces. Passe toutes les lettres en minuscules
    Ex: Aé. 3 devient ae3'''
    name=name.lower()
    # NFD sépare les lettres de leurs accents, puis on ignore les accents en passant par l'ASCII
    name = unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode('utf-8')
    # Ne garder que lettres et chiffres)
    name = re.sub(r'[^a-z0-9]', '', name)
    return name