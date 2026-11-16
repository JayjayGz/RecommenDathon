"""French/English intent normalization shared by every portfolio stage. No I/O."""
import re
import unicodedata


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c)).replace('’', "'")


# Spelled quantities remain whole percentage POINTS, never currency or targets.
SMALL = ('zero un deux trois quatre cinq six sept huit neuf dix onze douze treize '
         'quatorze quinze seize dix-sept dix-huit dix-neuf').split()
NUMBER_WORDS = {word: n for n, word in enumerate(SMALL)}
NUMBER_WORDS.update({'une': 1, 'vingt': 20, 'trente': 30, 'quarante': 40,
                     'cinquante': 50, 'soixante': 60, 'cent': 100})
for tens, word in ((20, 'vingt'), (30, 'trente'), (40, 'quarante'), (50, 'cinquante'), (60, 'soixante')):
    for n in range(1, 10):
        NUMBER_WORDS[f'{word}-{SMALL[n]}'] = tens + n
        NUMBER_WORDS[f'{word} {SMALL[n]}'] = tens + n
        if n == 1:
            NUMBER_WORDS[f'{word} et un'] = tens + n
for n in range(10, 20):
    NUMBER_WORDS[f'soixante-{SMALL[n]}'] = 60 + n
    NUMBER_WORDS[f'soixante {SMALL[n]}'] = 60 + n
NUMBER_WORDS['soixante et onze'] = 71
NUMBER_WORDS.update({'quatre-vingt': 80, 'quatre vingt': 80})
for n in range(20):
    word = 'quatre-vingts' if n == 0 else f'quatre-vingt-{SMALL[n]}'
    NUMBER_WORDS[word] = 80 + n
    NUMBER_WORDS[word.replace('-', ' ')] = 80 + n
WORDS = '|'.join(re.escape(w) for w in sorted(NUMBER_WORDS, key=len, reverse=True))
QUANTITY = re.compile(r'(?<![\w.,+\-])(?P<amount>\d+(?:[.,]\d+)?|' + WORDS +
                      r')\s*(?:%|pour\s*cent\b|points?(?:\s+de\s+pourcentage)?\b)', re.I)


def quantities(message):
    text = fold(message)
    result = []
    numeric_words = set(re.split(r'[ -]', ' '.join(NUMBER_WORDS))) | {'virgule', 'moins', 'plus'}
    for match in QUANTITY.finditer(text):
        previous = re.search(r'([\w]+)[\s-]*$', text[:match.start()])
        value = NUMBER_WORDS.get(match['amount'], match['amount'])
        # Never take the tail of an unsupported number (cent cinq, 1 000,
        # deux virgule cinq) as a complete amount.
        if previous and (previous[1] in numeric_words or previous[1].isdigit()):
            value = 'invalid'
        result.append((match, value))
    return result


def asset_aliases(ticker, asset):
    # Explicit controlled name alias; still requires the canonical catalogue row.
    extra = ("Ethereum",) if ticker == "ETH-USD" and asset.get("asset_class") == "crypto" else ()
    return (ticker, asset["name"], *extra)


def asset_mentions(message, assets):
    # Keep identifier punctuation intact: TD.TO.OTHER must not resolve to TD.TO.
    text = re.sub(r'[.!?]+(?=\s|$)', '', fold(message))
    return {ticker for ticker, asset in assets.items()
            if any(re.search(r'(?<![\w.^=-])' + re.escape(fold(alias)) + r'(?![\w.^=-])', text)
                   for alias in asset_aliases(ticker, asset))}


def ambiguous(message):
    text = fold(message)
    # Do not reinterpret negation, a target, a condition, money, or multiple edits.
    return bool(re.search(
        r"\b(?:not|pas|jamais|sans|without|aucun|aucune|ne|n'|ni|sauf|si|sinon|if|unless|"
        r"target|total|cible|atteindre|porter|ramener|remplacer|echanger|transferer|convertir|"
        r"ignore|ignorer|oublie|instructions?|systeme|system|plutot|pourquoi|comment|avis|penses|"
        r"peut-etre|eventuellement|moitie|demi|half)\b|don't|"
        r'(?<![\w.^=-])(?:to|a)\s+(?:\d|' + WORDS + r')\b|'
        r"\bs[' ]|[$€]|\b(?:dollars?|euros?)\b", text))


def intent(message):
    text = fold(message)
    patterns = {
        'exclude': r'\b(?:exclude|remove|exclu(?:re|s|ez|ons)|retir(?:er|e|ez|ons)|supprim(?:er|e|ez|ons)|enlev(?:er|e|ez|ons))\b',
        'reduce': r'\b(?:sell|reduce|decrease|vend(?:re|s|ez|ons)|redui(?:re|s|sez|sons)|diminu(?:er|e|ez|ons)|baiss(?:er|e|ez|ons)|alleg(?:er|e|ez|eons))\b',
        'add': r'\b(?:add|increase|buy|ajout(?:er|e|ez|ons)|augment(?:er|e|ez|ons)|achet(?:er|e|ez|ons)|renforc(?:er|e|ez|ons))\b',
    }
    found = {action for action, pattern in patterns.items() if re.search(pattern, text)}
    return next(iter(found)) if len(found) == 1 else ('conflict' if found else None)
