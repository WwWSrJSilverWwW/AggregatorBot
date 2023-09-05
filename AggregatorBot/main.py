import os
import json
from build.base import DataBase
from PIL import Image
from random import randint
from datetime import datetime
from aiogram import Bot, Dispatcher, executor
from aiogram.types import ContentType
from telethon.sync import TelegramClient, events
from telethon.tl.types import InputChatUploadedPhoto
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import CreateChatRequest, EditChatPhotoRequest, DeleteChatUserRequest
from telethon.errors.rpcerrorlist import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_time():
    return datetime.now().strftime("* [%H:%M:%S] ")


def tprint(x):
    print(datetime.now().strftime("* [%H:%M:%S] ") + x)


button_hi = KeyboardButton('Привет! 👋')
greet_kb = ReplyKeyboardMarkup()
greet_kb.add(button_hi)

DEBUG = 0

MAX_CATS, MAX_CHANNELS = 2, 2
SESSION_NAME = "build/sessions/bot.session"
PHONE = os.getenv("BOT_AGGREGATOR_PHONE")
API_ID = int(os.getenv("BOT_AGGREGATOR_API_ID"))
API_HASH = os.getenv("BOT_AGGREGATOR_API_HASH")
TOKEN = os.getenv("BOT_AGGREGATOR_TOKEN")
BOT_ID = int(TOKEN.split(":")[0])

data = DataBase("build/data.db")
data.open()
with open("build/jsons/phrases.json", "r", encoding="utf-8") as f:
    phrases = json.load(f)

bot = Bot(TOKEN)
dp = Dispatcher(bot)
inline_lang = InlineKeyboardMarkup()
for key in list(phrases.keys()):
    inline_lang.add(InlineKeyboardButton(phrases[key]["NAME"], callback_data=key))

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
client.connect()
pass_needed = False
if not client.is_user_authorized():
    tprint("Session not found or outdated. You need to pass authorization")
    client.send_code_request(PHONE)
    while not client.is_user_authorized():
        try:
            client.sign_in(PHONE, input(get_time() + "Code: "))
        except PhoneCodeInvalidError:
            tprint("Wrong code! Try again")
        except SessionPasswordNeededError:
            tprint("Two-factor authentication is enabled")
            pass_needed = True
            break
    if pass_needed:
        while not client.is_user_authorized():
            try:
                client.sign_in(password=input(get_time() + "Password: "))
            except PasswordHashInvalidError:
                tprint("Wrong password! Try again")
client_id = str(client.get_me().id)
client.get_dialogs()


@client.on(events.NewMessage)
async def event_handler(event):
    if event.chat is not None and event.chat.id in [x[1] for x in data.select("channels").fetchall()]:
        await client.forward_messages(BOT_ID, event.to_dict()["message"])


@dp.callback_query_handler()
async def callback_query_handler(callback):
    if DEBUG == 0:
        data.update("users", language=callback.data, user_id=callback["from"]["id"])
        await bot.send_message(callback.message.chat.id, phrases[callback.data]["CHANGE_LANGUAGE"])


@dp.message_handler(content_types=ContentType.all())
async def message_handler(message):
    from_id = str(message.from_user.id)
    chat_id = str(message.chat.id)
    if from_id == client_id:
        if from_id == chat_id:
            for cat_id in str(data.select("channels", channel_id=str(message.forward_from_chat.id)[4:]).fetchone()[2]).split(";"):
                await bot.copy_message(data.select("categories", id=cat_id).fetchone()[1], client_id, message.message_id)
    else:
        if int(from_id) not in [x[1] for x in data.select("users").fetchall()]:
            data.insert(
                "users",
                user_id=from_id,
                is_bot="0" if message.from_user.is_bot else "1",
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                username=message.from_user.username,
                language=message.from_user.language_code,
                step="none",
                category_ids="",
                max_category="2",
                max_channel="2"
            )
        user_entity_data = data.select("users", user_id=from_id).fetchone()
        user_entity = {
            "id": user_entity_data[0],
            "user_id": user_entity_data[1],
            "is_bot": user_entity_data[2],
            "first_name": user_entity_data[3],
            "last_name": user_entity_data[4],
            "username": user_entity_data[5],
            "language": user_entity_data[6],
            "step": user_entity_data[7],
            "category_ids": user_entity_data[8],
            "max_category": user_entity_data[9],
            "max_channel": user_entity_data[10]
        }
        if DEBUG == 0:
            if int(chat_id) >= 0:
                if message.text == "/start" and user_entity["step"] == "none":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["START"])
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["BOT_HELP"])
                elif message.text == "/cat" and user_entity["step"] == "none":
                    if len(str(user_entity["category_ids"]).split(";")) == user_entity["max_category"]:
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["NO_SUB_CATS"], parse_mode="html")
                    else:
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["CATEGORY_STEP"])
                        data.update("users", step="cat", user_id=from_id)
                elif user_entity["step"] == "cat":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["CATEGORY_CREATING"])
                    ch = await client(CreateChatRequest(title=message.text, users=[message.from_user.id, BOT_ID]))
                    created_chat_id = ch.chats[0].id
                    img = Image.new("RGB", (500, 500), tuple([randint(0, 255) for _ in range(3)]))
                    img.save(f"build/temp_imgs/random-{chat_id}.jpg")
                    upload = await client.upload_file(file=f"build/temp_imgs/random-{chat_id}.jpg")
                    uploaded = InputChatUploadedPhoto(upload)
                    await client(EditChatPhotoRequest(chat_id=created_chat_id, photo=uploaded))
                    await bot.send_message(-created_chat_id, phrases[user_entity["language"]]["CATEGORY_START"])
                    await bot.send_message(-created_chat_id, phrases[user_entity["language"]]["CATEGORY_HELP"])
                    data.insert(
                        "categories",
                        category_id=str(-created_chat_id),
                        step="none",
                        user_ids=str(user_entity["id"]),
                        channel_ids=""
                    )
                    data.update("users", category_ids=(str(user_entity["category_ids"]) + ";" + str(data.select("categories", category_id=-created_chat_id).fetchone()[0])).strip(";"), user_id=from_id)
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["CATEGORY_SUCCESS"])
                    os.remove(f"build/temp_imgs/random-{chat_id}.jpg")
                    data.update("users", step="none", user_id=from_id)
                elif message.text == "/lang" and user_entity["step"] == "none":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["CHOOSE_LANGUAGE"], reply_markup=inline_lang)
                else:
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["BOT_HELP"])
            else:
                chat_entity = data.select("categories", category_id=chat_id).fetchone()
                if message.left_chat_member is not None:
                    new = str(user_entity["category_ids"]).split(";")
                    new.remove(str(chat_entity[0]))
                    data.update("users", category_ids=";".join(new), user_id=message.left_chat_member.id)
                    if len(str(chat_entity[3]).split(";")) == 1:
                        await client.delete_dialog(int(chat_id))
                        data.delete("categories", category_id=chat_id)
                        # ClearingChannels: if no any other chats with these channels -> unsubscribe from those channels
                    else:
                        new = str(chat_entity[3]).split(";")
                        new.remove(str(user_entity["id"]))
                        data.update("categories", user_ids=";".join(new), category_id=chat_id)
                elif len(message.new_chat_members) != 0:
                    for new_user in message.new_chat_members:
                        new_user_id = str(new_user.id)
                        if new_user_id not in data.select("users").fetchall():
                            data.insert(
                                "users",
                                user_id=new_user_id,
                                is_bot="0" if new_user.is_bot else "1",
                                first_name=new_user.first_name,
                                username=new_user.username,
                                step="none",
                                category_ids="",
                                language=new_user.language_code,
                                max_category="2",
                                max_channel="2"
                            )
                        new_user_entity = data.select("users", user_id=new_user_id).fetchone()
                        if len(str(chat_entity[4]).split(";")) > new_user_entity[8] or len(str(new_user_entity[5]).split(";")) == new_user_entity[7]:
                            await client(DeleteChatUserRequest(-int(chat_id), new_user.id, revoke_history=True))
                            await bot.send_message(chat_id, phrases[user_entity["language"]]["NO_SUB_NEW_USER"])
                        else:
                            data.update("users", category_ids=str(new_user_entity[5]) + ";" + str(chat_entity[0]))
                            data.update("categories", user_ids=str(chat_entity[3]) + ";" + str(new_user_entity[0]))
                            await bot.send_message(chat_id, phrases[user_entity["language"]]["HELLO_USER"].format(name=new_user.first_name))
                elif message.text == "/add" and chat_entity[2] == "none":
                    if min([x[10] for x in data.select("users").fetchall() if str(chat_entity[0]) in str(x[8]).split(";")]) == len(str(chat_entity[4]).split(";")):
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["NO_SUB_CHANNELS"], parse_mode="html")
                    else:
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_DEL_STEP"])
                        data.update("categories", step="add", category_id=chat_id)
                elif chat_entity[2] == "add":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_PROCESS"])
                    try:
                        await client(JoinChannelRequest(message.text))
                        channel_id = str((await client.get_entity(message.text)).id)
                        if int(channel_id) not in [x[1] for x in data.select("channels").fetchall()]:
                            data.insert(
                                "channels",
                                channel_id=channel_id,
                                category_ids=str(chat_entity[0])
                            )
                        if str(data.select("channels", channel_id=channel_id).fetchone()[0]) in str(chat_entity[4]).split(";"):
                            await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_STOP_ALREADY"])
                        else:
                            data.update("categories", channel_ids=(str(chat_entity[4]) + ";" + str(data.select("channels", channel_id=channel_id).fetchone()[0])).strip(";"), category_id=chat_id)
                            await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_SUCCESS"])
                    except ValueError:
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_DEL_STOP_NONE"] + " /add")
                    except TypeError:
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_DEL_STOP_NONE"] + " /add")
                    data.update("categories", step="none", category_id=chat_id)
                elif message.text == "/del" and chat_entity[2] == "none":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_DEL_STEP"])
                    data.update("categories", step="del", category_id=chat_id)
                elif chat_entity[2] == "del":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["DEL_PROCESS"])
                    try:
                        channel_id = str((await client.get_entity(message.text)).id)
                        channel_entity = data.select("channels", channel_id=channel_id).fetchone()
                        if str(data.select("channels", channel_id=channel_id).fetchone()[0]) in str(chat_entity[4]).split(";"):
                            new = str(chat_entity[4]).split(";")
                            new.remove(str(channel_entity[0]))
                            data.update("categories", channel_ids=";".join(new), category_id=chat_id)
                            if len(str(channel_entity[2]).split(";")) == 1:
                                data.delete("channels", channel_id=channel_id)
                                await client(LeaveChannelRequest(message.text))
                            else:
                                new = str(channel_entity[2])    .split(";")
                                new.remove(str(chat_entity[0]))
                                data.update("channels", category_ids=";".join(new), channel_id=channel_id)
                            await bot.send_message(chat_id, phrases[user_entity["language"]]["DEL_SUCCESS"])
                        else:
                            await bot.send_message(chat_id, phrases[user_entity["language"]]["DEL_STOP_ALREADY"])
                    except ValueError:
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_DEL_STOP_NONE"] + " /del")
                    except TypeError:
                        await bot.send_message(chat_id, phrases[user_entity["language"]]["ADD_DEL_STOP_NONE"] + " /del")
                    data.update("categories", step="none", category_id=chat_id)
                elif message.text == "/lang" and chat_entity[2] == "none":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["CHOOSE_LANGUAGE"], reply_markup=inline_lang)
                elif message.text == "/help" and chat_entity[2] == "none":
                    await bot.send_message(chat_id, phrases[user_entity["language"]]["CATEGORY_HELP"], reply_markup=greet_kb)
        elif DEBUG == 1:
            if message.text == "/start":
                await bot.send_message(chat_id, phrases[user_entity["language"]]["START"])
            await bot.send_message(chat_id, phrases[user_entity["language"]]["DEBUG_MODE_1"], parse_mode="markdown")
        elif DEBUG == 2:
            if message.text == "/start":
                await bot.send_message(chat_id, phrases[user_entity["language"]]["START"])
            await bot.send_message(chat_id, phrases[user_entity["language"]]["DEBUG_MODE_2"], parse_mode="markdown")


if __name__ == "__main__":
    if DEBUG == 2:
        tprint("Debug mode: FULLY ENABLED")
    elif DEBUG == 1:
        tprint("Debug mode: ENABLED ONLY CHANNELS")
    elif DEBUG == 0:
        tprint("Debug mode: DISABLED")
    tprint("Everything is loaded and launched successfully!")
    executor.start_polling(dp)
    data.close()
