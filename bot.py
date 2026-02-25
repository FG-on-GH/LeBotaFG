import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Charge le token du bot contenu dans un fichier caché ".env"
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Charge les permissions discord basiques et lecture de message
intents = discord.Intents.default()
intents.message_content = True

# On crée une classe spécifique pour le bot héritant de la classe Discord de base
class LeBotaFG(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('/'), intents=intents)

    # setup_hook appelée automatiquement juste avant que le bot se connecte
    async def setup_hook(self):
        # Parcourt des fichiers du dossier cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                # Si le fichier est un python on charge l'extension
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"Cog chargé : {filename}")

bot = LeBotaFG()

@bot.event
async def on_ready():       # Evènement automatiquement déclenché quand le bot est connecté et prêt
    print(f'Connecté en tant que {bot.user}')

bot.run(TOKEN)