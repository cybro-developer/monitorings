import asyncio
import os
import random
import sys
from datetime import timedelta

import redis
import requests
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379/0")
REDIS_KEY = os.getenv("REDIS_KEY", "already_notified")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ETH_PRICE_API = os.getenv("ETH_PRICE_API",
                          "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd")
ORACLE_ADMIN_ADDRESS = os.getenv("ORACLE_ADMIN_ADDRESS")
NOTIFICATION_THRESHOLD_USD = os.getenv("NOTIFICATION_THRESHOLD_USD", "10,20").split(",")

BLASTSCAN_KEYS = os.getenv("BLASTSCAN_KEYS", "").split(",")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID should be set in environment variables")

redis_client = redis.StrictRedis.from_url(REDIS_URI, decode_responses=True)


bot = Bot(token=TELEGRAM_TOKEN)


def get_eth_price():
    response = requests.get(ETH_PRICE_API)
    response.raise_for_status()
    data = response.json()
    return data["ethereum"]["usd"]


def get_oracle_balance_eth():
    token = random.choice(BLASTSCAN_KEYS)
    response = requests.get(
        f"https://api.blastscan.io/api?module=account&action=balance&address={ORACLE_ADMIN_ADDRESS}&tag=latest&apikey={token}")
    response.raise_for_status()
    data = response.json()

    return data["result"]


def main():
    eth_price = get_eth_price()
    try:
        balance_eth = int(get_oracle_balance_eth())
    except ValueError:
        print("Error: cannot get oracle admin balance")
        sys.exit(1)

    balance_usd = balance_eth * float(eth_price) / 1e18
    for threshold in NOTIFICATION_THRESHOLD_USD:
        if balance_usd < float(threshold):
            if not redis_client.exists(f"{REDIS_KEY}:{threshold}"):
                print(f"Balance less than threshold ({threshold:.2f}): {balance_usd:.2f}")
                loop.run_until_complete(bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                                                         text=f"‼ Oracle admin balance too low: <b>${balance_usd:.2f}</b>\nTop up address <code>{ORACLE_ADMIN_ADDRESS}</code>",
                                                         parse_mode="html"))

                redis_client.setex(f"{REDIS_KEY}:{threshold}", value=balance_usd, time=timedelta(hours=1))
                break


if __name__ == "__main__":
    main()
