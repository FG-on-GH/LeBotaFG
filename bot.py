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

# Création de l'objet bot avec le préfixe qui sera utilisé pour les commandes et le permissions accordées
bot = commands.Bot(command_prefix=commands.when_mentioned_or('/'), intents=intents)

@bot.event
async def on_ready():   # Evènement automatiquement déclenché quand le bot est connecté et prêt
    print(f'Connecté en tant que {bot.user}')


@bot.command()
async def salut(ctx):
    await ctx.send(f'Salut {ctx.author.name} !')
# ctx.send : envoie un message dans le même salon que le contexte de la commande

bot.run(TOKEN)