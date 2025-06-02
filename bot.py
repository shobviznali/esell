import telebot
import os
from dotenv import load_dotenv
from woocommerce import API
import openai

# Загружаем .env
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WC_URL = os.getenv("WOOCOMMERCE_URL")
WC_KEY = os.getenv("WOOCOMMERCE_CONSUMER_KEY")
WC_SECRET = os.getenv("WOOCOMMERCE_CONSUMER_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([BOT_TOKEN, WC_URL, WC_KEY, WC_SECRET, OPENAI_API_KEY]):
    raise ValueError("Одна или несколько переменных окружения не установлены.")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# WooCommerce API
wcapi = API(
    url=WC_URL,
    consumer_key=WC_KEY,
    consumer_secret=WC_SECRET,
    version="wc/v3"
)

# Транслитерация
transliteration_map = {
    'sh': ['շ'], 'ch': ['չ', 'ճ'], 'zh': ['ժ'], 'ts': ['ց', 'ծ'], 'gh': ['ղ'],
    'kh': ['խ'], 'ye': ['ե'], 'vo': ['ո'], 'ev': ['և'],
    'a': ['ա'], 'b': ['բ'], 'g': ['գ'], 'd': ['դ'], 'e': ['ե', 'է'], 'z': ['զ'],
    't': ['տ', 'թ'], 'i': ['ի'], 'l': ['լ'], 'k': ['կ', 'ք'], 'h': ['հ'],
    'j': ['ջ'], 'x': ['խ', 'ղ'], 'c': ['ց', 'ք', 'ծ'], 'm': ['մ'],
    'y': ['յ'], 'n': ['ն'], 'o': ['օ', 'ո'], 'p': ['պ', 'փ'],
    'r': ['ր', 'ռ'], 's': ['ս'], 'v': ['վ'], 'u': ['ու'], 'f': ['ֆ'], 'q': ['ք']
}

reverse_map = {
    'ա': 'a', 'բ': 'b', 'գ': 'g', 'դ': 'd', 'ե': 'e', 'է': 'e', 'զ': 'z',
    'տ': 't', 'թ': 't', 'ի': 'i', 'լ': 'l', 'խ': 'kh', 'կ': 'k', 'ք': 'k',
    'հ': 'h', 'ձ': 'dz', 'ժ': 'zh', 'ջ': 'j', 'շ': 'sh', 'չ': 'ch', 'ճ': 'ch',
    'ղ': 'gh', 'ց': 'ts', 'ծ': 'ts', 'մ': 'm', 'յ': 'y', 'ն': 'n',
    'օ': 'o', 'ո': 'vo', 'պ': 'p', 'փ': 'p', 'ր': 'r', 'ռ': 'r',
    'ս': 's', 'վ': 'v', 'ու': 'u', 'ֆ': 'f', 'և': 'ev'
}


def transliterate_to_armenian(text):
    text = text.lower()
    result = ''
    i = 0
    while i < len(text):
        for length in [3, 2, 1]:
            fragment = text[i:i + length]
            if fragment in transliteration_map:
                result += transliteration_map[fragment][0]
                i += length
                break
        else:
            result += text[i]
            i += 1
    return result


def transliterate_to_english(text):
    result = ''
    i = 0
    while i < len(text):
        if text[i:i + 2] == 'ու':
            result += 'u'
            i += 2
        else:
            result += reverse_map.get(text[i], text[i])
            i += 1
    return result


def search_product(product_name):
    try:
        response = wcapi.get("products", params={"search": product_name})
        response.raise_for_status()
    except Exception as e:
        print(f"[WooCommerce Error] {e}")
        return "Սխալ տեղի ունեցավ ապրանքները որոնելիս 😕", []

    data = response.json()
    if not data:
        return f"Տվյալ ապրանքը `{product_name}` չի գտնվել 😕", []

    items = []
    for product in data[:3]:
        items.append({
            "name": product["name"],
            "price": product.get("price", "չի նշված"),
            "link": product.get("permalink", "")
        })
    return None, items


def extract_product_name(user_input):
    prompt = f"""
Դու արհեստական բանականություն ես, որը օգնում է դուրս բերել ապրանքի անունը հաճախորդի նամակից։
Նամակը: "{user_input}"

Ответь только названием товара, которое нужно найти на сайте. 
Не добавляй ничего лишнего, только название.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        extracted_name = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[OpenAI Error] {e}")
        return user_input, transliterate_to_armenian(user_input)

    armenian_name = transliterate_to_armenian(extracted_name)
    print(f"[GPT Extracted] '{extracted_name}' → [Armenian] '{armenian_name}'")
    return extracted_name, armenian_name


def generate_gpt_response(user_question, products):
    product_info = "\n".join([
        f"{p['name']} — {p['price']} դրամ — {p['link']}"
        for p in products
    ])

    prompt = f"""
Դու խանութի օնլայն կոնսուլտանտ ես։ Ահա թե ինչ է հարցրել հաճախորդը՝ "{user_question}"

Ահա թե ինչ ենք գտել
{product_info}

Պատասխանիր բարեհամբույթ, ասես թե դու կոնսուլտանտ ես և առաջարկիր ապրանքները։ Առանց ավելորդ ինֆորմացիայի։ Ուղարկիր հղումները։ Վերջում միայն նշիր՝ ունի արդյոք այլ հարցեր հաճախորդը։
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[OpenAI Error] {e}")
        return "Սխալ տեղի ունեցավ պատասխանը կազմելիս 😕"


start_message = "Ողջույն։ Ես MR Market-ի օնլայն խորհրդատուն եմ։ Ես կօգնեմ Ձեզ արագ գտնել ցանկալի ապրանքը։"


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, start_message)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_query = message.text.strip()
    extracted_name, armenian_name = extract_product_name(user_query)
    error, results = search_product(armenian_name)

    if error:
        bot.send_message(message.chat.id, error)
        return

    gpt_reply = generate_gpt_response(user_query, results)
    bot.send_message(message.chat.id, gpt_reply, parse_mode='Markdown')

    link = f"https://mrmarket.am/?s={armenian_name}&post_type=product"
    bot.send_message(message.chat.id, f"Այլ արդյունքների համար անցեք հետևյալ հղումով {link}")


print("Բոտը հաջողությամբ գործարկվել է։")
bot.polling()
