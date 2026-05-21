
import discord

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

client.run('ODU0ML1NDM3MjODU0MDI1ODQ1NDM3MjM1MjEw.GidQ6a.dOWcYLi3pQ1JoBtJ__zyaQrp8Z5u4y7K10rhIg')
