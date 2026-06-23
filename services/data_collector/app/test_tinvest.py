import os
from dotenv import load_dotenv
from tinkoff.invest import Client

load_dotenv("D:/MOEX_AI/.env")

TOKEN = os.getenv("TINVEST_TOKEN")

if not TOKEN:
    raise RuntimeError("TINVEST_TOKEN не найден в .env")

with Client(TOKEN) as client:
    accounts = client.sandbox.get_sandbox_accounts()
    print("Sandbox accounts:")
    print(accounts)

    instruments = client.instruments.shares()
    print(f"Shares loaded: {len(instruments.instruments)}")

    for item in instruments.instruments[:10]:
        print(item.ticker, item.name, item.figi)