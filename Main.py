import discord
from discord.ext import commands
import random, string, time
from github import Github
import traceback
import os

# --- Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "fen6i/codes"
GITHUB_FILE_PATH = "codes.txt"
CHANNEL_ID = 1345155806559080620

# Cooldown settings (in seconds)
GET_COOLDOWN_SECONDS   = 20
VIEW_COOLDOWN_SECONDS  = 20
RESET_COOLDOWN_SECONDS = 18000  # 5 hours

WARNING_MSG = "\n\nWarning: Sharing this code with anyone will result in an Instant perma ban."

# Image URL for the thumbnail.
IMAGE_URL = "https://cdn.discordapp.com/attachments/1329974562036912200/1345152431079821312/jxlogo.png?ex=67c38253&is=67c230d3&hm=882af3864c7798da95cabc7f84b312236db5a393662effed77aa7d8ce5700947"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory storage for user codes and cooldown timestamps.
user_codes = {}
get_cooldowns = {}
view_cooldowns = {}
reset_cooldowns = {}

def generate_random_code():
    """Generates a random 16-character alphanumeric code."""
    allowed = string.ascii_uppercase + string.digits
    return ''.join(random.choices(allowed, k=16))

def get_code_from_github(user_id: int):
    """
    Retrieves the code for the given user_id from GitHub.
    Expected format: "<generated_code> [<user_id>]"
    Returns the first token (generated code) if found; otherwise, None.
    """
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    try:
        file_content = repo.get_contents(GITHUB_FILE_PATH)
        content = file_content.decoded_content.decode("utf-8")
        for line in content.splitlines():
            if f"[{user_id}]" in line:
                parts = line.strip().split(" ", 1)
                if parts:
                    return parts[0]
        return None
    except Exception:
        return None

def update_github_file(user_id: int, new_code: str):
    """
    Updates the GitHub file with the user's new code.
    If a line for that user exists, it replaces it; otherwise, it appends a new line.
    Format: "<generated_code> [<user_id>]"
    """
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    try:
        file_content = repo.get_contents(GITHUB_FILE_PATH)
        content = file_content.decoded_content.decode("utf-8")
        lines = content.splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if f"[{user_id}]" in line:
                new_lines.append(f"{new_code} [{user_id}]")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"{new_code} [{user_id}]")
        updated_content = "\n".join(new_lines)
        repo.update_file(
            GITHUB_FILE_PATH,
            f"Update code for user {user_id}",
            updated_content,
            file_content.sha
        )
    except Exception as e:
        # If the file doesn't exist or any error occurs, create it instead.
        repo.create_file(
            GITHUB_FILE_PATH,
            f"Create codes file for user {user_id}",
            f"{new_code} [{user_id}]"
        )

async def send_ephemeral(interaction: discord.Interaction, msg: str):
    """Helper to send an ephemeral message, using followup if necessary."""
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        print("Error in send_ephemeral:", e)
        traceback.print_exc()

def create_embed():
    """Creates the embed for the interactive panel."""
    embed = discord.Embed(
        title="Manage Premium Code",
        color=discord.Color.blurple(),
        description=(
            "➡️ **Get a Code**: Generate a new single-use code for the Loader.\n\n"
            "➡️ **View Code**: Retrieve your existing code.\n\n"
            "➡️ **Reset Code**: Reset your code (after resetting, your old code will no longer be valid)."
        )
    )
    embed.set_footer(text="@fen6i cookin")
    embed.set_thumbnail(url=IMAGE_URL)
    return embed

class ManageCodeView(discord.ui.View):
    # No on_timeout method (so the bot won't delete the message or repost it)
    def __init__(self):
        super().__init__(timeout=None)  # No timeout
        self.message = None

    @discord.ui.button(label="Get a Code", style=discord.ButtonStyle.green, custom_id="get_code")
    async def get_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            user_id = interaction.user.id
            now = time.time()
            # Cooldown check
            if user_id in get_cooldowns and now - get_cooldowns[user_id] < GET_COOLDOWN_SECONDS:
                remaining = GET_COOLDOWN_SECONDS - (now - get_cooldowns[user_id])
                minutes, seconds = divmod(int(remaining), 60)
                msg = f"Please wait {minutes} minutes and {seconds} seconds before generating a new code."
                await interaction.followup.send(msg, ephemeral=True)
                return
            get_cooldowns[user_id] = now

            code = user_codes.get(user_id)
            if not code:
                code = get_code_from_github(user_id)
                if code:
                    user_codes[user_id] = code
            if code:
                msg = f"You already have a code: **{code}**" + WARNING_MSG
            else:
                new_code = generate_random_code()
                user_codes[user_id] = new_code
                update_github_file(user_id, new_code)
                msg = f"New code generated: **{new_code}**" + WARNING_MSG
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            try:
                await interaction.followup.send("An error occurred while generating your code.", ephemeral=True)
            except Exception:
                pass
            print("Error in get_code:", e)
            traceback.print_exc()

    @discord.ui.button(label="View Code", style=discord.ButtonStyle.primary, custom_id="view_code")
    async def view_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            user_id = interaction.user.id
            now = time.time()
            if user_id in view_cooldowns and now - view_cooldowns[user_id] < VIEW_COOLDOWN_SECONDS:
                remaining = VIEW_COOLDOWN_SECONDS - (now - view_cooldowns[user_id])
                minutes, seconds = divmod(int(remaining), 60)
                msg = f"Please wait {minutes} minutes and {seconds} seconds before viewing your code again."
                await interaction.followup.send(msg, ephemeral=True)
                return
            view_cooldowns[user_id] = now

            code = user_codes.get(user_id) or get_code_from_github(user_id)
            if code:
                user_codes[user_id] = code
                msg = f"hey, {interaction.user.mention} your code is **{code}**" + WARNING_MSG
            else:
                msg = "You don't have a code yet. Use **Get a Code** to generate one."
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            try:
                await interaction.followup.send("An error occurred while retrieving your code.", ephemeral=True)
            except Exception:
                pass
            print("Error in view_code:", e)
            traceback.print_exc()

    @discord.ui.button(label="Reset Code", style=discord.ButtonStyle.danger, custom_id="reset_code")
    async def reset_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            user_id = interaction.user.id
            now = time.time()
            if user_id in reset_cooldowns and now - reset_cooldowns[user_id] < RESET_COOLDOWN_SECONDS:
                remaining = RESET_COOLDOWN_SECONDS - (now - reset_cooldowns[user_id])
                minutes, seconds = divmod(int(remaining), 60)
                msg = f"Please wait {minutes} minutes and {seconds} seconds before resetting your code again."
                await interaction.followup.send(msg, ephemeral=True)
                return
            reset_cooldowns[user_id] = now
            if user_codes.get(user_id) or get_code_from_github(user_id):
                new_code = generate_random_code()
                user_codes[user_id] = new_code
                update_github_file(user_id, new_code)
                msg = f"Your code has been reset: **{new_code}**" + WARNING_MSG
            else:
                msg = "You don't have a code yet. Use **Get a Code** to generate one."
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            try:
                await interaction.followup.send("An error occurred while resetting your code.", ephemeral=True)
            except Exception:
                pass
            print("Error in reset_code:", e)
            traceback.print_exc()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("Error: Specified channel not found.")
        return
    embed = create_embed()
    view = ManageCodeView()  # No timeout, so it never deletes
    msg = await channel.send(embed=embed, view=view)
    view.message = msg
    print(f"Embed posted in channel {channel.name} ({CHANNEL_ID}).")

bot.run(BOT_TOKEN)
