import os

import discord
from discord.ext import commands

from datetime import datetime
import pytz

from passlib.hash import pbkdf2_sha256

from threading import Thread, Event

import csv

import pandas
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.ticker import AutoMinorLocator

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import text

engine = create_engine(os.getenv("HOST"))
db = scoped_session(sessionmaker(bind=engine))

def updateBotFileBalances():
  rs = db.execute(text('SELECT * FROM public.user'))
  for row in rs:
    liveData.userAccounts = [{k:(float(row[3]) if (k == "STC" and userDict['freemartId'] == row[0]) else v) for (k,v)  in userDict.items() } for userDict in liveData.userAccounts]


def updateFreemartFileBalances():
  for user in liveData.userAccounts:
    if user["Name"] != "pool":
      db.execute(text(f"UPDATE public.user SET balance = {user['STC']} WHERE id = {int(user['freemartId'])}"))
      db.commit()

      
TOKEN = os.getenv("TOKEN")
RED = 0x3498db
PURPLE = 0x7289da
BLUE = 0x3498db
choiceNumbers = [
  "0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"
]


description = '''Trade stock, lose money!'''
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="$",
                   description=description,
                   intents=intents)

# -- Daily update script --


class MyThread(Thread):

  def __init__(self, event):
    Thread.__init__(self)
    self.stopped = event

  def run(self):
    
    while True:
      updated = False
      now = datetime.now(pytz.timezone('Pacific/Auckland'))
      while (now.hour == 0 and now.minute == 0 and now.second == 0):
        now = datetime.now(pytz.timezone('Pacific/Auckland'))
        if not updated:
          updated = True
          updateRecord()
        else:
          pass


def updateRecord():
  time = datetime.now(pytz.timezone('Pacific/Auckland'))
  date = f"{time.year}-{time.month}-{time.day}"

  priceSum = 0
  for record in liveData.dailyRecords:
    priceSum += record["Price"]
  try:
    dailyPriceAvarage = priceSum / len(liveData.dailyRecords)
  except ZeroDivisionError:
    dailyPriceAvarage = liveData.records[-1]["Price"]

  liveData.records.append({
    "Date": date,
    "Price": dailyPriceAvarage
    })
  
  liveData.updateDatabase(True)


my_event = Event()
thread = MyThread(my_event)
thread.start()

# -- End daily update script --


class liveDatabase():

  def __init__(self):
    #Order matters, do not change!
    self.listNames = ["saleOffers", "userAccounts", "dailyRecords", "records"]

    self.loadDatabase()
    self.lll = [
      self.saleOffers, self.userAccounts, self.dailyRecords, self.records
    ]

    self.updateDatabase(first=True)
    print("Live database initialised.")

  def loadDatabase(self):
    for listName in self.listNames:
      with open(f'{listName}.csv', "r") as f:
        fileContent = list(csv.DictReader(f))

      if listName == "userAccounts":
        int_vals = ["$", "STC", "freemartId"]
      elif listName == "saleOffers":
        int_vals = ["q", "price"]
      elif listName == "dailyRecords" or listName == "records":
        int_vals = ["Price"]
      else:
        int_vals = []

      #Convert int_vals to int data-type
      fileContent = [{
        key: (float(val) if key in int_vals else val)
        for key, val in record.items()
      } for record in fileContent]

      exec("self.{} = {}".format(listName, fileContent))
      print(f'{listName}: {fileContent}\n')

  def updateDatabase(self, clearDaily=False, first=False):
    try:
      self.saleOffers[0]['price'] = self.dailyRecords[-1]['Price'] * 1.05
    except IndexError:
      pass

    if not first:
      updateFreemartFileBalances()
      
    
    listIndex = -1

    print("---Saving lists---")
    self.lll = [
      self.saleOffers, self.userAccounts, self.dailyRecords, self.records
    ]
    for list in self.lll:
      listIndex += 1

      if list == [] or (clearDaily and self.listNames[listIndex] == 'dailyRecords'):
        with open(f'{self.listNames[listIndex]}.csv', 'r+') as f:
            f.readline()
            f.truncate(f.tell())
        print(".........\n")
        continue
      

      keys = list[0].keys()
      print(keys)
      print(list)
      with open(f'{self.listNames[listIndex]}.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(list)
      print(".........\n")
      


def record(saleDict, amount):
  time = datetime.now(pytz.timezone('Pacific/Auckland'))
  pricePerCoin = saleDict["price"] / saleDict['q']
  saleRecord = {
    "Time": f'{time.hour}:{time.minute}',
    "Price": pricePerCoin
  }
  liveData.dailyRecords.append(saleRecord)


def generateProfileEmbed(userName):
  userDict = getDict(liveData.userAccounts, "Name", userName)
  profileEmbed = discord.Embed(
    title=f"{userName}'s Profile!",
    description=f'''
      Name: {userName}\n
      $: **{userDict['$']}**\n
      STC: **{userDict['STC']}**''',
    color=BLUE
  )
  return profileEmbed


def generateEmbed(bOs):
  saleEmbed = discord.Embed(
    title=f"{bOs} Offers",
    description="Press corresponding number to accept an offer.")
  saleEmbed.add_field(inline=False,
                      name="ID",
                      value=f'{bOs}er       Quantity       Price')
  saleEmbed.set_footer(
    text="P.S. you can use $sc _idNumber_ to accept a buy offer straight away."
  )
  for saleOffer in liveData.saleOffers:
    if saleOffer["type"] == bOs and saleOffer["name"] != "pool":
      saleEmbed.add_field(
        inline=False,
        name=saleOffer["id"],
        value=
        f'{saleOffer["name"]}       {saleOffer["q"]}     {saleOffer["price"]}')
  return saleEmbed


def registerUser(ctx, currentSTCPrice, id):
  welcomeEmbed = discord.Embed(
    title=f'Welocme to STC, {ctx.author}!',
    description='Buy, sell and exchange coins. Turn a profit if you can...',
    color=RED)
  welcomeEmbed.set_footer(
    text=
    f'Your balance has been topped with an initial ${currentSTCPrice*5.0}, enough for 5 coins rn. Yapi!'
  )
  
  liveData.userAccounts.append({
    "Name": str(ctx.author),
    "freemartId": float(id),
    "$": currentSTCPrice * 5.0,
    "STC": 0
  })
  updateBotFileBalances()
  return welcomeEmbed


def getDict(dictList, key, value, type=None):
  for dict in dictList:
    if dict[key] == value:
      if type:
        if dict["type"] == type:
          return dict
      else:
        return dict
  raise KeyError(f'No dictionary in list with {key} of {value} found!')


def proccessOffer(ctx, id, type, amount=1, pool=False):
  saleOffer = getDict(liveData.saleOffers, "id", id, type)
  if canAfford(str(ctx.author), saleOffer, amount):
    if saleOffer['name'] == str(ctx.author):
      return "You can't purchase stock from yourself!"
    chargeAccounts(str(ctx.author), saleOffer, amount)
    record(saleOffer, amount)
    if saleOffer['name'] != 'pool':
      liveData.saleOffers.remove(saleOffer)
      return f'{ctx.author} accepted {type.lower()} offer {saleOffer["id"]} from {saleOffer["name"]}'  
    if pool:
      return f'{ctx.author} bought coins from the pool at {saleOffer["price"]}/per coin'     
  return 'You cannot afford this offer!'


def canAfford(userName, saleOffer, amount):
  key = "$" if saleOffer['type'] == 'Sell' else 'STC'
  if getDict(liveData.userAccounts, "Name", userName)[key] >= saleOffer['price'] * amount:
    return True
  return False


def chargeAccounts(userName, saleDict, amount):
  q = (saleDict['q'] * amount)
  price = (saleDict['price'] * amount)
  productKey = "STC" if saleDict['type'] == "Sell" else "$"
  priceKey = "$" if saleDict['type'] == "Sell" else "STC"
  accepterIndex = liveData.userAccounts.index(getDict(liveData.userAccounts, "Name", userName))
  sellerIndex = liveData.userAccounts.index(getDict(liveData.userAccounts, "Name", saleDict['name']))
  liveData.userAccounts[sellerIndex][priceKey] += price
  liveData.userAccounts[sellerIndex][productKey] -= q
  liveData.userAccounts[accepterIndex][priceKey] -= price
  liveData.userAccounts[accepterIndex][productKey] += q
  
  
  return True


def getBalance(userName, currency):
  return getDict(liveData.userAccounts, "Name", userName)[currency]


def publishSaleOffer(ctx, q, price, type):
  i = 0
  for offer in liveData.saleOffers:
    if offer["type"] == type:
      i += 1
  newSaleOffer = {
    "id": choiceNumbers[i + 1],
    "name": str(ctx.author),
    "q": float(q),
    "price": float(price),
    "type": type
  }
  
  try:
    existingOffer = getDict(liveData.saleOffers, "name", str(ctx.author), type)
  except KeyError:
    liveData.saleOffers.append(newSaleOffer)
    return newSaleOffer
  return existingOffer['id']


def saleTypeList(type):
  saleListOfType = []
  for dict in liveData.saleOffers:
    if dict["type"] == type:
      saleListOfType.append(dict)
  print(saleListOfType)
  if len(saleListOfType): return saleListOfType
  raise KeyError("No sale offers of specified type")


def plotTrend():
  df = pandas.read_csv("records.csv")
  df["Date"] = pandas.to_datetime(df["Date"], format='%Y-%m-%d')
  
  fig, ax = plt.subplots()
  ax.plot(df["Date"], df["Price"], "r.-")
  plt.title("Trend")
  plt.ylabel('Price')
  plt.xlabel("Date")
  date_form = DateFormatter('%Y-%m-%d')
  ax.xaxis.set_major_formatter(date_form)
  ax.yaxis.set_minor_locator(AutoMinorLocator(5))
  ax.xaxis.set_minor_locator(AutoMinorLocator(5))
  ax.grid(which='major', color='#393E46', linestyle='-')
  ax.grid(which='minor', color='#6D9886', linestyle='--')
  plt.style.use("fivethirtyeight")
  plt.subplots_adjust(bottom=0.18)
  plt.ylim(ymin=0.0)
  fig.autofmt_xdate()
  
  plt.savefig("trend.png")
  
  plt.style.use('default')


def plotDailyTrend():
  df = pandas.read_csv("dailyRecords.csv")
  df["Time"] = pandas.to_datetime(df["Time"], format='%H:%M')
  
  fig, ax = plt.subplots()
  ax.plot(df["Time"], df["Price"], "r.-")
  plt.title("Daily Trend")
  plt.ylabel('Price')
  plt.xlabel("Time")
  date_form = DateFormatter('%H:%M')
  ax.xaxis.set_major_formatter(date_form)
  ax.yaxis.set_minor_locator(AutoMinorLocator(5))
  ax.xaxis.set_minor_locator(AutoMinorLocator(5))
  ax.grid(which='major', color='#393E46', linestyle='-')
  ax.grid(which='minor', color='#6D9886', linestyle='--')
  plt.style.use('fivethirtyeight')
  plt.subplots_adjust(bottom=0.18)
  plt.ylim(ymin=0.0)
  
  plt.savefig("dailyTrend.png")
  
  plt.style.use('default')


liveData = liveDatabase()
updateBotFileBalances()

@bot.event
async def on_ready():
  print(f'{bot.user} booting...')
  print('------')
  for guild in bot.guilds:
    print(f"Connected to {guild}")
  print("------" * 2)




@bot.event
async def on_message(ctx):
    if not ctx.guild and ctx.author != bot.user:
        rs = db.execute(text('SELECT * FROM public.user'))
        for row in rs:
          if row[0] == ctx.content.split(' ')[0]:
            if pbkdf2_sha256.verify(ctx.content.split(' ')[1], row[2]):
              print("FreemArt LOGIN")
              try:
                await ctx.reply(embed=registerUser(
        ctx,liveData.dailyRecords[-1]["Price"], ctx.content.split(' ')[0]), mention_author=False)
              except IndexError:
                await ctx.reply(embed=registerUser(
        ctx,liveData.records[-1]["Price"], ctx.content.split(' ')[0]), mention_author=False)
        liveData.updateDatabase()
    else:
      if ctx.author != bot.user:
        if str(ctx.author) in [user['Name'] for user in liveData.userAccounts]:
          await bot.process_commands(ctx)
        else:
          await ctx.reply('Check DMs to login to your FreeMart account', mention_author=True)
          discordUserName = await bot.fetch_user(ctx.author.id)
          await discordUserName.send("Please enter your FreeMart username *space* password, so:")
          await discordUserName.send("username password")


@bot.event
async def on_command_error(ctx, error):
  developer = await bot.fetch_user("909359661533233202")
  if isinstance(error, commands.CommandNotFound):
    await ctx.reply(
      "That's not a real command!", 
      mention_author=True
    )
    
  elif isinstance(error, commands.MissingRequiredArgument):
    await ctx.reply(
      "You missed one or more required arguments for this command:",
      mention_author=False
    )
    await ctx.send(gd[ctx.message.content.split(" ")[0]])
  else:
    await developer.send(error)
    raise error


# --- BOT COMMANDS ---


@bot.command(aliases=['p'], help="Show your profile, or another user's profile with $profile [userName]")
async def profile(ctx, userName=None):
  if not userName:
    await ctx.reply(
      embed=generateProfileEmbed(str(ctx.author)), 
      mention_author=False
    )
    
  else:
    if any(user['Name'] == userName for user in liveData.userAccounts):
      await ctx.reply(
        embed=generateProfileEmbed(userName),
        mention_author=False
      )
      
    else:
      await ctx.reply(
        f'No user with name {userName} exists.',
        mention_author=False
      )


@bot.command(aliases=['dt'], help="Show daily stock price trend on a graph")
async def dailyTrend(ctx):
  plotDailyTrend()
  await ctx.reply(
    file=discord.File('dailyTrend.png'), 
    mention_author=False
  )


@bot.command(aliases=['t'], help="Show all-time stock price trend on a graph")
async def trend(ctx):
  plotTrend()
  await ctx.reply(
    file=discord.File('trend.png'), 
    mention_author=False
  )


@bot.command(aliases=['bc'], help='View and choose from available STC sell offers')
async def buycoin(ctx, offerId=None):
  if offerId:
    if any(saleOffer['id'] == choiceNumbers[offerId] if saleOffer['type'] == "Sell" else False for saleOffer in liveData.saleOffers):
      await ctx.reply(
        proccessOffer(ctx, choiceNumbers[offerId], 'Sell'),
        mention_author=False
      )
      
    else:
      await ctx.reply(
        'Sell offer does not exist, or is no longer available',
        mention_author=False
      )
      
  else:
    sellOffersOptionsMessage = await ctx.reply(
      embed=generateEmbed('Sell'),
      mention_author=False
    )
    for saleOffer in saleTypeList('Sell'):
      if saleOffer['name'] != 'pool':
        await sellOffersOptionsMessage.add_reaction(saleOffer["id"])

    def check(reaction, user):
      #message.
      return user == ctx.author and reaction.message == sellOffersOptionsMessage

    reaction = await bot.wait_for('reaction_add', check=check, timeout=30)
    await ctx.reply(
      proccessOffer(ctx, str(reaction[0]), 'Sell'),
      mention_author=False
    )
    
  liveData.updateDatabase()


@bot.command(aliases=['bpc'], help='View STC pool or purchase from pool with $bpc [amount]. Coin price in the pool based on last sale price +5%')
async def buypoolcoin(ctx, amount=None):
  pool = getDict(liveData.userAccounts, "Name", "pool")
  if amount:
    amount = float(amount)
    if pool['STC'] >= amount:
      await ctx.reply(
        proccessOffer(ctx, choiceNumbers[0], "Sell", amount, True),
        mention_author=False
      )
      liveData.updateDatabase()
      
    else: 
      await ctx.reply('The pool does not have enough STC available')
      
  else:
    poolInfo = discord.Embed(
      title='Coin Pool',
      description=f'''
      Available coins: {pool['STC']}\n 
      Current price: ${liveData.saleOffers[0]['price']}/per coin''',
      color=PURPLE
    )
    await ctx.reply(
      embed=poolInfo, 
      mention_author=False
    )


@bot.command(aliases=['sc'],
  help='View and choose from available buy offers offers')
async def sellCoin(ctx, offerId=None):
  if offerId:
    if any(saleOffer["id"] == choiceNumbers[offerId] if saleOffer['type'] == 'Sell' else False for saleOffer in liveData.saleOffers):
      await ctx.reply(
        proccessOffer(ctx, str(choiceNumbers[offerId]), 'Buy'),
        mention_author=False
      )
      
    else:
      await ctx.reply(
        'Buy offer does not exist, or is no longer available',
        mention_author=False
      )
      
  else:
    buyOffersOptionsMessage = await ctx.reply(
      embed=generateEmbed("Buy"), 
      mention_author=False
    )
    for saleOffer in saleTypeList("Buy"):
      if saleOffer["name"] != "pool":
        await buyOffersOptionsMessage.add_reaction(saleOffer["id"])

    def check(reaction, user):
      return user == ctx.author and reaction.message == buyOffersOptionsMessage

    reaction = await bot.wait_for("reaction_add", check=check, timeout=30)
    await ctx.reply(
      proccessOffer(ctx, str(reaction[0]), "Buy"),
      mention_author=False
    )
    
  liveData.updateDatabase()


@bot.command(aliases=['mso'],
  help='Make a sell offer')
async def makeselloffer(ctx, quantity, price, *extra):
  if len([saleOffer for saleOffer in liveData.saleOffers if saleOffer['type'] == 'Sell']) > 10:
    await ctx.reply(
      "Maximum number of sell offers (10) reached. Please wait for a space",
      mention_author=False
    )
    return
    
  offer = publishSaleOffer(ctx, quantity, price, "Sell")
  if offer in choiceNumbers:
    await ctx.reply(
      f'You already have a sell offer up (id:{offer})',
      mention_author=False
    )
    return
    
  confirmationEmbed = discord.Embed(title='Sell Offer Published')
  confirmationEmbed.add_field(name='', value=offer)
  await ctx.reply(
    embed=confirmationEmbed, 
    mention_author=False
  )
  for ex in extra:
    await ctx.send(f'Ingored unnecessary argument: {ex}')
      
  liveData.updateDatabase()


@bot.command(aliases=['mbo'],
  help='Make a buy offer')
async def makebuyoffer(ctx, quantity, price, *extra):
  if len([saleOffer for saleOffer in liveData.saleOffers if saleOffer['type'] == 'Buy']) > 9:
    await ctx.reply(
      'Maximum number of buy offers (9) reached. Please wait for a space',
      mention_author=False
    )
    return
    
  offer = publishSaleOffer(ctx, quantity, price, "Buy")
  if offer in choiceNumbers:
    await ctx.reply(
      f'You already have a buy offer up (id:{offer})',
      mention_author=False
    )
    return

  confirmationEmbed = discord.Embed(title='Buy Offer Published')
  confirmationEmbed.add_field(name='', value=offer)
  await ctx.reply(
    embed=confirmationEmbed, 
    mention_author=False
  )
  for ex in extra:
    await ctx.send(f'Ingored unnecessary argument: {ex}')
    
  liveData.updateDatabase()


gd = {
  "$dt": "$dt",
  "$help": "$help [command name]",
  "$p": "$p [userName]",
  "$t": "$t",
  "$dt": "$dt",
  "$mso": "$mso [*quantity*] [*price*]",
  "$mbo": "$mbo [*quantity*] [*price*]",
  "$bc": "$bc [id]",
  "$sc": "$sc [id]",
  "$bpc": "$bpc [id]"
}

try:
  bot.run(TOKEN)
except discord.errors.HTTPException:
  print("\n\n\n Rate limit exceeded\n Connecting with new IP\n\n\n")
  os.system('kill 1')
