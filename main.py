import os

import asyncio

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


# ----- FreeMart Databse Sync -----

engine = create_engine(os.getenv("HOST"))
db = scoped_session(sessionmaker(bind=engine))

def syncToFreeMart():
  rows = db.execute(text('SELECT * FROM public.user'))
  for row in rows:
    liveData.userAccounts = [{k:(float(row[3]) if (k == "FMC" and int(userDict['freemartId']) == int(row[0])) else v) for (k,v)  in userDict.items() } for userDict in liveData.userAccounts]


def syncToBot():
  for user in liveData.userAccounts:
    if user["Name"] != "pool":
      db.execute(text(f"UPDATE public.user SET balance = {user['FMC']} WHERE id = {int(user['freemartId'])}"))
  db.commit()

  
# ----- Script constants ------
      
TOKEN = os.getenv("TOKEN")
RED = 0xed4245
PURPLE = 0x9b59b6
BLUE = 0x3498db
CHOICE_NUMBERS = [
  "0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"
]

# ----- Bot's settings -----

description = '''Trade stock, lose money!'''
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(
  command_prefix="$",
  description=description,
  intents=intents
)

# ----- Daily update script -----

class MyThread(Thread):

  def __init__(self, event):
    Thread.__init__(self)
    self.stopped = event

  def run(self):
    while True:
      updated = False
      now = datetime.now(pytz.timezone('Pacific/Auckland'))
      while (now.hour == 0 and now.minute == 0 and now.second == 0):
        if not updated:
          updated = True
          updateRecord()



my_event = Event()
thread = MyThread(my_event)
thread.start()

# ----- Local database class -----

class liveDatabase():

  def __init__(self):
    # Order matters, do not change!
    self.listNames = ["saleOffers", "userAccounts", "dailyRecords", "records"]

    self.loadDatabase()
    self.updateDatabase(noSync=True)
    
    print("Live database initialised.")

  
  def loadDatabase(self):
    for listName in self.listNames:
      with open(f'{listName}.csv', "r") as f:
        fileContent = list(csv.DictReader(f))

      if listName == "userAccounts":
        float_vals = ["$", "FMC", "freemartId"]
      elif listName == "saleOffers":
        float_vals = ["q", "price"]
      elif listName == "dailyRecords" or listName == "records":
        float_vals = ["Price"]
      else:
        float_vals = []

      #Convert float_vals to float data-type
      fileContent = [{
        key: (float(val) if key in float_vals else val)
        for key, val in record.items()
      } for record in fileContent]

      exec("self.{} = {}".format(listName, fileContent))
      print(f'{listName}: {fileContent}\n')

  
  def updateDatabase(self, clearDaily=False, noSync=False):
    try:
      self.saleOffers[0]['price'] = self.dailyRecords[-1]['Price'] * 1.05
    except IndexError:
      pass

    if not noSync:
      print("Syncing db to Bot version")
      syncToBot()

    print("---Saving lists---")
    self.lll = [
      self.saleOffers, self.userAccounts, self.dailyRecords, self.records
    ]
    listIndex = 0
    for list in self.lll:
      print(self.listNames[listIndex])
      if list == [] or (clearDaily and self.listNames[listIndex] == 'dailyRecords'):
        with open(f'{self.listNames[listIndex]}.csv', 'r+') as f:
            f.readline()
            f.truncate(f.tell())
        print("\n.........\n")
        continue
        
      keys = list[0].keys()
      
      print(list)
      with open(f'{self.listNames[listIndex]}.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(list)
      listIndex += 1
      print(".........\n")
      

# ----- Helper functions -----

def record(saleDict, amount):
  time = datetime.now(pytz.timezone('Pacific/Auckland'))
  pricePerCoin = saleDict["price"] / saleDict['q']
  saleRecord = {
    "Time": f'{time.hour}:{time.minute}',
    "Price": pricePerCoin
  }
  liveData.dailyRecords.append(saleRecord)


def updateRecord():
  time = datetime.now(pytz.timezone('Pacific/Auckland'))
  date = f"{time.year}-{time.month}-{time.day}"
  
  if liveData.dailyRecords != []:
    priceSum = 0
    for record in liveData.dailyRecords:
      priceSum += record["Price"]
    dailyPriceAvarage = priceSum / len(liveData.dailyRecords)
    
  else:
    dailyPriceAvarage = liveData.records[-1]["Price"]
    
  liveData.records.append({
    "Date": date,
    "Price": dailyPriceAvarage
    })
  
  liveData.updateDatabase(clearDaily=True)


def generateProfileEmbed(userName):
  userDict = getDict(liveData.userAccounts, 'Name', userName)
  profileEmbed = discord.Embed(
    title=f"{userName}'s Profile",
    description=f'''
      FreeMart: *{userDict['freemartName']}*\n
      $: **{userDict['$']}**\n
      FMC: **{userDict['FMC']}**''',
    color=BLUE
  )
  return profileEmbed


def generateSaleEmbed(bOs):
  saleEmbed = discord.Embed(
    title=f"{bOs} Offers",
    description="Press corresponding number to accept an offer."
  )
  saleEmbed.add_field(
    inline=False,
    name="ID",
    value=f'{bOs}er       Quantity       Price'
  )
  saleEmbed.set_footer(
    text="P.S. you can use $sc _idNumber_ to accept a buy offer straight away."
  )
  for saleOffer in liveData.saleOffers:
    if saleOffer["type"] == bOs and saleOffer["name"] != "pool":
      saleEmbed.add_field(
        inline=False,
        name=saleOffer["id"],
        value= f'{saleOffer["name"]}       {saleOffer["q"]}     {saleOffer["price"]}'
      )
  return saleEmbed


def registerUser(ctx):
  try:
    currentFMCPrice = liveData.dailyRecords[-1]['Price']
  except IndexError:
    currentFMCPrice = liveData.records[-1]['Price']
    
  welcomeEmbed = discord.Embed(
    title=f'Welocme to FreeStock, {ctx.author}!',
    description='Buy, sell and exchange FreeMart coins. Turn a profit if you can...',
    color=RED
  )
  welcomeEmbed.set_footer(
    text=f'''
    Your balance has been topped with an initial ${currentFMCPrice*5.0}, enough for 5 coins rn. Yapi!'''
  )
  
  rows = db.execute(text('SELECT * FROM public.user'))
  for row in rows:
    if row[1] == ctx.content.split(' ')[0]:
      if pbkdf2_sha256.verify(ctx.content.split(' ')[1], row[2]):
        print("Freemart LOGIN")
        liveData.userAccounts.append({
          'Name': str(ctx.author),
          'freemartId': float(row[0]),
          'freemartName': str(row[1]),
          '$': currentFMCPrice * 5.0,
          'FMC': 0.0
        })
        syncToFreeMart()
        liveData.updateDatabase(noSync=True)
        return welcomeEmbed 
  return '''Incorrect username or password!\n
    Make sure to reply with you username and password as:\n
    username password'''
    

def getDict(dictList, key, value, type=None):
  for dict in dictList:
    if dict[key] == value:
      if type:
        if dict["type"] == type:
          return dict
          
      else:
        return dict
  raise KeyError(f'No dictionary in list {dictList} with {key} of {value} found!')


def proccessOffer(ctx, id, type, amount=1):
  saleOffer = getDict(liveData.saleOffers, "id", id, type)
  if saleOffer['name'] == str(ctx.author):
      return "You can't purchase stock from yourself!"
  if canAfford(str(ctx.author), saleOffer, amount):
    chargeAccounts(str(ctx.author), saleOffer, amount)
    record(saleOffer, amount)
    if saleOffer['name'] != 'pool':
      liveData.saleOffers.remove(saleOffer)
      return f'{ctx.author} accepted {type.lower()} offer {saleOffer["id"]} from {saleOffer["name"]}' 
      
    else:
      return f'{ctx.author} bought coins from the pool at {saleOffer["price"]}/per coin'     
  return 'You cannot afford this exchange!'


def canAfford(userName, saleOffer, amount):
  key = "$" if saleOffer['type'] == 'Sell' else 'FMC'
  if getDict(liveData.userAccounts, 'Name', userName)[key] >= saleOffer['price'] * amount:
    return True
  return False


def chargeAccounts(userName, saleDict, amount):
  q = (saleDict['q'] * amount)
  price = (saleDict['price'] * amount)
  productKey = 'FMC' if saleDict['type'] == 'Sell' else '$'
  priceKey = '$' if saleDict['type'] == 'Sell' else 'FMC'
  accepterIndex = liveData.userAccounts.index(getDict(liveData.userAccounts, "Name", userName))
  sellerIndex = liveData.userAccounts.index(getDict(liveData.userAccounts, "Name", saleDict['name']))
  #liveData.userAccounts[2][productKey] += q*0.05
  liveData.userAccounts[sellerIndex][priceKey] += price
  liveData.userAccounts[sellerIndex][productKey] -= q
  liveData.userAccounts[accepterIndex][priceKey] -= price
  liveData.userAccounts[accepterIndex][productKey] += q 
  #^ liveData.userAccounts[accepterIndex][productKey] += q*0.95  


def publishSaleOffer(ctx, q, price, type):
  i = 0
  for offer in liveData.saleOffers:
    if offer["type"] == type:
      i += 1
  newSaleOffer = {
    "id": CHOICE_NUMBERS[i + 1],
    "name": str(ctx.author),
    "q": q,
    "price": price,
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
    if dict["type"] == type and dict['name'] != 'pool':
      saleListOfType.append(dict)
  if len(saleListOfType): 
    return saleListOfType
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


# ----- Initialize Database -----

liveData = liveDatabase()
syncToFreeMart()

# ----- Bot events -----

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
    outcome = registerUser(ctx)
    try:
      await ctx.reply(embed=outcome, mention_author=True) 
    except AttributeError:
      await ctx.reply(outcome, mention_author=False)
      
  elif ctx.content.startswith('$'):
    try:
      getDict(liveData.userAccounts, "Name", str(ctx.author))
      syncToFreeMart()
      await bot.process_commands(ctx)
    except KeyError:
      await ctx.reply('Check DMs to login to your FreeMart account', mention_author=True)
      discordUserName = await bot.fetch_user(ctx.author.id)
      await discordUserName.send("Please enter your FreeMart username *space* password, so:")
      await discordUserName.send("username password")


@bot.event
async def on_command_error(ctx, error):
  if isinstance(error, commands.CommandNotFound):
    await ctx.reply(
      "That's not a real command!", 
      mention_author=True
    )
    
  elif isinstance(error, commands.MissingRequiredArgument):
    await ctx.reply(
      'You missed one or more required arguments for this command:',
      mention_author=False
    )
    await ctx.send(f'Use $help{ctx.invoked_with} to learn more')
  else:
    developer = await bot.fetch_user('909359661533233202')
    await developer.send(error)
    raise error


# ----- BOT COMMANDS -----

@bot.command(aliases=['p'], brief="Display profile", description="Show your profile, or another user's profile with $profile [userName]")
async def profile(ctx, userName: discord.User = commands.parameter(default=None, description="- Mention desired user, or leave blank for self.")):
  if not userName:
    await ctx.reply(
      embed=generateProfileEmbed(str(ctx.author)), 
      mention_author=False
    )
    
  else:
    userName = userName.name + userName.discriminator
    if any(user['Name'] == userName for user in liveData.userAccounts):
      await ctx.reply(
        embed=generateProfileEmbed(userName),
        mention_author=False
      )
      
    else:
      await ctx.reply(
        f'No user with name {userName} exists',
        mention_author=False
      )


@bot.command(brief="Explain logic of FreeBot")
async def explain(ctx):
  await ctx.reply(
    file=discord.File('explain.png'), 
    mention_author=False
  )


@bot.command(aliases=['dt'], brief="Plot daily graph", description="Show daily stock price trend on a graph")
async def dailyTrend(ctx):
  plotDailyTrend()
  await ctx.reply(
    file=discord.File('dailyTrend.png'), 
    mention_author=False
  )


@bot.command(aliases=['t'], brief="Plot all-time graph", description="Show all-time stock price trend on a graph")
async def trend(ctx):
  plotTrend()
  await ctx.reply(
    file=discord.File('trend.png'), 
    mention_author=False
  )


@bot.command(aliases=['bc'], brief="Trade for FMS", description='View and choose from available FMC sell offers, or buy FMC directly with $bc [offerID]')
async def buycoin(ctx, offerId: int = commands.parameter(default=None, description="- ID of offer you want to accept.")):
  if offerId:
    if any(saleOffer['id'] == CHOICE_NUMBERS[offerId] if saleOffer['type'] == "Sell" else False for saleOffer in liveData.saleOffers):
      await ctx.reply(
        proccessOffer(ctx, CHOICE_NUMBERS[offerId], 'Sell'),
        mention_author=False
      )
      liveData.updateDatabase()
      
    else:
      await ctx.reply(
        'Sell offer does not exist, or is no longer available',
        mention_author=False
      )
      
  else:
    sellOffersOptionsMessage = await ctx.reply(
      embed=generateSaleEmbed('Sell'),
      mention_author=False
    )
    for saleOffer in saleTypeList('Sell'):
      await sellOffersOptionsMessage.add_reaction(saleOffer["id"])
      
    def check(reaction, user):
      return user == ctx.author and reaction.message == sellOffersOptionsMessage
      
    try:
      reaction = await bot.wait_for('reaction_add', check=check, timeout=30)
      await ctx.reply(
        proccessOffer(ctx, str(reaction[0]), 'Sell'),
        mention_author=False
      )
      liveData.updateDatabase()
    except asyncio.TimeoutError:
      pass
    
  


@bot.command(aliases=['bpc'], brief="Buy FMC from pool", description='View FMC pool or purchase from the pool using $bpc [amount]. Coin price in pool based on last sale price +5%')
async def buypoolcoin(ctx, amount: float = commands.parameter(default=None, description="- Amount of FMC to buy")):
  pool = getDict(liveData.userAccounts, "Name", "pool")
  if amount:
    if pool['FMC'] >= amount:
      await ctx.reply(
        proccessOffer(ctx, CHOICE_NUMBERS[0], "Sell", amount),
        mention_author=False
      )
      liveData.updateDatabase()
      
    else: 
      await ctx.reply('The pool does not have enough FMC available')
      
  else:
    poolInfo = discord.Embed(
      title='Coin Pool',
      description=f'''
      Available coins: **{pool['FMC']}**\n 
      Current price: **${liveData.saleOffers[0]['price']}** /per coin''',
      color=PURPLE
    )
    await ctx.reply(
      embed=poolInfo, 
      mention_author=False
    )


@bot.command(aliases=['sc'], brief="Trade for $", description='View and choose from available FMC buy offers, or sell FMC directly with $sc [offerID]')
async def sellcoin(ctx, offerId: int = commands.parameter(default=None, description="- ID of offer you want to accept.")):
  if offerId:
    if any(saleOffer["id"] == CHOICE_NUMBERS[offerId] if saleOffer['type'] == 'Buy' else False for saleOffer in liveData.saleOffers):
      await ctx.reply(
        proccessOffer(ctx, str(CHOICE_NUMBERS[offerId]), 'Buy'),
        mention_author=False
      )
      liveData.updateDatabase()
      
    else:
      await ctx.reply(
        'Buy offer does not exist, or is no longer available',
        mention_author=False
      )
      
  else:
    buyOffersOptionsMessage = await ctx.reply(
      embed=generateSaleEmbed("Buy"), 
      mention_author=False
    )
    for saleOffer in saleTypeList("Buy"):
      await buyOffersOptionsMessage.add_reaction(saleOffer["id"])

    def check(reaction, user):
      return user == ctx.author and reaction.message == buyOffersOptionsMessage
      
    try:
      reaction = await bot.wait_for("reaction_add", check=check, timeout=30)
      await ctx.reply(
        proccessOffer(ctx, str(reaction[0]), "Buy"),
        mention_author=False
      )
      liveData.updateDatabase()
    except asyncio.TimeoutError:
      pass
   


@bot.command(aliases=['mso'],
  brief='Make a sell offer', description='Provide a quantity of FMC to sell followed by the price for them: $mso [quantity] [amount]. Limit of 1 sell offers per person')
async def makeselloffer(ctx, quantity: float = commands.parameter(description="- Quantity of FMC you want to sell."), price: float = commands.parameter(description="- Price you want to charge for the FMC."), *extra):
  if ((price * -1) >= 0) or ((quantity * -1) >= 0):
    await ctx.reply(
      'Quantity and Price must be above 0, you monkey!',
      mention_author=False
    )
    return
    
  if len([saleOffer for saleOffer in liveData.saleOffers if saleOffer['type'] == 'Sell']) > 10:
    await ctx.reply(
      "Maximum number of sell offers (10) reached. Please wait for a space",
      mention_author=False
    )
    return
    
  offer = publishSaleOffer(ctx, quantity, price, "Sell")
  if offer in CHOICE_NUMBERS:
    await ctx.reply(
      f'You already have a sell offer up (id:{offer})',
      mention_author=False
    )
    return
    
  confirmationEmbed = discord.Embed(title='Sell Offer Published')
  confirmationEmbed.add_field(
    name='', 
    value=offer
  )
  await ctx.reply(
    embed=confirmationEmbed, 
    mention_author=False
  )
  for ex in extra:
    await ctx.send(f'Ingored unnecessary argument: {ex}')
      
  liveData.updateDatabase()


@bot.command(aliases=['mbo'],
  brief='Make a buy offer', description='Provide a quantity of FMC to buy followed by the price you will be willing to pay for it: $mbo [quantity] [amount]. Limit of 1 buy offers per person')
async def makebuyoffer(ctx, quantity: float = commands.parameter(description="- Quantity of FMC you want to buy."), price: float = commands.parameter(description="- Price you are willing to pay for the FMC."), *extra):
  if ((price * -1) >= 0) or ((quantity * -1) >= 0):
    await ctx.reply(
      'Quantity and Price must be above 0, you monkey!',
      mention_author=False
    )
    return
    
  if len([saleOffer for saleOffer in liveData.saleOffers if saleOffer['type'] == 'Buy']) > 11:
    await ctx.reply(
      'Maximum number of buy offers (11) reached. Please wait for a space',
      mention_author=False
    )
    return
    
  offer = publishSaleOffer(ctx, quantity, price, "Buy")
  if offer in CHOICE_NUMBERS:
    await ctx.reply(
      f'You already have a buy offer up (id:{offer})',
      mention_author=False
    )
    return

  confirmationEmbed = discord.Embed(title='Buy Offer Published')
  confirmationEmbed.add_field(
    name='', 
    value=offer
  )
  await ctx.reply(
    embed=confirmationEmbed, 
    mention_author=False
  )
  for ex in extra:
    await ctx.send(f'Ingored unnecessary argument: {ex}')
    
  liveData.updateDatabase()


@bot.command(aliases=['ro'], help="Remove one your offers")
async def removeoffer(ctx, type: str = commands.parameter(description="- Type of your offer Buy/Sell?"), id: int = commands.parameter(description="- ID of your offer to remove.")):
  offerToRemove = getDict(liveData.saleOffers, "id", CHOICE_NUMBERS[id], type.capitalize())
  if offerToRemove['name'] != str(ctx.author):
    await ctx.reply(
    f"Nice try, but you can't remove someone else's offer. It belongs to {offerToRemove['name']}", 
    mention_author=False
    )
  else:
    liveData.saleOffers = list(filter(lambda offer: offer['id'] != id and offer['type'] != type.capitalize(), liveData.saleOffers))
    await ctx.reply(
    f"Succesfully deleted your worthless {type.lower()} offer, id:{id}", 
    mention_author=False
    )

    liveData.updateDatabase()
  

# ----- Run/Restart Bot -----

try:
  bot.run(TOKEN)
except discord.errors.HTTPException:
  print("\n\n\n Rate limit exceeded\n Connecting with new IP\n\n\n")
  os.system('kill 1')
