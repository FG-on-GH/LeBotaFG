import discord
from discord.ext import commands
from discord import app_commands
from cogs.R2P.manage_libraries import *


class MyGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='mygames', description='Affiche tes jeux enregistrés dans la base de données')
    async def mygames(self, interaction:discord.Interaction):

        playerID = interaction.user.id
        validation_message=""
        load_data()

        if playerID not in player_libraries or not player_libraries[playerID]:
            await interaction.response.send_message("Je n'ai aucun jeux enregistré pour toi... Utilise /addgame pour avoir accès à toutes mes autres fonctionnalités !", ephemeral=True)
            return
        
        for reg_title in player_libraries[playerID]:
            validation_message+=(pretty_print_library[reg_title]+", ")
        validation_message=validation_message[:-2] # retire la virgule en trop quand on a parcouru toute la liste
        await interaction.response.send_message(f"Voici tous les jeux que tu as ajouté :\n{validation_message}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MyGames(bot))