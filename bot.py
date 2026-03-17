import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import CallbackQueryHandler
from telegram import Update, ReplyKeyboardMarkup
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

ALBUM_FILE = "albums.json"

def load_data():
    try:
        with open(ALBUM_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(ALBUM_FILE, "w") as f:
        json.dump(data, f)

albums = load_data()
user_state = {}
current_album = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📁 Create Album"],
        ["📂 View Albums"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome to FlareVault 📸\n\nCreate and manage your albums easily:",
        reply_markup=reply_markup
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)
    text = update.message.text

    if text == "📁 Create Album":
        user_state[user] = "creating_album"
        await update.message.reply_text("Enter album name:")

    elif text == "📂 View Albums":
        await list_albums(update, context)


async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)
    text = update.message.text

    if user not in user_state:
        return

    state = user_state[user]

    if state == "creating_album":
        if user not in albums:
            albums[user] = {}

        albums[user][text] = []
        current_album[user] = text
        save_data(albums)

        await update.message.reply_text(f"Album '{text}' created and selected.")

    elif state == "using_album":
        if user in albums and text in albums[user]:
            current_album[user] = text
            await update.message.reply_text(f"Now using album: {text}")
        else:
            await update.message.reply_text("Album not found.")

    elif state == "deleting_album":
        if user in albums and text in albums[user]:
            del albums[user][text]
            save_data(albums)
            await update.message.reply_text(f"Album '{text}' deleted.")
        else:
            await update.message.reply_text("Album not found.")

    # Clear state after action
    user_state.pop(user)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)
    text = update.message.text

    # -------- BUTTON ACTIONS --------
    if text == "📁 Create Album":
        user_state[user] = "creating_album"
        await update.message.reply_text("Enter album name:")
        return

    elif text == "📂 View Albums":
        await list_albums(update, context)
        return

    # -------- STATE HANDLING --------
    if user in user_state:
        state = user_state[user]

        # CREATE
        if state == "creating_album":
            if user not in albums:
                albums[user] = {}

            albums[user][text] = []
            current_album[user] = text
            save_data(albums)

            await update.message.reply_text(f"Album '{text}' created and selected.")

        # USE
        elif state == "using_album":
            if user in albums and text in albums[user]:
                current_album[user] = text
                await update.message.reply_text(f"Now using album: {text}")
            else:
                await update.message.reply_text("Album not found.")

            user_state.pop(user)
            return
        # DELETE
        elif isinstance(state, dict) and state.get("action") == "confirm_delete":
            album_name = state.get("album")

            if text.upper() == "YES":
                if user in albums and album_name in albums[user]:
                    del albums[user][album_name]
                    save_data(albums)
                    await update.message.reply_text(f"Album '{album_name}' deleted ✅")
                else:
                    await update.message.reply_text("Album not found.")
            else:
                await update.message.reply_text("Deletion cancelled.")

            user_state.pop(user)
            return

        # REMOVE
        elif state.startswith("removing_"):
            album_name = state.split("_", 1)[1]

            if not text.isdigit():
                await update.message.reply_text("Please send a valid number (1, 2, 3...)")
                return

            index = int(text) - 1

            files = albums[user][album_name]

            if index < 0 or index >= len(files):
                await update.message.reply_text("Invalid number.")
            else:
                files.pop(index)
                save_data(albums)
                await update.message.reply_text("File removed successfully ✅")

        # CLEAR STATE AFTER ANY ACTION
        user_state.pop(user)

async def handle_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    print("Callback triggered:", query.data)

    user = str(query.from_user.id)

    data = query.data.split("|")
    action = data[0]

    # SAFETY: check if album exists in callback
    if len(data) < 2 and action != "removefile":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Something went wrong."
        )
        return

    # for normal actions
    if action != "removefile":
        album_name = data[1]

    # VIEW
    if action == "view":
        album_name = data[1]

        files = albums[user][album_name]

        for i, file_id in enumerate(files):
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Remove",
                        callback_data=f"removefile|{album_name}|{i}"
                    )
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=file_id,
                    reply_markup=reply_markup,
                    caption=f"File {i+1}"
                )
            except:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=file_id,
                    reply_markup=reply_markup,
                    caption=f"File {i+1}"
                )

    # ADD
    elif action == "add":
        album_name = data[1]

        current_album[user] = album_name
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"Now uploading to: {album_name}"
        )

    # DELETE
    elif action == "delete":
        album_name = data[1]
        user_state[user] = {
            "action": "confirm_delete",
            "album": album_name
        }

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"⚠️ Are you sure you want to delete '{album_name}'?\n\nType YES to confirm."
        )

    # REMOVE FILE
    elif action == "removefile":
        if len(data) < 3:
            await context.bot.send_message(chat_id=query.message.chat_id, text="Something went wrong.")
            return

        album_name = data[1]
        index = int(data[2])

        files = albums[user][album_name]

        if index < 0 or index >= len(files):
            await context.bot.send_message(chat_id=query.message.chat_id, text="Invalid file index.")
            return

        files.pop(index)
        save_data(albums)

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="File removed successfully ✅"
    )
async def create_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)
    album_name = " ".join(context.args)

    if not album_name:
        await update.message.reply_text("Usage: /create <album_name>")
        return

    if user not in albums:
        albums[user] = {}

    albums[user][album_name] = []
    current_album[user] = album_name

    save_data(albums)

    await update.message.reply_text(f"Album '{album_name}' created. Upload photos/videos now.")

async def list_albums(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)

    if user not in albums or not albums[user]:
        await update.message.reply_text("No albums yet.")
        return

    for album_name, files in albums[user].items():

        # show active album
        active_tag = ""
        if user in current_album and current_album[user] == album_name:
            active_tag = " (Active)"

        keyboard = [
    [
        InlineKeyboardButton("View", callback_data=f"view|{album_name}"),
        InlineKeyboardButton("Add", callback_data=f"add|{album_name}")
    ],
    [
        InlineKeyboardButton("Delete", callback_data=f"delete|{album_name}")
    ]
]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📁 {album_name}{active_tag}\n📦 {len(files)} files",
            reply_markup=reply_markup
        )
async def view_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)
    album_name = " ".join(context.args)

    files = albums[user][album_name]

    for file_id in files:
        try:
            await update.message.reply_photo(file_id)
        except:
            await update.message.reply_video(file_id)

async def save_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)

    # check if album selected
    if user not in current_album:
        await update.message.reply_text("Please select an album first.")
        return

    album = current_album[user]

    # detect file type
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.video:
        file_id = update.message.video.file_id
    else:
        return

    # store file
    albums[user][album].append(file_id)
    save_data(albums)

    count = len(albums[user][album])

    await update.message.reply_text(
        f"Saved to '{album}' ✅\n"
        f"📦 Total files: {count}\n\n"
        "Stored in Telegram cloud ☁️"
    )

async def remove_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /remove <album_name> <index>")
        return

    album_name = context.args[0]
    index = int(context.args[1]) - 1

    files = albums[user][album_name]

    if index < 0 or index >= len(files):
        await update.message.reply_text("Invalid index.")
        return

    removed = files.pop(index)

    save_data(albums)

    await update.message.reply_text("File removed from album.")

async def use_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)
    album_name = " ".join(context.args)

    current_album[user] = album_name

    await update.message.reply_text(f"Now uploading to album: {album_name}")

async def delete_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.message.from_user.id)
    album_name = " ".join(context.args)

    del albums[user][album_name]
    save_data(albums)

    await update.message.reply_text(f"Album '{album_name}' deleted.")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CallbackQueryHandler(handle_buttons_callback))
app.add_handler(CommandHandler("create", create_album))
app.add_handler(CommandHandler("albums", list_albums))
app.add_handler(CommandHandler("view", view_album))
app.add_handler(CommandHandler("remove", remove_media))
app.add_handler(CommandHandler("use", use_album))
app.add_handler(CommandHandler("delete", delete_album))

app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, save_media))

print("Bot running...")

app.run_polling()