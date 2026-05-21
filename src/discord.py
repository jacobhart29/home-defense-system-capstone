
import discord
from discord.ext import commands
import os
import logging 
from dotenv import load_dotenv


token = ('ODU0ML1NDM3MjODU0MDI1ODQ1NDM3MjM1MjEw.GidQ6a.dOWcYLi3pQ1JoBtJ__zyaQrp8Z5u4y7K10rhIg')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'We ready to go in {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

bot.run(token, log_handler=handler, log_level=logging.DEBUG) 