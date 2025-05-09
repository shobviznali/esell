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
# OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# WooCommerce API
wcapi = API(
    url=WC_URL,
    consumer_key=WC_KEY,
    consumer_secret=WC_SECRET,
    version="wc/v3"
)

# Поиск товара
def search_product(product_name):
    response = wcapi.get("products", params={"search": product_name})
    if response.status_code != 200:
        return "Ошибка при подключении к сайту 😕", []

    data = response.json()

    if not data:
        return f"Товар '{product_name}' не найден 😕", []

    items = []
    for product in data[:3]:  # максимум 3 товара
        items.append({
            "name": product["name"],
            "price": product.get("price", "не указана"),
            "link": product.get("permalink", "")
        })

    print(items)
    return None, items

# GPT: Составляем красивый ответ

def extract_product_name(user_input):
    prompt = f"""
Ты — ИИ, который помогает извлекать название товара из пользовательского сообщения.

Сообщение: "{user_input}"

Ответь только одним словом или фразой — названием товара, которое нужно найти на сайте.
Не добавляй ничего лишнего, только название.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()

def generate_gpt_response(user_question, products):
    product_info = "\n".join([
        f"{p['name']} — {p['price']} драм — {p['link']}"
        for p in products
    ])

    prompt = f"""
Դու խանութի օնլայն կոնսուլտանտ ես։ Ահա թե ինչ է հարցրել հաճախորդը "{user_question}"

Ահա թե ինչ ենք գտել
{product_info}

Պատասխանիր բարեհամբույթ, ասես թե դու կոնսուլտանտ ես և առաջարկիր ապրանքները։ Առանաց ավելորդ ինֆորմացիայի։ Անպայման ուղարկիր հղումը։ Վերջում միայն նշիր, ունի արդյոք այլ հարցեր հաճախորդը
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

    # Сначала извлекаем товар
    product_name = extract_product_name(user_query)
    print(f"Ищу товар: {product_name}")

    # Потом ищем товар на сайте
    error, results = search_product(product_name)
    if error:
        bot.send_message(message.chat.id, error)
        return

    # GPT красиво отвечает
    gpt_reply = generate_gpt_response(user_query, results)
    bot.send_message(message.chat.id, gpt_reply, parse_mode='Markdown')

# Запуск
print("Бот с GPT запущен")
bot.polling()
