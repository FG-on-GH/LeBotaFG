import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from cogs.R2P.manage_libraries import *

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
    
    @app_commands.command(name="ready", description="T'ajoute à la liste des personnes prêtes à jouer")
    async def ready(self, interaction: discord.Interaction):
        last_announcement_id=load_last_annoucement()
        ready_channel_ID=int(os.getenv('READY_CHANNEL_ID'))
        channel=self.bot.get_channel(ready_channel_ID)
        playerID=interaction.user.id
        if playerID not in readies:
            readies.append(playerID)
        await interaction.response.send_message("Tu as bien été ajouté à la liste des joueurs prêts", ephemeral=True)
        if len(readies)==1:
            annoucement=(f"<@{playerID}> est prêt à jouer !")
        else:
            ready_mentions=""
            for IDs in readies:
                ready_mentions+=f"<@{IDs}>, "
            ready_mentions=ready_mentions[:-2]
            annoucement=f"Joueurs prêts :\n{ready_mentions}"
            (prettyprint_common_games, excluded_users)=find_common_games()
            if not prettyprint_common_games:
                annoucement+="\nAucun jeu en commun trouvé"
            else:
                annoucement+=f"\nJeux en commun :\n"
                for title in prettyprint_common_games:
                    annoucement+=f"{title}, "
                annoucement=annoucement[:-2]
            if excluded_users:
                annoucement+=f"\nJoueurs exclus de la recherche (bibliothèque vide) :\n"
                for id in excluded_users:
                    annoucement+=f"<@{id}>, "
                annoucement=annoucement[:-2]
                annoucement+=f"\nUtilisez `/addgame` pour en ajouter puis refaites `/ready` pour relancer la recherche"
        if last_announcement_id:
            try:
                old_msg = await channel.fetch_message(last_announcement_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                # On ignore si le message est déjà supprimé ou si on n'a pas la permission
                pass
        new_msg = await channel.send(annoucement)
        last_announcement_id = new_msg.id
        save_last_announcement(last_announcement_id)

    @app_commands.command(name="unready", description="Te retire de la liste des personnes prêtes à jouer")
    async def unready(self, interaction: discord.Interaction):
        playerID = interaction.user.id
        
        # 1. Vérification
        if playerID not in readies:
            await interaction.response.send_message("Tu n'étais pas dans la liste des joueurs prêts.", ephemeral=True)
            return

        # 2. Retrait de la liste
        readies.remove(playerID)
        await interaction.response.send_message("Tu as bien été retiré de la liste des joueurs prêts.", ephemeral=True)

        # 3. Préparation des variables pour le salon d'annonce
        last_announcement_id = load_last_annoucement()
        ready_channel_ID = int(os.getenv('READY_CHANNEL_ID'))
        channel = self.bot.get_channel(ready_channel_ID)

        # 4. Génération du nouveau message selon le nombre de joueurs restants
        if len(readies) == 0:
            annoucement = "Personne n'est prêt pour le moment. Utilisez `/ready` pour vous ajouter."
        elif len(readies) == 1:
            annoucement = f"<@{readies[0]}> est prêt à jouer !"
        else:
            ready_mentions = ""
            for IDs in readies:
                ready_mentions += f"<@{IDs}>, "
            ready_mentions = ready_mentions[:-2]
            
            annoucement = f"Joueurs prêts :\n{ready_mentions}"
            
            # Recalcul des jeux en commun
            (prettyprint_common_games, excluded_users) = find_common_games()
            
            if not prettyprint_common_games:
                annoucement += "\nAucun jeu en commun trouvé"
            else:
                annoucement += f"\nJeux en commun :\n"
                for title in prettyprint_common_games:
                    annoucement += f"{title}, "
                annoucement = annoucement[:-2]
                
            if excluded_users:
                annoucement += f"\nJoueurs exclus de la recherche (bibliothèque vide) :\n"
                for id in excluded_users:
                    annoucement += f"<@{id}>, "
                annoucement = annoucement[:-2]
                annoucement += f"\nUtilisez /addgame pour en ajouter puis refaites /ready pour relancer la recherche"

        # 5. Remplacement de l'ancien message
        if last_announcement_id:
            try:
                old_msg = await channel.fetch_message(last_announcement_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
                
        new_msg = await channel.send(annoucement)
        save_last_announcement(new_msg.id)
    
    @commands.Cog.listener()
    async def on_ready(self):
        
        # 1. On s'assure que la liste est bien vide au démarrage
        readies.clear()
        
        # 2. On récupère le salon et l'ancien ID
        last_announcement_id = load_last_annoucement()
        ready_channel_ID = int(os.getenv('READY_CHANNEL_ID'))
        channel = self.bot.get_channel(ready_channel_ID)
        
        if channel is None:
            print("Attention : Salon d'annonce introuvable au démarrage.")
            return

        # 3. Suppression de l'ancienne annonce
        if last_announcement_id:
            try:
                old_msg = await channel.fetch_message(last_announcement_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                # Le message a peut-être déjà été supprimé manuellement
                pass
        
        # 4. Envoi du nouveau message de remise à zéro
        announcement = "Personne n'est prêt pour le moment. Utilisez `/ready` pour vous ajouter."
        new_msg = await channel.send(announcement)
        
        # 5. Sauvegarde du nouvel ID
        save_last_announcement(new_msg.id)

        

async def setup(bot):
    await bot.add_cog(ready(bot))
