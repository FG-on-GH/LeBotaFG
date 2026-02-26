import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv

load_dotenv()

class R2P(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ready", description="T'ajoute à la liste des personnes prêtes à jouer")
    async def ready(self, interaction: discord.Interaction):
        channelID=int(os.getenv('READY_CHANNEL_ID'))
        channel=self.bot.get_channel(channelID)
        playerID=interaction.user.name
        name=interaction.user.display_name
        await channel.send(f"{name} est prêt à jouer !")
        await interaction.response.send_message("Tu as bien été ajouté à la liste des joueurs prêts", ephemeral=True)

async def setup(bot):
    await bot.add_cog(R2P(bot))