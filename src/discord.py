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


@bot.command()
async def ensafe(ctx):
    msg = await ctx.send('Would you like to ensafe? (y = Yes, n = No)')
    await msg.add_reaction('y')
    await msg.add_reaction('n')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['y', 'n'] and reaction.message.id == msg.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
        if str(reaction.emoji) == 'y':
            await ctx.send('You chose to ensafe! now we will proceed with the action')
        else:
            await ctx.send('You chose not to ensafe we will increase their social credit to be safe.')
    except Exception:
        await ctx.send('No response received. Please try again.')


bot.run(token, log_handler=handler, log_level=logging.DEBUG)