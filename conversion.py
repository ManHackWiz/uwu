import discord
import requests
import typing
from typing import Union
from discord.ext.commands import cooldown, BucketType
import asyncio
from discord.ext.commands import CommandOnCooldown

from discord.ext import commands
from bs4 import BeautifulSoup

TOKEN = 'no'
COOKIE_SERVER_URL = 'https://versions.pythonanywhere.com'

bot = commands.Bot(command_prefix='.', intents=discord.Intents.all())



@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Please try again in {error.retry_after:.2f} seconds. This is to prevent ratelimit in your Roblox Account.\n**Note:** If you are getting ratelimited errors, please try again later!")    

def set_cookie(discord_user_id, roblox_cookie):
    if not roblox_cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|_'):
        return False

    response = requests.post(f'{COOKIE_SERVER_URL}/setcookie', json={'discord_user_id': discord_user_id, 'roblox_cookie': roblox_cookie})
    return response.status_code == 200

def get_cookie(discord_user_id):
    response = requests.get(f'{COOKIE_SERVER_URL}/getcookie/{discord_user_id}')
    if response.status_code == 200:
        return response.json().get('roblox_cookie')
    else:
        return None

@bot.command(name='joinuser', description='Join a user by link')
@cooldown(1, 10, BucketType.user)
async def join_user(ctx, user_identifier: Union[int, str]):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    protected_page_url = 'https://roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})

    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    if isinstance(user_identifier, int):
        user_id = user_identifier
    elif isinstance(user_identifier, str):
        username_to_user_id_payload = {
            "usernames": [
                user_identifier
            ],
            "excludeBannedUsers": True
        }
        response = session.post('https://users.roblox.com/v1/usernames/users', json=username_to_user_id_payload, headers={'X-CSRF-TOKEN': csrf_token, 'accept': 'application/json', 'Content-Type': 'application/json'})
        if response.status_code == 200:
            user_id = response.json().get('data')[0].get('id')
        else:
            await ctx.send(f"Failed to find user with username '{user_identifier}'")
            return
    else:
        await ctx.send("Invalid input. Please provide a valid user ID or username.")
        return

    join_url = 'https://presence.roblox.com/v1/presence/users'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-CSRF-TOKEN': csrf_token
    }
    data = {
        "userIds": [
            user_id
        ]
    }

    response = session.post(join_url, headers=headers, json=data)

    if response.status_code == 200:
        user_presences = response.json().get('userPresences', [])
        if user_presences:
            presence = user_presences[0]
            user_presence_type = presence.get('userPresenceType')
            game_id = presence.get('gameId')
            place_id = presence.get('placeId')
            game = presence.get('lastLocation')

            if user_presence_type == 2:
                if game_id == 'null' or place_id == 'null':
                    await ctx.send("Failed to join user: The user is not friends with you or their joins are off")
                else:
                    join_link = f'https://auth-join.daiplayzroblox.workers.dev/?placeId={place_id}&gameInstanceId={game_id}'
                    await send_join_embed(ctx, user_id, join_link, game)
            elif user_presence_type in [0, 1, 3]:
                await ctx.send("Failed to join user: The user is not in a game")
            else:
                await ctx.send("Failed to get presence info | 1")
        else:
            await ctx.send("Failed to get presence info | 2")
    else:
        await ctx.send(f"Failed to join user with ID: `{user_id}`. Status code: {response.status_code}")

async def send_join_embed(ctx, user_id, join_link, game):
    user_info_response = requests.get(f'https://users.roblox.com/v1/users/{user_id}')
    if user_info_response.status_code == 200:
        user_info = user_info_response.json()
        username = user_info.get("name", "N/A")
        display_name = user_info.get("displayName", "N/A")
        avatar_url_response = requests.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=250x250&format=Png&isCircular=false")
        avatar_url = avatar_url_response.json().get('data', [{}])[0].get('imageUrl', 'N/A')
        description = user_info.get("description", "N/A")
        is_banned = user_info.get("isBanned", "N/A")
        has_verified_badge = user_info.get("hasVerifiedBadge", "N/A")

        embed = discord.Embed(title=f"Joined User: '{username}'", color=0x00ff00)
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="Username", value=username, inline=False)
        embed.add_field(name="Display Name", value=display_name, inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Ban Status", value=is_banned, inline=False)
        embed.add_field(name="Verified Badge", value=has_verified_badge, inline=False)
        embed.add_field(name="Join", value=f"[Join User]({join_link})", inline=False)
        embed.add_field(name="Experience", value=game, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Failed to retrieve user information.")


@bot.command(name='displayname', description='Changes your display name on Roblox')
@cooldown(1, 10, BucketType.user)
async def change_display_name(ctx, display_name: str):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    new_name = display_name
    protected_page_url = 'https://roblox.com/login'
    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    login_page_response = session.get(protected_page_url)
    login_page_soup = BeautifulSoup(login_page_response.content, 'html.parser')
    csrf_meta_tag = login_page_soup.find('meta', {'name': 'csrf-token'})

    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    user_info = session.get('https://users.roblox.com/v1/users/authenticated')
    user_info_response = user_info.json()

    if "id" not in user_info_response:
        await ctx.send("Failed to Change Display Name: Invalid Roblox Cookie.")
        return

    display_names_url = f'https://users.roblox.com/v1/users/{user_info_response["id"]}/display-names'

    display_names_headers = {
        'Content-Type': 'application/json',
        'X-Csrf-Token': csrf_token,
        'accept': 'application/json',
    }

    update_display_name_payload = {
        'newDisplayName': new_name
    }

    update_display_name_response = session.patch(display_names_url, headers=display_names_headers, json=update_display_name_payload)

    if update_display_name_response.status_code == 200:
        await ctx.send(f"Your display name has successfully changed to `{new_name}`")
    elif update_display_name_response.status_code == 429:
        await ctx.send(f"Failed to Change Display Name: You are currently on cooldown by Roblox.")
    elif update_display_name_response.status_code == 403:
        await ctx.send(f"Failed to Change Display Name: The Roblox Cookie you provided doesn't show your user ID. "
                       f"If your token is invalid, I suggest you re-link your Roblox cookie by executing the command '/setcookie'.")
    elif update_display_name_response.status_code == 401:
        await ctx.send(f'Failed to Change Display Name: Authorization has been denied for this request.')
    elif update_display_name_response.status_code == 400:
        response_json = update_display_name_response.json()
        error_message = response_json["errors"][0]["message"]
        await ctx.send(f'Failed to Change Display Name: {error_message}')

@bot.command(name='setcookie', description='Set Roblox cookie for the user')
@cooldown(1, 10, BucketType.user)
async def setcookie(ctx, roblox_cookie: str):
    if set_cookie(str(ctx.author.id), roblox_cookie):
        await ctx.send("Roblox cookie set successfully!")
    else:
        await ctx.send("Invalid Roblox cookie format. Please use a valid cookie.")

@bot.command(name='checkcookie', description='Check if the current Roblox cookie is valid')
@cooldown(1, 10, BucketType.user)
async def check_cookie(ctx):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    user_info_response = session.get('https://users.roblox.com/v1/users/authenticated')

    if user_info_response.status_code == 200:
        user_info = user_info_response.json()
        display_name = user_info.get("displayName", "N/A")
        name = user_info.get("name", "N/A")
        user_id = user_info.get("id", "N/A")

        description_response = session.get(f"https://users.roblox.com/v1/users/{user_id}")
        if description_response.status_code == 200:
            description_data = description_response.json()
            description = description_data.get("description", "N/A")
            is_banned = description_data.get("isBanned", "N/A")
            has_verified_badge = description_data.get("hasVerifiedBadge", "N/A")
        else:
            description = "N/A"
            is_banned = "N/A"
            has_verified_badge = "N/A"

        avatar_response = session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=250x250&format=Png&isCircular=false")
        if avatar_response.status_code == 200:
            avatar_data = avatar_response.json().get("data")
            if avatar_data:
                avatar_url = avatar_data[0].get("imageUrl")
            else:
                avatar_url = None 
        else:
            avatar_url = None  

        if description == '':
            description = 'User has no description'

        embed = discord.Embed(title="Roblox User Information", color=0x00ff00)
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="Display Name", value=display_name, inline=False)
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Ban Status", value=is_banned, inline=False)
        embed.add_field(name="Verified Badge", value=has_verified_badge, inline=False)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("Roblox cookie is invalid. Please set a new one using the .setcookie command.")

@bot.command(name='changedescription', description='Changes your Roblox description')
@cooldown(1, 10, BucketType.user)
async def change_description(ctx, new_description: str):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    description_payload = {
        'description': new_description
    }

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    response = session.post('https://users.roblox.com/v1/description', json=description_payload, headers=headers)

    if response.status_code == 200:
        await ctx.send(f"Your description has successfully changed to `{new_description}`")
    elif response.status_code == 400:
        error_code = response.json().get('errors')[0].get('code')
        if error_code == 1:
            await ctx.send("Failed to Change Description: User not found.")
        else:
            await ctx.send("Failed to Change Description: Please try again later.")
    elif response.status_code == 403:
        await ctx.send("Failed to Change Description: PIN is locked (I will find a way to do the pin automatically)")
    elif response.status_code == 500:
        error_code = response.json().get('errors')[0].get('code')
        await ctx.send(f"Failed to Change Description: An unknown error occurred")
    elif response.status_code == 503:
        error_code = response.json().get('errors')[0].get('code')
        if error_code == 3:
            await ctx.send("Failed to Change Description: This feature is currently disabled. Please try again later.")
    else:
        await ctx.send("Failed to change description: Please try again later.")

@bot.command(name='usestarcode', description='Use a star code')
@cooldown(1, 10, BucketType.user)
async def use_star_code(ctx, star_code: str):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    response = session.post('https://accountinformation.roblox.com/v1/star-code-affiliates', headers=headers, json={'code':star_code})

    if response.status_code == 200:
        user_info_response = session.get('https://accountinformation.roblox.com/v1/star-code-affiliates', headers=headers)
        user_info_endpoint_response = session.get(f'https://users.roblox.com/v1/users/{user_info_response.json().get("userId")}', headers=headers)
        username_info = user_info_endpoint_response.json().get('name')
        displayname_info = user_info_endpoint_response.json().get('displayName')
        ban_status_info = user_info_endpoint_response.json().get('isBanned')
        verify_status_info = user_info_endpoint_response.json().get('hasVerifiedBadge')


        if user_info_response.status_code == 200:
            user_info = user_info_response.json()
            user_id = user_info.get("userId", "N/A")
            youtuber_name = user_info.get("name", "N/A")
            avatar_url = session.get(f'https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=250x250&format=Png&isCircular=false')
            avatar_url_res = avatar_url.json().get('data', [{}])[0].get('imageUrl')
            embed = discord.Embed(title=f"You are now supporting '{star_code}' :tada:!", color=0xffd700)
            embed.set_thumbnail(url=avatar_url_res)
            embed.add_field(name="User ID", value=user_id, inline=False)
            embed.add_field(name="Username", value=username_info, inline=False)
            embed.add_field(name="Display Name", value=displayname_info, inline=False)
            embed.add_field(name="Banned", value=ban_status_info, inline=False)
            embed.add_field(name="Verified Badge", value=verify_status_info, inline=False)
            embed.add_field(name="Youtuber Name", value=youtuber_name, inline=False)
            await ctx.send('Star code applied successfully!')
            await ctx.send(embed=embed)
    elif response.status_code == 400:
        await ctx.send("Failed to apply star code: The code was invalid")
    elif response.status_code == 500:
        await ctx.send("Failed to apply star code: An unknown error has occurred")


@bot.command(name='removestarcode', description='Delete the star code')
@cooldown(1, 10, BucketType.user)
async def delete_star_code(ctx):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    user_info_response = session.get('https://accountinformation.roblox.com/v1/star-code-affiliates', headers=headers)
    user_info_response_json = user_info_response.json()

    response = session.delete('https://accountinformation.roblox.com/v1/star-code-affiliates', headers=headers)

    if response.status_code == 200:
        await ctx.send(f"Star code removed successfully! You were using star code '{user_info_response_json.get('code')}'")
    elif response.status_code == 404:
        await ctx.send("Failed to remove star code: No star code found to remove.")
    elif response.status_code == 500:
        await ctx.send("Failed to remove star code: An unknown error has occurred")

@bot.command(name='declineallfriendreqs', description='Decline all friend requests')
@cooldown(1, 10, BucketType.user)
async def decline_all_requests(ctx):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    response = session.post('https://friends.roblox.com/v1/user/friend-requests/decline-all', headers=headers)

    if response.status_code == 200:
        await ctx.send("All friend requests declined successfully!")
    elif response.status_code == 404:
        await ctx.send("No friend requests found to decline.")
    elif response.status_code == 500:
        await ctx.send("Failed to decline friend requests: An unknown error has occurred")
    
@bot.command(name='acceptfriendreq', description='Accept a friend request by user ID or username')
@cooldown(1, 10, BucketType.user)
async def accept_friend_request(ctx, user: Union[int, str]):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    if isinstance(user, int):
        user_id = user
    else: 
        response = session.post('https://users.roblox.com/v1/usernames/users', json={"usernames": [user], "excludeBannedUsers": True}, headers=headers)
        if response.status_code == 200:
            user_id = response.json()["data"][0].get('id')
        else:
            await ctx.send(f"Failed to find user with username {user}.")
            return

    response = session.post(f'https://friends.roblox.com/v1/users/{user_id}/accept-friend-request', headers=headers)

    if response.status_code == 200:
        user_info_response = session.get(f'https://users.roblox.com/v1/users/{user_id}', headers=headers)
        if user_info_response.status_code == 200:
            user_info = user_info_response.json()
            username = user_info.get("name", "N/A")
            display_name = user_info.get("displayName", "N/A")
            description = user_info.get("description", "N/A")
            is_banned = user_info.get("isBanned", "N/A")
            has_verified_badge = user_info.get("hasVerifiedBadge", "N/A")
            avatar_response = session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=250x250&format=Png&isCircular=false", headers=headers)
            if avatar_response.status_code == 200:
                avatar_data = avatar_response.json().get("data")
                if avatar_data:
                    avatar_url = avatar_response.json().get('data', [{}])[0].get('imageUrl')
                    embed = discord.Embed(title="Friend Request Accepted", color=0xffd700)
                    embed.set_thumbnail(url=avatar_url)
                    embed.add_field(name="Username", value=username, inline=False)
                    embed.add_field(name="Display Name", value=display_name, inline=False)
                    embed.add_field(name="Description", value=description, inline=False)
                    embed.add_field(name="Ban Status", value=is_banned, inline=False)
                    embed.add_field(name="Verified Badge", value=has_verified_badge, inline=False)
                    await ctx.send("Friend request accepted successfully!")
                    await ctx.send(embed=embed)
                    return
        else:
            await ctx.send("Failed to fetch user information.")
    else:
        error_message = ""
        error_data = response.json().get("errors", [{}])[0]
        error_code = error_data.get("code", -1)
        error_message = error_data.get("message", "Unknown error occurred.")
        if error_code == 1:
            error_message = "The user is invalid or doesn't exist"
        elif error_code == 10:
            error_message = "The friend request doesn't exist"
        elif error_code == 11:
            error_message = "You have exceeded the max number of friends on Roblox"
        elif error_code == 12:
            error_message = "The user has exceeded the max number of friends on Roblox"
        elif error_code == 3:
            error_message = "You are blocked from sending a friend request"
        
        await ctx.send(f"Failed to accept friend request: {error_message}")

@bot.command(name='declinefriendreq', description='Decline a friend request by user ID or username')
@cooldown(1, 10, BucketType.user)
async def decline_friend_request(ctx, user: Union[int, str]):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    if isinstance(user, int): 
        user_id = user
    else:
        response = session.post('https://users.roblox.com/v1/usernames/users', json={"usernames": [user], "excludeBannedUsers": True}, headers=headers)
        if response.status_code == 200:
            user_id = response.json()["data"][0].get('id')  
        else:
            await ctx.send(f"Failed to find user with username {user}.")
            return

    response = session.post(f'https://friends.roblox.com/v1/users/{user_id}/decline-friend-request', headers=headers)

    if response.status_code == 200:
        user_info_response = session.get(f'https://users.roblox.com/v1/users/{user_id}', headers=headers)
        if user_info_response.status_code == 200:
            user_info = user_info_response.json()
            username = user_info.get("name", "N/A")
            display_name = user_info.get("displayName", "N/A")
            is_banned = user_info.get("isBanned", "N/A")
            has_verified_badge = user_info.get("hasVerifiedBadge", "N/A")
            avatar_url_response = session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=250x250&format=Png&isCircular=false")
            avatar_url_json = avatar_url_response.json()
            avatar_url = avatar_url_json.get('data', [{}])[0].get('imageUrl')

            
            embed = discord.Embed(title="Friend Request Declined", color=0xff0000)
            embed.set_thumbnail(url=avatar_url)
            embed.add_field(name="Username", value=username, inline=False)
            embed.add_field(name="Display Name", value=display_name, inline=False)
            embed.add_field(name="Banned", value=is_banned, inline=False)
            embed.add_field(name="Verified Badge", value=has_verified_badge, inline=False)
            
            await ctx.send("Friend request declined successfully!", embed=embed)
        else:
            await ctx.send("Friend request declined successfully!")
    else:
        error_message = ""
        error_data = response.json().get("errors", [{}])[0]
        error_code = error_data.get("code", -1)
        if error_code == 1:
            error_message = "The user is invalid or doesn't exist"
        elif error_code == 10:
            error_message = "The friend request does not exist"
        else:
            error_message = error_data.get("message", "Unknown error occurred.")
        await ctx.send(f"Failed to decline friend request: {error_message}")

@bot.command(name='frienduser', description='Add a friend on Roblox by user ID or username')
@cooldown(1, 10, BucketType.user)
async def add_friend(ctx, friend_identifier: Union[int, str]):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    if isinstance(friend_identifier, int):
        friend_user_id = friend_identifier
    else:
        username_to_user_id_payload = {
            "usernames": [
                friend_identifier
            ],
            "excludeBannedUsers": True
        }
        response = session.post('https://users.roblox.com/v1/usernames/users', json=username_to_user_id_payload, headers=headers)
        if response.status_code == 200:
            user_id = response.json().get('data')[0].get('id')
            friend_user_id = user_id
        else:
            await ctx.send(f"Failed to find user with username '{friend_identifier}'")
            return

    add_friend_payload = {
        "friendshipOriginSourceType": 0
    }

    response = session.post(f'https://friends.roblox.com/v1/users/{friend_user_id}/request-friendship', json=add_friend_payload, headers=headers)

    if response.status_code == 200:
        friend_info_response = session.get(f'https://users.roblox.com/v1/users/{friend_user_id}')
        if friend_info_response.status_code == 200:
            friend_info = friend_info_response.json()
            friend_username = friend_info.get("name", "N/A")
            friend_displayname = friend_info.get("displayName", "N/A")
            friend_avatar_url_response = session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={friend_user_id}&size=250x250&format=Png&isCircular=false")
            friend_avatar_url = friend_avatar_url_response.json().get('data', {})[0].get('imageUrl', 'N/A')
            friend_description = friend_info.get("description", "N/A")
            friend_is_banned = friend_info.get("isBanned", "N/A")
            friend_has_verified_badge = friend_info.get("hasVerifiedBadge", "N/A")

            embed = discord.Embed(title=f"Friend Request Sent to '{friend_username}'", color=0x00ff00)
            embed.set_thumbnail(url=friend_avatar_url)
            embed.add_field(name="Username", value=friend_username, inline=False)
            embed.add_field(name="Display Name", value=friend_displayname, inline=False)
            embed.add_field(name="Description", value=friend_description, inline=False)
            embed.add_field(name="Ban Status", value=friend_is_banned, inline=False)
            embed.add_field(name="Verified Badge", value=friend_has_verified_badge, inline=False)

            await ctx.send("Friend request sent successfully!")
            await ctx.send(embed=embed)
    elif response.status_code == 400:
        response_json = response.json()
        error_code = response_json.get('errors')[0].get('code')
        if error_code == 1:
            await ctx.send("Failed to send friend request: The user is invalid or doesn't exist")
        elif error_code == 5:
            await ctx.send("Failed to send friend request: The user is already a friend")
        elif error_code == 7:
            await ctx.send("Failed to send friend request: The user cannot be friends with itself")
        elif error_code == 10:
            await ctx.send("Failed to send friend request: The friend request does not exist")
        elif error_code == 31:
            await ctx.send("Failed to send friend request: User with max friends sent friend request")
    elif response.status_code == 403:
        response_json = response.json()
        error_code = response_json.get('errors')[0].get('code')
        print(f"Error: Failed to send friend request - {error_code} | 403")
        if error_code == 2:
            await ctx.send("Failed to send friend request: The user is banned from performing operation")
        elif error_code == 3:
            await ctx.send("Failed to send friend request: You are blocked from sending a friend request")
        elif error_code == 14:
            await ctx.send("Failed to send friend request: The user has not passed the captcha")
        elif error_code == 0:
            await ctx.send("Failed to send friend request: You are being ratelimited (Forbidden). Please try again later!")
    elif response.status_code == 429:
        response_json = response.json()
        error_code = response_json.get('errors')[0].get('code')
        print(f"Error: Failed to send friend request - {error_code} | 429")
        if error_code == 9:
            await ctx.send("Failed to send friend request: The flood limit has been exceeded")
    else:
        await ctx.send("Failed to send friend request. Please try again later.")




@bot.command(name='unfrienduser', description='Unfriend a user on Roblox by user ID or username')
@cooldown(1, 10, BucketType.user)
async def unfriend_user(ctx, user_identifier: Union[int, str]):
    roblox_cookie = get_cookie(str(ctx.author.id))
    if roblox_cookie is None:
        await ctx.send("Roblox cookie not found. Please use the .setcookie command to set it.")
        return

    session = requests.Session()
    session.cookies.update({'.ROBLOSECURITY': roblox_cookie})

    csrf_token = None
    protected_page_url = 'https://www.roblox.com/login'
    protected_page_response = session.get(protected_page_url)
    protected_page_soup = BeautifulSoup(protected_page_response.content, 'html.parser')
    csrf_meta_tag = protected_page_soup.find('meta', {'name': 'csrf-token'})
    if csrf_meta_tag:
        csrf_token = csrf_meta_tag.get('data-token', '')
    else:
        await ctx.send("Failed to retrieve CSRF token.")
        return

    headers = {
        'X-CSRF-TOKEN': csrf_token,
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    if isinstance(user_identifier, int):
        user_id = user_identifier
    else:
        username = user_identifier.lower()
        
        username_to_user_id_payload = {
            "usernames": [
                username
            ],
            "excludeBannedUsers": True
        }
        response = session.post('https://users.roblox.com/v1/usernames/users', json=username_to_user_id_payload, headers=headers)
        if response.status_code == 200:
            user_id = response.json().get('data')[0].get('id')
        else:
            await ctx.send(f"Failed to find user with username '{user_identifier}'")
            return

    unfriend_payload = {}

    response = session.post(f'https://friends.roblox.com/v1/users/{user_id}/unfriend', json=unfriend_payload, headers=headers)

    if response.status_code == 200:
        friend_info_response = session.get(f'https://users.roblox.com/v1/users/{user_id}')
        if friend_info_response.status_code == 200:
            friend_info = friend_info_response.json()
            friend_username = friend_info.get("name", "N/A")
            friend_displayname = friend_info.get("displayName", "N/A")
            friend_avatar_url_response = session.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=250x250&format=Png&isCircular=false")
            friend_avatar_url = friend_avatar_url_response.json().get('data', {})[0].get('imageUrl', 'N/A')
            friend_description = friend_info.get("description", "N/A")
            friend_is_banned = friend_info.get("isBanned", "N/A")
            friend_has_verified_badge = friend_info.get("hasVerifiedBadge", "N/A")

            embed = discord.Embed(title="User Unfriended", description=f"The user with ID {user_id} has been unfriended.", color=0x00ff00)
            embed.set_thumbnail(url=friend_avatar_url)
            embed.add_field(name="Username", value=friend_username, inline=False)
            embed.add_field(name="Display Name", value=friend_displayname, inline=False)
            embed.add_field(name="Description", value=friend_description, inline=False)
            embed.add_field(name="Ban Status", value=friend_is_banned, inline=False)
            embed.add_field(name="Verified Badge", value=friend_has_verified_badge, inline=False)

            await ctx.send("User unfriended successfully!", embed=embed)
    elif response.status_code == 400:
        response_json = response.json()
        error_code = response_json.get('errors')[0].get('code')
        if error_code == 1:
            await ctx.send("Failed to unfriend user: The target user is invalid or does not exist")
    else:
        await ctx.send("Failed to unfriend user: Please try again later.")


bot.run(TOKEN)
