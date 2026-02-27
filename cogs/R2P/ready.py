import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv

load_dotenv()

# Ensemble pour stocker les joueurs prêts
readies=list()

class ready(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ready", description="T'ajoute à la liste des personnes prêtes à jouer")
    async def ready(self, interaction: discord.Interaction):
        ready_channel_ID=int(os.getenv('READY_CHANNEL_ID'))
        channel=self.bot.get_channel(ready_channel_ID) 
        player_mention=interaction.user.mention
        if len(readies)==0:
            await channel.send(f"{player_mention} est prêt à jouer !")
        else:
            ready_mentions=player_mention+","
            for name in readies:
                ready_mentions+=(name+", ")
            ready_mentions=ready_mentions[:-2]
            await channel.send(f"Joueurs prêts :\n{ready_mentions}")
        readies.append(player_mention)
        await interaction.response.send_message("Tu as bien été ajouté à la liste des joueurs prêts", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ready(bot))