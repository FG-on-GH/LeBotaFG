import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv

# Importation de notre nouvelle base de données
from cogs.R2P.game_data import player_games, game_display_names, load_data

load_dotenv()

class ReadyManager(commands.Cog):
    """
    Cog gérant le système de matchmaking (LFG - Looking For Group).
    Permet aux joueurs de se déclarer prêts, calcule les jeux en commun,
    et maintient une annonce à jour dans un salon dédié.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # État du système
        self.ready_players: list[int] = []
        
        # Gestion de l'annonce
        self.announcement_file = Path("./cogs/R2P/last_announcement_id.json")
        
        # Dictionnaires pour stocker les tâches asynchrones (chronomètres) par ID utilisateur
        self.offline_timers: dict[int, asyncio.Task] = {}
        self.timeout_timers: dict[int, asyncio.Task] = {}
        self.pending_timers: dict[int, asyncio.Task] = {}
        self.grace_timers: dict[int, asyncio.Task] = {}
        
        # Chargement initial des jeux
        load_data()

    # --- GESTION DE L'ANNONCE ---

    def _get_last_announcement_id(self) -> int | None:
        """Récupère l'ID du dernier message d'annonce."""
        try:
            with open(self.announcement_file, "r") as f:
                return json.load(f).get("last_announcement_id")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_last_announcement_id(self, message_id: int):
        """Sauvegarde l'ID du nouveau message d'annonce."""
        self.announcement_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.announcement_file, "w") as f:
            json.dump({"last_announcement_id": message_id}, f)

    def find_common_games(self) -> tuple[list[str], list[int]]:
        """
        Croise les bibliothèques des joueurs prêts.
        Retourne : (Liste des jeux en commun formatés, Liste des joueurs sans jeu)
        """
        sets_of_games = []
        excluded_users = []
        
        for uid in self.ready_players:
            str_id = str(uid)
            if str_id in player_games and player_games[str_id]:
                sets_of_games.append(player_games[str_id])
            else:
                excluded_users.append(uid)
        
        if not sets_of_games:
            return [], excluded_users

        # Intersection de tous les sets de jeux
        common_games = set.intersection(*sets_of_games)
        
        # On récupère les noms d'affichage et on les trie par ordre alphabétique
        pretty_games = sorted(
            [game_display_names.get(game, game) for game in common_games],
            key=str.casefold
        )
        
        return pretty_games, excluded_users

    async def update_announcement(self):
        """Génère l'annonce Embed, supprime l'ancienne et publie la nouvelle."""
        channel_id = int(os.getenv('READY_CHANNEL_ID', 0))
        channel = self.bot.get_channel(channel_id)
        
        if not channel:
            print("⚠️ Attention : Salon d'annonce introuvable (Vérifiez READY_CHANNEL_ID dans le .env).")
            return

        # 1. Construction de l'Embed
        if not self.ready_players:
            embed = discord.Embed(
                title="🔴 En attente de joueurs", 
                description="Personne n'est prêt pour le moment.\nUtilisez `/ready` pour vous ajouter.", 
                color=discord.Color.red()
            )
        elif len(self.ready_players) == 1:
            embed = discord.Embed(
                title="🟠 Un joueur est prêt !", 
                description=f"<@{self.ready_players[0]}> est prêt à jouer ! On attend les autres...", 
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="🟢 Des joueurs sont prêts !", 
                description="Voici le récapitulatif pour la session :",
                color=discord.Color.green()
            )
            
            ready_mentions = "\n".join([f"<@{uid}>" for uid in self.ready_players])
            embed.add_field(name="Joueurs", value=ready_mentions, inline=False)
            
            common_games, excluded_users = self.find_common_games()
            
            if not common_games:
                embed.add_field(name="Jeux en commun", value="*Aucun jeu en commun trouvé*", inline=False)
            else:
                games_str = "\n".join(common_games)
                embed.add_field(name="Jeux en commun", value=games_str, inline=False)
                
            if excluded_users:
                excluded_str = ", ".join([f"<@{uid}>" for uid in excluded_users])
                embed.add_field(
                    name="⚠️ Joueurs sans jeux enregistrés", 
                    value=f"{excluded_str}\n*Utilisez `/addgame` pour en ajouter puis refaites `/ready`.*", 
                    inline=False
                )

        # 2. Suppression de l'ancienne annonce
        last_id = self._get_last_announcement_id()
        if last_id:
            try:
                old_msg = await channel.fetch_message(last_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass 
                
        # 3. Envoi et sauvegarde de la nouvelle annonce
        new_msg = await channel.send(embed=embed)
        self._save_last_announcement_id(new_msg.id)


    # --- CHRONOMÈTRES ET TIMERS ---

    def cancel_all_timers(self, user_id: int):
        """Annule tous les chronomètres liés à un joueur pour éviter les conflits."""
        for timer_dict in [self.offline_timers, self.timeout_timers, self.pending_timers, self.grace_timers]:
            if user_id in timer_dict:
                timer_dict[user_id].cancel()
                del timer_dict[user_id]

    async def auto_remove_offline(self, user_id: int):
        """Retire le joueur après 5 minutes de déconnexion."""
        try:
            await asyncio.sleep(5 * 60) # 5 minutes
            
            if user_id in self.ready_players:
                self.ready_players.remove(user_id)
            
            # Nettoyage global
            if user_id in self.offline_timers: del self.offline_timers[user_id]
            if user_id in self.timeout_timers:
                self.timeout_timers[user_id].cancel()
                del self.timeout_timers[user_id]

            await self.update_announcement()
        except asyncio.CancelledError:
            pass # Le timer a été annulé car le joueur s'est reconnecté
    
    async def auto_remove_timeout(self, user_id: int):
        """Retire le joueur automatiquement au bout de 6 heures."""
        try:
            await asyncio.sleep(6 * 60 * 60) # 6 heures
            
            if user_id in self.ready_players:
                self.ready_players.remove(user_id)
            
            if user_id in self.timeout_timers: del self.timeout_timers[user_id]
            if user_id in self.offline_timers:
                self.offline_timers[user_id].cancel()
                del self.offline_timers[user_id]

            await self.update_announcement()
        except asyncio.CancelledError:
            pass
            
    async def grace_period(self, user_id: int):
        """Accorde 15 minutes au joueur en retard pour se connecter sur Discord."""
        try:
            await asyncio.sleep(15 * 60) # 15 minutes
            if user_id in self.grace_timers:
                del self.grace_timers[user_id]
        except asyncio.CancelledError:
            pass

    async def delayed_ready(self, member: discord.Member, delay_sec: int):
        """Attend le délai demandé avant d'essayer d'ajouter le joueur à la liste."""
        try:
            await asyncio.sleep(delay_sec)
            
            user_id = member.id
            if user_id in self.pending_timers:
                del self.pending_timers[user_id]
                
            guild = member.guild
            updated_member = guild.get_member(user_id)
            if not updated_member: return
            
            # Si le joueur est en ligne, on l'ajoute !
            if updated_member.status != discord.Status.offline:
                if user_id not in self.ready_players:
                    self.ready_players.append(user_id)
                self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id))
                await self.update_announcement()
            else:
                # S'il est hors-ligne, on lance la période de grâce de 15 minutes
                self.grace_timers[user_id] = asyncio.create_task(self.grace_period(user_id))
                
        except asyncio.CancelledError:
            pass


    # --- UTILITAIRES ---

    def parse_time(self, time_str: str) -> int:
        """Convertit une chaîne de temps (1h30, 90m) en secondes."""
        if not time_str: return 0
            
        time_str = time_str.lower().replace(',', '.')
        hours, mins = 0.0, 0.0
        
        h_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:h|heure|heures)', time_str)
        if h_match:
            hours = float(h_match.group(1))
            time_str = time_str[:h_match.start()] + time_str[h_match.end():]
            
        m_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)', time_str)
        if m_match:
            mins = float(m_match.group(1))
            time_str = time_str[:m_match.start()] + time_str[m_match.end():]
            
        if hours == 0 and mins == 0:
            num_match = re.search(r'(\d+(?:\.\d+)?)', time_str)
            if num_match:
                mins = float(num_match.group(1))
                
        return int((hours * 3600) + (mins * 60))


    # --- COMMANDES ET ÉVÉNEMENTS ---

    @app_commands.command(name="ready", description="Rejoins la liste des joueurs prêts")
    @app_commands.describe(delai="Dans combien de temps es-tu dispo ? (ex: 15m, 1h30, 90)")
    async def ready_cmd(self, interaction: discord.Interaction, delai: str = None):
        user_id = interaction.user.id
        self.cancel_all_timers(user_id)
        
        # Cas 1 : Ajout différé
        if delai and delai != "0":
            delay_sec = self.parse_time(delai)
            
            if delay_sec == 0:
                await interaction.response.send_message(
                    "❌ Je n'ai pas compris le format du temps. Utilise par exemple : `15m`, `1h30` ou `90`.", 
                    ephemeral=True
                )
                return
                
            if delay_sec > 21600:
                await interaction.response.send_message(
                    "⏳ Tu ne peux pas prévoir une session plus de 6 heures à l'avance.", 
                    ephemeral=True
                )
                return
                
            self.pending_timers[user_id] = asyncio.create_task(self.delayed_ready(interaction.user, delay_sec))
            
            heures = delay_sec // 3600
            minutes = (delay_sec % 3600) // 60
            temps_str = f"{heures}h{minutes:02d}" if heures > 0 else f"{minutes} minute(s)"
            
            await interaction.response.send_message(
                f"✅ C'est noté ! Je t'ajouterai à la liste dans {temps_str} si tu es connecté.", 
                ephemeral=True
            )
            return
                
        # Cas 2 : Ajout immédiat
        if user_id not in self.ready_players:
            self.ready_players.append(user_id)
            
        self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id))
        
        await interaction.response.send_message("✅ Tu es maintenant dans la liste des joueurs prêts.", ephemeral=True)
        await self.update_announcement()


    @app_commands.command(name="unready", description="Te retire de la liste des joueurs prêts")
    async def unready_cmd(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        if user_id not in self.ready_players:
            await interaction.response.send_message("Tu n'étais pas dans la liste.", ephemeral=True)
            return

        self.ready_players.remove(user_id)
        self.cancel_all_timers(user_id)

        await interaction.response.send_message("✅ Tu as été retiré de la liste.", ephemeral=True)
        await self.update_announcement()


    @commands.Cog.listener()
    async def on_ready(self):
        """Réinitialise la liste au démarrage du bot."""
        self.ready_players.clear()
        await self.update_announcement()


    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Surveille les connexions/déconnexions des joueurs impliqués."""
        user_id = after.id

        # 1. Période de grâce (le joueur devait se connecter)
        if after.status != discord.Status.offline and user_id in self.grace_timers:
            self.grace_timers[user_id].cancel()
            del self.grace_timers[user_id]
            
            if user_id not in self.ready_players:
                self.ready_players.append(user_id)
            self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id))
            await self.update_announcement()
            return

        # 2. Gestion des déconnexions (5 minutes)
        if user_id not in self.ready_players:
            return

        if after.status == discord.Status.offline:
            if user_id not in self.offline_timers:
                self.offline_timers[user_id] = asyncio.create_task(self.auto_remove_offline(user_id))
        elif after.status != discord.Status.offline:
            if user_id in self.offline_timers:
                self.offline_timers[user_id].cancel()
                del self.offline_timers[user_id]


async def setup(bot: commands.Bot):
    await bot.add_cog(ReadyManager(bot))