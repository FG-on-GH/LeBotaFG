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
        super().__init__(command_prefix=commands.when_mentioned_or('!'), intents=intents)

    # setup_hook appelée automatiquement juste avant que le bot se connecte
    async def setup_hook(self):
        # Parcourt des fichiers du dossier cogs
        for root, dirs, files in os.walk("./cogs"):
            for filename in files:
                if filename.endswith(".py"):
                    path = os.path.relpath(os.path.join(root, filename), ".")
                    extension = path.replace(os.sep, ".")[:-3]
                    try:
                        await bot.load_extension(extension)
                        print(f"{extension} - chargé")
                    except Exception as e:
                        print(f"{extension} - erreur : {e}")
            
        await self.tree.sync()
        print("Slash-commands synced")

bot = LeBotaFG()

@bot.event
async def on_ready():       # Evènement automatiquement déclenché quand le bot est connecté et prêt
    print(f'Connecté en tant que {bot.user}')

bot.run(TOKEN)