import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
from datetime import datetime

class ChuchoterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fichier_logs = "cogs/shush_logs.json" # Nom du fichier de sauvegarde

    def save_log(self, interaction: discord.Interaction, message: str):
        """Fonction qui gère la sauvegarde dans le fichier JSON."""
        
        new_log = {
            "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "author_name": str(interaction.user),
            "author_id": interaction.user.id,
            "channel": interaction.channel.name if interaction.channel else "Inconnu",
            "message": message
        }

        logs = []
        
        if os.path.exists(self.fichier_logs):
            with open(self.fichier_logs, "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []

        logs.append(new_log)

        # On garde uniquement les 50 derniers éléments
        if len(logs) > 50:
            logs = logs[-50:]
        
        with open(self.fichier_logs, "w", encoding="utf-8") as f:
            # indent=4 permet de rendre le fichier lisible pour un humain
            json.dump(logs, f, indent=4, ensure_ascii=False)


    @app_commands.command(name="chuchoter", description="Envoie un message 83,33% anonyme !")
    @app_commands.describe(message="Le message que tu veux envoyer")
    async def chuchoter(self, interaction: discord.Interaction, message: str):
        
        self.save_log(interaction, message)
        chance = random.randint(1, 6)
        
        await interaction.response.send_message("🤫 Ton message a bien été envoyé en mode ninja !", ephemeral=True)
           
        if chance == 1:
            await interaction.channel.send(f'Quelqu\'un m\'a chuchoté : "{message}"\nJe balance, c\'est {interaction.user.mention} !')
        else:
            await interaction.channel.send(f'Quelqu\'un m\'a chuchoté : "{message}"')

async def setup(bot):
    await bot.add_cog(ChuchoterCog(bot))