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
            "drilatère !",
            "feur !",
            "quoicoubeh !",
            "feur"
            "ffffffffffffffffffffffffffffffffffffffffffeur",
            "feur !",
            "( ͡° ͜ʖ ͡°) chuis sympa pour cette fois",
            "feur !",
            f"@<{feur_role_id}> je te le laisse celui là"
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
        # BLAGUE "JE SUIS / JE M'APPELLE"
        # ---------------------------------------------------------
        match_nom = re.match(r"^(?:je\s+suis|je\s+m['’\s]?appelle)\s+(.+)", content, re.IGNORECASE)
        
        if match_nom:
            cle = f"{message.guild.id}-{message.author.id}"
            data = self.load_pseudos()
            
            # 1. On détermine le vrai pseudo d'origine
            if cle in data:
                # Si la personne est déjà dans le fichier, on garde le VRAI nom intact
                ancien_nom = data[cle] 
            else:
                # Si c'est la première fois, on prend son pseudo actuel
                ancien_nom = message.author.nick 
                
            nouveau_nom = match_nom.group(1).strip()[:32]

            try:
                # 2. On change le pseudo
                await message.author.edit(nick=nouveau_nom)
                await message.add_reaction("👋")

                # 3. Si ça a réussi, on sauvegarde dans le JSON (seulement si c'est nouveau)
                if cle not in data:
                    data[cle] = ancien_nom
                    self.save_pseudos(data)

                # 4. Gestion des chronomètres (on annule l'ancien si la personne refait la blague)
                if cle in self.timers:
                    self.timers[cle].cancel()

                # 5. On crée le nouveau compte à rebours
                async def restaurer_pseudo():
                    heures = random.randint(2, 12)
                    await asyncio.sleep(heures * 3600)
                    
                    try:
                        # Fin du temps : on restaure
                        await message.author.edit(nick=ancien_nom)
                        
                        # On nettoie le fichier JSON
                        donnees_actuelles = self.load_pseudos()
                        if cle in donnees_actuelles:
                            del donnees_actuelles[cle]
                            self.save_pseudos(donnees_actuelles)
                            
                    except discord.Forbidden:
                        pass 
                    finally:
                        # On retire le timer de la mémoire
                        if cle in self.timers:
                            del self.timers[cle]

                # On lance la tâche et on la stocke dans notre dictionnaire self.timers
                tache = self.bot.loop.create_task(restaurer_pseudo())
                self.timers[cle] = tache

            except discord.Forbidden:
                # Le bot n'a pas les permissions (ex: membre trop haut gradé)
                pass

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