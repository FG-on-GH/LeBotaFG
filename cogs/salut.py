import discord
from discord.ext import commands

class Salut(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Dans un Cog, on utilise @commands.command() au lieu de @bot.command()
    # et la fonction prend "self" comme premier argument !
    @commands.command()
    async def salut(self, ctx):
        await ctx.send(f'Salut {ctx.author.display_name} !')

# Obligatoire à la fin de chaque fichier Cog
# Permet au fichier principal d'ajouter ce module au bot
async def setup(bot):
    await bot.add_cog(Salut(bot))