import discord
from discord.ext import commands
from discord import app_commands

class Salut(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Mis en place d'une "Slash-Commande" visible dans l'UI
    @app_commands.command(name="salut", description="Le bot te dit bonjour de manière personnalisée")
    async def salut(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Salut {interaction.user.display_name} :smile: !')


# Obligatoire à la fin de chaque fichier Cog
# Permet au fichier principal d'ajouter ce module au bot
async def setup(bot):
    await bot.add_cog(Salut(bot))