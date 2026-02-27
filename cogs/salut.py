import discord
from discord.ext import commands
from discord import app_commands

class Salut(commands.Cog):
    """
    Un module (Cog) très simple pour démontrer le fonctionnement des commandes Slash.
    C'est la structure de base à reproduire pour créer de nouvelles fonctionnalités.
    """
    
    def __init__(self, bot: commands.Bot):
        # On stocke une référence au bot principal pour pouvoir l'utiliser si besoin
        self.bot = bot
    
    # Le décorateur @app_commands.command transforme la méthode en commande Slash
    # name = le mot à taper (ex: /salut)
    # description = l'explication affichée par Discord en grisé
    @app_commands.command(name="salut", description="Le bot te dit bonjour de manière personnalisée")
    async def salut(self, interaction: discord.Interaction):
        """
        Exécute la commande /salut.
        Répond simplement avec le pseudo de l'utilisateur.
        """
        # interaction.user contient toutes les infos sur la personne qui a tapé la commande
        pseudo = interaction.user.display_name
        
        # interaction.response.send_message() est la façon standard de répondre à une Slash-Commande
        await interaction.response.send_message(f'Salut {pseudo} 😄 !')


async def setup(bot: commands.Bot):
    """
    Fonction asynchrone obligatoire à la fin de chaque fichier Cog.
    Elle est appelée par setup_hook() dans bot.py pour lier ce module au bot.
    """
    await bot.add_cog(Salut(bot))