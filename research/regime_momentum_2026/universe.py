"""Universe for the 2026 regime-momentum research.

Survivorship-bias note
----------------------
Any hand-picked list of *today's* large caps is survivorship biased. To dampen
this, the pool deliberately mixes in names that were heavily owned in 2021-2022
and then lost 50-80% through 2023-2025 (LONGi, China Tourism Group Duty Free,
WuXi AppTec, Tianqi Lithium, Shanghai Airport, Air China, SAIC, Muyuan, ...).
A momentum strategy that only ever sees winners would look great and mean
nothing; these losers are what the regime filter and stops have to dodge.

Codes are bare (data-API convention). The engine's trading APIs accept bare
codes too (exchange suffix is inferred).
"""

# sector -> list of bare codes
UNIVERSE_BY_SECTOR = {
    "banks":        ["601398", "601939", "600036", "601288"],
    "insurance":    ["601318", "601628"],
    "liquor_food":  ["600519", "000858", "000568", "603288"],
    "pharma":       ["600276", "300760", "603259"],
    "new_energy":   ["002594", "300750", "601012", "002460", "300274"],
    "tech_semis":   ["000725", "603501", "002371", "002230"],
    "brokers_net":  ["300059", "600030", "002555"],
    "materials":    ["600585", "601899", "600019", "002466"],
    "energy":       ["601088", "600028", "601857"],
    "transport":    ["601111", "600009", "601006", "600018"],
    "auto":         ["600104", "000625"],
    "agri_consumer": ["002714", "600887", "000651", "601633"],
    "utilities":    ["600900", "601985"],
}

UNIVERSE = [c for codes in UNIVERSE_BY_SECTOR.values() for c in codes]

# Names that lost 50%+ from their 2021-2022 highs through 2023-2025.
# Kept explicit so reporting can show how much of the PnL came from
# *avoiding* them rather than from picking winners.
KNOWN_LOSERS = {
    "601012",  # LONGi Green Energy
    "002460",  # Ganfeng Lithium
    "002466",  # Tianqi Lithium
    "603259",  # WuXi AppTec
    "600009",  # Shanghai Airport
    "601111",  # Air China
    "600104",  # SAIC Motor
    "002714",  # Muyuan Foods
    "300750",  # CATL (de-rated hard in 2022-2024)
    "600585",  # Conch Cement
}

BENCHMARK = "000300.XSHG"   # CSI 300

if __name__ == "__main__":
    print(f"{len(UNIVERSE)} names, {len(UNIVERSE_BY_SECTOR)} sectors")
    print(f"{len(KNOWN_LOSERS)} deliberately-included post-2021 losers")
    for sector, codes in UNIVERSE_BY_SECTOR.items():
        print(f"  {sector:14s} {codes}")
