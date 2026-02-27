import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from cogs.R2P.manage_libraries import *
import asyncio

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
    async def ready(self, interaction: discord.Interaction):
        playerID = interaction.user.id
        if playerID not in readies:
            readies.append(playerID)
        
        # Gestion du timer de 4h
        # Si le joueur avait déjà un timer en cours (s'il refait /ready), on le réinitialise
        if playerID in self.timeout_timers:
            self.timeout_timers[playerID].cancel()
        
        # On lance le chronomètre de 4h
        self.timeout_timers[playerID] = asyncio.create_task(self.auto_remove_timeout(playerID))
        
        await interaction.response.send_message("Tu as bien été ajouté à la liste des joueurs prêts (pour une durée maximum de 4h).", ephemeral=True)
        await self.update_announcement()

    @app_commands.command(name="unready", description="Te retire de la liste des personnes prêtes à jouer")
    async def unready(self, interaction: discord.Interaction):
        playerID = interaction.user.id
        
        if playerID not in readies:
            await interaction.response.send_message("Tu n'étais pas dans la liste des joueurs prêts.", ephemeral=True)
            return

        readies.remove(playerID)
        
        # On annule le chronomètre de 4h car le joueur part de lui-même
        if playerID in self.timeout_timers:
            self.timeout_timers[playerID].cancel()
            del self.timeout_timers[playerID]
            
        # On annule aussi le timer hors-ligne au cas où il était en cours
        if playerID in self.offline_timers:
            self.offline_timers[playerID].cancel()
            del self.offline_timers[playerID]

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
        """Détecte les changements de statut pour lancer ou annuler le timer de déconnexion."""
        user_id = after.id

        # Si le joueur n'est pas dans la liste des gens prêts, on ignore
        if user_id not in readies:
            return

        # Si le joueur passe hors ligne (invisible ou déconnecté)
        if after.status == discord.Status.offline:
            # S'il n'a pas déjà un timer en cours
            if user_id not in self.offline_timers:
                # On lance le chronomètre de 10 minutes
                self.offline_timers[user_id] = asyncio.create_task(self.auto_remove_offline(user_id))
        
        # Si le joueur revient en ligne (online, idle, dnd)
        elif after.status != discord.Status.offline:
            # Si un timer était en cours, on l'annule !
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
        

async def setup(bot):
    await bot.add_cog(ready(bot))
