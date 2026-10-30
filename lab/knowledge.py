"""What the director knows: topics, moods, things that can be drawn, and how to spot numbers and script structure.

Everything here is plain data (regular expressions and tables), so adding a topic, a prop or an environment is a
one-line change.
"""
import re

R = lambda p: re.compile(p, re.I)

# ------------------------------------------------------------------ topics
TOPICS = {
    "space": R(r"\b(space|planets?|stars?|galax\w+|universe|orbit\w*|solar system|the sun|moon|astronaut\w*|rockets?|nasa|comets?|asteroids?|black holes?|light.?years?|cosmic|cosmos|mars|jupiter|saturn|venus|mercury|neptune|uranus|milky way|meteor\w*|supernova\w*|big bang|telescope\w*|aliens?|extraterrestrial|exoplanets?|nebula\w*|spacecraft|spaceship|satellites?|zero gravity|interstellar)\b"),
    "earth": R(r"\b(earth|crust|mantle|core|atmosphere|ozone|climate|continents?|tectonic\w*|planet earth|globe|equator|poles?|magnetic field|layers? of the earth|gravity)\b"),
    "ocean": R(r"\b(ocean\w*|sea|seas|waves?|tsunami\w*|deep sea|marine|whales?|sharks?|fish|coral|reef|submarine|dive[rs]?|diving|underwater|tides?|current\w*|jellyfish|octopus|squid|abyss|trench|titanic)\b"),
    "weather": R(r"\b(weather|storms?|hurricanes?|tornado\w*|thunder\w*|lightning|rain\w*|clouds?|wind\w*|flood\w*|drought|monsoon|blizzard\w*|forecast|humidity|cyclones?|hail)\b"),
    "volcano": R(r"\b(volcan\w+|lava|magma|eruption\w*|erupt\w*|earthquake\w*|seismic|fault lines?|ash|geyser\w*|yellowstone|supervolcano\w*|tectonic plates?)\b"),
    "ice": R(r"\b(ice|icy|glaciers?|arctic|antarctic\w*|polar|snow\w*|frozen|freez\w+|frost\w*|iceberg\w*|cold|permafrost|tundra|winter)\b"),
    "desert": R(r"\b(deserts?|sahara|sand\w*|dunes?|dry|arid|oasis|scorching|heat ?wave|sun.?baked|camels?|mirage)\b"),
    "nature": R(r"\b(forests?|jungles?|trees?|plants?|animals?|birds?|insects?|ants?|bees?|dinosaurs?|evolution|species|wildlife|predators?|prey|mammals?|reptiles?|elephants?|lions?|wolves|wolf|bears?|rainforest\w*|photosynthesis|ecosystems?|extinct\w*|fossils?|spiders?|snakes?|horses?|dogs?|cats?)\b"),
    "body": R(r"\b(human body|bod(y|ies)|blood|hearts?|bones?|organs?|skin|muscles?|lungs?|stomach|sleep\w*|diseases?|immune|vaccines?|medicine|doctors?|hospital|cancer|oxygen|breath\w*|digest\w*|hormones?|kidneys?|liver|infection\w*|symptoms?|pain|calories|vitamins?|fever|surgery|teeth|tongue|hair|aging|ageing)\b"),
    "brain": R(r"\b(brains?|neurons?|memor(y|ies)|minds?|thoughts?|dream\w*|conscious\w*|psycholog\w*|emotions?|intelligence|iq|think\w*|focus|attention|neural|synapses?|senses?|perception|illusions?|habits?|learn\w*|curiosity|fear)\b"),
    "micro": R(r"\b(cells?|bacteria\w*|virus\w*|dna|genes?|genetic\w*|molecules?|microb\w*|microscop\w*|protein\w*|tiny|nano\w*|organisms?|germs?|parasites?|enzymes?|chromosomes?|rna|plankton|fungus|fungi|mutations?|embryo\w*)\b"),
    "physics": R(r"\b(atoms?|atomic|energy|light|speed of light|quantum|particles?|forces?|electric\w*|magnet\w*|sound|radiation|nuclear|fusion|fission|physics|relativity|einstein|photons?|electrons?|protons?|neutrons?|wavelengths?|temperature|degrees|matter|antimatter|mass|velocity|friction|pressure|vacuum|chemical|chemistry|element\w*|reaction\w*|acids?|oxygen|hydrogen|carbon|gold|metal\w*|liquid|gas\w*|plasma|time dilation|speed)\b"),
    "tech": R(r"\b(computers?|internet|ai|artificial intelligence|robots?|phones?|smartphones?|data|code|coding|machines?|batter(y|ies)|chips?|processors?|software|algorithms?|networks?|wifi|electronics?|drones?|screens?|digital|online|website|social media|technology|engines?|3d print\w*|hackers?|passwords?|servers?)\b"),
    "city": R(r"\b(cit(y|ies)|building\w*|skyscrapers?|people|humans?|humanity|population|society|civili[sz]ation\w*|government\w*|econom\w+|money|dollars?|rich|poor|countr(y|ies)|nations?|crowds?|billion people|traffic|roads?|bridges?|streets?|workers?|jobs?|school|children|kids|families|world|everyone)\b"),
    "history": R(r"\b(history|historic\w*|ancient|empire\w*|kings?|queens?|pharaohs?|pyramids?|romans?|egypt\w*|greeks?|medieval|centur(y|ies)|ago|war\w*|battles?|revolution\w*|invent\w*|discover\w*|first ever|archaeolog\w*|civilizations?|dynasty|renaissance|ancestors?|prehistoric|stone age|bronze age|19\d\d|18\d\d|17\d\d|20[0-2]\d)\b"),
    "disaster": R(r"\b(apocalypse|extinction|destroy\w*|explo(de|des|ded|sion\w*)|collapse\w*|catastroph\w*|disaster\w*|bombs?|impact|crash\w*|doomsday|end of the world|wipe\w? out|mass death|die|dies|died|dead|death|kill\w*|deadly|lethal|survive\w*|survival|danger\w*|threat\w*|toxic|poison\w*|radioactive|meltdown|wildfire\w*|burn\w*)\b"),
    "food": R(r"\b(food|eat\w*|ate|hungry|hunger|sugar|coffee|diet|water|drinks?|drink\w*|pizza|bread|meat|fruits?|vegetables?|milk|chocolate|salt|fat|protein|restaurants?|cook\w*|kitchen|calories|alcohol|caffeine|tea|rice|candy|burgers?)\b"),
}

# a word or two that says "this is about people in a situation" -> infographic-style characters
PEOPLE = R(r"\b(you|your|imagine|suppose|what if|what would|a person|someone|somebody|a man|a woman|a boy|a girl|people|humans?|we|us|he|she|they|his|her|their|worker|passenger|driver|pilot|student|child|kid|jump\w*|walk\w*|stand\w*|run\w*|wak\w+|live\w*)\b")
BLOCKY = R(r"\b(minecraft|blocks?|blocky|pixel\w*|voxel\w*|build\w*|cubes?|lego|game|gaming|8.?bit|crafting)\b")

TOPIC_STYLE = {   # preference weights: (flat, voxel, toon)
    "space": (3.0, 1.6, 0.8), "earth": (3.0, 1.6, 1.0), "ocean": (2.6, 1.7, 1.2), "weather": (2.2, 1.6, 1.5), "volcano": (2.2, 2.2, 1.0),
    "ice": (2.2, 1.7, 1.4), "desert": (1.6, 2.2, 1.5), "nature": (2.2, 1.7, 1.5), "body": (3.2, 0.4, 1.5), "brain": (3.2, 0.3, 1.5),
    "micro": (3.6, 0.6, 0.5), "physics": (3.2, 0.9, 1.0), "tech": (2.2, 1.6, 1.6), "city": (1.2, 1.8, 3.0), "history": (1.5, 1.9, 2.6),
    "disaster": (2.2, 2.2, 1.5), "food": (1.6, 1.3, 3.0), "generic": (2.2, 1.2, 2.0),
}

# ------------------------------------------------------------------ environments (ids live in flat.py / voxel.py / toon.py)
ENVS = {
    "space": {"flat": ["deep_space", "nebula", "solar", "orbit"], "voxel": ["space"], "toon": ["space", "stage"]},
    "earth": {"flat": ["orbit", "strata", "day_sky"], "voxel": ["plains", "islands"], "toon": ["hills", "beach"]},
    "ocean": {"flat": ["ocean_deep", "ocean_surface"], "voxel": ["ocean", "underwater"], "toon": ["underwater", "beach"]},
    "weather": {"flat": ["storm", "day_sky"], "voxel": ["plains", "islands"], "toon": ["hills", "street"]},
    "volcano": {"flat": ["ember", "strata"], "voxel": ["volcano", "cave"], "toon": ["desert", "cave"]},
    "ice": {"flat": ["arctic"], "voxel": ["snow"], "toon": ["snow"]},
    "desert": {"flat": ["dusk_desert"], "voxel": ["desert"], "toon": ["desert"]},
    "nature": {"flat": ["forest", "day_sky"], "voxel": ["plains", "islands"], "toon": ["forest", "hills"]},
    "body": {"flat": ["micro", "lab"], "voxel": ["cave"], "toon": ["room", "lab"]},
    "brain": {"flat": ["neural", "micro"], "voxel": ["cave"], "toon": ["room", "stage"]},
    "micro": {"flat": ["micro", "lab"], "voxel": ["cave", "underwater"], "toon": ["lab", "stage"]},
    "physics": {"flat": ["lab", "tunnel", "deep_space"], "voxel": ["space", "cave"], "toon": ["lab", "stage"]},
    "tech": {"flat": ["data", "night_city", "lab"], "voxel": ["city"], "toon": ["room", "rooftop"]},
    "city": {"flat": ["night_city", "day_sky"], "voxel": ["city", "plains"], "toon": ["street", "rooftop"]},
    "history": {"flat": ["tunnel", "dusk_desert", "day_sky"], "voxel": ["desert", "plains"], "toon": ["desert", "street", "stage"]},
    "disaster": {"flat": ["ember", "storm", "deep_space"], "voxel": ["volcano", "space"], "toon": ["street", "desert"]},
    "food": {"flat": ["day_sky", "lab"], "voxel": ["plains"], "toon": ["room", "street"]},
    "generic": {"flat": ["lab", "day_sky", "tunnel"], "voxel": ["plains"], "toon": ["stage", "hills", "street"]},
}
ENV_STYLE = {}          # env id -> style, filled from ENVS
for _t, _d in ENVS.items():
    for _s, _lst in _d.items():
        for _e in _lst:
            ENV_STYLE.setdefault(_e, set()).add(_s)
ALL_ENVS = {"flat": ["deep_space", "nebula", "solar", "orbit", "ocean_deep", "ocean_surface", "strata", "ember", "arctic", "dusk_desert", "storm",
                      "micro", "neural", "lab", "night_city", "data", "tunnel", "day_sky", "forest"],
            "voxel": ["plains", "desert", "snow", "ocean", "volcano", "city", "cave", "space", "underwater", "islands"],
            "toon": ["street", "room", "hills", "beach", "space", "desert", "snow", "stage", "underwater", "rooftop", "cave", "lab", "forest"]}
STYLE_NAMES = {"flat": "Flat explainer", "voxel": "Blocky 3D world", "toon": "Simple characters"}

# time of day / palette flavours per topic
PALETTES = {
    "space": ["cosmos", "nebula", "neon"], "earth": ["cosmos", "day", "dusk"], "ocean": ["ocean", "deep"], "weather": ["storm", "day"],
    "volcano": ["ember", "dusk"], "ice": ["ice"], "desert": ["dusk", "day"], "nature": ["forest", "day"], "body": ["bio", "lab"],
    "brain": ["bio", "neon", "lab"], "micro": ["bio", "lab"], "physics": ["lab", "neon", "cosmos"], "tech": ["neon", "lab"],
    "city": ["dusk", "day", "neon"], "history": ["dusk", "day"], "disaster": ["ember", "storm"], "food": ["day", "dusk"], "generic": ["lab", "day", "dusk"],
}

# ------------------------------------------------------------------ moods
MOODS = {
    "wonder": R(r"\b(amazing|incredible|beautiful|vast|huge|enormous|massive|stunning|mind.?blowing|wonder\w*|magnificent|infinite|endless|billions?|trillions?|biggest|largest|universe|breathtaking|gigantic|astonishing|fascinating|remarkable)\b"),
    "danger": R(r"\b(danger\w*|deadly|kill\w*|die[sd]?|death|destroy\w*|explo\w+|crash\w*|collapse\w*|burn\w*|disaster|toxic|lethal|catastroph\w*|extinct\w*|doom|threat\w*|crush\w*|melt\w*|scorch\w*|survive\w*|fatal|panic|terrifying|horrif\w+)\b"),
    "funny": R(r"\b(funny|weird|strange|bizarre|silly|ridiculous|absurd|hilarious|odd|awkward|bonkers|ironic\w*|joke\w*|lol)\b"),
    "calm": R(r"\b(slowly|quiet\w*|gentle|gently|peaceful\w*|calm\w*|float\w*|drift\w*|sleep\w*|relax\w*|serene|soft\w*)\b"),
    "shock": R(r"\b(suddenly|instantly|in seconds|in an instant|shock\w*|wait|unexpected\w*|surprising\w*|boom|bang|flash|snap)\b"),
    "curious": R(r"\b(why|how|what if|imagine|wonder|mystery|mysterious|secret|unknown|nobody knows|question|strange|puzzle)\b"),
}
MOOD_VOICE = {"wonder": "excited", "danger": "worried", "funny": "happy", "calm": "neutral", "shock": "shocked", "curious": "curious", "neutral": "neutral"}

# ------------------------------------------------------------------ structure detectors
HYPO = R(r"\b(what if|what would happen|imagine|suppose|let.s say|if you|if we|if the|if a|if an|if every|what happens (if|when))\b")
COMPARE = R(r"\b(versus|vs\.?|compared (to|with)|difference between|than|bigger than|smaller than|faster than|hotter than|colder than|heavier than|more than|less than|as (big|large|small|fast|hot|cold|heavy) as)\b")
SCALE = R(r"\b(\w+ times (bigger|larger|smaller|faster|heavier|hotter|colder|longer|taller|older|more|stronger)|bigger|larger|smaller|taller|tallest|biggest|largest|smallest|heaviest|the size of|size|diameter|width|wide|long|tall|high|deep|distance|far|away|huge|tiny)\b")
PROCESS = R(r"\b(first|then|next|after that|finally|step|stage|begins?|starts?|becomes?|turns? into|leads? to|causes?|results? in|process|cycle|which then)\b")
LISTY = R(r"\b(number (one|two|three|four|five|\d+)|top (\d+|three|five|ten)|reasons?|ways?|things|facts?|first,? second)\b")
TIMEY = R(r"\b(in (the year )?\d{3,4}|\d+ (million |billion |thousand )?years? (ago|later|from now)|century|centuries|decade|era|timeline|eons?)\b")
HOOK = R(r"^(what if|imagine|did you know|have you ever|why|how|what|where|when|who|can|could|would|is|are|do|does)\b.*\?$")
UNIT_WORDS = {
    "degrees": "°", "degree": "°", "celsius": "°C", "fahrenheit": "°F", "percent": "%", "%": "%", "kilometers": " km", "kilometres": " km", "km": " km",
    "miles": " miles", "mile": " mile", "meters": " m", "metres": " m", "feet": " ft", "years": " years", "year": " year", "times": "×",
    "tons": " tons", "tonnes": " tonnes", "kg": " kg", "kilograms": " kg", "seconds": " s", "minutes": " min", "hours": " hours", "days": " days",
    "people": " people", "stars": " stars", "light-years": " light-years", "light years": " light-years", "dollars": " $", "degrees celsius": "°C",
}
NUM = re.compile(r"(?<![\w.])(\$?\d{1,3}(?:,\d{3})+|\$?\d+(?:\.\d+)?)\s*(trillion|billion|million|thousand)?\s*(degrees celsius|degrees fahrenheit|degrees|°\s?[CF]|percent|%|kilometers|kilometres|km|miles?|meters|metres|feet|years?|times|tons|tonnes|kg|kilograms|seconds|minutes|hours|days|people|stars|light.?years?|dollars)?(?![\w])", re.I)


def topic_scores(text):
    sc = {}
    for t, rx in TOPICS.items():
        hits = rx.findall(text)
        if hits:
            sc[t] = min(len(hits), 5) + 0.5 * len({h[0] if isinstance(h, tuple) else h for h in hits})
    return sc


def topic_of(text):
    sc = topic_scores(text)
    if not sc:
        return None
    return max(sc.items(), key=lambda kv: kv[1])[0]


def mood_of(text):
    best, bs = "neutral", 0
    for m, rx in MOODS.items():
        n = len(rx.findall(text))
        if n > bs:
            best, bs = m, n
    return best


def numbers(text):
    """-> [{value: float, display: str, unit: str, pos: int, kind: 'count'|'percent'|'year'|'temp'|...}]"""
    out = []
    for m in NUM.finditer(text):
        raw, mult, unit = m.group(1), (m.group(2) or "").lower(), (m.group(3) or "")
        cleaned = raw.replace(",", "").replace("$", "")
        try:
            val = float(cleaned)
        except ValueError:
            continue
        ul = re.sub(r"\s+", " ", unit.lower()).strip()
        is_year = (not mult and not ul and re.fullmatch(r"\d{4}", cleaned) and 1000 <= val <= 2200) or False
        if val < 10 and not mult and not ul and not is_year:
            continue                                  # "3 of them" is not a statistic
        if val < 2 and not is_year and not mult:
            continue
        kind = "year" if is_year else ("percent" if ul in ("percent", "%") else ("temp" if ul.startswith(("degrees", "°")) else "count"))
        scale = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}.get(mult, 1)
        shown_unit = UNIT_WORDS.get(ul, (" " + ul) if ul else "")
        if raw.startswith("$"):
            shown_unit, pre = "", "$"
        else:
            pre = ""
        disp_num = raw.replace("$", "")
        suffix = {"thousand": "K", "million": " million", "billion": " billion", "trillion": " trillion"}.get(mult, "")
        out.append(dict(value=val * scale, base=val, mult=scale, display=f"{pre}{disp_num}{suffix}{shown_unit}".strip(), unit=ul, pos=m.start(),
                        kind=kind, big=val * scale >= 1e6))
    return out[:3]


# ------------------------------------------------------------------ things that can be drawn (flat entities; voxel props have their own table)
ENTITIES = [   # (name, regex, label)
    ("blackhole", R(r"\bblack holes?\b"), "Black hole"),
    ("galaxy", R(r"\b(galax\w+|milky way)\b"), "Galaxy"),
    ("sun", R(r"\b(the sun|sun|solar|sunlight|sunshine|star like our)\b"), "Sun"),
    ("moon", R(r"\b(the moon|moon|lunar)\b"), "Moon"),
    ("earth_layers", R(r"\b(layers? of the earth|inner core|outer core|the mantle|earth.s core|the crust|center of the earth)\b"), "Earth's layers"),
    ("earth", R(r"\b(earth|our planet|the globe)\b"), "Earth"),
    ("ringed", R(r"\b(saturn|rings?)\b"), "Saturn"),
    ("planet", R(r"\b(planets?|mars|jupiter|venus|mercury|neptune|uranus|exoplanets?)\b"), "Planet"),
    ("asteroid", R(r"\b(asteroids?|meteors?|meteorite\w*|space rocks?|impactor)\b"), "Asteroid"),
    ("comet", R(r"\bcomets?\b"), "Comet"),
    ("rocket", R(r"\b(rockets?|spacecraft|spaceship|launch\w*|shuttle|capsule)\b"), "Rocket"),
    ("satellite", R(r"\b(satellites?|space station|iss)\b"), "Satellite"),
    ("ufo", R(r"\b(ufos?|aliens?|flying saucers?|extraterrestrial\w*)\b"), "Aliens"),
    ("volcano", R(r"\b(volcan\w+|lava|magma|eruption\w*|erupt\w*)\b"), "Volcano"),
    ("mountain", R(r"\b(mountains?|peaks?|everest|cliffs?|hills?)\b"), "Mountain"),
    ("tree", R(r"\b(trees?|forests?|plants?|leaf|leaves|jungle|rainforest)\b"), "Trees"),
    ("cloud", R(r"\b(clouds?|sky|atmosphere)\b"), "Clouds"),
    ("bolt", R(r"\b(lightning|thunder\w*|electric\w*|zap\w*|volts?|voltage|shock)\b"), "Lightning"),
    ("rain", R(r"\b(rain\w*|storm\w*|flood\w*|drops?)\b"), "Rain"),
    ("wave", R(r"\b(ocean\w*|sea|waves?|tsunami\w*|water|tides?|seawater)\b"), "Ocean"),
    ("whale", R(r"\b(whales?|dolphins?)\b"), "Whale"),
    ("shark", R(r"\bsharks?\b"), "Shark"),
    ("fish", R(r"\b(fish|fishes|salmon|tuna|coral|reef)\b"), "Fish"),
    ("jellyfish", R(r"\b(jellyfish|squid|octopus)\b"), "Jellyfish"),
    ("cell", R(r"\b(cells?|bacteria\w*|microb\w*|organisms?|germs?|plankton)\b"), "Cell"),
    ("virus", R(r"\b(virus\w*|infection\w*|pathogens?|disease\w*)\b"), "Virus"),
    ("dna", R(r"\b(dna|genes?|genetic\w*|genome|chromosomes?|mutations?)\b"), "DNA"),
    ("atom", R(r"\b(atoms?|atomic|molecules?|electrons?|protons?|particles?|quantum|nuclear|nucleus)\b"), "Atom"),
    ("brain", R(r"\b(brains?|neurons?|mind|thoughts?|memor(y|ies)|conscious\w*|dream\w*)\b"), "Brain"),
    ("heart", R(r"\b(hearts?|blood|pulse|heartbeat|cardio\w*)\b"), "Heart"),
    ("bulb", R(r"\b(ideas?|bulbs?|invent\w*|inventor\w*|light bulbs?|innovation|discover\w*|genius)\b"), "Idea"),
    ("clock", R(r"\b(time|clocks?|years?|centur(y|ies)|ages?|aging|ageing|minutes?|hours?|seconds?|decades?|ancient|eons?)\b"), "Time"),
    ("hourglass", R(r"\b(hourglass|running out|deadline|countdown)\b"), "Time"),
    ("thermo", R(r"\b(temperatures?|degrees|hot|heat\w*|boil\w*|scorch\w*|fever|celsius|fahrenheit|warm\w*)\b"), "Heat"),
    ("snowflake", R(r"\b(snow\w*|ice|icy|frozen|freez\w+|glaciers?|cold|arctic|frost\w*)\b"), "Ice"),
    ("fire", R(r"\b(fires?|flames?|burn\w*|blaze|wildfire\w*|combustion|inferno)\b"), "Fire"),
    ("skyline", R(r"\b(cit(y|ies)|skyscrapers?|buildings?|towers?|downtown|metropolis)\b"), "City"),
    ("house", R(r"\b(houses?|homes?|rooms?|apartment\w*|roof|villages?)\b"), "Home"),
    ("car", R(r"\b(cars?|vehicles?|trucks?|traffic|highway|drive\w*|driving|trains?|buses?)\b"), "Car"),
    ("plane", R(r"\b(planes?|aircraft|airplane\w*|jets?|fly(?:ing)?|flight\w*|airline\w*|pilot\w*)\b"), "Plane"),
    ("monitor", R(r"\b(computers?|internet|screens?|online|software|code|coding|algorithms?|data|websites?|digital|ai|artificial intelligence)\b"), "Computer"),
    ("phone", R(r"\b(phones?|smartphones?|apps?|texts?|social media|messages?)\b"), "Phone"),
    ("robot", R(r"\b(robots?|machines?|automat\w+|androids?|drones?|cyborgs?)\b"), "Robot"),
    ("coin", R(r"\b(money|dollars?|cash|rich|wealth\w*|economy|econom\w+|price|cost\w*|trillions?|billionaires?|gold)\b"), "Money"),
    ("magnet", R(r"\b(magnet\w*|magnetic|poles)\b"), "Magnet"),
    ("battery", R(r"\b(batter(y|ies)|power|energy|electricity|charge|fuel|watts?)\b"), "Energy"),
    ("eye", R(r"\b(eyes?|see|seeing|vision|look\w*|watch\w*|sight|light waves?)\b"), "Vision"),
    ("sound", R(r"\b(sound\w*|noise|loud|echo\w*|vibrat\w*|hear\w*|music|waves? of sound)\b"), "Sound"),
    ("skull", R(r"\b(dead|death|die[sd]?|kill\w*|deadly|lethal|fatal|poison\w*|toxic)\b"), "Danger"),
    ("crowd", R(r"\b(people|humans?|humanity|population|everyone|crowds?|billion people|citizens|society)\b"), "People"),
    ("person", R(r"\b(you|a person|someone|astronaut\w*|a man|a woman|human)\b"), "You"),
    ("explosion", R(r"\b(explo\w+|blast|bomb\w*|bang|boom|impact|crater\w*|detonat\w*|supernova)\b"), "Explosion"),
    ("gear", R(r"\b(engines?|gears?|mechanism|works|working|system|factory|industr\w+)\b"), "Machine"),
    ("water_drop", R(r"\b(drinks?|drinking|thirst\w*|liquid|sweat|tears?|droplets?)\b"), "Water"),
    ("dino", R(r"\b(dinosaurs?|t\.? ?rex|prehistoric|fossils?|extinct\w*|reptiles?)\b"), "Dinosaur"),
    ("pyramid", R(r"\b(pyramids?|egypt\w*|pharaohs?|ancient (ruins|temples?))\b"), "Pyramid"),
    ("scale", R(r"\b(weigh\w*|mass|heavy|heavier|balance|gravity)\b"), "Mass"),
]
ENTITY_LABEL = {n: lab for n, _, lab in ENTITIES}
FLAT_ENTITIES = [n for n, _, _ in ENTITIES]

# who stars in the character style, by topic
ROLES = {
    "space": "astronaut", "earth": "geologist", "ocean": "diver", "weather": "explorer", "volcano": "geologist", "ice": "explorer",
    "desert": "explorer", "nature": "explorer", "body": "scientist", "brain": "scientist", "micro": "scientist", "physics": "scientist",
    "tech": "engineer", "city": "citizen", "history": "citizen", "disaster": "citizen", "food": "citizen", "generic": "citizen",
}

# keyword -> sound effect (names from yuki/sfx.py and lab/sfxlab.py)
SFX_RULES = [
    (R(r"\b(explo\w+|blast|boom|bang|detonat\w*|supernova|big bang)\b"), "explosion"),
    (R(r"\b(crash\w*|collid\w*|collision|smash\w*|impact|slam\w*)\b"), "crash"),
    (R(r"\b(thunder|lightning|bolt|zap\w*)\b"), "thunder"),
    (R(r"\b(rocket\w*|launch\w*|blast off|lift.?off)\b"), "rocket"),
    (R(r"\b(rumbl\w+|earthquake\w*|quake|tremor\w*|eruption|erupt\w*|volcan\w*)\b"), "rumble"),
    (R(r"\b(suddenly|instantly|in an instant|rushes?|zoom\w*|speeds?|race[sd]?|fl(y|ies|ew)|shoot\w*|accelerat\w*)\b"), "whoosh"),
    (R(r"\b(bubbl\w+|underwater|dive[sd]?|dives|splash\w*|submerge\w*|sink\w*)\b"), "bubbles"),
    (R(r"\b(surpris\w+|shock\w*|gasp\w*|unbelievable|wait)\b"), "gasp"),
    (R(r"\b(sparkl\w+|magic\w*|amazing|incredible|beautiful|discover\w*|wonder\w*|bright|glow\w*)\b"), "sparkle"),
    (R(r"\b(idea|aha|realiz\w+|figure[sd]? out|answer|solution|eureka|bulb)\b"), "ding"),
    (R(r"\b(tick\w*|countdown|seconds|clock|timer|running out)\b"), "tick"),
    (R(r"\b(heartbeat|heart (beats|pounds|races)|pulse)\b"), "heartbeat"),
    (R(r"\b(wind\w*|storm\w*|blizzard|freez\w+|cold)\b"), "wind"),
    (R(r"\b(rain\w*|pouring|downpour|flood\w*)\b"), "rain"),
    (R(r"\b(beep\w*|computer\w*|robot\w*|digital|data|signal|code|software|ai)\b"), "beep"),
    (R(r"\b(laugh\w*|funny|silly|hilarious|joke\w*)\b"), "laugh"),
    (R(r"\b(money|dollars?|cash|billions? of dollars|costs?)\b"), "cash"),
    (R(r"\b(boing|bounce\w*|jump\w*|leap\w*|hop\w*)\b"), "boing"),
    (R(r"\b(applaus\w*|cheer\w*|celebrat\w*|win|won|victory)\b"), "applause"),
    (R(r"\b(sad|tragic|lost|failed|disaster|extinct\w*|died|gone)\b"), "sad"),
    (R(r"\b(footsteps?|walk\w*|step\w*|marching|hike\w*)\b"), "footsteps"),
    (R(r"\b(alarm|warning|danger\w*|emergency|siren)\b"), "alarm"),
]


# ------------------------------------------------------------------ WHERE a piece of narration takes place
# alias -> (regex, weak). Aliases are the keys of director.ENV_ALIASES, so every style resolves them to a real environment.
# "weak" words (data, room, sky ...) only count when written as a place ("in the room", "across the sky").
_PLACE_DEFS = {
    "space":        (r"outer space|deep space|space|cosmos|universe|interstellar|zero gravity|spacecraft|spaceship", False),
    "galaxy":       (r"galax\w+|milky way|nebula\w*", False),
    "solar_system": (r"solar system|planets?", False),
    "orbit":        (r"orbit\w*|the moon|lunar|satellites?|mars", False),
    "underwater":   (r"underwater|under the (sea|ocean|water)|beneath the (waves|surface of the (sea|ocean))|sea ?floor|ocean floor|coral|reefs?|submarine|scuba|dive[rs]?|diving", False),
    "deep_sea":     (r"deep sea|abyss\w*|trench\w*|bathyal|hadal|midnight zone", False),
    "ocean":        (r"ocean\w*|the sea|seas|waves?|tsunami\w*|shore|coast\w*|harbou?r|ship|sailing|sailors?", False),
    "beach":        (r"beach\w*|seaside|sand castle", False),
    "volcano":      (r"volcan\w+|lava|magma|erupt\w*|crater", False),
    "ice":          (r"glaciers?|arctic|antarctic\w*|polar|icebergs?|tundra|permafrost|snow\w*|frozen|ice sheets?|ice caps?", False),
    "desert":       (r"deserts?|sahara|dunes?|oasis|arid|sand", False),
    "storm":        (r"storms?|hurricanes?|tornado\w*|thunder\w*|lightning|cyclones?|blizzards?", False),
    "cell":         (r"inside (the|your|a) body|bloodstream|blood vessels?|inside (a|the|your) cells?|microscop\w+|bacteria|viruses|virus|organs?|tissues?|dna", False),
    "brain":        (r"brains?|neurons?|synapses?|neural|cortex|skull", False),
    "lab":          (r"laborator\w+|lab|experiments?|scientists?", True),
    "city":         (r"cit(y|ies)|downtown|skyscrapers?|metropolis|skyline|urban", False),
    "street":       (r"streets?|roads?|traffic|sidewalks?|crosswalk|neighbou?rhood|town", True),
    "rooftop":      (r"rooftops?|on the roof", False),
    "data":         (r"internet|servers?|data ?centers?|computers?|network|online|cyberspace|software|the cloud|database", True),
    "tunnel":       (r"wormhole|tunnel|through time|time travel|time machine|timeline", True),
    "sky":          (r"sky|skies|clouds?|atmosphere|airplanes?|aeroplane|flying|altitude|high above", True),
    "forest":       (r"forests?|jungles?|woods?|rainforest\w*|woodland|trees", False),
    "cave":         (r"caves?|caverns?|underground|mines?|beneath the (ground|surface|earth)|bedrock|rock layers|strata", False),
    "hills":        (r"hills?|meadow\w*|countryside|farms?|fields?|plains|mountains?|valley|village", True),
    "room":         (r"rooms?|kitchen|bedroom|living room|classroom|office|apartment|inside (a|the|his|her|your) house", True),
}
_PLACE_RX = {a: re.compile(r"\b(?:" + rx + r")\b", re.I) for a, (rx, weak) in _PLACE_DEFS.items()}
_PLACE_WEAK = {a for a, (rx, weak) in _PLACE_DEFS.items() if weak}
_PREP_BEFORE = re.compile(r"\b(in|at|on|under|beneath|inside|across|through|above|over|near|into|from|within|along|toward|towards|beyond|around|deep in|out in|to)\s+(the|a|an|this|that|his|her|their|our|your|its|these|those)?\s*(\w+\s+){0,2}$", re.I)
# which topic's palette fits a place
PLACE_TOPIC = {"space": "space", "galaxy": "space", "solar_system": "space", "orbit": "space", "underwater": "ocean", "deep_sea": "ocean",
               "ocean": "ocean", "beach": "ocean", "volcano": "volcano", "ice": "ice", "desert": "desert", "storm": "weather", "cell": "body",
               "brain": "brain", "lab": "physics", "city": "city", "street": "city", "rooftop": "city", "data": "tech", "tunnel": "physics",
               "sky": "weather", "forest": "nature", "cave": "earth", "hills": "nature", "room": "generic"}


def place_scores(text):
    """{alias: score}. A place written as a place ('in the desert', 'under the sea') counts 3, a plain mention 1;
    weak words only count when written as a place."""
    sc = {}
    for a, rx in _PLACE_RX.items():
        for m in rx.finditer(text):
            strong = bool(_PREP_BEFORE.search(text[max(0, m.start() - 40):m.start()]))
            if a in _PLACE_WEAK and not strong:
                continue
            sc[a] = sc.get(a, 0) + (3 if strong else 1)
    return sc


def place_of(text):
    """-> (alias or None, score). Score >= 2 is a clear place; >= 3 a place that was named as one."""
    sc = place_scores(text)
    if not sc:
        return None, 0
    # more specific places beat their general cousins when both appear (underwater > ocean, galaxy > space)
    for specific, general in (("underwater", "ocean"), ("deep_sea", "ocean"), ("deep_sea", "underwater"), ("galaxy", "space"),
                              ("solar_system", "space"), ("orbit", "space"), ("beach", "ocean"), ("rooftop", "city")):
        if specific in sc and general in sc:
            sc[specific] += sc.pop(general)
    best = max(sc.items(), key=lambda kv: kv[1])
    return best
