import os
import discord
import requests
from dotenv import load_dotenv

load_dotenv()

FORUM_CHANNEL_ID = int(os.environ["FORUM_CHANNEL_ID"])
LABEL = "To Categorize"

GITLAB_URL = os.environ["GITLAB_URL"]
GITLAB_TOKEN = os.environ["GITLAB_TOKEN"]
GITLAB_PROJECT_ID = os.environ["GITLAB_PROJECT_ID"]

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

def create_gitlab_issue(title: str, description: str) -> int:
    print("title:", title)
    print("description:", description)

    resp = requests.post(
        f"{GITLAB_URL}/api/v4/projects/{GITLAB_PROJECT_ID}/issues",
        headers={
            "PRIVATE-TOKEN": GITLAB_TOKEN,
        },
        data={
            "title": title,
            "description": description,
            "labels": LABEL,
        },
        timeout=10,
    )

    print("GitLab status:", resp.status_code)
    print("GitLab response:", resp.text)

    resp.raise_for_status()

    return resp.json()["iid"]


client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    
    # Process existing threads when bot starts up
    await process_existing_threads()
    
    print("Available channels:")
    for guild in client.guilds:
        print(f"  Guild: {guild.name} ({guild.id})")
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel) and channel.id == FORUM_CHANNEL_ID:
                print(f"  Found forum channel: {channel.name} ({channel.id})")

async def process_existing_threads():
    print("Processing existing threads...")

    forum_channel = None
    for guild in client.guilds:
        for channel in guild.channels:
            if channel.id == FORUM_CHANNEL_ID and isinstance(channel, discord.ForumChannel):
                forum_channel = channel
                break
        if forum_channel:
            break
    
    if not forum_channel:
        print("Warning: Could not find forum channel")
        return
    
    print(f"Found forum channel: {forum_channel.name}")
    try:
        thread_count = 0
        if hasattr(forum_channel, 'threads'):
            for thread in forum_channel.threads:
                if thread.parent_id == FORUM_CHANNEL_ID:
                    print(f"Processing existing thread: {thread.name} ({thread.id})")
                    await process_thread(thread)
                    thread_count += 1
        
        print(f"Processed {thread_count} existing threads")
        
    except Exception as e:
        print(f"Error processing existing threads: {e}")

async def process_thread(thread):
    try:
        starter = await thread.fetch_message(thread.id)
        description = f"{starter.content}\n\n---\nReported via Discord: {thread.jump_url}"
        
        print("Creating GitLab issue...")
        issue_iid = create_gitlab_issue(title=thread.name, description=description)
        print(f"Created GitLab issue #{issue_iid}")
        await thread.send(f"Logged as GitLab issue #{issue_iid}.")
        print("Sent confirmation message.")
        
    except Exception as e:
        print(f"Error processing thread {thread.name}: {e}")
        try:
            await thread.send(f"Error processing report: {e}")
        except:
            pass

@client.event
async def on_thread_create(thread: discord.Thread):
    print(f"Thread create event received!")
    print(f"Thread ID: {thread.id}")
    print(f"Thread name: {thread.name}")
    print(f"Parent ID: {thread.parent_id}")
    print(f"Forum Channel ID: {FORUM_CHANNEL_ID}")
    
    if thread.parent_id != FORUM_CHANNEL_ID:
        print("Thread not in our forum channel, ignoring...")
        return
    
    print(f"Processing thread {thread.name} ({thread.id})...")
    
    await process_thread(thread)

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN environment variable is not set!")
        exit(1)
    
    print("Starting bot with token...")
    client.run(token)
