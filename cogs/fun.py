import discord
from discord.ext import commands
import random
import re
import asyncio
import json
import os

DATA_FILE = "cogs/pseudos.json"

class Quoifeur(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.reponses_quoi = [
            "feur !",
            "chi !",
            "drilatère !",
            "ffeur !",
            "cou !",
            "artz !"
        ]

    # --- GESTION DU FICHIER JSON ---
    def load_pseudos(self):
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, "r") as f:
            return json.load(f)

    def save_pseudos(self, data):
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

    # --- ÉVÉNEMENT AU DÉMARRAGE DU COG ---
    async def cog_load(self):
        # On lance la tâche en arrière-plan pour ne pas bloquer le démarrage du bot
        self.bot.loop.create_task(self.restaurer_pseudos_au_demarrage())

    async def restaurer_pseudos_au_demarrage(self):
        # On attend que le bot soit totalement connecté à Discord
        await self.bot.wait_until_ready()
        
        data = self.load_pseudos()
        if not data:
            return # Rien à restaurer

        print("🔄 Restauration des pseudos suite à un redémarrage...")
        
        # On copie les clés dans une liste pour pouvoir modifier le dictionnaire original en toute sécurité
        cles_a_supprimer = []

        for key, ancien_nom in data.items():
            try:
                guild_id_str, user_id_str = key.split("-")
                guild = self.bot.get_guild(int(guild_id_str))
                
                if guild:
                    member = guild.get_member(int(user_id_str)) or await guild.fetch_member(int(user_id_str))
                    if member:
                        # Si ancien_nom est None, ça remet le nom par défaut de l'utilisateur
                        await member.edit(nick=ancien_nom)
                        print(f"✅ Pseudo de {member.name} restauré.")
                        cles_a_supprimer.append(key)
            except discord.Forbidden:
                print(f"❌ Permission manquante pour restaurer {key}.")
                cles_a_supprimer.append(key) # On supprime quand même pour ne pas bloquer en boucle
            except Exception as e:
                print(f"⚠️ Erreur avec {key} : {e}")

        # On nettoie le fichier JSON
        for cle in cles_a_supprimer:
            if cle in data:
                del data[cle]
        
        self.save_pseudos(data)

    # --- ÉCOUTEUR DE MESSAGES ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        content = message.content

        # ---------------------------------------------------------
        # JE SUIS / JE M'APPELLE
        # ---------------------------------------------------------
        match_nom = re.match(r"^(?:je\s+suis|je\s+m['’\s]?appelle)\s+(.+)", content, re.IGNORECASE)
        
        if match_nom:
            data = self.load_pseudos()
            cle = f"{message.guild.id}-{message.author.id}"

            # Si la personne est déjà dans le fichier, on ne fait rien
            # Sinon, elle pourrait écraser son vrai pseudo de secours par son pseudo de blague !
            if cle not in data:
                nouveau_nom = match_nom.group(1).strip()[:32]
                ancien_nom = message.author.nick
                
                try:
                    # On sauvegarde d'abord dans le JSON
                    data[cle] = ancien_nom
                    self.save_pseudos(data)

                    # Puis on change le pseudo
                    await message.author.edit(nick=nouveau_nom)

                    
                    # Chronomètre en arrière-plan
                    async def restaurer_pseudo():
                        heures = random.randint(2, 12)
                        await asyncio.sleep(heures * 3600)
                        
                        try:
                            # On restaure le pseudo
                            await message.author.edit(nick=ancien_nom)
                            
                            # On retire la personne du fichier JSON car le timer est fini
                            donnees_actuelles = self.load_pseudos()
                            if cle in donnees_actuelles:
                                del donnees_actuelles[cle]
                                self.save_pseudos(donnees_actuelles)
                                
                        except discord.Forbidden:
                            pass 

                    self.bot.loop.create_task(restaurer_pseudo())

                except discord.Forbidden:
                    # Si le bot n'a pas les droits, on annule l'enregistrement dans le JSON
                    del data[cle]
                    self.save_pseudos(data)

        # ---------------------------------------------------------
        # QUOI / OUI / NON
        # ---------------------------------------------------------
        if re.search(r'quoi[\s\W]*$', content, re.IGNORECASE):
            if random.randint(1, 4) == 1:
                await message.reply(random.choice(self.reponses_quoi))

        elif re.search(r'oui[\s\W]*$', content, re.IGNORECASE):
            if random.randint(1, 4) == 1:
                await message.reply("stiti !")

        elif re.search(r'non[\s\W]*$', content, re.IGNORECASE):
            if random.randint(1, 4) == 1:
                await message.reply("bril !")

async def setup(bot):
    await bot.add_cog(Quoifeur(bot))