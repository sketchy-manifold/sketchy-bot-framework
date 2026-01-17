class HousekeepingConfig:
    BALANCE_THRESHOLD = 3000
    TARGET_BALANCE = 2500
    RECIPIENT_USER_ID = "YOUR MAIN ACCOUNT USERID HERE" # TODO Your main account id here
    MESSAGE_BASE = "Profits"
    EMOJIS = ["💰", "💵", "🤑", "💸", "$", "📈", "🪙", "🏦", "💹"]
    KILLSWITCH_PHRASE = "<ACTIVATE_KILLSWITCH>"
    KILLSWITCH_CONFIRMATION_MESSAGE = "Shutdown confirmed"
    KILLSWITCH_EASTER_EGG_MESSAGE = "Thanks for the mana"
    RUN_INTERVAL_MINUTES = 5
    SHUTDOWN_LOOKBACK_MINUTES = RUN_INTERVAL_MINUTES + 1

