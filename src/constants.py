"""Constants and default values for the dashboard."""
from typing import List, Tuple

# Coin definitions: (coin_id, symbol, category, group)
COINS: List[Tuple[str, str, str, str]] = [
    # Infrastructure
    ("bitcoin", "BTC", "Store of Value / Base asset", "infra"),
    ("ethereum", "ETH", "Layer 1 (L1)", "infra"),
    ("binancecoin", "BNB", "CEX token / exchange ecosystem", "infra"),
    ("arbitrum", "ARB", "Layer 2 (L2)", "infra"),
    ("cosmos", "ATOM", "Layer 0 (L0)", "infra"),
    ("avalanche-2", "AVAX", "Appchains / Subnets", "infra"),
    ("wormhole", "W", "Interoperability / Bridges", "infra"),
    ("chainlink", "LINK", "Oracles", "infra"),
    ("ankr", "ANKR", "RPC / Node infrastructure", "infra"),
    ("celestia", "TIA", "Modular / Data Availability", "infra"),

    # DeFi
    ("uniswap", "UNI", "DEXs", "defi"),
    ("1inch", "1INCH", "Aggregators", "defi"),
    ("aave", "AAVE", "Lending / Borrowing", "defi"),
    ("tether", "USDT", "Stablecoins", "defi"),
    ("dydx", "DYDX", "Derivatives", "defi"),
    ("lido-dao", "LDO", "Liquid Staking (LSD/LRT)", "defi"),
    ("yearn-finance", "YFI", "Yield / Vaults", "defi"),
    ("sky", "SKY", "CDPs (Maker → Sky)", "defi"),
    ("ondo-finance", "ONDO", "RWA", "defi"),

    # Consumer
    ("apecoin", "APE", "NFTs (collectibles / art)", "consumer"),
    ("blur", "BLUR", "NFT marketplaces", "consumer"),
    ("immutable-x", "IMX", "Gaming NFTs / Game assets", "consumer"),
    ("decentraland", "MANA", "Metaverse / virtual worlds", "consumer"),
    ("cyberconnect", "CYBER", "SocialFi", "consumer"),
    ("chiliz", "CHZ", "Fan tokens", "consumer"),

    # Memes
    ("dogecoin", "DOGE", "Memecoins", "memes"),
    ("fartcoin", "FART", "Memecoins (Fartcoin)", "memes"),
]

# Default UI Settings
DEFAULT_GROUP = "infra+memes"
DEFAULT_SMOOTHING = "7D SMA"
DEFAULT_VIEW = "Normalized (Linear)"  # Options: "Normalized (Linear)" | "Normalized (Log)" | "Market Cap (Log)"
DEFAULT_CORR_MODE = "returns"  # Options: "off" | "returns" | "levels"

# Pseudo series (USDT Dominance)
DOM_SYM = "USDT.D"
DOM_CAT = "USDT dominance (USDT / sum(coins)) — indexed"
DOM_GRP = "metric"

# Data Quality Thresholds
MIN_MARKET_CAP_FOR_VALID = 200_000_000  # Minimum MC to consider data valid
Q_DROP_THRESHOLD = -0.30  # Q drop threshold to detect corruption (≤-30%)
PRICE_DROP_THRESHOLD = -0.30  # Price drop threshold for comparison (≤-30%)

