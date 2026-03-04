import discord
from discord.ext import commands
import random
import re
import os
import asyncio

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        feur_role_id = os.getenv('FEUR_ROLE_ID')
        self.reponses = [
            "feur !",
            "drilatère !",
            "feur !",
            "quoicoubeh !",
            "ffffffffffffffffffffffffffffffffffffffffffeur",
            "feur !",
            "( ͡° ͜ʖ ͡°) chuis sympa pour cette fois",
            "feur !",
            f"@<{feur_role_id}> je te le laisse celui là"
        ]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Toujours ignorer les messages du bot pour éviter les boucles infinies
        if message.author.bot:
            return

        content=message.content

        # ^ : force à chercher au tout début du message
        # (?:je\s+suis|je\s+m['’\s]?appelle) : cherche "je suis" OU "je m'appelle" (avec ou sans apostrophe/espace)
        # \s+(.+) : récupère absolument tout ce qui suit après un espace
        match_nom = re.match(r"^(?:je\s+suis|je\s+m['’\s]?appelle)\s+(.+)", content, re.IGNORECASE)
        
        if match_nom:
            # On récupère le nouveau nom et on le limite à 32 caractères (limite Discord)
            nouveau_nom = match_nom.group(1).strip()[:32]
            
            # On sauvegarde le pseudo actuel (None si la personne n'a pas de pseudo personnalisé)
            ancien_nom = message.author.nick
            
            try:
                # On change le pseudo
                await message.author.edit(nick=nouveau_nom)

                # Fonction asynchrone pour attendre et remettre l'ancien pseudo
                async def restaurer_pseudo():
                    # Calcul du temps aléatoire entre 2h et 12h (en secondes)
                    heures = random.randint(2, 12)
                    secondes = heures * 3600
                    
                    await asyncio.sleep(secondes)
                    
                    try:
                        # On remet l'ancien pseudo
                        await message.author.edit(nick=ancien_nom)
                    except discord.Forbidden:
                        pass # On ignore si les permissions ont changé entre temps

                # On lance le chronomètre en arrière-plan sans bloquer le reste du bot
                self.bot.loop.create_task(restaurer_pseudo())

            except discord.Forbidden:
                # Le bot n'a pas la permission (ex: proprio serv)
                print("Rename forbidden")
                pass

        # Expression régulière (Regex) pour détecter le "quoi"
        # [\s\W]*$ : Autorise n'importe quel espace ou ponctuation jusqu'à la fin de la ligne ($)
        # re.IGNORECASE : Ignore les majuscules/minuscules
        if re.search(r'quoi[\s\W]*$', content, re.IGNORECASE):
            if random.randint(1, 4) == 1:
                mot_choisi = random.choice(self.reponses)
                await message.reply(mot_choisi)
        
        elif re.search(r'oui[\s\W]*$', content, re.IGNORECASE):
            if random.randint(1, 4) == 1:
                await message.reply("stiti !")

        elif re.search(r'non[\s\W]*$', content, re.IGNORECASE):
            if random.randint(1, 4) == 1:
                await message.reply("bril !")

async def setup(bot):
    await bot.add_cog(Fun(bot))