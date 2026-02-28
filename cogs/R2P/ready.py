import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import re
import random
import time
from pathlib import Path
from dotenv import load_dotenv


import io
import urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageOps


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
        # offline_timers : Gère les 5 minutes avant retrait d'un joueur déconnecté
        self.offline_timers: dict[int, asyncio.Task] = {}
        # timeout_timers : Gère les 6 heures max de présence dans la liste (anti-oubli)
        self.timeout_timers: dict[int, asyncio.Task] = {}
        # pending_timers : Gère les joueurs qui ont fait "/ready 1h" (en attente d'ajout)
        self.pending_timers: dict[int, asyncio.Task] = {}
        # grace_timers : Gère les 15 minutes accordées à un joueur en retard pour se connecter
        self.grace_timers: dict[int, asyncio.Task] = {}
        # pending_timers : Gère les joueurs qui ont fait "/ready 1h" (en attente d'ajout)
        self.pending_timers: dict[int, asyncio.Task] = {}
        # Stocke le timestamp (l'heure exacte) d'arrivée prévue
        self.pending_arrivals: dict[int, float] = {}
        # voice_disconnect_timers : Gère les 30 min après avoir quitté un vocal
        self.voice_disconnect_timers: dict[int, asyncio.Task] = {}
        
        # Chargement initial des jeux
        load_data()


    # --- GENERATION D'IMAGES ---

    async def _generate_lfg_image(self, members: list[discord.Member], common_games: list[str]) -> io.BytesIO:
        """Génère l'image LFG dynamiquement selon le nombre de joueurs et de jeux."""
        
        show_avatars = len(members) <= 5
        show_games = 1 <= len(common_games) <= 3
        
        IMG_WIDTH = 1000
        TEXT_COLOR = (255, 255, 255, 255)
        
        # Hauteur dynamique selon le contenu
        if show_avatars and show_games:
            IMG_HEIGHT = 900
        elif show_games:
            IMG_HEIGHT = 600  # 600px laisse assez de marge pour les grandes pochettes
        else:
            IMG_HEIGHT = 500

        BASE_DIR = Path(__file__).parent
        ASSETS_DIR = BASE_DIR / "assets"
        
        # --- SÉLECTION ALÉATOIRE DES ASSETS ---
        bg_files = list((ASSETS_DIR / "backgrounds").glob("*.png")) + list((ASSETS_DIR / "backgrounds").glob("*.jpg"))
        title_files = list((ASSETS_DIR / "titres").glob("*.ttf"))
        subtitle_files = list((ASSETS_DIR / "sous_titres").glob("*.ttf"))
        
        bg_path = random.choice(bg_files) if bg_files else ASSETS_DIR / "background.png"
        title_path = random.choice(title_files) if title_files else ASSETS_DIR / "titre.ttf"
        subtitle_path = random.choice(subtitle_files) if subtitle_files else ASSETS_DIR / "sous_titre.ttf"
        
        # 1. Chargement du fond
        try:
            bg_img = Image.open(bg_path).convert('RGBA')
            img = ImageOps.fit(bg_img, (IMG_WIDTH, IMG_HEIGHT), Image.Resampling.LANCZOS)
        except IOError as e:
            print(f"⚠️ Erreur chargement fond ({bg_path}) : {e}") 
            img = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), color=(24, 25, 28, 255))
            
        draw = ImageDraw.Draw(img)
        
        # 2. Polices
        try:
            font_title = ImageFont.truetype(str(title_path), 80)
            font_starring = ImageFont.truetype(str(subtitle_path), 45) 
        except IOError as e:
            print(f"⚠️ Erreur chargement polices : {e}")
            font_title = ImageFont.load_default()
            font_starring = ImageFont.load_default()
            
        # 3. Titre (Toujours tout en haut)
        title_text = "Now playing"
        left, top, right, bottom = draw.textbbox((0, 0), title_text, font=font_title)
        draw.text(((IMG_WIDTH - (right - left)) / 2, 15), title_text, font=font_title, fill=TEXT_COLOR)
        
        # Curseur vertical dynamique : il commence à 150px du haut
        current_y = 150 
        
        # 4. AVATARS (S'ils doivent être affichés)
        if show_avatars:
            starring_text = "Starring"
            left, top, right, bottom = draw.textbbox((0, 0), starring_text, font=font_starring)
            draw.text(((IMG_WIDTH - (right - left)) / 2, current_y), starring_text, font=font_starring, fill=TEXT_COLOR)
            
            avatar_size = 150
            spacing = 40
            num_avatars = len(members)
            total_width = (num_avatars * avatar_size) + ((num_avatars - 1) * spacing)
            start_x = (IMG_WIDTH - total_width) / 2
            
            avatar_y = current_y + 80
            
            for i, member in enumerate(members):
                avatar_url = member.display_avatar.with_format('png').url
                async with self.bot.session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        avatar_img = Image.open(io.BytesIO(avatar_data)).convert('RGBA')
                        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                        
                        mask = Image.new('L', (avatar_size, avatar_size), 0)
                        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
                        
                        pos_x = int(start_x + (i * (avatar_size + spacing)))
                        img.paste(avatar_img, (pos_x, avatar_y), mask)
            
            # On descend le curseur pour la section suivante s'il y en a une
            current_y = avatar_y + avatar_size + 40 

        # 5. POCHETTES DE JEUX (Si elles doivent être affichées)
        if show_games:
            poison_text = "Pick your poison"
            left, top, right, bottom = draw.textbbox((0, 0), poison_text, font=font_starring)
            draw.text(((IMG_WIDTH - (right - left)) / 2, current_y), poison_text, font=font_starring, fill=TEXT_COLOR)
            
            grid_w, grid_h = 200, 300
            grid_spacing = 50
            total_grid_w = (len(common_games) * grid_w) + ((len(common_games) - 1) * grid_spacing)
            start_grid_x = (IMG_WIDTH - total_grid_w) / 2
            
            game_y = current_y + 80
            
            for i, game_name in enumerate(common_games):
                img_bytes = await self.fetch_steamgrid_image(game_name)
                if img_bytes:
                    grid_img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
                    grid_img = ImageOps.fit(grid_img, (grid_w, grid_h), Image.Resampling.LANCZOS)
                    
                    mask = Image.new('L', (grid_w, grid_h), 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, grid_w, grid_h), radius=15, fill=255)
                    
                    pos_x = int(start_grid_x + (i * (grid_w + grid_spacing)))
                    img.paste(grid_img, (pos_x, game_y), mask)
            
        # 6. Sauvegarde
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    async def fetch_steamgrid_image(self, game_name: str) -> bytes | None:
        """Cherche et télécharge la pochette 2:3 (600x900) d'un jeu via SteamGridDB."""
        api_key = os.getenv("STEAMGRIDDB_API_KEY")
        if not api_key:
            print("⚠️ Clé API SteamGridDB manquante dans le .env")
            return None
            
        headers = {"Authorization": f"Bearer {api_key}"}
        
        try:
            # 1. Chercher l'ID du jeu (on encode le nom pour les espaces/caractères spéciaux)
            safe_name = urllib.parse.quote(game_name)
            search_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{safe_name}"
            
            async with self.bot.session.get(search_url, headers=headers) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                if not data.get("data"): return None
                game_id = data["data"][0]["id"]

            # 2. Récupérer les images au format 2:3 (dimensions=600x900)
            grids_url = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=600x900"
            async with self.bot.session.get(grids_url, headers=headers) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                if not data.get("data"): return None
                image_url = data["data"][0]["url"]

            # 3. Télécharger l'image trouvée
            async with self.bot.session.get(image_url) as resp:
                if resp.status != 200: return None
                return await resp.read()
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération SteamGridDB pour {game_name}: {e}")
            return None


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
        
        # MODIFICATION ICI : S'il y a 1 seul (ou aucun) joueur avec des jeux, 
        # on ne cherche pas de points communs.
        if len(sets_of_games) <= 1:
            return [], excluded_users

        # Intersection de tous les sets de jeux
        common_games = set.intersection(*sets_of_games)
        
        # On récupère les noms d'affichage et on les trie par ordre alphabétique
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
        common_games = []  # CORRECTION 1 : On l'initialise à vide par défaut !
        
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
            
            # Ici common_games prend sa vraie valeur car il y a au moins 2 joueurs
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

        # --- AJOUT DES JOUEURS EN ATTENTE (S'applique à tous les embeds) ---
        if self.pending_arrivals:
            # On trie le dictionnaire par valeur (le timestamp) croissant
            sorted_pending = sorted(self.pending_arrivals.items(), key=lambda x: x[1])
            
            # Création de la liste des mentions séparées par une virgule
            mentions = ", ".join([f"<@{uid}>" for uid, ts in sorted_pending])
            
            # Récupération du timestamp du tout premier joueur de la liste triée
            next_ts = int(sorted_pending[0][1])
            
            embed.add_field(
                name="⏳ Joueurs en attente",
                value=f"{mentions}\n*Prochaine arrivée à <t:{next_ts}:t>*",
                inline=False
            )
                
        # 2. GÉNÉRATION DE L'IMAGE
        # CORRECTION 2 : Ce bloc est maintenant désindenté de la condition d'au-dessus !
        # On ne génère l'image que s'il y a au moins 1 joueur prêt à afficher
        if len(ready_members) >= 1:
            show_avatars = len(ready_members) <= 5
            show_games = 1 <= len(common_games) <= 3
            
            if show_avatars or show_games:
                buffer = await self._generate_lfg_image(ready_members, common_games)
                lfg_file = discord.File(buffer, filename="lfg_image.png")

        # 3. Récupération de l'ancienne annonce (sans la supprimer tout de suite)
        last_id = self._get_last_announcement_id()
        old_msg = None
        if last_id:
            try:
                old_msg = await channel.fetch_message(last_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass 
                
        # 4. Envoi et sauvegarde de la NOUVELLE annonce
        if lfg_file:
            new_msg = await channel.send(file=lfg_file, embed=embed)
        else:
            new_msg = await channel.send(embed=embed)
            
        self._save_last_announcement_id(new_msg.id)

        # 5. Suppression de l'ANCIENNE annonce
        if old_msg:
            try:
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass


    # --- CHRONOMÈTRES ET TIMERS ---

    def cancel_all_timers(self, user_id: int):
        """Annule tous les chronomètres liés à un joueur pour éviter les conflits."""
        # AJOUT de self.voice_disconnect_timers dans la liste
        for timer_dict in [self.offline_timers, self.timeout_timers, self.pending_timers, self.grace_timers, self.voice_disconnect_timers]:
            if user_id in timer_dict:
                timer_dict[user_id].cancel()
                del timer_dict[user_id]
        
        # On le retire de la liste des arrivées prévues
        if user_id in self.pending_arrivals:
            del self.pending_arrivals[user_id]

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
    
    async def auto_remove_voice_disconnect(self, user_id: int, guild: discord.Guild):
        """Retire le joueur 30 minutes après avoir quitté un salon vocal."""
        try:
            await asyncio.sleep(30 * 60) # 30 minutes
            
            # Le temps est écoulé, on le retire
            await self._remove_ready_player(user_id, guild)
            
            # On nettoie tous ses autres chronos potentiels proprement
            self.cancel_all_timers(user_id)
            
            # On met à jour l'annonce
            await self.update_announcement(guild)
        except asyncio.CancelledError:
            pass # Le timer a été annulé car le joueur a rejoint un vocal

    async def delayed_ready(self, member: discord.Member, delay_sec: int):
        """Attend le délai demandé avant d'essayer d'ajouter le joueur à la liste."""
        try:
            await asyncio.sleep(delay_sec)
            
            user_id = member.id
            guild = member.guild # Récupération de la guild
            
            if user_id in self.pending_timers:
                del self.pending_timers[user_id]
            
            if user_id in self.pending_arrivals:
                del self.pending_arrivals[user_id]
                
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
        
        # Ceci nettoie tous les chronos (gère parfaitement le joueur qui arrive en avance !)
        self.cancel_all_timers(user_id) 
        
        # Cas 1 : Ajout différé (avec un délai)
        if delai and delai != "0":
            delay_sec = self.parse_time(delai)
            
            if delay_sec == 0:
                await interaction.response.send_message("❌ Format non compris (ex: 15m, 1h30).", ephemeral=True)
                return
            if delay_sec > 21600:
                await interaction.response.send_message("⏳ Pas plus de 6 heures à l'avance.", ephemeral=True)
                return
                
            # Si le joueur était déjà prêt, on le retire immédiatement
            if user_id in self.ready_players:
                await self._remove_ready_player(user_id, guild)

            # On calcule et on enregistre l'heure d'arrivée
            target_time = time.time() + delay_sec
            self.pending_arrivals[user_id] = target_time

            self.pending_timers[user_id] = asyncio.create_task(self.delayed_ready(interaction.user, delay_sec))
            
            heures = delay_sec // 3600
            minutes = (delay_sec % 3600) // 60
            temps_str = f"{heures}h{minutes:02d}" if heures > 0 else f"{minutes} minute(s)"
            
            await interaction.response.send_message(
                f"✅ C'est noté ! Je t'ajouterai à la liste dans {temps_str} (si tu es connecté).", 
                ephemeral=True
            )
            
            # On met à jour l'annonce pour afficher la liste d'attente !
            await self.update_announcement(guild)
            return
                
        # Cas 2 : Ajout immédiat (sans délai ou délai = 0)
        # _add_ready_player ignore silencieusement l'ajout si le joueur y est déjà, donc pas de risque de doublon.
        await self._add_ready_player(user_id, guild)
        
        # Ajout de guild dans l'appel du timer d'expiration de 6 heures
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
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Gère le chronomètre anti-oubli de 30 minutes quand un joueur quitte un vocal."""
        user_id = member.id
        guild = member.guild
        
        # On ignore ceux qui ne sont pas dans la liste des joueurs prêts
        if user_id not in self.ready_players:
            return

        # Cas 1 : Le joueur quitte un vocal (il n'est plus dans aucun salon vocal)
        if before.channel is not None and after.channel is None:
            # S'il n'a pas déjà un chronomètre en cours, on en lance un
            if user_id not in self.voice_disconnect_timers:
                self.voice_disconnect_timers[user_id] = asyncio.create_task(self.auto_remove_voice_disconnect(user_id, guild))
                
        # Cas 2 : Le joueur rejoint un vocal (ou change de vocal)
        elif after.channel is not None:
            # S'il avait un chronomètre de déconnexion vocale, on l'annule
            if user_id in self.voice_disconnect_timers:
                self.voice_disconnect_timers[user_id].cancel()
                del self.voice_disconnect_timers[user_id]


async def setup(bot: commands.Bot):
    # Ajout d'une session aiohttp au bot pour télécharger les avatars
    import aiohttp
    if not hasattr(bot, 'session') or bot.session.closed:
        bot.session = aiohttp.ClientSession()
        
    await bot.add_cog(ReadyManager(bot))