from core.broker.adapters import LiveBroker, TInvestSandboxBroker

def main():
    assert LiveBroker().place_order("TEST","BUY",1,100)["status"] == "BLOCKED"
    assert TInvestSandboxBroker().place_order("TEST","BUY",1,100)["status"] in {"DRY_RUN","SANDBOX_NOT_IMPLEMENTED_YET"}
    print("Broker safety OK")

if __name__ == "__main__":
    main()
