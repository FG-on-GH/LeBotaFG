import discord
from discord.ext import commands
from discord import app_commands
from cogs.R2P.manage_libraries import *

class RemoveGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='removegame', description='Retire des jeux de ta bibliothèque (virgule entre chaque titre)')
    async def removegame(self, interaction: discord.Interaction, jeux: str):

        playerID = interaction.user.id
        validation_message = ""
        load_data()

        # Vérifier si le joueur a une bibliothèque et si elle n'est pas vide
        if playerID not in player_libraries or not player_libraries[playerID]:
            await interaction.response.send_message("Ta bibliothèque est déjà vide !", ephemeral=True)
            return

        # Création de la liste des jeux à retirer
        title_list = [title.strip() for title in jeux.split(",") if title.strip()]
        if not title_list:
            await interaction.response.send_message("Aucun titre de jeu reçu.", ephemeral=True)
            return
        
        for title in title_list:
            reg_title = reg_name(title)
            if reg_title not in pretty_print_library:
                pretty_print_library[reg_title]=title
            else:
                title=pretty_print_library[reg_title]
            # Vérifier si le jeu est bien dans la bibliothèque du joueur
            if reg_title in player_libraries[playerID]:
                player_libraries[playerID].remove(reg_title)
                validation_message += f"{title} a été retiré :x:\n"
            else:
                validation_message += f"{title} n'était pas dans ta bibliothèque ¯\\_(ツ)_/¯\n"
        
        save_data()
        await interaction.response.send_message(validation_message, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RemoveGame(bot))