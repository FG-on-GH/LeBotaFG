import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv

import io
from PIL import Image, ImageDraw, ImageFont, ImageChops

# Importation de notre nouvelle base de données
from cogs.R2P.game_data import player_games, game_display_names, load_data

load_dotenv()

class ReadyManager(commands.Cog):
    """
    Cog gérant le système de matchmaking (LFG - Looking For Group).
    Permet aux joueurs de se déclarer prêts, calcule les jeux en commun,
    et maintient une annonce à jour dans un salon dédié avec une image dynamique.
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


    # --- GENERATION D'IMAGES (NOUVEAU) ---

    async def _generate_lfg_image(self, members: list[discord.Member]) -> io.BytesIO:
        """Génère l'image LFG 'Now playing' avec les avatars."""
        # Configuration de base
        IMG_WIDTH = 1000
        IMG_HEIGHT = 500
        BG_COLOR = (24, 25, 28) # Gris foncé type Discord
        TEXT_COLOR = (255, 255, 255) # Blanc
        
        # Création du canvas
        img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), color=BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        # Essai de chargement de polices standard (Arial ou similaire)
        # Si ça échoue, on utilise la police par défaut
        try:
            font_title = ImageFont.truetype("arial.ttf", 60)
            font_starring = ImageFont.truetype("arial.ttf", 40)
        except IOError:
            font_title = ImageFont.load_default()
            font_starring = ImageFont.load_default()
            
        # 1. Dessiner le titre "Now playing"
        title_text = "Now playing"
        # draw.textbbox() remplace draw.textsize() dans les versions récentes de Pillow
        left, top, right, bottom = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = right - left
        
        draw.text(
            ((IMG_WIDTH - title_width) / 2, 30), 
            title_text, 
            font=font_title, 
            fill=TEXT_COLOR
        )
        
        # 2. Dessiner "Starring"
        starring_text = "Starring"
        left, top, right, bottom = draw.textbbox((0, 0), starring_text, font=font_starring)
        starring_width = right - left
        
        draw.text(
            ((IMG_WIDTH - starring_width) / 2, 110), 
            starring_text, 
            font=font_starring, 
            fill=TEXT_COLOR
        )
        
        # 3. Charger et positionner les avatars
        avatar_size = 150
        spacing = 30
        
        num_avatars = len(members)
        total_width = (num_avatars * avatar_size) + ((num_avatars - 1) * spacing)
        start_x = (IMG_WIDTH - total_width) / 2
        
        for i, member in enumerate(members):
            # Récupération de l'avatar (et de la version par défaut si besoin)
            avatar_url = member.display_avatar.with_format('png').url
            async with self.bot.session.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_data = await resp.read()
                    avatar_img = Image.open(io.BytesIO(avatar_data))
                    
                    # Redimensionnement et mise en cercle
                    avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                    
                    # Masque pour faire le cercle
                    mask = Image.new('L', (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    
                    # Application du masque (on utilise l'image elle-même comme masque pour gérer la transparence)
                    circular_avatar = ImageChops.composite(avatar_img, Image.new('RGBA', avatar_img.size, (0,0,0,0)), mask)
                    circular_avatar = circular_avatar.convert('RGB') # Conversion finale en RGB pour coller sur le canvas

                    # Collage
                    img.paste(circular_avatar, (int(start_x + (i * (avatar_size + spacing))), 180))
            
        # Sauvegarde de l'image dans un buffer mémoire
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer


    # --- GESTION DES JOUEURS ET DES RÔLES ---

    async def _update_role(self, user_id: int, guild: discord.Guild, add: bool):
        """Ajoute (add=True) ou retire (add=False) le rôle 'Ready to play' au joueur."""
        role_id_str = os.getenv('READY_ROLE_ID')
        if not role_id_str:
            return
            
        try:
            role_id = int(role_id_str)
            member = guild.get_member(user_id)
            if not member:
                return
                
            role = guild.get_role(role_id)
            if not role:
                print("⚠️ Attention : Le rôle spécifié dans READY_ROLE_ID est introuvable sur le serveur.")
                return
                
            if add and role not in member.roles:
                await member.add_roles(role)
            elif not add and role in member.roles:
                await member.remove_roles(role)
                
        except discord.Forbidden:
            print("❌ Erreur : Le bot n'a pas les permissions de modifier ce rôle.")
        except Exception as e:
            print(f"❌ Erreur lors de la modification du rôle : {e}")

    async def _add_ready_player(self, user_id: int, guild: discord.Guild):
        """Ajoute le joueur à la liste et lui donne le rôle."""
        if user_id not in self.ready_players:
            self.ready_players.append(user_id)
            await self._update_role(user_id, guild, add=True)

    async def _remove_ready_player(self, user_id: int, guild: discord.Guild):
        """Retire le joueur de la liste et lui enlève le rôle."""
        if user_id in self.ready_players:
            self.ready_players.remove(user_id)
            await self._update_role(user_id, guild, add=False)


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

        common_games = set.intersection(*sets_of_games)
        
        pretty_games = sorted(
            [game_display_names.get(game, game) for game in common_games],
            key=str.casefold
        )
        
        return pretty_games, excluded_users

    async def update_announcement(self, guild: discord.Guild):
        """Génère l'annonce Embed, l'image, supprime l'ancienne et publie la nouvelle."""
        channel_id = int(os.getenv('READY_CHANNEL_ID', 0))
        channel = self.bot.get_channel(channel_id)
        
        if not channel:
            print("⚠️ Attention : Salon d'annonce introuvable.")
            return

        # 0. Préparation des variables d'image
        lfg_file = None
        ready_members = []
        
        # Résolution des membres
        for uid in self.ready_players:
            member = guild.get_member(uid)
            if member: ready_members.append(member)

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
                
            # 2. GÉNÉRATION DE L'IMAGE (NOUVEAU)
            if 2 <= len(ready_members) <= 5:
                buffer = await self._generate_lfg_image(ready_members)
                # On prépare le fichier pour l'envoi
                lfg_file = discord.File(buffer, filename="lfg_image.png")
                # On intègre l'image dans l'embed (attachment:// fait le lien)
                embed.set_image(url="attachment://lfg_image.png")

        # 3. Suppression de l'ancienne annonce
        last_id = self._get_last_announcement_id()
        if last_id:
            try:
                old_msg = await channel.fetch_message(last_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass 
                
        # 4. Envoi et sauvegarde de la nouvelle annonce (avec le fichier si présent)
        if lfg_file:
            # IMPORTANT : file= doit être dans l'envoi du message, pas dans l'embed
            new_msg = await channel.send(file=lfg_file, embed=embed)
        else:
            new_msg = await channel.send(embed=embed)
            
        self._save_last_announcement_id(new_msg.id)


    # --- CHRONOMÈTRES ET TIMERS ---

    def cancel_all_timers(self, user_id: int):
        """Annule tous les chronomètres liés à un joueur pour éviter les conflits."""
        for timer_dict in [self.offline_timers, self.timeout_timers, self.pending_timers, self.grace_timers]:
            if user_id in timer_dict:
                timer_dict[user_id].cancel()
                del timer_dict[user_id]

    async def auto_remove_offline(self, user_id: int, guild: discord.Guild):
        """Retire le joueur après 5 minutes de déconnexion."""
        try:
            await asyncio.sleep(5 * 60) # 5 minutes
            
            await self._remove_ready_player(user_id, guild)
            
            # Nettoyage global
            if user_id in self.offline_timers: del self.offline_timers[user_id]
            if user_id in self.timeout_timers:
                self.timeout_timers[user_id].cancel()
                del self.timeout_timers[user_id]

            await self.update_announcement(guild)
        except asyncio.CancelledError:
            pass # Le timer a été annulé car le joueur s'est reconnecté
    
    async def auto_remove_timeout(self, user_id: int, guild: discord.Guild):
        """Retire le joueur automatiquement au bout de 6 heures."""
        try:
            await asyncio.sleep(6 * 60 * 60) # 6 heures
            
            await self._remove_ready_player(user_id, guild)
            
            if user_id in self.timeout_timers: del self.timeout_timers[user_id]
            if user_id in self.offline_timers:
                self.offline_timers[user_id].cancel()
                del self.offline_timers[user_id]

            await self.update_announcement(guild)
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
            guild = member.guild # Récupération de la guild
            
            if user_id in self.pending_timers:
                del self.pending_timers[user_id]
                
            updated_member = guild.get_member(user_id)
            if not updated_member: return
            
            # Si le joueur est en ligne, on l'ajoute !
            if updated_member.status != discord.Status.offline:
                await self._add_ready_player(user_id, guild)
                # Ajout de guild dans l'appel du timer
                self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id, guild))
                await self.update_announcement(guild)
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
        guild = interaction.guild # Récupération de la guild
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
        await self._add_ready_player(user_id, guild)
        
        # Ajout de guild dans l'appel du timer
        self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id, guild))
        
        await interaction.response.send_message("✅ Tu es maintenant dans la liste des joueurs prêts.", ephemeral=True)
        await self.update_announcement(guild)


    @app_commands.command(name="unready", description="Te retire de la liste des joueurs prêts")
    async def unready_cmd(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild = interaction.guild # Récupération de la guild
        
        if user_id not in self.ready_players:
            await interaction.response.send_message("Tu n'étais pas dans la liste.", ephemeral=True)
            return

        await self._remove_ready_player(user_id, guild)
        self.cancel_all_timers(user_id)

        await interaction.response.send_message("✅ Tu as été retiré de la liste.", ephemeral=True)
        await self.update_announcement(guild)


    @commands.Cog.listener()
    async def on_ready(self):
        """Réinitialise la liste et sécurise les rôles au démarrage du bot."""
        self.ready_players.clear()
        
        # Récupération de la guild via le channel id
        channel_id = int(os.getenv('READY_CHANNEL_ID', 0))
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print("⚠️ Attention : Salon d'annonce introuvable au démarrage.")
            return
        
        guild = channel.guild

        # Nettoyage de sécurité : on retire le rôle à tout le monde au redémarrage
        role_id_str = os.getenv('READY_ROLE_ID')
        if role_id_str:
            role = guild.get_role(int(role_id_str))
            if role:
                for member in role.members:
                    try:
                        await member.remove_roles(role)
                    except discord.Forbidden:
                        print("❌ Permissions insuffisantes pour nettoyer les rôles au démarrage.")
                        break 
                            
        await self.update_announcement(guild)


    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Surveille les connexions/déconnexions des joueurs impliqués."""
        user_id = after.id
        guild = after.guild # Récupération de la guild

        # 1. Période de grâce (le joueur devait se connecter)
        if after.status != discord.Status.offline and user_id in self.grace_timers:
            self.grace_timers[user_id].cancel()
            del self.grace_timers[user_id]
            
            await self._add_ready_player(user_id, guild)
            # Ajout de guild dans l'appel du timer
            self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id, guild))
            await self.update_announcement(guild)
            return

        # 2. Gestion des déconnexions (5 minutes)
        if user_id not in self.ready_players:
            return

        if after.status == discord.Status.offline:
            if user_id not in self.offline_timers:
                # Ajout de guild dans l'appel du timer
                self.offline_timers[user_id] = asyncio.create_task(self.auto_remove_offline(user_id, guild))
        elif after.status != discord.Status.offline:
            if user_id in self.offline_timers:
                self.offline_timers[user_id].cancel()
                del self.offline_timers[user_id]


async def setup(bot: commands.Bot):
    # Ajout d'une session aiohttp au bot pour télécharger les avatars
    import aiohttp
    if not hasattr(bot, 'session') or bot.session.closed:
        bot.session = aiohttp.ClientSession()
        
    await bot.add_cog(ReadyManager(bot))