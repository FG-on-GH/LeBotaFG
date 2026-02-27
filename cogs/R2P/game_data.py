import json
import re
import unicodedata
from pathlib import Path

# - - - Variables Globales (Base de données en mémoire) - - - #

# Chemin vers le fichier de sauvegarde
DATA_PATH = Path("./cogs/R2P/game_data.json")

# Dictionnaire : { "id_discord_en_texte": {"jeu1", "jeu2"} }
player_games: dict[str, set[str]] = {}

# Dictionnaire : { "nom_normalise": "Nom d'Affichage" }
game_display_names: dict[str, str] = {}


# - - - Fonctions de traitement - - - #

def normalize_game_name(name: str) -> str:
    """
    Normalise le nom d'un jeu pour faciliter les comparaisons.
    Ex: "Aé. 3" -> "ae3"
    - Passe en minuscules
    - Retire les accents (NFD + ASCII)
    - Supprime tout ce qui n'est pas alphanumérique
    """
    name = name.lower()
    # NFD sépare les lettres de leurs accents, l'encodage ASCII les ignore
    name = unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode('utf-8')
    # Conserve uniquement les lettres (a-z) et les chiffres (0-9)
    name = re.sub(r'[^a-z0-9]', '', name)
    return name


# - - - Fonctions de Sauvegarde et Chargement - - - #

def load_data():
    """
    Charge la base de données depuis le fichier JSON.
    Met à jour les dictionnaires en mémoire sans recréer leur référence.
    """
    global player_games, game_display_names
    
    if not DATA_PATH.exists():
        print("ℹ️ Fichier de sauvegarde introuvable. Démarrage avec une base vierge.")
        return

    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Nettoyage des dictionnaires actuels
            player_games.clear()
            game_display_names.clear()
            
            # Chargement des données (on reconvertit les listes du JSON en sets Python)
            # On utilise les anciennes clés JSON pour ne pas casser ta sauvegarde existante
            loaded_libraries = data.get("player_libraries", {})
            player_games.update({str(k): set(v) for k, v in loaded_libraries.items()})
            
            game_display_names.update(data.get("pretty_print_library", {}))
            
            print("✅ Sauvegarde des jeux chargée avec succès.")
            
    except json.JSONDecodeError:
        print("❌ Erreur : Le fichier de sauvegarde est corrompu.")


def save_data():
    """
    Enregistre l'état actuel des dictionnaires dans le fichier JSON.
    Convertit les sets en listes car le format JSON ne supporte pas les sets.
    """
    # On s'assure que le dossier parent existe avant de sauvegarder
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # On prépare les données avec les clés attendues par ton ancien fichier
    data_to_save = {
        "player_libraries": {str(k): list(v) for k, v in player_games.items()},
        "pretty_print_library": game_display_names,
    }
    
    try:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            # indent=4 permet de rendre le fichier JSON lisible par un humain
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        print("💾 Données sauvegardées avec succès.")
    except IOError as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")