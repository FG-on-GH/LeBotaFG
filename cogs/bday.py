import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

DATA_FILE = "bday.json"

class BDay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # On lance la tâche en arrière-plan dès que le Cog est chargé
        self.check_annivs.start()

    def cog_unload(self):
        # On coupe proprement la tâche si le Cog est déchargé
        self.check_annivs.cancel()

    # --- GESTION DU FICHIER JSON ---
    def load_data(self):
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, "r") as f:
            return json.load(f)

    def save_data(self, data):
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

    # --- COMMANDE /anniv ---
    @app_commands.command(name="anniv", description="Ajoute, modifie ou retire ta date d'anniversaire")
    @app_commands.describe(date="Format JJ/MM ou JJ/MM/AAAA. Laisse vide ou mets 0 pour supprimer.")
    async def anniv(self, interaction: discord.Interaction, date: str = None):
        data = self.load_data()
        user_id = str(interaction.user.id)

        # Suppression
        if not date or date == "0":
            if user_id in data:
                del data[user_id]
                self.save_data(data)
                await interaction.response.send_message("✅ Ton anniversaire a bien été retiré !", ephemeral=True)
            else:
                await interaction.response.send_message("Tu n'avais pas d'anniversaire enregistré.", ephemeral=True)
            return

        # Validation du format
        try:
            # On tente d'abord avec l'année
            parsed_date = datetime.strptime(date, "%d/%m/%Y")
            date_to_save = parsed_date.strftime("%d/%m/%Y")
        except ValueError:
            try:
                # On tente ensuite sans l'année
                parsed_date = datetime.strptime(date, "%d/%m")
                date_to_save = parsed_date.strftime("%d/%m")
            except ValueError:
                # Si les deux échouent, le format est mauvais
                await interaction.response.send_message(
                    "❌ Format invalide. Utilise `JJ/MM` (ex: 15/04) ou `JJ/MM/AAAA` (ex: 15/04/1998).", 
                    ephemeral=True
                )
                return

        # Sauvegarde
        data[user_id] = date_to_save
        self.save_data(data)
        await interaction.response.send_message(f"🎉 C'est noté ! Ton anniversaire est enregistré pour le **{date_to_save}**.", ephemeral=True)

    # --- TÂCHE QUOTIDIENNE (10h00, heure de Paris) ---
    tz = ZoneInfo("Europe/Paris")
    run_at = time(hour=10, minute=0, tzinfo=tz)

    @tasks.loop(time=run_at)
    async def check_dates(self):
        # On attend que le bot soit prêt avant de chercher des salons
        await self.bot.wait_until_ready()
        
        channel_id = os.getenv("GENERAL_CHANNEL_ID")
        if not channel_id:
            print("Erreur : GENERAL_CHANNEL_ID manquant dans le .env")
            return
            
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            print(f"Erreur : Impossible de trouver le channel avec l'ID {channel_id}")
            return

        data = self.load_data()
        today = datetime.now(self.tz)
        today_str_no_year = today.strftime("%d/%m") # Format: "15/04"

        annivs_du_jour = []

        for uid, date_str in data.items():
            # Si la date (ex: "15/04/1998" ou "15/04") commence par la date du jour ("15/04")
            if date_str.startswith(today_str_no_year):
                age = None
                # année de précisée -> longueur > 5
                if len(date_str) > 5:
                    year = int(date_str[6:])
                    age = today.year - year
                annivs_du_jour.append((uid, age))

        # Envoi des messages
        for uid, age in annivs_du_jour:
            msg = f"🎂 Joyeux anniversaire <@{uid}> !"
            if age is not None:
                msg += f" Ça te fait **{age} ans** aujourd'hui ! 🥳"
            await channel.send(msg)

async def setup(bot):
    await bot.add_cog(BDay(bot))