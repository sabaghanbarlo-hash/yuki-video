"""The lab's "reading comprehension": what is this sentence DOING in the video, how should Yuki feel about it, and what picture explains it?

The old collage director matched single keywords ("best" -> happy face, "don't" -> smug, "run" -> a runner sticker).  This module reads a beat
the way a person would:

  ROLE      what the sentence does in the story: intro, hook (a question), definition, problem, contrast, advice, example, conclusion
  FEELING   the emotion the words carry, with NEGATION handled ("you don't have to solve every thought" is relief, not worry; "it isn't fun" is not joy)
  CONCEPT   the abstract idea being explained (overthinking, replaying the past, the unknown future, being stuck, letting go, a choice, progress ...)
            and the visual METAPHOR that explains it (lab/metaphors.py: tangle, thought_loop, rewind_clock, crystal_ball, maze, balloons ...)

From these it picks Yuki's face, pose and accents (never a hand on her face) and the things to draw.  A memory of the last beats keeps poses,
faces and metaphors from repeating.  If an LLM key is configured, lab/brain.py asks a language model for the same fields and they replace the rules'
answers (the rules still fill every gap, so it never fails).  Pure functions + a small memory dict: deterministic for a given seed.
"""
import re

R = lambda p: re.compile(p, re.I)

# ------------------------------------------------------------------ vocabulary Yuki can act out (checked against lab/yuki_rig.py)
FACES = {"neutral", "smile", "happy", "worried", "shocked", "curious", "angry", "sleepy", "smug", "serene", "sad", "excited", "laughing", "crying", "teary", "starry",
         "lovestruck", "dizzy", "deadpan", "nervous", "gasp", "terrified", "cheeky", "scheming", "proud", "pained", "creepy", "determined", "confused", "awkward",
         "embarrassed", "inspired", "bored", "grumpy", "dreamy", "yum"}
POSES = {"rest", "relax", "talk_a", "talk_b", "present", "explain", "point_r", "point_l", "point_up", "shrug", "shrug_big", "wave", "cheer", "hug", "cross", "welcome",
         "idea", "pen", "magnify", "ponder", "ponder_l", "worry", "slump", "slump_sigh", "droop", "clap", "hands_up", "surprise", "shy", "stop", "hips", "heart", "dance",
         "shake", "fist", "wave_both", "bow", "lean_in", "nod_yes", "thumbs_up"}
ACCENTS = {"spark", "q", "sweat", "zzz", "gloom", "ex", "anger", "heart", "star", "note", "bulb", "ha", "dots"}
ROLES = ("intro", "hook", "definition", "problem", "contrast", "advice", "example", "conclusion", "statement")
EMOTIONS = ("worried", "scared", "sad", "angry", "happy", "proud", "excited", "curious", "confused", "shocked", "tired", "bored", "embarrassed", "calm", "determined",
            "hopeful", "smug")

# ------------------------------------------------------------------ discourse roles
ROLE_RX = [
    ("intro", R(r"^\s*(hey|hi|hello|welcome|in this (video|episode)|today,? (we|i|let)|let.s (talk|dive|explore|look))\b")),
    ("hook", R(r"^\s*(have you (ever|noticed)|ever (wonder|notice|feel|had|felt)\w*|did you know|why (do|does|is|are|can.t|don.t)|what (if|happens|would)|how (do|does|come|can)|imagine|picture this|think about (it|this)|"
               r"do you (ever|know)|ever wondered|what.s the (reason|deal))\b")),
    ("problem", R(r"\b(here.s the (problem|catch|issue|trap|thing)|the (problem|issue|catch|trap|danger|trouble|risk) (is|with)|unfortunately|sadly|the (bad|hard) (news|part)|that.s (where|when) (it|things) (goes|go|gets?) wrong|"
                  r"the (more|harder) you)\b")),
    ("definition", R(r"\b(that.s called|this is called|is called|are called|known as|is (when|what|the (tendency|habit|process|state|feeling))|means that|refers to|is defined as|in (psychology|science|biology|economics)|"
                    r"psycholog\w+,|scientists (call|say|define)|experts (call|say))\b")),
    ("contrast", R(r"\b(but|however|instead|rather than|on the other hand|yet|although|though|not (always|quite|really)|doesn.t always|isn.t (always|really)|myth|in fact|actually|the truth is|contrary)\b")),
    ("advice", R(r"\b(try|remember|you (can|could|should|might want to|don.t have to|do not have to|don.t need to|need to|must)|the (best|first|key|simplest|easiest) (thing|way|step|move|trick)|start (by|with|small)|"
                 r"accept|allow yourself|let yourself|give yourself|it.s (okay|ok|fine|normal)|it is (okay|ok|fine|normal)|next time|make (it|sure)|stop (trying|worrying|overthinking))\b")),
    ("example", R(r"\b(for (example|instance)|such as|say you|like when|picture|think of (a|the)|for me|take (a|the) (person|man|woman|friend))\b")),
    ("conclusion", R(r"\b(in the end|at the end of the day|so (next time|remember|if you|the next)|the takeaway|that.s (why|how)|to sum up|in short|bottom line|and that.s|remember,)\b")),
]

# ------------------------------------------------------------------ emotion words (stem regexes) and negation
EMO_RX = [
    ("worried", R(r"\b(anxi\w+|worr\w+|stress\w*|nervous\w*|overthink\w*|overwhelm\w*|dread\w*|uneasy|tense\w*|panic\w*|spiral\w*|ruminat\w*|restless\w*|uncertain\w*|insecur\w+|doubt\w*|replay\w*|second.guess\w*)\b"), 1.0),
    ("scared", R(r"\b(afraid|scared|fear\w*|terrif\w+|frighten\w*|horror|creep\w*|danger\w*|threat\w*)\b"), 1.0),
    ("sad", R(r"\b(sad\w*|cry\w*|tears?|grie\w+|lonel\w+|alone|heartbr\w+|depress\w+|hopeless\w*|miss(ed|ing)?|loss|lost|regret\w*|empty|hurt\w*|painful|suffer\w*)\b"), 1.0),
    ("angry", R(r"\b(angry|anger|furious|rage|hate\w*|annoy\w*|frustrat\w*|resent\w*|unfair|toxic)\b"), 1.0),
    ("happy", R(r"\b(happy|happiness|joy\w*|glad|delight\w*|cheerful|fun|enjoy\w*|smil\w+|laugh\w*|celebrat\w*|wonderful|great|lov(e|ed|es|ing)|grateful|gratitude|thankful)\b"), 1.0),
    ("proud", R(r"\b(proud|achiev\w+|accomplish\w*|success\w*|nail(ed)?|master(ed|y)?|victor\w+|win(s|ning)?|won|improv\w+|progress\w*)\b"), 0.9),
    ("excited", R(r"\b(excit\w+|thrill\w*|amazing|incredible|awesome|wow|mind.?blowing|unbelievable|spectacular|astonish\w+)\b"), 1.0),
    ("curious", R(r"\b(curious|wonder\w*|ever|why|how come|what if|mystery|mysterious|secret\w*|discover\w*|interesting|fascinat\w+|imagine|question\w*|puzzle\w*)\b"), 0.8),
    ("confused", R(r"\b(confus\w+|puzzl\w+|paradox\w*|unclear|complicated|baffl\w+|makes no sense|mess(y)?|chaos|chaotic|tangled|lost in|no idea)\b"), 1.0),
    ("shocked", R(r"\b(shock\w*|suddenly|unexpected\w*|surpris\w+|whoa|instantly|boom|can.t believe|out of nowhere)\b"), 1.0),
    ("tired", R(r"\b(tired|sleepy|exhaust\w*|fatigue\w*|burn\w*out|drain\w*|yawn\w*|insomnia|weary|worn out)\b"), 1.0),
    ("bored", R(r"\b(bor(ed|ing)|dull|monoton\w+|same thing|meh|nothing (new|happens))\b"), 0.9),
    ("embarrassed", R(r"\b(embarrass\w+|awkward\w*|cringe\w*|shy|blush\w*|oops|sorry|apolog\w+|mistakes?|said something wrong|something wrong)\b"), 0.9),
    ("calm", R(r"\b(calm\w*|peace\w*|relax\w*|breath\w*|gentle|gently|quiet|still|serene|accept\w*|let(ting)? go|release\w*|lighter|relief|relieved|ease|at ease|rest)\b"), 1.0),
    ("determined", R(r"\b(determin\w+|discipline\w*|commit\w*|persist\w*|keep going|never give up|push\w* through|focus\w*|effort|work hard|grind\w*|resolve|consisten\w+)\b"), 1.0),
    ("hopeful", R(r"\b(hop(e|es|ed|ing|eful)|wish\w*|dream\w*|someday|believ\w+|trust\w*|possib\w+|inspir\w+|optimis\w+)\b"), 0.9),
    ("smug", R(r"\b(actually|myth\w*|false|fake|so.called|supposedly|nope|not quite|the truth is|turns out)\b"), 0.8),
]
NEGATORS = R(r"\b(not|no|never|without|hardly|barely|neither|nor|nothing|nobody|cannot|can.t|don.t|doesn.t|didn.t|isn.t|aren.t|wasn.t|won.t|wouldn.t|shouldn.t|couldn.t|stop|quit)\b")
SCOPE_BREAK = {"more", "most", "so", "as", "that", "such", "this", "too", "very", "really"}      # "never felt MORE alone" is not a negation of sadness
FLIP = {"worried": "calm", "scared": "calm", "sad": "calm", "angry": "calm", "happy": "bored", "proud": "sad", "excited": "bored", "calm": "worried", "tired": "calm",
        "confused": "calm", "embarrassed": "calm", "determined": "tired", "hopeful": "sad", "curious": "bored", "bored": "calm", "shocked": "calm", "smug": "calm"}
RELIEF = R(r"\b(you don.t (have|need) to|you do not (have|need) to|no need to|doesn.t (need|have) to|does not (need|have) to|not everything (needs|has|is)|it.s (okay|ok|fine) (to|if)|it is (okay|ok|fine) (to|if)|"
           r"you can (stop|let|just|simply)|allowed to|permission to|give yourself (permission|a break|grace)|let (it|them|that|things) (go|be)|good enough)\b")

# ------------------------------------------------------------------ abstract concepts -> what to draw
# (id, regex, weight, looks, icon_words, hints)   looks = alternatives, each a list of entity names (the first not used recently is chosen)
CONCEPTS = [
    ("overthink", R(r"\b(overthink\w*|over.think\w*|ruminat\w*|spiral\w*|racing (thoughts|mind)|can.t stop thinking|think(ing)? (too much|more|harder|about it|too hard)|too many thoughts|analy[sz]ing|second.guess\w*|"
                    r"overanaly\w+|mind (races|racing)|going in circles|round and round|every thought)\b"), 1.6, [["tangle"], ["thought_loop"], ["brain"]], [], dict(face="worried", pose="ponder")),
    ("replay", R(r"\b(replay\w*|rewind\w*|over and over|again and again|on repeat|loop\w*|keep (coming|going) back|same (thought|thing|worry|mistake)|cycle|dwell\w*|rehears\w+)\b"), 1.8,
     [["thought_loop"], ["tangle"]], [], dict(face="worried", pose="ponder")),
    ("past", R(r"\b(the past|yesterday|memor(y|ies)|back then|last (year|week|night|month)|used to|regret\w*|childhood|the old days|years ago|earlier|history|flashback\w*|conversation (you|i|we) had)\b"), 1.2,
     [["rewind_clock"], ["calendar"]], [], dict()),
    ("future", R(r"\b(the future|tomorrow|next (year|week|month|decade)|someday|what.s (next|ahead)|ahead of (us|you)|predict\w*|forecast\w*|what if|might happen|could happen|will happen|up ahead|imagin\w+ the)\b"), 1.2,
     [["crystal_ball"], ["signpost"]], [], dict(face="curious")),
    ("uncertain", R(r"\b(uncertain\w*|unknown|not sure|unsure|don.t know|no idea|unclear|ambigu\w+|who knows|mystery|question\w*|wonder\w*|doubt\w*|guess\w*|puzzl\w+)\b"), 1.0,
     [["qmarks"], ["maze"]], [], dict(face="confused", pose="shrug")),
    ("stuck", R(r"\b(stuck|trapped|lost in|dead end|no way out|complicated|complex|overwhelm\w*|maze|can.t (escape|get out|move)|paralys\w+|frozen|struggl\w+)\b"), 1.3,
     [["maze"], ["tangle"]], [], dict(face="worried")),
    ("control", R(r"\b(control\w*|in charge|grip|steer\w*|manage\w*|handle\w*|regulat\w+|mechanism)\b"), 0.9, [["gear"], ["lock"]], [], dict()),
    ("mind", R(r"\b(brain\w*|mind|mental\w*|psycholog\w+|neuro\w*|cognit\w+|consciousness|subconscious|thoughts?)\b"), 0.7, [["brain"], ["bulb"]], [], dict()),
    ("letgo", R(r"\b(let(ting)? go|release\w*|surrender\w*|move on|stop trying|don.t have to|doesn.t need|not everything|relax\w*|peace\w*|calm\w*|breath\w*|lighter|accept\w*|relief)\b"), 1.5,
     [["balloons"]], [], dict(face="serene", pose="relax")),
    ("choice", R(r"\b(decid\w+|decision\w*|choice\w*|choose|options?|which (way|one|path)|crossroads|dilemma|path\w*|direction|should (i|we|you)|either)\b"), 1.1, [["signpost"], ["scale"]], [], dict(face="curious")),
    ("balance", R(r"\b(balanc\w+|weigh\w*|trade.?offs?|pros and cons|both sides|fair(ness)?|equal)\b"), 1.1, [["scale"]], [], dict()),
    ("progress", R(r"\b(progress\w*|improv\w+|grow(s|th|ing)?|level up|increas\w+|rise|rising|boost\w*|results?|compound\w*|small steps?|step by step|momentum|upgrade\w*)\b"), 1.1,
     [["bars_up"], ["sprout"], ["ladder"]], [], dict(face="happy", pose="thumbs_up")),
    ("decline", R(r"\b(declin\w+|drops?|dropp\w+|decreas\w+|losing|worsen\w*|ruin\w*|damag\w+|falling (behind|apart)|collaps\w+|crash\w*)\b"), 1.1, [["bars_down"]], [], dict(face="worried")),
    ("energy", R(r"\b(energy|exhaust\w*|tired|fatigue\w*|burn\w*out|drain\w*|low battery|recharge\w*|run out of|worn out)\b"), 1.2, [["battery"], ["bed"]], [], dict(face="sleepy")),
    ("time", R(r"\b(deadline\w*|rush\w*|hurry|hurried|running out of time|no time|waste time|wasting time|procrastinat\w*|delay\w*|waiting|wait\b|time is)\b"), 1.2, [["hourglass"], ["alarm"]], [], dict()),
    ("sleep", R(r"\b(sleep\w*|insomnia|bedtime|nap\w*|dream\w*|asleep|bed)\b"), 1.0, [["bed"]], [], dict()),
    ("phone", R(r"\b(phone\w*|scroll\w*|social media|notification\w*|doomscroll\w*|feed|instagram|tiktok|youtube|screen time|app|apps)\b"), 1.2, [["scroll_phone"], ["phone"]], [], dict()),
    ("goal", R(r"\b(goals?|targets?|aim\w*|purpose|objective\w*|ambition\w*|bullseye|on track|hit the mark)\b"), 1.1, [["target"], ["flag"]], [], dict(face="determined")),
    ("idea", R(r"\b(idea\w*|insight\w*|realiz\w+|aha|solution\w*|answer\w*|secret\w*|trick\w*|lesson\w*|truth|understand\w*|clarity|clear (mind|head)|figure (it )?out)\b"), 1.0, [["bulb"]], [], dict(face="inspired", pose="idea")),
    ("habit", R(r"\b(habits?|routines?|daily|every day|everyday|consisten\w+|streak\w*|discipline\w*|schedul\w+|day by day)\b"), 1.1, [["calendar"], ["checklist"]], [], dict()),
    ("success", R(r"\b(success\w*|win(ning|ner|s)?|achiev\w+|victor\w+|accomplish\w*|champion\w*|goal reached|reward\w*|trophy|finish line)\b"), 1.1, [["trophy"]], [], dict(face="proud", pose="fist")),
    ("mistake", R(r"\b(mistakes?|fail\w*|wrong|error\w*|flaw\w*|blunder\w*|slip.?up|messed up|screw\w* up|embarrass\w+|awkward\w*|cringe\w*)\b"), 1.0, [["speech"]], ["wrong"], dict(face="embarrassed", pose="shy")),
    ("conversation", R(r"\b(conversation\w*|said|talk(ed|ing|s)?|speak\w*|chat\w*|argument\w*|text(ed|ing)|messages?|repl(y|ied)|gossip\w*)\b"), 0.9, [["speech"]], [], dict()),
    ("judged", R(r"\b(judg\w+|what (others|people|they) think|opinion\w*|criticis\w+|criticiz\w+|watching you|everyone is looking|being watched|reputation|approval|validation|compar\w+ (yourself|to others))\b"), 1.3,
     [["eye"], ["crowd"]], [], dict(face="nervous")),
    ("money", R(r"\b(money|rich\w*|wealth\w*|cash|salary|invest\w*|saving\w*|budget\w*|price\w*|cost\w*|spend\w*|debt|income|dollars?)\b"), 1.1, [["coin"]], [], dict()),
    ("exercise", R(r"\b(exercis\w+|workout\w*|gym|muscle\w*|fitness|lift\w*|training|strength)\b"), 1.1, [["dumbbell"]], [], dict(face="determined", pose="fist")),
    ("health", R(r"\b(health\w*|heart|body|wellbeing|well.being|wellness|medicine|doctor\w*|immune)\b"), 0.8, [["heart"]], [], dict()),
    ("learning", R(r"\b(read\w*|books?|learn\w*|stud(y|ies|ied|ying)|knowledge|education|school|lessons?|lectures?|curriculum)\b"), 0.9, [["book"]], [], dict()),
    ("work", R(r"\b(work(ing)?|jobs?|career\w*|office|emails?|projects?|productiv\w+|computers?|cod(e|ing)|freelanc\w+|boss|client\w*)\b"), 0.8, [["laptop"]], [], dict()),
    ("food", R(r"\b(food|eat(ing)?|meals?|diet\w*|snacks?|sugar|hungry|breakfast|lunch|dinner|coffee|caffeine)\b"), 0.8, [["coffee"], ["apple"]], [], dict()),
    ("love", R(r"\b(love[sd]?|relationships?|friend(s|ship)?|family|partner|connection|belong\w*|together|lonel\w+)\b"), 0.8, [["heart"]], [], dict()),
    ("fear", R(r"\b(afraid|scared|fears?|terrif\w+|anxi\w+|worr\w+|panic\w*|dread\w*)\b"), 0.8, [["cloud"], ["skull"]], [], dict(face="nervous")),
    ("evidence", R(r"\b(research\w*|stud(y|ies)|scientists?|evidence|data|experiment\w*|found that|according to|proof|psycholog\w+ (say|show|shows|found))\b"), 0.9, [["book"], ["bars_up"]], [], dict(face="smile", pose="magnify")),
]
ROLE_FALLBACK_THINGS = {"hook": [["qmarks"]], "problem": [["maze"], ["qmarks"]], "conclusion": [["balloons"], ["sprout"]], "advice": [["bulb"]]}

# ------------------------------------------------------------------ what Yuki does for each role / feeling:  (face, pose, accents)
ROLE_BASE = {
    "intro": [("happy", "wave", ["spark"]), ("smile", "welcome", [])],
    "hook": [("curious", "lean_in", ["q"]), ("curious", "ponder", ["q"]), ("curious", "point_up", [])],
    "definition": [("smile", "explain", []), ("neutral", "present", []), ("smile", "point_up", []), ("neutral", "explain", [])],
    "problem": [("worried", "worry", ["sweat"]), ("nervous", "stop", []), ("worried", "shake", ["sweat"])],
    "contrast": [("deadpan", "shrug", []), ("smug", "cross", []), ("neutral", "explain", [])],
    "advice": [("smile", "welcome", []), ("serene", "heart", []), ("happy", "thumbs_up", ["spark"]), ("smile", "nod_yes", [])],
    "example": [("curious", "explain", []), ("smile", "pen", []), ("neutral", "point_r", [])],
    "conclusion": [("serene", "heart", ["heart"]), ("happy", "welcome", ["spark"]), ("smile", "bow", [])],
    "statement": [("smile", "talk_a", []), ("neutral", "talk_b", []), ("smile", "explain", []), ("neutral", "present", [])],
}
EMO_LOOKS = {
    "worried": [("worried", "worry", ["sweat"]), ("nervous", "shake", ["sweat"]), ("worried", "ponder", [])],
    "scared": [("terrified", "hands_up", ["ex"]), ("nervous", "shake", ["sweat"])],
    "sad": [("sad", "slump", ["gloom"]), ("teary", "droop", ["gloom"]), ("sad", "slump_sigh", [])],
    "angry": [("angry", "cross", ["anger"]), ("grumpy", "hips", ["anger"]), ("angry", "fist", ["anger"])],
    "happy": [("happy", "cheer", ["spark"]), ("happy", "talk_a", []), ("proud", "talk_b", [])],
    "proud": [("proud", "hips", ["spark"]), ("proud", "fist", ["star"]), ("happy", "thumbs_up", ["spark"])],
    "excited": [("excited", "cheer", ["spark"]), ("starry", "clap", ["star"]), ("inspired", "idea", ["bulb"])],
    "curious": [("curious", "ponder", ["q"]), ("curious", "lean_in", []), ("curious", "magnify", [])],
    "confused": [("confused", "shrug", ["q"]), ("dizzy", "shake", ["q"]), ("confused", "ponder_l", ["q"])],
    "shocked": [("gasp", "surprise", ["ex"]), ("shocked", "hands_up", ["ex"])],
    "tired": [("sleepy", "slump", ["zzz"]), ("bored", "slump_sigh", ["zzz"])],
    "bored": [("bored", "relax", ["dots"]), ("deadpan", "shrug", ["dots"])],
    "embarrassed": [("embarrassed", "shy", ["sweat"]), ("awkward", "shy", ["dots"])],
    "calm": [("serene", "relax", []), ("smile", "welcome", []), ("serene", "heart", [])],
    "determined": [("determined", "fist", ["spark"]), ("determined", "hips", [])],
    "hopeful": [("dreamy", "ponder", []), ("inspired", "point_up", ["spark"]), ("smile", "welcome", [])],
    "smug": [("smug", "cross", []), ("deadpan", "shrug", [])],
}
STRONG = {"shocked", "scared", "angry", "sad", "excited", "proud", "tired", "happy"}               # feelings big enough to leave the explaining pose
EXPLAINING_POSES = {"explain", "present", "point_up", "point_r", "talk_a", "talk_b", "pen"}      # roles that keep explaining while the face shows the feeling


# ------------------------------------------------------------------ memory
def new_memory():
    return dict(poses=[], faces=[], looks=[], things=[], concepts=[], accents=[], n=0)


STATE = dict(n_scenes=0, brain={}, primed=False)


def begin(title, raw_scenes, force_style=None):
    """Called once before the director plans the scenes: lets the optional LLM read the whole script at once."""
    STATE.update(n_scenes=len(raw_scenes), brain={}, primed=True)
    try:
        from . import brain
        STATE["brain"] = brain.prime(title, raw_scenes) or {}
    except Exception as e:                                           # never let the optional brain break a video
        print(f"  [brain] skipped ({type(e).__name__}: {e})", flush=True)


def norm(txt):
    return re.sub(r"[^a-z0-9 ]+", "", re.sub(r"\s+", " ", txt.lower())).strip()


# ------------------------------------------------------------------ analysis
def role_of(txt, first=False, last=False):
    t = txt.strip()
    if first and ROLE_RX[0][1].search(t):
        return "intro"
    if t.endswith("?") or ROLE_RX[1][1].search(t):
        return "hook"
    role = "statement"
    for name, rx in ROLE_RX[2:]:
        if rx.search(t):
            role = name
            break
    if last and role in ("advice", "statement", "contrast"):
        return "conclusion"                                           # the final beat wraps the video up
    return role


def feeling_of(txt):
    """-> (emotion or None, strength 0..1.6, negated?).  Negation within three words before an emotion word flips it (worry -> relief)."""
    t = txt.lower()
    scores = {}
    negated = False
    relief = bool(RELIEF.search(t))
    for emo, rx, w in EMO_RX:
        for m in rx.finditer(t):
            before = t[max(0, m.start() - 28):m.start()]
            words = re.findall(r"[a-z']+", before)[-3:]
            neg = False
            for wi, tok in enumerate(words):
                if NEGATORS.fullmatch(tok) and not set(words[wi + 1:]) & SCOPE_BREAK:
                    neg = True
            
            e = FLIP.get(emo, emo) if neg else emo
            negated = negated or neg
            scores[e] = scores.get(e, 0.0) + w * (0.8 if neg else 1.0)
    if relief:
        scores["calm"] = scores.get("calm", 0.0) + 1.6
        negated = True
    if not scores:
        return None, 0.0, negated
    emo = max(scores.items(), key=lambda kv: kv[1])
    return emo[0], min(1.6, emo[1]), negated


def concepts_of(txt):
    """-> [(score, concept tuple)] best first."""
    out = []
    for c in CONCEPTS:
        n = len(c[1].findall(txt))
        if n:
            out.append((c[2] * (1 + 0.35 * (min(n, 3) - 1)), c))
    out.sort(key=lambda x: -x[0])
    return out


def _fresh(options, recent, key=lambda o: o):
    fresh = [o for o in options if key(o) not in recent]
    return fresh or options


def _choose_look(options, mem, rng, role):
    """Pick a (face, pose, accents) that did not just happen."""
    recent_p, recent_f = mem["poses"][-3:], mem["faces"][-1:]
    ok = [o for o in options if o[1] not in recent_p and not (o[0] in recent_f and o[1] in mem["poses"][-1:])]
    if not ok:
        ok = [o for o in options if o[1] != (mem["poses"][-1] if mem["poses"] else None)] or options
    return rng.choice(ok)


def hint(txt, mem, rng, first=False, last=False):
    """Everything the director needs to know about one beat.
    -> dict(role, emotion, face, pose, acc, metaphors [entity names], icon_words [words], concepts [ids], negated, source)"""
    t = txt.strip()
    role = role_of(t, first, last)
    emo, strength, negated = feeling_of(t)
    cons = concepts_of(t)
    brain = STATE["brain"].get(norm(t)) or {}
    if brain.get("role") in ROLES:
        role = brain["role"]
    if brain.get("emotion") in EMOTIONS:
        emo, strength = brain["emotion"], max(strength, 1.2)

    # ---- how Yuki looks
    if emo and strength >= 0.8:
        emo_looks = EMO_LOOKS[emo]
        if role in ("statement", "example") and emo in STRONG and strength >= 1.0:
            face, pose, acc = _choose_look(emo_looks, mem, rng, role)
        elif role in ("definition", "example", "statement", "contrast") and (role != "contrast" or emo != "smug"):
            base = _choose_look(ROLE_BASE[role], mem, rng, role)
            elook = _choose_look(emo_looks, mem, rng, role)
            face, pose, acc = elook[0], (base[1] if base[1] in EXPLAINING_POSES or role == "contrast" else elook[1]), elook[2]
        elif role in ("problem", "advice", "conclusion", "hook", "intro"):
            base = _choose_look(ROLE_BASE[role], mem, rng, role)
            elook = _choose_look(emo_looks, mem, rng, role)
            compatible = {"problem": {"worried", "scared", "sad", "angry", "confused", "embarrassed", "tired", "shocked"},
                          "advice": {"calm", "happy", "hopeful", "determined", "proud", "curious", "excited"},
                          "conclusion": {"calm", "happy", "hopeful", "proud", "determined", "excited"},
                          "hook": {"curious", "confused", "shocked", "worried", "excited", "hopeful", "scared"},
                          "intro": {"happy", "excited", "curious", "calm", "hopeful"}}[role]
            if emo in compatible:
                face, pose, acc = elook[0], (elook[1] if role == "problem" else base[1]), elook[2] or base[2]
            else:
                face, pose, acc = base                                  # e.g. a "happy" word inside a problem sentence: keep the sentence's job
        else:
            face, pose, acc = _choose_look(emo_looks, mem, rng, role)
    else:
        face, pose, acc = _choose_look(ROLE_BASE[role], mem, rng, role)
    top = cons[0][1] if cons else None
    if top and top[5] and role in ("statement", "example", "definition"):   # a concept can colour the face (stuck -> worried) when the words carry no feeling
        if not (emo and strength >= 0.8):
            face = top[5].get("face", face)
            pose = top[5].get("pose", pose) if role in ("statement", "example") else pose
    if brain.get("face") in FACES:
        face = brain["face"]
    if brain.get("pose") in POSES:
        pose = brain["pose"]
    acc = [a for a in acc if a in ACCENTS]
    if mem["accents"] and mem["accents"][-1] and rng.random() < 0.75:    # accents are seasoning, not on every beat
        acc = []

    # ---- what explains it
    things, used = [], []
    top_sc = cons[0][0] if cons else 0.0
    for k_, (sc_, c) in enumerate(cons[:3]):
        if sc_ < 0.85 or (k_ and (sc_ < 1.0 or sc_ < 0.55 * top_sc)):
            continue
        looks = c[3]
        recent = set(sum(([x] if isinstance(x, str) else list(x) for x in mem["things"][-4:]), []))
        look = _fresh(looks, recent, key=lambda L: L[0])[0]
        for nm in look:
            if nm not in things:
                things.append(nm); used.append(c[0])
        if len(things) >= 2:
            break
    bth = [x for x in (brain.get("metaphors") or []) if isinstance(x, str)]
    if bth:
        things = bth[:2]
    if not things and role in ROLE_FALLBACK_THINGS and (role != "advice" or not cons):
        looks = ROLE_FALLBACK_THINGS[role]
        recent = set(sum(([x] if isinstance(x, str) else list(x) for x in mem["things"][-4:]), []))
        things = list(_fresh(looks, recent, key=lambda L: L[0])[0])
    things = things[:2]
    icon_words = list(brain.get("icon_words") or [])
    for sc_, c in cons[:2]:
        for w in c[4]:
            if w not in icon_words:
                icon_words.append(w)
    env = brain.get("place")
    action = brain.get("action")
    h = dict(role=role, emotion=emo, face=face, pose=pose, acc=acc, metaphors=things, icon_words=icon_words[:3], concepts=used or [c[1][0] for c in cons[:2]],
             negated=negated, env=env, action=action, source="llm" if brain else "rules")
    return h


def remember(mem, h):
    mem["poses"].append(h["pose"]); mem["faces"].append(h["face"]); mem["accents"].append(bool(h["acc"]))
    if h["metaphors"]:
        mem["things"].append(list(h["metaphors"]))
    mem["concepts"].append(h["concepts"][:1])
    mem["n"] += 1
    for k in ("poses", "faces", "things", "concepts", "accents"):
        mem[k] = mem[k][-8:]
