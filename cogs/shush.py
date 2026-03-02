import discord
from discord.ext import commands
from discord import app_commands

class Shush(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="chuchoter", description="Envoie un message de façon 100% anonyme.")
    @app_commands.describe(message="Le message que tu veux envoyer anonymement")
    async def chuchoter(self, interaction: discord.Interaction, message: str):
        
        # On valide l'interaction de manière invisible pour les autres
        await interaction.response.send_message("🤫 Ton message a bien été envoyé !", ephemeral=True)
        
        # Le bot envoie le message publiquement
        await interaction.channel.send(f'Quelqu\'un m\'a chuchoté : "{message}"')

async def setup(bot):
    await bot.add_cog(Shush(bot))