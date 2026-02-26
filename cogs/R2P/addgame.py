import discord
from discord.ext import commands
from discord import app_commands
from manage_libraries import *


class AddGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='addgame', description='Ajoute des jeux à ta bibliothèque (virgule entre chaque titre)')
    async def addgame(self, interaction:discord.Interaction, Jeux:str):

        player = interaction.user.name
        validation_message=""
        load_data()

        # Création d'une liste avec le titre de chaque jeu
        title_list=[title.strip() for title in Jeux.split(",") if title.strip()]
        if not title_list:
            await interaction.response.send_message("Aucun titre de jeu reçu", ephemeral=True)
            return
        
        for title in title_list:
            reg_title=reg_name(title)
            if reg_title not in pretty_print_library:
                pretty_print_library[reg_title]=title
            else:
                title=pretty_print_library[reg_title]
            if player not in player_libraries:
                player_libraries[player]=set()
            if reg_title in player_libraries[player]:
                validation_message+=(title+" déjà présent\n")
            else:
                player_libraries[player].add(reg_title)
                validation_message+=(title+" ajouté :white_check_mark:\n")
        
        save_data()
        await interaction.response.send_message(validation_message, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AddGame(bot))