import discord
from discord.ext import commands
import random
import re
import os


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