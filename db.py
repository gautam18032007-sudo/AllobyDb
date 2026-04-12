"""
db.py — AlloyDB (PostgreSQL) database layer

- Connection pooling via psycopg2.pool
- Auto-creates and seeds the products table on first run
- Executes SELECT queries and returns JSON-safe results
- Exposes schema metadata for the AI prompt
"""

import logging
from decimal import Decimal
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, TABLE_NAME

log = logging.getLogger(__name__)

_pool: psycopg2.pool.SimpleConnectionPool | None = None


# ── Pool management ────────────────────────────────────────────────────────

def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1, maxconn=10,
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            connect_timeout=10,
        )
        log.info("AlloyDB connection pool created")
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    get_pool().putconn(conn)


# ── Seed data (20 products across 5 categories) ────────────────────────────

SEED_PRODUCTS = [
    # (name, category, price, stock, rating, description)
    ("Wireless Noise-Cancelling Headphones", "Electronics", 149.99, 35, 4.7,
     "Over-ear ANC headphones with 30-hour battery and premium sound."),
    ("Ergonomic Office Chair",               "Furniture",   329.00, 12, 4.5,
     "Lumbar-support mesh chair for all-day comfort and posture."),
    ("Stainless Steel Water Bottle",         "Kitchen",      24.95, 120, 4.8,
     "32oz double-walled insulated bottle, cold 24h or hot 12h."),
    ("Mechanical Keyboard TKL",              "Electronics",  89.99,  60, 4.6,
     "Cherry MX Brown switches, RGB backlight, compact tenkeyless."),
    ("Yoga Mat Premium",                     "Sports",       45.00,  80, 4.4,
     "6mm non-slip TPE foam with alignment lines, eco-friendly."),
    ("Air Purifier HEPA 500sqft",            "Home",        199.00,  25, 4.3,
     "Covers 500 sq ft, removes 99.97% of particles ≥0.3 microns."),
    ("Portable Bluetooth Speaker",           "Electronics",  59.99,  45, 4.5,
     "IPX7 waterproof, 360-degree sound, 12-hour playback."),
    ("Cast Iron Skillet 12in",               "Kitchen",      39.95,  70, 4.9,
     "Pre-seasoned, works on all cooktops including induction."),
    ("Standing Desk Converter",              "Furniture",   249.00,  18, 4.2,
     "Sit-stand riser with gas-spring lift, smooth height adjustment."),
    ("Running Shoes Pro",                    "Sports",      119.99,  55, 4.6,
     "Breathable mesh upper, responsive foam midsole for long runs."),
    ("Smart LED Desk Lamp",                  "Electronics",  49.99,  90, 4.5,
     "Touch-control with 5 colour temps and USB-C charging port."),
    ("French Press Coffee Maker",            "Kitchen",      34.99,  65, 4.7,
     "8-cup borosilicate glass, stainless double-screen filter."),
    ("Foam Roller Deep Tissue",              "Sports",       29.99, 100, 4.3,
     "High-density EVA foam, 36-inch length for full-back coverage."),
    ("Weighted Blanket 15lb",                "Home",         79.00,  40, 4.6,
     "Glass-bead fill in 48x72in premium cotton shell."),
    ("White Noise Sleep Machine",            "Home",         44.95,  55, 4.8,
     "30 soothing sounds, auto-off timer, compact bedside design."),
    ("4K Webcam Pro",                        "Electronics",  99.99,  30, 4.4,
     "4K autofocus, built-in ring light and noise-cancelling mic."),
    ("Bamboo Cutting Board Set",             "Kitchen",      32.00,  85, 4.6,
     "3-piece set with juice grooves, naturally antimicrobial."),
    ("Resistance Bands Set",                 "Sports",       19.99, 150, 4.5,
     "5 resistance levels, latex-free, includes carry bag."),
    ("Electric Kettle 1.7L",                 "Kitchen",      44.99,  60, 4.7,
     "1500W rapid boil, 6 temperature presets, keep-warm mode."),
    ("Monitor Light Bar",                    "Electronics",  35.99,  75, 4.5,
     "Auto-dimming sensor, no screen glare, USB-C powered."),
    # New products added below
    ("Gaming Mouse RGB",                     "Electronics",  69.99,  42, 4.6,
     "12 programmable buttons, 16K DPI, customizable RGB lighting."),
    ("Smart Doorbell Camera",                "Home",        159.99,  22, 4.4,
     "1080p HD video, two-way audio, night vision, motion detection."),
    ("Espresso Machine Automatic",           "Kitchen",     299.99,  15, 4.7,
     "15-bar pressure, built-in grinder, milk frother, one-touch brewing."),
    ("Adjustable Dumbbells Set",             "Sports",      189.99,  28, 4.5,
     "5-52.5 lbs per dumbbell, dial adjustment system, space-saving."),
    ("Robot Vacuum Cleaner",                 "Home",        249.99,  20, 4.3,
     "Smart mapping, 2000Pa suction, auto-charging, app control."),
    ("Ceramic Cookware Set",                  "Kitchen",      89.99,  38, 4.5,
     "10-piece non-stick set, PTFE-free, oven safe to 450°F."),
    ("Premium Yoga Blocks",                   "Sports",       24.99,  65, 4.4,
     "High-density cork, set of 2, natural and eco-friendly material."),
    ("Smart Thermostat",                      "Home",        179.99,  25, 4.6,
     "Learning algorithms, energy saving, voice control compatible."),
    ("Wireless Charging Pad",                 "Electronics",  29.99,  90, 4.3,
     "15W fast charging, LED indicator, compatible with all Qi devices."),
    ("Massage Gun Deep Tissue",               "Sports",      129.99,  35, 4.7,
     "30 speeds, 6 attachments, quiet motor, carrying case included."),
    ("Under Desk Elliptical",                 "Fitness",     139.99,  18, 4.2,
     "Compact pedal exerciser, 8 resistance levels, digital monitor."),
    ("Smart Plant Monitor",                   "Garden",       34.99,  48, 4.1,
     "Soil moisture, light level, temperature tracking, app alerts."),
    ("Aromatherapy Diffuser",                 "Home",         39.99,  55, 4.5,
     "300ml capacity, 7 LED colors, timer settings, whisper quiet."),
    ("Digital Picture Frame",                 "Electronics",  79.99,  32, 4.4,
     "10-inch HD display, WiFi enabled, unlimited cloud storage."),
    ("Adjustable Laptop Stand",               "Furniture",    45.99,  50, 4.6,
     "Aluminum construction, 7 angles, ergonomic design, portable."),
    # Additional products (Batch 3)
    ("Smart Air Fryer Pro",                   "Kitchen",     149.99,  24, 4.5,
     "8qt capacity, 12 presets, app control, rapid air circulation."),
    ("Bluetooth Sleep Headphones",            "Electronics",  39.99,  72, 4.3,
     "Soft headband design, 10-hour battery, white noise compatible."),
    ("Electric Standing Desk",                "Furniture",   399.99,  12, 4.4,
     "Dual motor, memory positions, 48x30in desktop, cable management."),
    ("Portable Power Station",                "Electronics", 299.99,  20, 4.6,
     "500W output, solar charging, LCD display, emergency backup."),
    ("Smart Water Bottle",                    "Kitchen",      49.99,  45, 4.2,
     "Hydration reminders, temperature display, app integration."),
    ("Foam Mattress Topper",                  "Home",         89.99,  38, 4.5,
     "3-inch memory foam, cooling gel, hypoallergenic cover."),
    ("Cordless Vacuum Cleaner",               "Home",        179.99,  28, 4.4,
     "25KPa suction, 40min runtime, HEPA filter, wall mount."),
    ("Smart Bike Trainer",                    "Fitness",     349.99,  10, 4.7,
     "Direct drive, Zwift compatible, 2000W resistance, quiet."),
    ("Outdoor Security Camera",               "Home",        129.99,  30, 4.3,
     "Solar powered, 2K resolution, color night vision, 2-way audio."),
    ("Electric Toothbrush Pro",               "Electronics",  79.99,  55, 4.6,
     "Pressure sensor, 5 modes, UV sanitizer, 30-day battery."),
    ("Indoor Herb Garden Kit",                "Garden",       59.99,  40, 4.4,
     "LED grow lights, self-watering, 9 pods, basil, mint, parsley."),
    ("Smart Scale Body Composition",          "Fitness",      49.99,  65, 4.5,
     "13 metrics tracked, WiFi sync, multi-user, trend analysis."),
    ("Noise Cancelling Earbuds",              "Electronics", 129.99,  42, 4.5,
     "ANC 40dB reduction, 8-hour battery, IPX5 waterproof, transparency mode."),
    ("Robot Lawn Mower",                      "Garden",      899.99,   8, 4.2,
     "1/4 acre coverage, boundary wire free, rain sensor, app scheduling."),
    ("Heated Massage Pad",                    "Home",         69.99,  48, 4.4,
     "3 heat settings, 5 massage modes, auto shutoff, chair strap."),
    # Batch 4 - More Electronics (20+ items)
    ("USB-C Hub 7-in-1",                      "Electronics",  39.99,  85, 4.5,
     "4K HDMI, 100W PD charging, SD/TF card reader, 3 USB 3.0 ports."),
    ("Wireless Earbuds Pro",                  "Electronics",  89.99,  60, 4.6,
     "Active noise cancelling, 8hr battery, transparency mode, IPX4."),
    ("Smart Home Hub",                        "Electronics",  129.99, 35, 4.3,
     "Zigbee/Z-Wave compatible, voice control, automation scenes."),
    ("Tablet Stand Adjustable",               "Electronics",  24.99,  95, 4.4,
     "Aluminum alloy, 270° rotation, foldable, compatible with 4-13in devices."),
    ("Bluetooth Tracker 4-Pack",              "Electronics",  49.99,  70, 4.5,
     "Find keys, wallets, luggage, 400ft range, replaceable battery."),
    ("USB Microphone Cardioid",               "Electronics",  59.99,  55, 4.6,
     "192kHz/24bit, plug & play, headphone output, shock mount included."),
    ("Wireless Presenter Clicker",            "Electronics",  19.99,  110, 4.4,
     "2.4GHz, 100ft range, red laser pointer, volume control."),
    ("HDMI Switch 5-Port",                    "Electronics",  34.99,  45, 4.3,
     "4K@60Hz, auto-switching, remote control, HDCP 2.2 compliant."),
    ("Smart Plug WiFi 4-Pack",                "Electronics",  29.99,  80, 4.5,
     "Voice control, scheduling, energy monitoring, 15A max load."),
    ("Phone Camera Lens Kit",                 "Electronics",  44.99,  40, 4.2,
     "Wide, macro, fisheye lenses, clip-on, universal compatibility."),
    ("Portable Monitor 15.6in",              "Electronics",  199.99, 25, 4.6,
     "1080p IPS, USB-C/HDMI, built-in speakers, protective case."),
    ("Cable Management Box Set",              "Electronics",  22.99,  65, 4.4,
     "3 sizes, bamboo lid, hide power strips, surge protector safe."),
    # Batch 5 - More Kitchen (20+ items)
    ("Knife Set Block 15-Piece",              "Kitchen",      79.99,  42, 4.7,
     "High-carbon stainless, full tang, wood block, sharpener included."),
    ("Non-Stick Pan Set 3pc",                 "Kitchen",      54.99,  58, 4.5,
     "8/10/12 inch, ceramic coating, PFOA-free, stay-cool handles."),
    ("Food Processor 14-Cup",                 "Kitchen",      249.99, 20, 4.6,
     "750W motor, 8 attachments, dough blade, variable speeds."),
    ("Stand Mixer 5qt",                       "Kitchen",      349.99, 15, 4.8,
     "Tilt-head, 10 speeds, dough hook, whisk, flat beater included."),
    ("Air Fryer Toaster Oven",                "Kitchen",      179.99, 28, 4.5,
     "12 functions, 26qt capacity, rotisserie, 3 rack positions."),
    ("Sous Vide Precision Cooker",            "Kitchen",      89.99,  35, 4.4,
     "WiFi enabled, 1100W, 0.1°C accuracy, app with 1000+ recipes."),
    ("Spice Rack Organizer 20-Jar",           "Kitchen",      34.99,  48, 4.5,
     "Revolving carousel, pre-filled jars, labels, stainless steel."),
    ("Cutting Board Set 4pc",                 "Kitchen",      29.99,  62, 4.6,
     "Color-coded, dishwasher safe, BPA-free, non-slip edges."),
    ("Oil Dispenser Bottle Set",              "Kitchen",      18.99,  75, 4.4,
     "2 bottles, pour spout, brush set, 500ml, glass body."),
    ("Kitchen Utensil Set 15pc",              "Kitchen",      24.99,  88, 4.5,
     "Silicone heads, stainless handles, holder included, heat resistant."),
    ("Blender Professional",                  "Kitchen",      159.99, 22, 4.6,
     "1400W, 72oz pitcher, 6 blades, 8 speeds, pulse function."),
    ("Rice Cooker 10-Cup",                    "Kitchen",      69.99,  38, 4.5,
     "Fuzzy logic, keep warm, delay timer, non-stick pot."),
    ("Instant Pot 8qt",                       "Kitchen",      119.99, 30, 4.7,
     "7-in-1 multi-cooker, pressure, slow cook, steam, sauté."),
    ("Coffee Grinder Burr",                   "Kitchen",      59.99,  45, 4.4,
     "18 grind settings, 12 cup capacity, conical burr, low noise."),
    ("Tea Kettle Stovetop",                  "Kitchen",      39.99,  52, 4.5,
     "Gooseneck spout, stainless steel, 1.2L, thermometer built-in."),
    ("Salad Spinner Large",                  "Kitchen",      19.99,  68, 4.3,
     "5qt capacity, pump handle, brake button, colander basket."),
    ("Meat Thermometer Digital",              "Kitchen",      16.99,  95, 4.6,
     "Instant read 2-3sec, backlight, waterproof, magnetic back."),
    ("Baking Sheet Set 3pc",                  "Kitchen",      27.99,  42, 4.5,
     "Aluminized steel, non-stick, jelly roll, half, quarter sizes."),
    # Batch 6 - More Sports (20+ items)
    ("Treadmill Folding",                     "Sports",       599.99, 12, 4.4,
     "2.5HP motor, 12 programs, incline, pulse sensors, app sync."),
    ("Exercise Bike Stationary",              "Sports",       249.99, 25, 4.5,
     "Magnetic resistance, 35lb flywheel, tablet holder, quiet belt."),
    ("Rowing Machine Magnetic",               "Sports",       349.99, 18, 4.6,
     "16 resistance levels, LCD monitor, foldable, max 300lb."),
    ("Pull Up Bar Doorway",                   "Sports",       34.99,  55, 4.4,
     "No screws needed, foam grips, fits 24-36in doors, 300lb max."),
    ("Kettlebell Set 3pc",                    "Sports",       69.99,  35, 4.5,
     "5/10/15 lb, vinyl coated, flat base, color coded."),
    ("Jump Rope Adjustable",                  "Sports",       12.99,  85, 4.3,
     "Speed rope, ball bearings, 10ft length, anti-slip handles."),
    ("Yoga Wheel Set 3",                      "Sports",       29.99,  40, 4.4,
     "Back stretcher, pose support, ABS core, TPE padding."),
    ("Resistance Band Loop Set",              "Sports",       14.99,  72, 4.5,
     "5 levels, 12in loops, cloth fabric, non-roll design."),
    ("Balance Ball Chair",                  "Sports",       79.99,  28, 4.4,
     "52cm ball, base with wheels, pump included, improves posture."),
    ("Push Up Board System",                  "Sports",       24.99,  48, 4.5,
     "14-in-1 positions, color coded, non-slip, foldable."),
    ("Ab Roller Wheel",                       "Sports",       19.99,  65, 4.3,
     "Wide wheel, knee pad included, ergonomic handles, stable."),
    ("Boxing Gloves Pair",                    "Sports",       34.99,  38, 4.5,
     "12oz, synthetic leather, wrist support, breathable mesh."),
    ("Tennis Racket Set",                     "Sports",       59.99,  32, 4.4,
     "2 rackets, 3 balls, lightweight, shock absorption, grip tape."),
    ("Basketball Indoor/Outdoor",             "Sports",       29.99,  58, 4.6,
     "Composite leather, deep channels, butyl bladder, all court."),
    ("Soccer Ball Size 5",                    "Sports",       24.99,  45, 4.5,
     "Thermoplastic polyurethane, 32 panels, butyl bladder."),
    ("Dumbbell Rack 3-Tier",                  "Sports",       149.99, 15, 4.4,
     "Steel construction, rubber feet, holds 10 pairs, compact."),
    ("Medicine Ball Set 3",                   "Sports",       54.99,  28, 4.5,
     "6/8/10 lb, textured grip, durable rubber, bounce resistant."),
    ("Swimming Goggles Anti-Fog",             "Sports",       18.99,  62, 4.4,
     "UV protection, 3 nose bridges, mirrored lenses, leak proof."),
    ("Golf Putting Mat 9ft",                  "Sports",       49.99,  22, 4.3,
     "Auto ball return, wood grain look, 2 hole sizes, foldable."),
    # Batch 7 - More Home (20+ items)
    ("Throw Pillow Covers Set 4",             "Home",         24.99,  65, 4.5,
     "18x18in, velvet, invisible zipper, modern geometric patterns."),
    ("Blackout Curtains 84in",                "Home",         59.99,  35, 4.6,
     "2 panels, thermal insulated, noise reducing, 8 grommets."),
    ("Area Rug 5x7ft",                        "Home",         129.99, 20, 4.4,
     "Soft shag, non-slip backing, stain resistant, easy clean."),
    ("Wall Shelves Floating Set 3",           "Home",         39.99,  48, 4.5,
     "Rustic wood, metal brackets, 16in each, holds 40lb per shelf."),
    ("Storage Ottoman Bench",                 "Home",         89.99,  25, 4.6,
     "30in, hinged lid, fabric, holds 300lb, tufted top."),
    ("Closet Organizer System",                 "Home",         79.99,  30, 4.4,
     "8 shelves, 3 rods, expandable 48-84in, all hardware included."),
    ("Bedside Table Lamp 2pc",                "Home",         44.99,  42, 4.5,
     "Touch control, 3 brightness, USB charging port, fabric shade."),
    ("Shower Curtain Liner",                  "Home",         14.99,  75, 4.3,
     "72x72in, mildew resistant, 12 hooks, weighted hem, clear."),
    ("Bath Towel Set 6pc",                    "Home",         54.99,  38, 4.6,
     "100% cotton, 600 GSM, 2 bath, 2 hand, 2 wash, quick dry."),
    ("Mirror Full Length",                    "Home",         69.99,  28, 4.5,
     "65x22in, wall/door mount, aluminum frame, shatterproof."),
    ("Laundry Hamper 2-Section",              "Home",         34.99,  45, 4.4,
     "Sorter basket, 132L total, removable bags, breathable mesh."),
    ("Door Draft Stopper 2pk",                "Home",         16.99,  58, 4.3,
     "36in, double sided, sound blocker, under door seal, washable."),
    ("Toilet Brush Set 2pc",                  "Home",         19.99,  52, 4.5,
     "Stainless steel holder, silicone bristles, ventilated, floor stand."),
    ("Soap Dispenser 3pc Set",                "Home",         24.99,  40, 4.4,
     "Glass bottles, stainless pumps, 16oz, labels included."),
    ("Picture Frame Collage 10pc",            "Home",         39.99,  35, 4.5,
     "4x6in, black wood, wall hanging template, assorted layouts."),
    ("Coasters Set 8",                        "Home",         15.99,  68, 4.4,
     "Marble pattern ceramic, cork backing, gold rim, holder included."),
    ("Essential Oil Set 10",                  "Home",         29.99,  48, 4.6,
     "100% pure, lavender, eucalyptus, peppermint, 10ml each."),
    ("Candle Set Scented 4pc",                "Home",         34.99,  42, 4.5,
     "Soy wax, cotton wick, 50hr burn each, jar candles."),
    ("Trash Can Step 13gal",                  "Home",         49.99,  32, 4.6,
     "Stainless steel, soft close lid, odor control, fingerprint proof."),
    # Batch 8 - Additional 50 products for 30-50 results per category
    ("Smart Lock Deadbolt",                   "Home",        199.99,  22, 4.5,
     "Keyless entry, fingerprint, app control, auto-lock, door sensor."),
    ("Window AC Unit 8000 BTU",               "Home",        299.99,  15, 4.4,
     "Cools 350 sq ft, remote control, 3 speeds, energy saver mode."),
    ("Humidifier Cool Mist 6L",               "Home",         59.99,  38, 4.5,
     "Top fill, 60hr runtime, essential oil tray, night light, quiet."),
    ("Dehumidifier 22 Pint",                  "Home",        179.99,  20, 4.3,
     "1500 sq ft coverage, auto defrost, continuous drain option."),
    ("Space Heater 1500W",                    "Home",         79.99,  45, 4.4,
     "Ceramic, oscillating, thermostat, tip-over protection, remote."),
    ("Air Quality Monitor",                   "Home",         89.99,  28, 4.2,
     "PM2.5, CO2, VOC, temp, humidity tracking, app alerts, WiFi."),
    ("Water Filter Pitcher",                  "Kitchen",      34.99,  55, 4.6,
     "10 cup, 5-stage filtration, BPA-free, 2 filters included."),
    ("Ice Maker Countertop",                  "Kitchen",     149.99,  25, 4.5,
     "26lbs/day, 9 cubes in 6min, self-cleaning, bullet shape ice."),
    ("Wine Fridge 12 Bottle",                 "Kitchen",     179.99,  18, 4.4,
     "Dual zone, 46-66°F, thermoelectric cooling, UV protection."),
    ("Dish Rack Large",                       "Kitchen",      39.99,  42, 4.5,
     "2-tier, drainboard, utensil holder, rustproof, extendable."),
    ("Pot and Pan Organizer",                 "Kitchen",      29.99,  48, 4.4,
     "5 slots, adjustable, cabinet storage, lid holder, chrome."),
    ("Canisters Set 4pc",                     "Kitchen",      32.99,  52, 4.6,
     "Airtight, bamboo lid, stainless steel, labels included."),
    ("Paper Towel Holder",                    "Kitchen",      16.99,  65, 4.3,
     "Wall mount, under cabinet, one-handed tear, stainless steel."),
    ("Nespresso Machine",                     "Kitchen",     129.99,  30, 4.7,
     "Original line, 19 bar pressure, fast heat, energy saving."),
    ("Waffle Maker Belgian",                  "Kitchen",      49.99,  38, 4.5,
     "Deep pockets, non-stick, indicator lights, overflow channel."),
    ("Slow Cooker 6qt",                        "Kitchen",      59.99,  45, 4.6,
     "Programmable, digital timer, warm setting, stoneware pot."),
    ("Immersion Blender 500W",                "Kitchen",      34.99,  58, 4.4,
     "Variable speed, whisk attachment, chopper bowl, BPA-free."),
    ("Kitchen Scale Digital",                 "Kitchen",      19.99,  72, 4.7,
     "11lb capacity, 1g precision, LCD, tare function, batteries included."),
    ("Thermos Food Jar",                      "Kitchen",      24.99,  48, 4.5,
     "16oz, vacuum insulated, keeps food hot 7hr or cold 9hr."),
    ("Laptop Stand Adjustable",               "Electronics",  49.99,  55, 4.6,
     "Aluminum, 8 angles, ergonomic, 10-17in compatible, portable."),
    ("Webcam 1080p Ring Light",               "Electronics",  59.99,  42, 4.5,
     "Autofocus, dual mic, 3 color temps, privacy cover, tripod."),
    ("USB Docking Station",                   "Electronics", 129.99,  28, 4.4,
     "12-in-1, triple display, 4K HDMI, Ethernet, 100W PD charging."),
    ("Power Strip Tower",                     "Electronics",  39.99,  48, 4.5,
     "10 outlets + 4 USB, surge protection, 6ft cord, vertical."),
    ("Bluetooth Keyboard",                    "Electronics",  34.99,  62, 4.6,
     "Multi-device, 3 channels, slim, rechargeable, quiet keys."),
    ("Mouse Pad Extended",                    "Electronics",  19.99,  75, 4.4,
     "31.5x11.8in, RGB lighting, waterproof, stitched edges, rubber base."),
    ("Phone Stand Desktop",                   "Electronics",  12.99,  88, 4.5,
     "Adjustable angle, anti-slip, foldable, compatible with all phones."),
    ("Screen Cleaner Kit",                    "Electronics",  14.99,  65, 4.3,
     "200ml spray + microfiber cloth, streak-free, all screens safe."),
    ("Cable Organizer Box 3pc",               "Electronics",  22.99,  52, 4.4,
     "Hide power strips, cords, remote control, flame retardant."),
    ("Surge Protector Wall",                  "Electronics",  18.99,  70, 4.5,
     "6 outlets + 2 USB, 1080J, wall mountable, space saving."),
    ("Earphones Wired",                       "Electronics",  15.99,  95, 4.4,
     "3.5mm, in-ear, bass boost, microphone, noise isolating, tangle-free."),
    ("Fitness Tracker Watch",                 "Fitness",       49.99,  55, 4.5,
     "Heart rate, sleep monitor, 14 sports modes, 7-day battery, water resistant."),
    ("Resistance Bands Door Anchor",          "Fitness",       19.99,  68, 4.4,
     "Heavy duty, foam padding, fits all bands, secure, portable."),
    ("Foam Roller Grid",                      "Fitness",       34.99,  42, 4.6,
     "13in, multi-density, trigger point therapy, hollow core."),
    ("Protein Shaker Bottle",                 "Fitness",       12.99,  82, 4.5,
     "24oz, blender ball, leak-proof, measurement scale, BPA-free."),
    ("Yoga Strap Set 2",                      "Fitness",       14.99,  58, 4.4,
     "8ft cotton, D-ring buckle, stretch assist, 2 pack."),
    ("Gym Bag Large",                         "Fitness",       39.99,  48, 4.5,
     "40L capacity, shoe compartment, wet pocket, water resistant."),
    ("Exercise Ball 65cm",                    "Fitness",       22.99,  65, 4.5,
     "Anti-burst, pump included, 2200lb rating, office or gym use."),
    ("Pull Up Assist Band",                   "Fitness",       16.99,  72, 4.3,
     "Resistance 30-60lb, 41in loop, latex, powerlifting, stretching."),
    ("Ankle Weights Set 2",                   "Fitness",       24.99,  45, 4.4,
     "2.5lb each, adjustable strap, neoprene, walking, running, rehab."),
    ("Sports Headband 6pc",                   "Sports",        14.99,  68, 4.5,
     "Moisture-wicking, elastic, non-slip, athletic, unisex."),
    ("Golf Balls 12 Pack",                    "Sports",        24.99,  52, 4.6,
     "Distance, 2-piece construction, durable cover, consistent flight."),
    ("Bike Helmet Adult",                     "Sports",        39.99,  38, 4.5,
     "CPSC certified, adjustable dial, 18 vents, removable padding."),
    ("Tennis Balls 12 Can",                   "Sports",        19.99,  62, 4.4,
     "Pressureless, durable felt, consistent bounce, practice or match."),
    ("Hiking Boots Waterproof",               "Outdoor",       89.99,  32, 4.5,
     "Leather upper, rubber sole, ankle support, 6in height, rugged."),
    ("Camping Lantern LED",                   "Outdoor",       24.99,  48, 4.6,
     "1000 lumens, 4 modes, 12hr runtime, water resistant, collapsible."),
    ("Sleeping Bag Mummy",                    "Outdoor",       59.99,  28, 4.4,
     "0°F rating, synthetic fill, compression sack, 3 season."),
    ("Portable Grill Tabletop",               "Outdoor",       49.99,  35, 4.5,
     "Propane, 10,000 BTU, 189 sq in, porcelain grates, briefcase style."),
    ("Trekking Poles Pair",                   "Outdoor",       34.99,  42, 4.6,
     "Carbon fiber, cork grip, flip lock, shock absorbing, collapsible."),
    ("Beach Tent Shelter",                    "Outdoor",       44.99,  25, 4.3,
     "4 person, UPF 50+, sand pockets, 2 windows, instant setup."),
    ("Fishing Rod and Reel",                  "Outdoor",       69.99,  22, 4.4,
     "6.5ft medium action, spinning reel, 5.2:1 ratio, line included."),
    ("Car Vacuum Cleaner",                    "Automotive",    39.99,  45, 4.5,
     "12V, handheld, HEPA filter, LED light, 16ft cord, 4500Pa."),
    ("Dash Cam Front and Rear",               "Automotive",    89.99,  28, 4.4,
     "1080p both cameras, G-sensor, loop recording, night vision, 32GB."),
    ("Tire Inflator Portable",               "Automotive",    49.99,  38, 4.6,
     "150PSI, digital gauge, auto shutoff, LED light, 10ft cord."),
    ("Car Cover All Weather",                 "Automotive",    59.99,  32, 4.5,
     "6 layers, waterproof, UV protection, sedan up to 200in, lock included."),
    ("Seat Cushion Memory Foam",              "Automotive",    29.99,  52, 4.7,
     "Coccyx relief, non-slip bottom, washable cover, universal fit."),
    ("Bluetooth FM Transmitter",              "Automotive",    19.99,  68, 4.4,
     "QC 3.0 charging, hands-free calling, 2 USB ports, voice navigation."),
    ("Phone Mount Dashboard",                 "Automotive",    14.99,  75, 4.5,
     "Gravity linkage, one-hand operation, 360° rotation, washable suction."),
]


CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id          SERIAL PRIMARY KEY,
    name        TEXT           NOT NULL,
    category    TEXT           NOT NULL,
    price       NUMERIC(10,2)  NOT NULL,
    stock       INTEGER        NOT NULL DEFAULT 0,
    rating      NUMERIC(3,1),
    description TEXT,
    created_at  TIMESTAMPTZ    DEFAULT NOW()
);
"""

CREATE_INDEXES_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_category ON {TABLE_NAME}(category);
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_price    ON {TABLE_NAME}(price);
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_rating   ON {TABLE_NAME}(rating);
"""

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    email       TEXT           UNIQUE NOT NULL,
    password_hash TEXT         NOT NULL,
    name        TEXT,
    created_at  TIMESTAMPTZ    DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""


def init_db() -> bool:
    """
    Create table + indexes and seed data if table is empty.
    Returns True on success, False on failure.
    """
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Try enabling pgvector (available on AlloyDB)
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
            except Exception:
                conn.rollback()
                log.info("pgvector not available (OK for local dev)")

            cur.execute(CREATE_TABLE_SQL)
            for stmt in CREATE_INDEXES_SQL.strip().split("\n"):
                if stmt.strip():
                    cur.execute(stmt)
            
            # Create users table for authentication
            cur.execute(CREATE_USERS_TABLE_SQL)

            cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME};")
            count = cur.fetchone()[0]
            if count == 0:
                cur.executemany(
                    f"""INSERT INTO {TABLE_NAME}
                        (name, category, price, stock, rating, description)
                        VALUES (%s,%s,%s,%s,%s,%s)""",
                    SEED_PRODUCTS,
                )
                log.info(f"Seeded {len(SEED_PRODUCTS)} products into {TABLE_NAME}")
            else:
                log.info(f"Table {TABLE_NAME} already has {count} rows")

        conn.commit()
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        log.error(f"init_db failed: {exc}")
        return False
    finally:
        if conn:
            put_conn(conn)


# ── Query execution ────────────────────────────────────────────────────────

def _serialize(val):
    """Make a value JSON-safe."""
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return val


def execute_query(sql: str, params=None) -> dict:
    """
    Execute a SQL SELECT and return:
      { columns, rows, count, error }
    All values are JSON-serialisable.
    """
    conn = None
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            raw = cur.fetchall()
            rows = [{k: _serialize(v) for k, v in row.items()} for row in raw]
            return {
                "columns": list(rows[0].keys()) if rows else [],
                "rows":    rows,
                "count":   len(rows),
                "error":   None,
            }
    except Exception as exc:
        if conn:
            conn.rollback()
        log.error(f"execute_query error: {exc}\nSQL: {sql}")
        return {"columns": [], "rows": [], "count": 0, "error": str(exc)}
    finally:
        if conn:
            put_conn(conn)


def get_table_stats() -> dict:
    """Return summary stats for the dashboard."""
    result = execute_query(f"""
        SELECT
            COUNT(*)                          AS total_products,
            COUNT(DISTINCT category)          AS total_categories,
            ROUND(AVG(price)::numeric, 2)     AS avg_price,
            MIN(price)                        AS min_price,
            MAX(price)                        AS max_price,
            ROUND(AVG(rating)::numeric, 2)    AS avg_rating,
            MAX(rating)                       AS max_rating,
            SUM(stock)                        AS total_stock
        FROM {TABLE_NAME};
    """)
    return result["rows"][0] if result["rows"] else {}


def get_all_rows() -> dict:
    return execute_query(
        f"SELECT id, name, category, price, stock, rating, description "
        f"FROM {TABLE_NAME} ORDER BY id;"
    )


def get_schema_text() -> str:
    return f"""Table name: {TABLE_NAME}

Columns:
  id          INTEGER        – auto-increment primary key
  name        TEXT           – product name (e.g. "Wireless Headphones")
  category    TEXT           – one of: Electronics, Kitchen, Sports, Furniture, Home
  price       NUMERIC(10,2)  – price in USD (e.g. 49.99)
  stock       INTEGER        – units currently in stock
  rating      NUMERIC(3,1)   – customer rating from 0.0 to 5.0
  description TEXT           – short product description
  created_at  TIMESTAMPTZ    – row creation timestamp

Sample values:
  categories : Electronics, Kitchen, Sports, Furniture, Home
  price range: $19.99 – $329.00
  stock range: 12 – 150 units
  rating range: 4.2 – 4.9

Total rows: ~20 products"""