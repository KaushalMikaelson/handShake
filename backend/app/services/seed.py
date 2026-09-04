"""Demo seed data.

Comprehensive catalog of 60+ products spanning audio, computing, mobile,
gaming, wearables, smart home, and companion accessories with pre-approved
bundle opportunities for the Merchant Growth Agent.
"""
import uuid
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    BundleOpportunity,
    Buyer,
    Merchant,
    OpportunityStatus,
    Product,
    User,
)
from app.enums import AutonomyLevel, UserRole

MERCHANT_ID = settings.demo_merchant_id
BUYER_ID = settings.demo_buyer_id

PRODUCTS = [
    # ------------------ Audio & Headphones ------------------
    dict(
        id="prod_sony_whch720n",
        name="Sony WH-CH720N Wireless Noise Cancelling Headphones",
        brand="Sony",
        price=899_900,  # Rs 8,999
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "35h-battery", "bluetooth-5.2"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux"],
    ),
    dict(
        id="prod_boat_rockerz_551",
        name="boAt Rockerz 551ANC Wireless Headphones",
        brand="boAt",
        price=349_900,  # Rs 3,499
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "60h-battery", "bluetooth-5.3"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux"],
    ),
    dict(
        id="prod_sennheiser_hd450bt",
        name="Sennheiser HD 450BT Wireless Headphones",
        brand="Sennheiser",
        price=1_199_900,  # Rs 11,999
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "30h-battery", "aptx-codec"],
        bundle_eligible=True,
        max_discount_pct=5,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux"],
    ),
    dict(
        id="prod_sony_wh1000xm5",
        name="Sony WH-1000XM5 Premium Noise Cancelling Headphones",
        brand="Sony",
        price=2_999_000,  # Rs 29,990
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "ldac", "30h-battery", "premium"],
        bundle_eligible=True,
        max_discount_pct=12,
        companion_product_ids=["prod_case_hardshell", "prod_stand_headphone", "prod_cable_aux"],
    ),
    dict(
        id="prod_bose_qc45",
        name="Bose QuietComfort 45 Bluetooth Wireless Headphones",
        brand="Bose",
        price=2_490_000,  # Rs 24,900
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "comfort", "24h-battery"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_hardshell", "prod_stand_headphone"],
    ),
    dict(
        id="prod_apple_airpods_pro2",
        name="Apple AirPods Pro (2nd Gen) with USB-C MagSafe",
        brand="Apple",
        price=2_490_000,  # Rs 24,900
        category="electronics",
        attributes=["wireless", "noise-cancelling", "in-ear", "spatial-audio", "h2-chip"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_earbuds", "prod_charger_20w_apple", "prod_pad_wireless_charge"],
    ),
    dict(
        id="prod_sony_wf1000xm5",
        name="Sony WF-1000XM5 Truly Wireless Noise Cancelling Earbuds",
        brand="Sony",
        price=2_199_000,  # Rs 21,990
        category="electronics",
        attributes=["wireless", "noise-cancelling", "in-ear", "hires-audio", "24h-battery"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_earbuds", "prod_pad_wireless_charge"],
    ),
    dict(
        id="prod_jbl_tune760nc",
        name="JBL Tune 760NC Wireless Over-Ear Active Noise Cancelling",
        brand="JBL",
        price=549_900,  # Rs 5,499
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "pure-bass", "35h-battery"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux"],
    ),
    dict(
        id="prod_marshall_major4",
        name="Marshall Major IV Wireless On-Ear Bluetooth Headphones",
        brand="Marshall",
        price=1_299_900,  # Rs 12,999
        category="electronics",
        attributes=["wireless", "on-ear", "80h-battery", "custom-drivers", "wireless-charging"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux"],
    ),
    dict(
        id="prod_oneplus_buds_pro2",
        name="OnePlus Buds Pro 2 Spatial Audio Dual-Driver Earbuds",
        brand="OnePlus",
        price=999_900,  # Rs 9,999
        category="electronics",
        attributes=["wireless", "noise-cancelling", "in-ear", "spatial-audio", "dynaudio"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_earbuds", "prod_charger_65w_gan"],
    ),
    dict(
        id="prod_hyperx_cloud2",
        name="HyperX Cloud II Wireless 7.1 Surround Gaming Headset",
        brand="HyperX",
        price=1_049_000,  # Rs 10,490
        category="gaming",
        attributes=["wireless", "gaming", "surround-sound", "memory-foam", "30h-battery"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_stand_headphone", "prod_rest_wrist_ergo"],
    ),
    dict(
        id="prod_audio_technica_m50x",
        name="Audio-Technica ATH-M50x Professional Studio Monitor Headphones",
        brand="Audio-Technica",
        price=1_350_000,  # Rs 13,500
        category="electronics",
        attributes=["wired", "studio-monitor", "over-ear", "audiophile", "detachable-cable"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux", "prod_stand_headphone"],
    ),

    # ------------------ Laptops & Computers ------------------
    dict(
        id="prod_macbook_air_m3",
        name="Apple MacBook Air 13-inch (M3, 16GB, 512GB SSD)",
        brand="Apple",
        price=12_490_000,  # Rs 1,24,900
        category="computing",
        attributes=["laptop", "m3-chip", "16gb-ram", "liquid-retina", "18h-battery"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_sleeve_laptop", "prod_hub_usbc_7in1", "prod_stand_laptop_alu"],
    ),
    dict(
        id="prod_dell_xps13",
        name="Dell XPS 13 Plus Intel Core i7 (16GB RAM, 1TB SSD)",
        brand="Dell",
        price=14_999_000,  # Rs 1,49,990
        category="computing",
        attributes=["laptop", "intel-i7", "oled-touch", "16gb-ram", "ultrabook"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_sleeve_laptop", "prod_hub_usbc_7in1", "prod_stand_laptop_alu"],
    ),
    dict(
        id="prod_lenovo_thinkpad_x1",
        name="Lenovo ThinkPad X1 Carbon Gen 11 Ultralight",
        brand="Lenovo",
        price=13_500_000,  # Rs 1,35,000
        category="computing",
        attributes=["laptop", "business", "carbon-fiber", "intel-evo", "lightweight"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_sleeve_laptop", "prod_hub_usbc_7in1", "prod_charger_65w_gan"],
    ),
    dict(
        id="prod_asus_rog_zephyrus",
        name="ASUS ROG Zephyrus G14 OLED Gaming Laptop (RTX 4060)",
        brand="ASUS",
        price=15_999_000,  # Rs 1,59,990
        category="gaming",
        attributes=["laptop", "gaming", "rtx-4060", "ryzen-9", "oled-120hz"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_pad_gaming_mouse", "prod_hub_usbc_7in1", "prod_stand_laptop_alu"],
    ),
    dict(
        id="prod_hp_spectre_x360",
        name="HP Spectre x360 2-in-1 Touchscreen Laptop",
        brand="HP",
        price=12_999_000,  # Rs 1,29,990
        category="computing",
        attributes=["laptop", "2-in-1", "oled-touch", "intel-evo", "aluminum"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_sleeve_laptop", "prod_stylus_pen", "prod_hub_usbc_7in1"],
    ),
    dict(
        id="prod_acer_swift_go",
        name="Acer Swift Go 14 OLED Intel Core Ultra 5",
        brand="Acer",
        price=6_299_000,  # Rs 62,990
        category="computing",
        attributes=["laptop", "oled", "intel-core-ultra", "lightweight", "fast-charge"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_sleeve_laptop", "prod_hub_usbc_7in1", "prod_stand_laptop_alu"],
    ),

    # ------------------ Smartphones & Tablets ------------------
    dict(
        id="prod_iphone_15_pro",
        name="Apple iPhone 15 Pro (256GB, Natural Titanium)",
        brand="Apple",
        price=12_799_000,  # Rs 1,27,990
        category="electronics",
        attributes=["smartphone", "a17-pro", "titanium", "oled-120hz", "usb-c"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_charger_20w_apple", "prod_protector_screen", "prod_pad_wireless_charge"],
    ),
    dict(
        id="prod_samsung_s24_ultra",
        name="Samsung Galaxy S24 Ultra 5G AI Smartphone (256GB)",
        brand="Samsung",
        price=12_999_900,  # Rs 1,29,999
        category="electronics",
        attributes=["smartphone", "galaxy-ai", "snapdragon-8-gen3", "200mp-camera", "s-pen"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_charger_65w_gan", "prod_protector_screen", "prod_pad_wireless_charge"],
    ),
    dict(
        id="prod_oneplus_12",
        name="OnePlus 12 5G (16GB RAM, 512GB Storage)",
        brand="OnePlus",
        price=6_499_900,  # Rs 64,999
        category="electronics",
        attributes=["smartphone", "snapdragon-8-gen3", "100w-charging", "2k-120hz-display"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_charger_65w_gan", "prod_protector_screen"],
    ),
    dict(
        id="prod_google_pixel_8_pro",
        name="Google Pixel 8 Pro with Gemini AI (128GB)",
        brand="Google",
        price=9_899_900,  # Rs 98,999
        category="electronics",
        attributes=["smartphone", "google-tensor-g3", "ai-camera", "super-actua-display"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_charger_65w_gan", "prod_protector_screen", "prod_pad_wireless_charge"],
    ),
    dict(
        id="prod_ipad_air_m2",
        name="Apple iPad Air 11-inch (M2 Chip, Liquid Retina, 128GB)",
        brand="Apple",
        price=5_990_000,  # Rs 59,900
        category="computing",
        attributes=["tablet", "m2-chip", "liquid-retina", "apple-pencil-pro-support", "usb-c"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_stylus_pen", "prod_protector_screen", "prod_charger_20w_apple"],
    ),
    dict(
        id="prod_samsung_tab_s9",
        name="Samsung Galaxy Tab S9 Ultra (14.6-inch Dynamic AMOLED)",
        brand="Samsung",
        price=10_899_900,  # Rs 1,08,999
        category="computing",
        attributes=["tablet", "amoled", "s-pen-included", "snapdragon-8-gen2", "ip68"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_stylus_pen", "prod_protector_screen", "prod_charger_65w_gan"],
    ),

    # ------------------ Keyboards, Mice & Peripherals ------------------
    dict(
        id="prod_logitech_mx_master3s",
        name="Logitech MX Master 3S Wireless Performance Ergonomic Mouse",
        brand="Logitech",
        price=949_500,  # Rs 9,495
        category="computing",
        attributes=["mouse", "ergonomic", "quiet-clicks", "8k-dpi", "bluetooth-usb"],
        bundle_eligible=True,
        max_discount_pct=12,
        companion_product_ids=["prod_mat_desk_xl", "prod_rest_wrist_ergo"],
    ),
    dict(
        id="prod_keychron_k2",
        name="Keychron K2 Wireless Mechanical Keyboard (RGB Hot-swap)",
        brand="Keychron",
        price=849_900,  # Rs 8,499
        category="computing",
        attributes=["keyboard", "mechanical", "hot-swap", "rgb-backlit", "mac-windows"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_rest_wrist_ergo", "prod_kit_cleaning_pro", "prod_mat_desk_xl"],
    ),
    dict(
        id="prod_razer_deathadder_v3",
        name="Razer DeathAdder V3 Pro Ultra-lightweight Wireless Gaming Mouse",
        brand="Razer",
        price=1_399_900,  # Rs 13,999
        category="gaming",
        attributes=["mouse", "gaming", "ultra-light", "30k-sensor", "wireless"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_pad_gaming_mouse", "prod_kit_cleaning_pro"],
    ),
    dict(
        id="prod_logitech_mx_keys",
        name="Logitech MX Keys Advanced Wireless Illuminated Keyboard",
        brand="Logitech",
        price=1_099_500,  # Rs 10,995
        category="computing",
        attributes=["keyboard", "low-profile", "smart-illumination", "multi-device"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_rest_wrist_ergo", "prod_mat_desk_xl"],
    ),
    dict(
        id="prod_steelseries_apex_pro",
        name="SteelSeries Apex Pro TKL Mechanical Gaming Keyboard",
        brand="SteelSeries",
        price=1_999_900,  # Rs 19,999
        category="gaming",
        attributes=["keyboard", "gaming", "adjustable-actuation", "oled-smart-display", "rgb"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_rest_wrist_ergo", "prod_kit_cleaning_pro", "prod_pad_gaming_mouse"],
    ),
    dict(
        id="prod_elgato_stream_deck",
        name="Elgato Stream Deck MK.2 Studio Controller (15 LCD Keys)",
        brand="Elgato",
        price=1_399_900,  # Rs 13,999
        category="computing",
        attributes=["creator-gear", "lcd-keys", "macro-pad", "streaming", "customizable"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_hub_usbc_7in1", "prod_cable_tb4"],
    ),
    dict(
        id="prod_logitech_brio_4k",
        name="Logitech Brio 4K Ultra HD Streaming Webcam with HDR",
        brand="Logitech",
        price=1_850_000,  # Rs 18,500
        category="computing",
        attributes=["webcam", "4k-ultra-hd", "hdr", "rightlight-3", "dual-mics"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_hub_usbc_7in1", "prod_kit_cleaning_pro"],
    ),
    dict(
        id="prod_shure_mv7",
        name="Shure MV7 USB/XLR Dynamic Broadcast Microphone",
        brand="Shure",
        price=2_299_900,  # Rs 22,999
        category="electronics",
        attributes=["microphone", "broadcast", "usb-xlr", "voice-isolation", "touch-panel"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_cable_aux", "prod_kit_cleaning_pro"],
    ),

    # ------------------ Wearables & Smartwatches ------------------
    dict(
        id="prod_apple_watch_series9",
        name="Apple Watch Series 9 GPS + Cellular (45mm Aluminum)",
        brand="Apple",
        price=4_490_000,  # Rs 44,900
        category="wearables",
        attributes=["smartwatch", "s9-sip", "double-tap", "ecg", "always-on-retina"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_strap_watch_silicone", "prod_strap_watch_leather", "prod_pad_wireless_charge"],
    ),
    dict(
        id="prod_samsung_galaxy_watch6",
        name="Samsung Galaxy Watch 6 Classic (47mm Rotating Bezel)",
        brand="Samsung",
        price=3_699_900,  # Rs 36,999
        category="wearables",
        attributes=["smartwatch", "sapphire-crystal", "rotating-bezel", "body-composition"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_strap_watch_silicone", "prod_strap_watch_leather", "prod_pad_wireless_charge"],
    ),
    dict(
        id="prod_garmin_forerunner_265",
        name="Garmin Forerunner 265 AMOLED Running Smartwatch",
        brand="Garmin",
        price=4_649_000,  # Rs 46,490
        category="wearables",
        attributes=["smartwatch", "running", "amoled", "training-readiness", "multisport"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_strap_watch_silicone", "prod_protector_screen"],
    ),
    dict(
        id="prod_fitbit_charge6",
        name="Fitbit Charge 6 Advanced Fitness Tracker",
        brand="Fitbit",
        price=1_499_900,  # Rs 14,999
        category="wearables",
        attributes=["fitness-band", "heart-rate", "built-in-gps", "google-maps", "7-day-battery"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_strap_watch_silicone", "prod_protector_screen"],
    ),
    dict(
        id="prod_noise_colorfit_ultra3",
        name="Noise ColorFit Ultra 3 AMOLED Bluetooth Calling Smartwatch",
        brand="Noise",
        price=349_900,  # Rs 3,499
        category="wearables",
        attributes=["smartwatch", "amoled-display", "bluetooth-calling", "metallic-finish"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_strap_watch_silicone", "prod_protector_screen"],
    ),

    # ------------------ Smart Home & Displays ------------------
    dict(
        id="prod_amazon_echo_dot5",
        name="Amazon Echo Dot (5th Gen) Smart Speaker with Alexa",
        brand="Amazon",
        price=449_900,  # Rs 4,499
        category="smart_home",
        attributes=["smart-speaker", "alexa", "deeper-bass", "voice-control", "motion-sensor"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_bulb_smart_rgb", "prod_plug_smart_wifi"],
    ),
    dict(
        id="prod_google_nest_hub",
        name="Google Nest Hub (2nd Gen) Smart Home Controller Display",
        brand="Google",
        price=799_900,  # Rs 7,999
        category="smart_home",
        attributes=["smart-display", "google-assistant", "sleep-sensing", "gesture-control"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_bulb_smart_rgb", "prod_plug_smart_wifi"],
    ),
    dict(
        id="prod_philips_hue_starter",
        name="Philips Hue White & Color Ambiance Smart Starter Kit",
        brand="Philips",
        price=999_900,  # Rs 9,999
        category="smart_home",
        attributes=["smart-lighting", "16m-colors", "hue-bridge", "voice-control"],
        bundle_eligible=True,
        max_discount_pct=12,
        companion_product_ids=["prod_plug_smart_wifi", "prod_bulb_smart_rgb"],
    ),
    dict(
        id="prod_kindle_paperwhite",
        name="Amazon Kindle Paperwhite 16GB (6.8-inch Glare-Free Display)",
        brand="Amazon",
        price=1_499_900,  # Rs 14,999
        category="electronics",
        attributes=["e-reader", "glare-free", "waterproof-ipx8", "adjustable-warm-light"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_protector_screen", "prod_charger_20w_apple"],
    ),

    # ------------------ Accessories & Companion Bonus Items ------------------
    dict(
        id="prod_case_hardshell",
        name="Universal Hardshell Headphone Carry Case",
        brand="AudioHub",
        price=79_900,  # Rs 799
        category="accessories",
        attributes=["hardshell", "water-resistant", "universal-fit", "eva-foam"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_cable_aux",
        name="Braided 3.5mm AUX Cable (1.5m, Gold-Plated)",
        brand="AudioHub",
        price=29_900,  # Rs 299
        category="accessories",
        attributes=["braided", "3.5mm", "1.5m", "gold-plated", "tangle-free"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
    dict(
        id="prod_stand_headphone",
        name="Minimalist Aluminum Headphone Desktop Stand",
        brand="AudioHub",
        price=129_900,  # Rs 1,299
        category="accessories",
        attributes=["aluminum", "anti-slip-silicone", "desktop-stand", "sturdy"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_case_earbuds",
        name="Protective Silicone Earbud Case with Carabiner",
        brand="AudioHub",
        price=49_900,  # Rs 499
        category="accessories",
        attributes=["silicone", "shockproof", "carabiner-clip", "wireless-charging-compatible"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
    dict(
        id="prod_charger_65w_gan",
        name="65W GaN Multi-Port USB-C Fast Wall Charger",
        brand="AudioHub",
        price=249_900,  # Rs 2,499
        category="accessories",
        attributes=["gan-charger", "65w", "dual-usb-c", "fast-charging", "compact"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_charger_20w_apple",
        name="20W USB-C Power Delivery Fast Adapter",
        brand="AudioHub",
        price=169_900,  # Rs 1,699
        category="accessories",
        attributes=["20w", "usb-c-pd", "fast-charging", "safe-current"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_pad_wireless_charge",
        name="15W Qi Fast Wireless Charging Pad",
        brand="AudioHub",
        price=149_900,  # Rs 1,499
        category="accessories",
        attributes=["wireless-charger", "15w-fast", "led-indicator", "anti-slip"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_sleeve_laptop",
        name="Water-Resistant Padded Laptop Sleeve (13-14 inch)",
        brand="AudioHub",
        price=119_900,  # Rs 1,199
        category="accessories",
        attributes=["laptop-sleeve", "water-resistant", "fleece-lining", "extra-pocket"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_stand_laptop_alu",
        name="Ergonomic Foldable Aluminum Laptop Riser",
        brand="AudioHub",
        price=189_900,  # Rs 1,899
        category="accessories",
        attributes=["laptop-stand", "aluminum", "adjustable-height", "heat-dissipation"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_hub_usbc_7in1",
        name="7-in-1 USB-C Hub with 4K HDMI & 100W PD",
        brand="AudioHub",
        price=279_900,  # Rs 2,799
        category="accessories",
        attributes=["usb-c-hub", "4k-hdmi", "100w-pd", "sd-card-reader", "aluminum"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_mat_desk_xl",
        name="Premium Vegan Leather XL Desk Mat (90x40cm)",
        brand="AudioHub",
        price=99_900,  # Rs 999
        category="accessories",
        attributes=["desk-mat", "vegan-leather", "waterproof", "anti-slip-base"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
    dict(
        id="prod_pad_gaming_mouse",
        name="Anti-Fray Precision Gaming Mouse Pad",
        brand="AudioHub",
        price=69_900,  # Rs 699
        category="accessories",
        attributes=["mouse-pad", "micro-weave-cloth", "stitched-edges", "anti-slip-rubber"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
    dict(
        id="prod_rest_wrist_ergo",
        name="Memory Foam Ergonomic Keyboard & Mouse Wrist Rest",
        brand="AudioHub",
        price=79_900,  # Rs 799
        category="accessories",
        attributes=["wrist-rest", "memory-foam", "ergonomic", "cooling-gel", "anti-slip"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
    dict(
        id="prod_kit_cleaning_pro",
        name="7-in-1 Electronic Screen & Keycap Cleaning Kit",
        brand="AudioHub",
        price=39_900,  # Rs 399
        category="accessories",
        attributes=["cleaning-kit", "keycap-puller", "brush", "spray-bottle", "microfiber"],
        bundle_eligible=True,
        max_discount_pct=25,
        companion_product_ids=[],
    ),
    dict(
        id="prod_cable_tb4",
        name="Braided Thunderbolt 4 / USB4 100W Cable (1m)",
        brand="AudioHub",
        price=149_900,  # Rs 1,499
        category="accessories",
        attributes=["thunderbolt-4", "40gbps", "100w-pd", "braided", "8k-video"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_protector_screen",
        name="9H Tempered Glass Anti-Glare Screen Protector 2-Pack",
        brand="AudioHub",
        price=49_900,  # Rs 499
        category="accessories",
        attributes=["screen-protector", "9h-tempered-glass", "anti-glare", "anti-fingerprint"],
        bundle_eligible=True,
        max_discount_pct=25,
        companion_product_ids=[],
    ),
    dict(
        id="prod_strap_watch_silicone",
        name="Premium Quick-Release Breathable Silicone Watch Band",
        brand="AudioHub",
        price=69_900,  # Rs 699
        category="accessories",
        attributes=["watch-band", "silicone", "quick-release", "sweatproof", "breathable"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
    dict(
        id="prod_strap_watch_leather",
        name="Genuine Italian Leather Watch Strap with Steel Buckle",
        brand="AudioHub",
        price=149_900,  # Rs 1,499
        category="accessories",
        attributes=["watch-strap", "genuine-leather", "stainless-steel-buckle", "classic"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_stylus_pen",
        name="Precision Tilt-Sensitive Magnetic Stylus Pen",
        brand="AudioHub",
        price=299_900,  # Rs 2,999
        category="accessories",
        attributes=["stylus", "palm-rejection", "tilt-sensitivity", "magnetic-attach", "usb-c"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_plug_smart_wifi",
        name="16A Wi-Fi Smart Plug with Energy Monitoring",
        brand="AudioHub",
        price=89_900,  # Rs 899
        category="accessories",
        attributes=["smart-plug", "wifi", "energy-meter", "voice-control", "surge-protection"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
    dict(
        id="prod_bulb_smart_rgb",
        name="12W RGB Wi-Fi Smart LED Bulb",
        brand="AudioHub",
        price=69_900,  # Rs 699
        category="accessories",
        attributes=["smart-bulb", "16m-colors", "wifi", "dimmable", "voice-control"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
]


def sync_catalog(db: Session) -> None:
    """Ensure all catalog items and pre-approved companion opportunities are in DB."""
    # Ensure merchant exists
    merchant = db.query(Merchant).filter_by(id=MERCHANT_ID).first()
    if not merchant:
        merchant = Merchant(
            id=MERCHANT_ID,
            name="AudioHub India",
            description="Audio & consumer tech gear merchant with an AI growth agent for bundling and upsell.",
            max_discount_pct=15,
            max_campaign_budget=5_000_000,  # Rs 50,000
            auto_approve_bundle_discount_below_pct=10,
            verified_catalog=True,
            successful_transactions=128,
            failed_transactions=2,
        )
        db.add(merchant)
        db.flush()

    # Sync products
    existing_products = {p.id: p for p in db.query(Product).all()}
    for spec in PRODUCTS:
        p_id = spec["id"]
        if p_id not in existing_products:
            db.add(Product(merchant_id=MERCHANT_ID, currency="INR", stock_available=True, **spec))
        else:
            p = existing_products[p_id]
            p.name = spec["name"]
            p.brand = spec["brand"]
            p.price = spec["price"]
            p.category = spec["category"]
            p.attributes = spec["attributes"]
            p.bundle_eligible = spec["bundle_eligible"]
            p.max_discount_pct = spec["max_discount_pct"]
            p.companion_product_ids = spec["companion_product_ids"]

    db.flush()
    _seed_opportunities(db)
    
    # Ensure buyer has all allowed categories
    buyer = db.query(Buyer).filter_by(id=BUYER_ID).first()
    if buyer:
        buyer.allowed_categories = [
            "electronics",
            "accessories",
            "computing",
            "wearables",
            "gaming",
            "smart_home",
        ]
        buyer.daily_budget = max(buyer.daily_budget, 10_000_000)      # Rs 100,000
        buyer.monthly_budget = max(buyer.monthly_budget, 30_000_000)  # Rs 300,000
        buyer.max_transaction = max(buyer.max_transaction, 20_000_000) # Rs 200,000

    db.flush()


def seed_if_empty(db: Session) -> bool:
    """Idempotent seed. Returns True if data was written or synchronized."""
    data_written = False
    
    if db.query(Merchant).count() == 0 or db.query(Product).count() < len(PRODUCTS):
        sync_catalog(db)
        data_written = True

    if db.query(Buyer).filter_by(id=BUYER_ID).count() == 0:
        db.add(
            Buyer(
                id=BUYER_ID,
                name="Aditi",
                daily_budget=10_000_000,           # Rs 100,000
                monthly_budget=30_000_000,         # Rs 300,000
                max_transaction=20_000_000,        # Rs 200,000
                allowed_categories=[
                    "electronics",
                    "accessories",
                    "computing",
                    "wearables",
                    "gaming",
                    "smart_home",
                ],
                blocked_categories=["financial_services"],
                require_approval_above=500_000,    # Rs 5,000
                allow_automatic_purchase_below=200_000,  # Rs 2,000
                autonomy_level=AutonomyLevel.BOUNDED_AUTO,
            )
        )
        db.flush()
        data_written = True

    if db.query(User).count() == 0:
        _seed_users(db)
        data_written = True

    db.commit()
    return data_written


DEMO_PASSWORD = "Demo@1234"

DEMO_USERS = [
    dict(
        email="aditi@handshake.demo",
        name="Aditi Rao",
        role=UserRole.BUYER,
        buyer_id=BUYER_ID,
        merchant_id=None,
    ),
    dict(
        email="merchant@audiohub.demo",
        name="AudioHub Growth Team",
        role=UserRole.MERCHANT,
        buyer_id=None,
        merchant_id=MERCHANT_ID,
    ),
    dict(
        email="admin@handshake.demo",
        name="Platform Admin",
        role=UserRole.ADMIN,
        buyer_id=BUYER_ID,
        merchant_id=MERCHANT_ID,
    ),
]


def _seed_users(db: Session) -> None:
    from app.services.auth import create_user

    for spec in DEMO_USERS:
        create_user(db, password=DEMO_PASSWORD, **spec)


def create_buyer_profile(db: Session, *, name: str) -> Buyer:
    buyer = Buyer(
        id=f"buyer_{uuid.uuid4().hex[:10]}",
        name=name,
        daily_budget=5_000_000,                  # Rs 50,000
        monthly_budget=20_000_000,               # Rs 200,000
        max_transaction=10_000_000,              # Rs 100,000
        allowed_categories=[
            "electronics",
            "accessories",
            "computing",
            "wearables",
            "gaming",
            "smart_home",
        ],
        blocked_categories=["financial_services"],
        require_approval_above=500_000,          # Rs 5,000
        allow_automatic_purchase_below=200_000,  # Rs 2,000
        autonomy_level=AutonomyLevel.PREPARE,
    )
    db.add(buyer)
    db.flush()
    return buyer


def _seed_opportunities(db: Session) -> None:
    """Pre-approve companion relationships for every anchor product with companions."""
    by_id = {p["id"]: p for p in PRODUCTS}
    existing_opps = {
        (o.anchor_product_id, o.companion_product_id): o
        for o in db.query(BundleOpportunity).all()
    }

    for anchor in PRODUCTS:
        for companion_id in anchor["companion_product_ids"]:
            if companion_id not in by_id:
                continue
            pair = (anchor["id"], companion_id)
            if pair not in existing_opps:
                companion = by_id[companion_id]
                db.add(
                    BundleOpportunity(
                        id=f"opp_{uuid.uuid4().hex[:10]}",
                        merchant_id=MERCHANT_ID,
                        anchor_product_id=anchor["id"],
                        companion_product_id=companion_id,
                        potential_aov_uplift=companion["price"],
                        rationale=(
                            f"Buyers of {anchor['brand']} {anchor['name']} frequently add "
                            f"{companion['name'].lower()}; attaching it lifts order value by "
                            f"{companion['price'] // 100} rupees."
                        ),
                        status=OpportunityStatus.APPROVED,
                    )
                )
