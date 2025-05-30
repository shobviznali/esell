import telebot
import os
from dotenv import load_dotenv
from woocommerce import API
from openai import OpenAI

# Загружаем .env
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WC_URL = os.getenv("WOOCOMMERCE_URL")
WC_KEY = os.getenv("WOOCOMMERCE_CONSUMER_KEY")
WC_SECRET = os.getenv("WOOCOMMERCE_CONSUMER_SECRET")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# WooCommerce API
wcapi = API(
    url=WC_URL,
    consumer_key=WC_KEY,
    consumer_secret=WC_SECRET,
    version="wc/v3"
)

# Транслитерация с русского/английского на армянский
transliteration_map = {
    'a': ['ա'], 'b': ['բ'], 'g': ['գ'], 'd': ['դ'],
    'e': ['ե', 'է'], 'z': ['զ'], 't': ['տ', 'թ'], 'i': ['ի'],
    'l': ['լ'], 'kh': ['խ'], 'k': ['կ', 'ք'], 'h': ['հ'], 'j': ['ջ'],
    'sh': ['շ'], 'ch': ['չ', 'ճ'], 'zh': ['ժ'], 'x': ['խ', 'ղ'],
    'c': ['ց', 'ք', 'ծ'], 'm': ['մ'], 'y': ['յ'], 'n': ['ն'],
    'o': ['օ', 'ո'], 'p': ['պ', 'փ'], 'r': ['ր', 'ռ'], 's': ['ս'],
    'v': ['վ'], 'u': ['ու'], 'f': ['ֆ'], 'q': ['ք'], 'ev': ['և'],
    'ts': ['ց', 'ծ'], 'ye': ['ե'], 'gh': ['ղ'], 'vo': ['ո']
}

def transliterate_to_armenian(text):
    text = text.lower()
    result = ''

    i = 0
    while i < len(text):
        # Сначала двухбуквенные сочетания
        two_letter = text[i:i+2]
        if two_letter in transliteration_map:
            result += transliteration_map[two_letter][0]
            i += 2
            continue

        # Потом однобуквенные
        one_letter = text[i]
        if one_letter in transliteration_map:
            result += transliteration_map[one_letter][0]
        else:
            result += one_letter
        i += 1

    return result

# Поиск товара
def search_product(product_name):
    response = wcapi.get("products", params={"search": product_name})
    if response.status_code != 200:
        return "Ошибка при подключении к сайту 😕", []

    data = response.json()

    if not data:
        return f"Տվյալ ապրանքը `{product_name}` չի գտնվել 😕", []

    items = []
    for product in data[:3]:  # максимум 3 товара
        items.append({
            "name": product["name"],
            "price": product.get("price", "չի նշված"),
            "link": product.get("permalink", "")
        })

    return None, items

# Извлекаем название товара
def extract_product_name(user_input):
    prompt = f"""
Ты — ИИ, который помогает извлекать название товара из пользовательского сообщения.

Сообщение: "{user_input}"

Ответь только названием товара, которое нужно найти на сайте. 
Не добавляй ничего лишнего, только название.
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    extracted_name = response.choices[0].message.content.strip()
    armenian_name = transliterate_to_armenian(extracted_name)
    print(f"[GPT Extracted] '{extracted_name}' → [Armenian] '{armenian_name}'")
    return armenian_name

# Составляем ответ
def generate_gpt_response(user_question, products):
    product_info = "\n".join([
        f"{p['name']} — {p['price']} դրամ — {p['link']}"
        for p in products
    ])

    prompt = f"""
Դու խանութի օնլայն կոնսուլտանտ ես։ Ահա թե ինչ է հարցրել հաճախորդը "{user_question}"

Ահա թե ինչ ենք գտել
{product_info}

Պատասխանիր բարեհամբույթ, ասես թե դու կոնսուլտանտ ես և առաջարկիր ապրանքները։ Առանց ավելորդ ինֆորմացիայի։ Ուղարկիր հղումները։ Վերջում միայն նշիր՝ ունի արդյոք այլ հարցեր հաճախորդը։
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )

    return response.choices[0].message.content

# Обработка сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_query = message.text.strip()

    # Извлекаем и транслитерируем
    product_name = extract_product_name(user_query)

    # Поиск товара
    error, results = search_product(product_name)
    if error:
        bot.send_message(message.chat.id, error)
        return

    # GPT: формируем ответ
    gpt_reply = generate_gpt_response(user_query, results)
    bot.send_message(message.chat.id, gpt_reply, parse_mode='Markdown')

# Запуск
print("Бот с GPT и транслитерацией запущен")
bot.polling()
