import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from dotenv import load_dotenv
from deeppavlov import build_model
from bs4 import BeautifulSoup
from urllib import request


def getHtmlDocument(url):
    """ Получаем html-документ с сайта по url. """
    fp = request.urlopen(url)
    mybytes = fp.read()
    fp.close()
    return mybytes.decode('utf8')


def getTextFromHtml(HtmlDocument):
    """ Получаем текст из html-документа. """
    soup = BeautifulSoup(HtmlDocument,
                         features='html.parser')
    content = soup.find('div', {'id': 'post-content-body'})
    return content.text


model = build_model('squad_ru_bert', download=True, install=True)

url = "https://habr.com/ru/articles/339914/"

text = getTextFromHtml(getHtmlDocument(url))

qa_mode = {}

logging.basicConfig(level=logging.INFO)
load_dotenv()
bot_token = os.getenv('TOKEN')
bot = Bot(token=bot_token)
dp = Dispatcher()

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Начать QA")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

qa_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Закончить")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,

)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Используемая статья: {url}\nПросто нажмите кнопку \"Начать QA\", чтобы включить режим вопрос-ответ:",
        reply_markup=start_keyboard)


@dp.message(lambda msg: msg.text == "Начать QA")
async def enable_qa_mode(message: types.Message):
    user_id = message.from_user.id
    qa_mode[user_id] = True
    await message.answer("Режим вопрос-ответ включен. Задавайте свои вопросы.", reply_markup=qa_keyboard)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)


@dp.message(lambda msg: msg.text == "Закончить")
async def disable_qa_mode(message: types.Message):
    user_id = message.from_user.id
    if qa_mode.get(user_id):
        qa_mode[user_id] = False
        await message.answer("Режим вопрос-ответ отключен.", reply_markup=start_keyboard)
    else:
        await message.answer("Режим вопрос-ответ уже был отключен.", reply_markup=start_keyboard)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    if qa_mode.get(user_id):
        message_to_del = await message.answer(f"Ищу ответ на ваш вопрос!")
        result = model([text], [message.text])

        if isinstance(result, list) and len(result) > 2:
            confidence = result[2][0]
            if isinstance(confidence, (float, int, str)):
                confidence = float(confidence)
                if abs(confidence - 1) < 1e-6:
                    answer = result[0]
                    if isinstance(answer, list):
                        answer = " ".join(answer)
                    if answer.strip():
                        await message.reply(
                            f"{answer}",
                            reply_markup=qa_keyboard
                        )
                    else:
                        await message.reply(
                            "Извините, я не нашёл ответа на ваш вопрос в предоставленном тексте.",
                            reply_markup=qa_keyboard
                        )
                else:
                    await message.reply(
                        "Извините, я не нашёл ответа на ваш вопрос в предоставленном тексте.",
                        reply_markup=qa_keyboard
                    )
            else:
                await message.reply(
                    "Ошибка: невозможно обработать метрику вероятности.",
                    reply_markup=qa_keyboard
                )
        else:
            await message.reply(
                "Ошибка: неожиданный формат ответа от модели.",
                reply_markup=qa_keyboard
            )
        await bot.delete_message(chat_id=message_to_del.chat.id, message_id=message_to_del.message_id)
    else:
        await message.reply(
            "Пожалуйста, нажмите \"Начать QA\" для включения режима вопрос-ответ.",
            reply_markup=start_keyboard
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
