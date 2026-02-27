import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from cogs.R2P.manage_libraries import *
import asyncio
import re

load_dotenv()

# Ensemble pour stocker les joueurs prêts
readies=list()

announcement_id_path=Path("./cogs/R2P/last_announcement_id.json")
def load_last_annoucement():
    """Charge l'ID depuis le fichier JSON."""
    try:
        with open(announcement_id_path, "r") as f:
            data = json.load(f)
            return data.get("last_announcement_id")
    except FileNotFoundError:
        print("Annoucement not found")
        return
    except json.JSONDecodeError:
        print("Announcement corrupted")
        return

def save_last_announcement(id):
    """Sauvegarde l'ID dans le fichier JSON."""
    with open(announcement_id_path, "w") as f:
        json.dump({"last_announcement_id": id}, f)


def find_common_games():
    '''
    Prend une liste d'ID de joueurs et renvoie :
    1. Une liste des noms d'affichage des jeux qu'ils ont en commun
    2. Une liste des ID des joueurs exclus (car ils n'ont aucun jeu enregistré)
    '''
    sets_of_games = []
    excluded_users = []
    
    for id in readies:
        # Conversion en str pour chercher dans le dictionnaire JSON
        str_id = str(id)
        
        # Si le joueur a une entrée et qu'elle n'est pas vide
        if str_id in player_libraries and player_libraries[str_id]:
            sets_of_games.append(player_libraries[str_id])
        else:
            # Sinon, on l'ajoute à la liste des exclus (on garde l'ID original pour le taguer)
            excluded_users.append(id)
    
    # Si absolument personne dans la liste n'a de jeu
    if not sets_of_games:
        return [], excluded_users

    # On fait l'intersection uniquement sur ceux qui ont des jeux
    common_games = set.intersection(*sets_of_games)
    prettyprint_common_games = sorted([pretty_print_library.get(game, game) for game in common_games])
    
    return prettyprint_common_games, excluded_users

class ready(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_data()
        self.offline_timers = {}
        self.timeout_timers = {}
        self.pending_timers = {}
        self.grace_timers = {}
    
    async def update_announcement(self):
        """Génère l'annonce sous forme d'Embed, supprime l'ancienne et envoie la nouvelle."""
        ready_channel_ID = int(os.getenv('READY_CHANNEL_ID'))
        channel = self.bot.get_channel(ready_channel_ID)
        
        if channel is None:
            print("Attention : Salon d'annonce introuvable.")
            return

        # 1. Création de l'Embed selon le nombre de joueurs
        if len(readies) == 0:
            embed = discord.Embed(
                title=":red_circle: En attente de joueurs", 
                description="Personne n'est prêt pour le moment.\nUtilisez `/ready` pour vous ajouter.", 
                color=discord.Color.red()
            )
        elif len(readies) == 1:
            embed = discord.Embed(
                title=":orange_circle: Un joueur est prêt !", 
                description=f"<@{readies[0]}> est prêt à jouer ! On attend les autres...", 
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title=":green_circle: Des joueurs sont prêts !", 
                description="Voici le récapitulatif pour la session :",
                color=discord.Color.green()
            )
            
            # Champ 1 : Joueurs prêts
            ready_mentions = "\n".join([f"<@{uid}>" for uid in readies])
            embed.add_field(name="Joueurs", value=ready_mentions, inline=False)
            
            # Recherche des jeux
            (prettyprint_common_games, excluded_users) = find_common_games()
            
            # Champ 2 : Jeux en commun
            if not prettyprint_common_games:
                embed.add_field(name="Jeux en commun", value="*Aucun jeu en commun trouvé*", inline=False)
            else:
                games_str = "\n".join([f"{game}" for game in prettyprint_common_games])
                embed.add_field(name="Jeux en commun", value=games_str, inline=False)
                
            # Champ 3 (Optionnel) : Joueurs exclus
            if excluded_users:
                excluded_str = ", ".join([f"<@{uid}>" for uid in excluded_users])
                embed.add_field(
                    name="⚠️ Joueurs sans jeux enregistrés", 
                    value=f"{excluded_str}\n*Utilisez `/addgame` pour en ajouter puis refaites `/ready`.*", 
                    inline=False
                )

        # 2. Suppression de l'ancien message
        last_announcement_id = load_last_annoucement()
        if last_announcement_id:
            try:
                old_msg = await channel.fetch_message(last_announcement_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass 
                
        # 3. Envoi du nouvel Embed et sauvegarde de l'ID
        # Attention ici : on utilise l'argument `embed=` au lieu de passer du texte brut
        new_msg = await channel.send(embed=embed)
        save_last_announcement(new_msg.id)

    @app_commands.command(name="ready", description="T'ajoute à la liste des personnes prêtes à jouer")
    @app_commands.describe(delai="Dans combien de temps es-tu dispo ? (ex: 15m, 1h30, 90)")
    async def ready(self, interaction: discord.Interaction, delai: str = None):
        user_id = interaction.user.id
        
        # On nettoie tous ses anciens compteurs pour repartir à zéro
        self.cancel_all_timers(user_id)
        
        # Cas 1 : L'utilisateur a précisé un délai
        if delai and delai!="0":
            delay_sec = self.parse_time(delai)
            
            # Sécurité 1 : Le format n'a pas été compris (retourne 0)
            if delay_sec == 0:
                await interaction.response.send_message(
                    ":x: Je n'ai pas compris le format du temps. Utilise par exemple : `15m`, `1h30`, `90` ou `2 heures`.", 
                    ephemeral=True
                )
                return # On arrête l'exécution ici, il n'est pas ajouté
                
            # Sécurité 2 : Le délai dépasse 6 heures (6 * 3600 = 21600 secondes)
            if delay_sec > 21600:
                await interaction.response.send_message(
                    ":hourglass: C'est un peu trop pour ma mémoire ! Tu ne peux pas prévoir une session plus de 6 heures à l'avance.", 
                    ephemeral=True
                )
                return # On arrête l'exécution ici
                
            # Si tout est bon, on lance l'attente
            self.pending_timers[user_id] = asyncio.create_task(self.delayed_ready(interaction.user, delay_sec))
            
            # Petit calcul pour un affichage propre dans le message de confirmation
            heures = delay_sec // 3600
            minutes = (delay_sec % 3600) // 60
            temps_str = f"{heures}h{minutes:02d}" if heures > 0 else f"{minutes} minute(s)"
            
            await interaction.response.send_message(
                f":white_check_mark: C'est noté ! Je t'ajouterai à la liste dans {temps_str} si tu es toujours connecté à ce moment là.", 
                ephemeral=True
            )
            return # Le processus s'arrête là, le reste se fera dans `delayed_ready`
                
        # Cas 2 : Ajout immédiat (aucun argument "delai" fourni)
        if user_id not in readies:
            readies.append(user_id)
            
        # On lance les 4h de présence max
        self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id))
        
        await interaction.response.send_message(":white_check_mark: Tu as bien été ajouté à la liste des joueurs prêts.", ephemeral=True)
        await self.update_announcement()

    @app_commands.command(name="unready", description="Te retire de la liste des personnes prêtes à jouer")
    async def unready(self, interaction: discord.Interaction):
        playerID = interaction.user.id
        
        if playerID not in readies:
            await interaction.response.send_message("Tu n'étais pas dans la liste des joueurs prêts.", ephemeral=True)
            return

        readies.remove(playerID)
        self.cancel_all_timers(interaction.user.id)

        await interaction.response.send_message("Tu as bien été retiré de la liste des joueurs prêts.", ephemeral=True)
        await self.update_announcement()
    
    @commands.Cog.listener()
    async def on_ready(self):
        # On s'assure que la liste est bien vide au démarrage
        readies.clear()
        # On met à jour l'annonce (qui affichera que personne n'est prêt)
        await self.update_announcement()
    
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        user_id = after.id

        # 1. GESTION DE LA PÉRIODE DE GRÂCE (Le joueur était en retard mais vient de se connecter)
        if after.status != discord.Status.offline and user_id in self.grace_timers:
            self.grace_timers[user_id].cancel()
            del self.grace_timers[user_id]
            
            # On l'ajoute officiellement
            if user_id not in readies:
                readies.append(user_id)
            self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id))
            await self.update_announcement()
            return # On s'arrête là pour ce joueur

        # 2. GESTION CLASSIQUE DE LA DÉCONNEXION (les 10 minutes)
        if user_id not in readies:
            return

        if after.status == discord.Status.offline:
            if user_id not in self.offline_timers:
                self.offline_timers[user_id] = asyncio.create_task(self.auto_remove_offline(user_id))
        elif after.status != discord.Status.offline:
            if user_id in self.offline_timers:
                self.offline_timers[user_id].cancel()
                del self.offline_timers[user_id]

    async def auto_remove_offline(self, user_id: int):
        """Attend 10 minutes puis retire le joueur s'il est toujours hors ligne."""
        try:
            # Attente 1 minute
            await asyncio.sleep(60)
            
            # Si on arrive ici, la minute s'est écoulée sans annulation
            if user_id in readies:
                readies.remove(user_id)
            
            if user_id in self.offline_timers:
                del self.offline_timers[user_id]
            
            # On annule le timer global de 4h si le joueur est viré pour inactivité
            if user_id in self.timeout_timers:
                self.timeout_timers[user_id].cancel()
                del self.timeout_timers[user_id]

            # On met à jour l'annonce pour refléter son départ
            await self.update_announcement()
            
        except asyncio.CancelledError:
            # Cette exception est levée si la tâche a été annulée (le joueur est revenu en ligne)
            pass
    
    async def auto_remove_timeout(self, user_id: int):
        """Attend 4 heures puis retire le joueur s'il est toujours dans la liste."""
        try:
            # Attente de 4 heures
            await asyncio.sleep(4*60*60)
            
            # Si le timer arrive à bout, on retire le joueur
            if user_id in readies:
                readies.remove(user_id)
            
            # On nettoie les dictionnaires
            if user_id in self.timeout_timers:
                del self.timeout_timers[user_id]
            
            # S'il y avait un timer de déconnexion en cours pour lui, on l'annule aussi
            if user_id in self.offline_timers:
                self.offline_timers[user_id].cancel()
                del self.offline_timers[user_id]

            # Mise à jour de l'annonce
            await self.update_announcement()
            
        except asyncio.CancelledError:
            # Annulé car le joueur a fait /unready manuellement ou a été retiré par le timer hors-ligne
            pass
    
    def parse_time(self, time_str: str) -> int:
        """Convertit une chaîne de caractères (ex: 1h30, 90, 15m) en secondes."""
        if not time_str:
            return 0
            
        time_str = time_str.lower().replace(',', '.')
        hours, mins = 0.0, 0.0
        
        # Recherche des heures (ex: 1.5h, 2 heures)
        h_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:h|heure|heures)', time_str)
        if h_match:
            hours = float(h_match.group(1))
            time_str = time_str[:h_match.start()] + time_str[h_match.end():]
            
        # Recherche des minutes (ex: 15m, 5 min)
        m_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)', time_str)
        if m_match:
            mins = float(m_match.group(1))
            time_str = time_str[:m_match.start()] + time_str[m_match.end():]
            
        # S'il n'y a ni 'h' ni 'm', on cherche juste un nombre (qu'on considérera comme des minutes, ex: "90")
        if hours == 0 and mins == 0:
            num_match = re.search(r'(\d+(?:\.\d+)?)', time_str)
            if num_match:
                mins = float(num_match.group(1))
                
        return int((hours * 3600) + (mins * 60))

    def cancel_all_timers(self, user_id: int):
        """Annule absolument tous les chronomètres liés à un joueur pour repartir à zéro."""
        for timer_dict in [self.offline_timers, self.timeout_timers, self.pending_timers, self.grace_timers]:
            if user_id in timer_dict:
                timer_dict[user_id].cancel()
                del timer_dict[user_id]

    async def delayed_ready(self, member: discord.Member, delay_sec: int):
        """Attend le délai demandé avant de vérifier si on ajoute le joueur."""
        try:
            await asyncio.sleep(delay_sec)
            
            user_id = member.id
            if user_id in self.pending_timers:
                del self.pending_timers[user_id]
                
            # On vérifie le statut de l'utilisateur sur le serveur
            guild = member.guild
            updated_member = guild.get_member(user_id)
            if not updated_member: 
                return
            
            if updated_member.status != discord.Status.offline:
                # S'il est en ligne, on l'ajoute directement et on lance les 4h !
                if user_id not in readies:
                    readies.append(user_id)
                self.timeout_timers[user_id] = asyncio.create_task(self.auto_remove_timeout(user_id))
                await self.update_announcement()
            else:
                # S'il est hors-ligne, on lui laisse 15 minutes de grâce
                self.grace_timers[user_id] = asyncio.create_task(self.grace_period(user_id))
                
        except asyncio.CancelledError:
            pass

    async def grace_period(self, user_id: int):
        """Attend 15 minutes. Si la tâche n'est pas annulée (reconnexion), le joueur est ignoré."""
        try:
            await asyncio.sleep(15 * 60) # 15 minutes en secondes
            
            if user_id in self.grace_timers:
                del self.grace_timers[user_id]
                # Optionnel : tu pourrais envoyer un DM au joueur ici pour dire "Délai expiré"
        except asyncio.CancelledError:
            pass
        

async def setup(bot):
    await bot.add_cog(ready(bot))
