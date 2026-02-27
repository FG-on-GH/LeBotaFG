import discord
from discord.ext import commands
from discord import app_commands

# Importation de notre nouveau gestionnaire de base de données
# Assure-toi que le nom du fichier correspond bien à ce que tu as choisi (ex: game_data)
from cogs.R2P.game_data import (
    load_data, 
    save_data, 
    normalize_game_name, 
    player_games, 
    game_display_names
)

class ManageGames(commands.Cog):
    """
    Cog regroupant toutes les commandes liées à la gestion 
    de la bibliothèque de jeux personnelle de l'utilisateur.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='addgame', description='Ajoute des jeux à ta bibliothèque (sépare les titres par des virgules)')
    async def addgame(self, interaction: discord.Interaction, jeux: str):
        """Commande pour ajouter un ou plusieurs jeux."""
        # On convertit l'ID en chaîne de caractères car le format JSON stocke les clés en texte
        user_id = str(interaction.user.id)
        validation_message = ""
        
        load_data()

        # Découpage de la chaîne de texte en liste de jeux (séparés par des virgules)
        # strip() enlève les espaces inutiles avant et après le nom du jeu
        title_list = [title.strip() for title in jeux.split(",") if title.strip()]
        
        if not title_list:
            await interaction.response.send_message("❌ Aucun titre de jeu valide reçu.", ephemeral=True)
            return
        
        # Initialisation de la bibliothèque du joueur si elle n'existe pas
        if user_id not in player_games:
            player_games[user_id] = set()

        for title in title_list:
            norm_title = normalize_game_name(title)
            
            # Mise à jour du dictionnaire d'affichage si le jeu est nouveau
            if norm_title not in game_display_names:
                game_display_names[norm_title] = title
            else:
                # On récupère le nom avec la bonne casse s'il existait déjà
                title = game_display_names[norm_title]
            
            # Ajout dans la bibliothèque du joueur
            if norm_title in player_games[user_id]:
                validation_message += f"**{title}** est déjà dans ta bibliothèque.\n"
            else:
                player_games[user_id].add(norm_title)
                validation_message += f"✅ **{title}** a été ajouté !\n"
        
        save_data()
        await interaction.response.send_message(validation_message, ephemeral=True)

    @app_commands.command(name='removegame', description='Retire des jeux de ta bibliothèque (sépare les titres par des virgules)')
    async def removegame(self, interaction: discord.Interaction, jeux: str):
        """Commande pour retirer un ou plusieurs jeux."""
        user_id = str(interaction.user.id)
        validation_message = ""
        
        load_data()

        # Vérification si le joueur a une bibliothèque et si elle n'est pas vide
        if user_id not in player_games or not player_games[user_id]:
            await interaction.response.send_message("⚠️ Ta bibliothèque est déjà vide !", ephemeral=True)
            return

        title_list = [title.strip() for title in jeux.split(",") if title.strip()]
        
        if not title_list:
            await interaction.response.send_message("❌ Aucun titre de jeu valide reçu.", ephemeral=True)
            return
        
        for title in title_list:
            norm_title = normalize_game_name(title)
            
            # Récupération du nom d'affichage correct s'il existe (sinon on garde la saisie de l'utilisateur)
            display_title = game_display_names.get(norm_title, title)
            
            if norm_title in player_games[user_id]:
                player_games[user_id].remove(norm_title)
                validation_message += f"❌ **{display_title}** a été retiré.\n"
            else:
                validation_message += f"🤷 **{display_title}** n'était pas dans ta bibliothèque.\n"
        
        save_data()
        await interaction.response.send_message(validation_message, ephemeral=True)

    @app_commands.command(name='mygames', description='Affiche tes jeux enregistrés dans la base de données')
    async def mygames(self, interaction: discord.Interaction):
        """Commande pour lister les jeux du joueur."""
        user_id = str(interaction.user.id)
        
        load_data()

        # Si le joueur n'a pas de bibliothèque ou qu'elle est vide
        if user_id not in player_games or not player_games[user_id]:
            await interaction.response.send_message(
                "📭 Je n'ai aucun jeu enregistré pour toi... Utilise `/addgame` pour commencer !", 
                ephemeral=True
            )
            return
        
        # Création de la liste des noms d'affichage
        display_list = [game_display_names.get(norm_title, norm_title) for norm_title in player_games[user_id]]
        
        # Petit bonus : on trie la liste par ordre alphabétique (insensible à la casse)
        display_list.sort(key=str.casefold)
        
        # .join() permet de lier tous les éléments de la liste avec ", " proprement
        validation_message = ", ".join(display_list)
        
        await interaction.response.send_message(
            f"🎮 **Voici les jeux dans ta bibliothèque :**\n{validation_message}", 
            ephemeral=True
        )

# Obligatoire pour charger le Cog
async def setup(bot: commands.Bot):
    await bot.add_cog(ManageGames(bot))