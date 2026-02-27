import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

class LeBotaFG(commands.Bot):
    """
    Classe principale du bot. 
    Gère la configuration initiale et le chargement dynamique des modules (Cogs).
    """
    def __init__(self):
        # Configuration des permissions (intents) nécessaires au bot
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        # Initialisation de la classe parente commands.Bot
        super().__init__(
            command_prefix=commands.when_mentioned_or('!'), 
            intents=intents
        )

    async def setup_hook(self):
        """
        Méthode exécutée automatiquement avant la connexion à Discord.
        C'est l'endroit idéal pour charger les Cogs et synchroniser l'arbre des commandes.
        """
        print("Initialisation : Chargement des extensions (Cogs)...")
        
        # Parcours dynamique du dossier 'cogs' et de ses sous-dossiers
        for root, dirs, files in os.walk("./cogs"):
            for filename in files:
                if filename.endswith(".py"):
                    # Transformation du chemin d'accès en format module (ex: cogs.R2P.manage_libraries)
                    path = os.path.relpath(os.path.join(root, filename), ".")
                    extension = path.replace(os.sep, ".")[:-3]
                    
                    try:
                        # Utilisation de 'self' pour charger l'extension dans l'instance courante
                        await self.load_extension(extension)
                        print(f"✅ {extension} - chargé")
                    except Exception as e:
                        print(f"❌ {extension} - erreur : {e}")
        
        # Synchronisation des commandes slash (UI) avec l'API Discord
        await self.tree.sync()
        print("🌐 Commandes Slash synchronisées avec succès.")

    async def on_ready(self):
        """
        Événement déclenché quand le bot est connecté à Discord et prêt à interagir.
        Remplacement du décorateur @bot.event par la surcharge de la méthode.
        """
        print(f'🤖 Connecté en tant que {self.user} (ID: {self.user.id})')
        print('--- Le bot est opérationnel ---')


def main():
    """Point d'entrée du programme."""
    # Charge le token depuis le fichier caché ".env"
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    if not TOKEN:
        print("Erreur critique : Aucun token Discord (DISCORD_TOKEN) trouvé dans le fichier .env")
        return

    # Création de l'instance du bot et lancement
    bot = LeBotaFG()
    bot.run(TOKEN)

# S'assure que le bot ne se lance que si ce fichier est exécuté directement
if __name__ == '__main__':
    main()