import os

import discord
from discord.ext import commands

import traceback

from datetime import datetime
import pytz

from threading import Thread, Event

import csv

import pandas
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.ticker import AutoMinorLocator

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
bot = commands.Bot(
  command_prefix="$",
  description=description,
  intents=intents
)

# -- Daily update script --

class MyThread(Thread):

  def __init__(self, event):
    Thread.__init__(self)
    self.stopped = event

  def run(self):
    while not self.stopped.wait(3600):
      updateRecord()
      

def updateRecord():
  time = datetime.now(pytz.timezone('Pacific/Auckland'))
  date = f"{time.year}-{time.month}-{time.day}"

  if len(liveData.dailyRecords):
    priceSum = 0
    for record in liveData.dailyRecords:
      priceSum += record["Price"]
    dailyPriceAvarage = round(priceSum / len(liveData.dailyRecords), 2)

    liveData.records.append({
      "Date": date,
      "Price": dailyPriceAvarage if dailyPriceAvarage != 0 else liveData.records[-1]["Price"]
    })
    
  liveData.dailyRecords = []
  liveData.updateDatabase()


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

    self.updateDatabase()
    print("Live database initialised.")

  def loadDatabase(self):    
    for listName in self.listNames:
      with open(f'{listName}.csv', "r") as f:
        fileContent = list(csv.DictReader(f))

      if listName == "userAccounts":
        int_vals = ["$", "STC"]
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

  def updateDatabase(self):
    poolPrice = self.saleOffers[0]['price']
    self.saleOffers[0]['price'] = round(poolPrice *1.05, 2) if poolPrice >0.6 else round(poolPrice * 1.5, 2)
    listIndex = -1
    
    print("---Saving lists---")
    for list in self.lll:
      listIndex += 1
      print(list)

      if list == []:
        with open(f'{self.listNames[listIndex]}.csv', 'w') as f:
          print(".........")
          continue

      keys = list[0].keys()

      with open(f'{self.listNames[listIndex]}.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(list)
      print(".........\n\n")


def record(saleDict):
  time = datetime.now(pytz.timezone('Pacific/Auckland'))
  pricePerCoin = round(saleDict["price"] / saleDict["q"], 2)
  saleRecord = {
    "Time": f'{time.hour}:{time.minute}',
    "Price": round(pricePerCoin, 2)
  }
  liveData.dailyRecords.append(saleRecord)


def generateProfileEmbed(userName):
  userDict = getDict(liveData.userAccounts, "Name", userName)
  profileEmbed = discord.Embed(
    title=f"{userName}'s Profile!",
    description=
    f"Name: {userName}\n$: **{userDict['$']}**\nSTC: **{userDict['STC']}**",
    color=BLUE)
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


def registerUser(ctx, currentSTCPrice):
  welcomeEmbed = discord.Embed(
    title=f'Welocme to STC, {ctx.author}!',
    description='Buy, sell and exchange coins. Turn a profit if you can...',
    color=RED)
  welcomeEmbed.set_footer(
    text=
    f'Your balance has been topped with an initial ${round(currentSTCPrice*5.0,2)}, enough for 5 coins rn. Yapi!'
  )
  liveData.userAccounts.append({
    "Name": str(ctx.author),
    "$": round(currentSTCPrice * 5.0, 2),
    "STC": 0
  })
  return welcomeEmbed


def getDict(dictList, key, value, type=101):
  for dict in dictList:
    if dict[key] == value:
      if type != 101:
        if dict["type"] == type:
          return dict
      else:
        return dict
  raise KeyError(f'No dictionary in list with {key} of {value} found!')


def proccessOffer(ctx, id, type, amount=1, pool=False):
  saleOffer = getDict(liveData.saleOffers, "id", id, type)
  if canAfford(str(ctx.author), saleOffer, type, amount):
    if saleOffer["name"] == str(ctx.author):
      return "You can't purchase stock from yourself!"
    if chargeAccounts(ctx, saleOffer, amount):
      if saleOffer["name"] != "pool":
        liveData.saleOffers.remove(saleOffer)
        if pool:
          return f'{ctx.author} bought coins from the pool at {saleOffer["price"]}/per coin.'
        return f'{ctx.author} accepted {type.lower()} offer {saleOffer["id"]} from {saleOffer["name"]}.'
    return "Transaction failed for an unknow reason. Error report sent."
  return "You can not afford this offer!"


def canAfford(userName, saleOffer, type, amount):
  key = "$" if type == "Sell" else "STC"
  if getDict(liveData.userAccounts, "Name", userName)[key] >= round(
      saleOffer["price"] * float(amount), 2):
    return True
  return False


def chargeAccounts(ctx, saleDict, amount):
  quant = round((saleDict['q'] * float(amount)), 2)
  price = round((saleDict['price'] * float(amount)), 2)
  productKey = "STC" if saleDict["type"] == "Sell" else "$"
  priceKey = "$" if saleDict["type"] == "Sell" else "STC"
  accepterIndex = liveData.userAccounts.index(
    getDict(liveData.userAccounts, "Name", str(ctx.author)))
  sellerIndex = liveData.userAccounts.index(
    getDict(liveData.userAccounts, "Name", saleDict['name']))
  try:
    liveData.userAccounts[sellerIndex][priceKey] += price
    liveData.userAccounts[sellerIndex][productKey] -= quant
    liveData.userAccounts[accepterIndex][priceKey] -= price
    liveData.userAccounts[accepterIndex][productKey] += quant
  except Exception as e:
    print(traceback.format_exc())
    return False
  return True


def getBalance(userName, currency):
  return getDict(liveData.userAccounts, "Name", userName)[currency]


def publishSaleOffer(ctx, q, price, type):
  i = 0
  for offer in liveData.saleOffers:
    if offer["type"] == type:
      i += 1
  newSaleOffer = {
    "id": choiceNumbers[i+1],
    "name": str(ctx.author),
    "q": int(q),
    "price": int(price),
    "type": type
  }
  try:
    existingOffer = getDict(liveData.saleOffers, "name", str(ctx.author), type)
  except KeyError:
    liveData.saleOffers.append(newSaleOffer)
    return newSaleOffer
  return existingOffer["id"]


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
  #ax.yaxis.set_major_locator(MultipleLocator(20))
  ax.yaxis.set_minor_locator(AutoMinorLocator(5))
  ax.xaxis.set_minor_locator(AutoMinorLocator(5))

  ax.grid(which='major', color='#393E46', linestyle='-')
  ax.grid(which='minor', color='#6D9886', linestyle='--')
  plt.style.use('fivethirtyeight')
  plt.subplots_adjust(bottom=0.18)
  plt.ylim(ymin=0.0)
  plt.savefig("dailyTrend.png")


liveData = liveDatabase()


@bot.event
async def on_ready():
  print(f'{bot.user} booting...')
  print('------')
  for guild in bot.guilds:
    print(f"Connected to {guild}")
  print("------" * 2)


@bot.event
async def on_command(ctx):
  if str(ctx.author) in [user['Name'] for user in liveData.userAccounts]:
    pass
  else:
    await ctx.reply(embed=registerUser(ctx,
                                       liveData.dailyRecords[-1]["Price"]),
                    mention_author=False)
    liveData.updateDatabase()
    await ctx.message.delete()


@bot.event
async def on_command_error(ctx, error):
  if isinstance(error, commands.CommandNotFound):
    await ctx.reply("That's not a real command!", mention_author=False)
  elif isinstance(error, commands.MissingRequiredArgument):
    await ctx.reply(
      "You missed one or more required arguments for this command:",
      mention_author=False)
    await ctx.send(gd[ctx.message.content.split(" ")[0]])
  else:
    raise error


@bot.command()
async def p(ctx, userName="noone"):
  if userName == "noone":
    await ctx.reply(embed=generateProfileEmbed(str(ctx.author)),
                    mention_author=False)
  else:
    if any(d["Name"] == userName for d in liveData.userAccounts):
      await ctx.reply(embed=generateProfileEmbed(userName),
                      mention_author=False)
    else:
      await ctx.reply(f"No user with name {userName} exists.",
                      mention_author=False)



@bot.command()
async def dt(ctx):
  plotDailyTrend()
  await ctx.reply(file=discord.File('dailyTrend.png'), mention_author=False)
  os.remove("dailyTrend.png")


@bot.command()
async def t(ctx):
  plotTrend()
  await ctx.reply(file=discord.File('trend.png'), mention_author=False)
  os.remove("trend.png")


@bot.command(help='View and choose from available sell offers, to get STC.')
async def bc(ctx, offerId=101):
  if offerId != 101:
    if any(d["id"] == choiceNumbers[offerId] for d in liveData.saleOffers):
      await ctx.reply(proccessOffer(ctx, str(choiceNumbers[offerId]), "Sell"),
                      mention_author=False)
    else:
      await ctx.reply("Sell offer does not exist, or is no longer available.",
                      mention_author=False)
  else:
    message = await ctx.reply(embed=generateEmbed("Sell"),
                              mention_author=False)
    for saleOffer in saleTypeList("Sell"):
      if saleOffer["name"] != "pool":
        await message.add_reaction(saleOffer["id"])

    def check(reaction, user):
      return user == ctx.message.author and reaction.message == message

    reaction = await bot.wait_for("reaction_add", check=check, timeout=30)
    await ctx.reply(proccessOffer(ctx, str(reaction[0]), "Sell"),
                    mention_author=False)
  liveData.updateDatabase()


@bot.command(
  help=
  "Purchase STC from the pool. Coin price in the pool based on last sale price  +5%."
)
async def bpc(ctx, amount=None):
  if amount:
    await ctx.reply(proccessOffer(ctx, choiceNumbers[0], "Sell", amount, True), mention_author=False)
    liveData.updateDatabase()
  else:
    pool = getDict(liveData.userAccounts, "Name", "pool")
    poolInfo = discord.Embed(
      title="Coin Pool",
      description= f"Available coins: {pool['STC']}\n Current price: ${liveData.saleOffers[0]['price']}",
      color=PURPLE
    )
    await ctx.reply(embed=poolInfo, mention_author=False)



@bot.command(
  help='View and choose from available sell offers. To echange for $.')
async def sc(ctx, offerId=101):
  if offerId != 101:
    if any(d["id"] == choiceNumbers[offerId]
           for d in liveData.saleOffers) and offerId != 0:
      await ctx.reply(proccessOffer(ctx, str(choiceNumbers[offerId]), "Buy"),
                      mention_author=False)
    else:
      await ctx.reply("Buy offer does not exist, or is no longer available.",
                      mention_author=False)
  else:
    message = await ctx.reply(embed=generateEmbed("Buy"), mention_author=False)
    for saleOffer in saleTypeList("Buy"):
      if saleOffer["name"] != "pool":
        await message.add_reaction(saleOffer["id"])

    def check(reaction, user):
      return user == ctx.message.author

    reaction = await bot.wait_for("reaction_add", check=check, timeout=60)
    await ctx.reply(proccessOffer(ctx, str(reaction[0]), "Buy"),
                    mention_author=False)
  liveData.updateDatabase()


@bot.command()
async def mso(ctx, quantity, price, *extra):
  if len(liveData.saleOffers) > 9:
    await ctx.reply(
      "Maximum number of sell offers reached. Please wait for a space.",
      mention_author=False)
    return
  offer = publishSaleOffer(ctx, quantity, price, "Sell")
  if offer in choiceNumbers:
    await ctx.reply(f"You already have a sell offer up (id:{offer})",
                    mention_author=False)
  else:
    confirmationEmbed = discord.Embed(title="Sell Offer Publiched")
    confirmationEmbed.add_field(name="Hi", value=offer)
    await ctx.reply(embed=confirmationEmbed, mention_author=False)
    for ex in extra:
      await ctx.send(f"Ingored unnecessary argument: {ex}")
  liveData.updateDatabase()


@bot.command()
async def mbo(ctx, quantity, price, *extra):
  if len(liveData.saleOffers) > 9:
    await ctx.reply(
      "Maximum number of buy offers reached. Please wait for a space.",
      mention_author=False)
    return
  offer = publishSaleOffer(ctx, quantity, price, "Buy")
  if offer in choiceNumbers:
    await ctx.reply(f"You already have a buy offer up (id:{offer})",
                    mention_author=False)
  else:
    confirmationEmbed = discord.Embed(title="Buy Offer Published")
    confirmationEmbed.add_field(name="Behold", value=offer)
    await ctx.reply(embed=confirmationEmbed, mention_author=False)
    for ex in extra:
      await ctx.send(f"Ingored unnecessary argument: {ex}")
  liveData.updateDatabase()


gd = {
  "$dt": "$dt",
  "$help": "$help [command name]",
  "$t": "$t",
  "$mso": "$mso *quantity* *price*",
  "$mbo": "$mbo *quantity* *price*",
  "$bc": "$bc [id]",
  "$bpc": "$bpc [id]"
}

try:
  bot.run(TOKEN)
except discord.errors.HTTPException:
  print("\n\n\n Rate limit exceeded\n Connecting with new IP\n\n\n")
  os.system('kill 1')
