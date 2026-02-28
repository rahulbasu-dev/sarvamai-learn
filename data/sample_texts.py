"""
Canonical Indic text constants used across all notebooks.
Each sentence is chosen for maximum J&M pedagogical contrast.
"""

# Hindi (hi-IN): Sandhi, Devanagari script, SOV order
HINDI = "विद्यालय में शिक्षक छात्रों को भाषा प्रसंस्करण समझा रहे हैं।"

# Tamil (ta-IN): Heavy agglutination — 1 Tamil word = English phrase
TAMIL = "மாணவர்கள் பல்கலைக்கழகத்தின் கணினி அறிவியல் துறைக்கு வந்துகொண்டிருக்கிறார்கள்."

# Bengali (bn-IN): Conjunct characters, aspirated consonants
BENGALI = "আজকাল স্বাভাবিক ভাষা প্রক্রিয়াকরণ অনেক প্রযুক্তিতে ব্যবহৃত হচ্ছে।"

# Telugu (te-IN): Dravidian, distinct morphology from Tamil
TELUGU = "భాషా ప్రాసెసింగ్ నేటి సాంకేతిక పరిజ్ఞానంలో చాలా ముఖ్యమైన పాత్ర పోషిస్తుంది."

# Code-mixed (Hindi-English): for code-mix demos
CODE_MIXED = "मुझे machine learning बहुत interesting लगती है।"

# Dictionary for iteration
SAMPLE_TEXTS = {
    "hi-IN": HINDI,
    "ta-IN": TAMIL,
    "bn-IN": BENGALI,
    "te-IN": TELUGU,
}

LANGUAGE_NAMES = {
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "bn-IN": "Bengali",
    "te-IN": "Telugu",
}

# English translation (for comparison / BLEU reference)
ENGLISH_TRANSLATIONS = {
    "hi-IN": "The teacher is explaining language processing to students in school.",
    "ta-IN": "Students are coming to the computer science department of the university.",
    "bn-IN": "Nowadays, natural language processing is being used in many technologies.",
    "te-IN": "Language processing plays a very important role in today's technology.",
}

# Tamil word famous for agglutination demo
TAMIL_AGGLUTINATED = "வந்துகொண்டிருக்கிறார்கள்"
TAMIL_AGGLUTINATED_GLOSS = "came-taking-are-being-they (they are in the process of coming)"

# NLP terminology in Indic languages (for OOV / transliteration demo)
NLP_TERMS = {
    "tokenization": {
        "hi-IN": "टोकनाइज़ेशन",
        "ta-IN": "டோக்கனைசேஷன்",
        "bn-IN": "টোকেনাইজেশন",
        "te-IN": "టోకనైజేషన్",
    },
    "embedding": {
        "hi-IN": "एम्बेडिंग",
        "ta-IN": "எம்பெடிங்",
        "bn-IN": "এমবেডিং",
        "te-IN": "ఎంబెడింగ్",
    },
    "transformer": {
        "hi-IN": "ट्रांसफॉर्मर",
        "ta-IN": "டிரான்ஸ்ஃபார்மர்",
        "bn-IN": "ট্রান্সফর্মার",
        "te-IN": "ట్రాన్స్ఫార్మర్",
    },
}
