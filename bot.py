# bot.py

import os
from telegram import Update, Document
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)

ASK_VCF_COUNT, ASK_CONTACTS_PER_FILE, ASK_CONTACT_NAME_BASE, ASK_FILE_NAME_BASE, PROCESS_FILE = range(5)
user_data_temp = {}
bot_active = True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if not bot_active:
        await update.message.reply_text("🤖 Bot is currently stopped. Use /startbot to activate.")
        return ConversationHandler.END

    user_data_temp.pop(update.effective_user.id, None)
    await update.message.reply_text("👋 Send a `.txt` file with phone numbers (one per line).")
    return PROCESS_FILE

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if not bot_active:
        return

    document: Document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Only .txt files are supported.")
        return ConversationHandler.END

    file_path = f"{update.effective_user.id}_numbers.txt"
    new_file = await context.bot.get_file(document.file_id)
    await new_file.download_to_drive(file_path)

    with open(file_path, 'r') as f:
        numbers = [line.strip() for line in f if line.strip()]

    user_data_temp[update.effective_user.id] = {
        "file_path": file_path,
        "numbers": numbers
    }

    await update.message.reply_text("📦 How many VCF files would you like?")
    return ASK_VCF_COUNT

async def ask_vcf_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return ASK_VCF_COUNT

    user_data_temp[update.effective_user.id]["vcf_count"] = count
    await update.message.reply_text("🔢 How many numbers in each VCF file?")
    return ASK_CONTACTS_PER_FILE

async def ask_contacts_per_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        per_file = int(update.message.text)
        if per_file <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return ASK_CONTACTS_PER_FILE

    data = user_data_temp[update.effective_user.id]
    total = len(data["numbers"])
    expected = per_file * data["vcf_count"]

    if total != expected:
        await update.message.reply_text(
            f"❌ Mismatch: {total} numbers uploaded, but {data['vcf_count']} × {per_file} = {expected}.\nFix and try again."
        )
        return ASK_CONTACTS_PER_FILE

    data["contacts_per_file"] = per_file
    await update.message.reply_text("🧍 Enter a contact name prefix (e.g., Client):")
    return ASK_CONTACT_NAME_BASE

async def ask_contact_name_base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_temp[update.effective_user.id]["contact_name_base"] = update.message.text.strip()
    await update.message.reply_text("📁 Enter base file name for VCF files (e.g., contacts):")
    return ASK_FILE_NAME_BASE

async def ask_file_name_base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = user_data_temp[update.effective_user.id]
    user_input["file_name_base"] = update.message.text.strip()

    files = generate_vcf_files(user_input)
    for path in files:
        with open(path, 'rb') as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f)

    await update.message.reply_text("✅ VCF files generated successfully.")
    return ConversationHandler.END

def generate_vcf_files(data):
    numbers = data["numbers"]
    vcf_count = data["vcf_count"]
    per_file = data["contacts_per_file"]
    prefix = data["contact_name_base"]
    base = data["file_name_base"]

    vcf_files = []
    index = 0
    for i in range(vcf_count):
        filename = f"{base}_{i+1}.vcf"
        with open(filename, 'w') as f:
            for j in range(per_file):
                f.write("BEGIN:VCARD\n")
                f.write("VERSION:3.0\n")
                f.write(f"FN:{prefix} {index + 1}\n")
                f.write(f"TEL;TYPE=CELL:{numbers[index]}\n")
                f.write("END:VCARD\n\n")
                index += 1
        vcf_files.append(filename)
    return vcf_files

async def startbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    bot_active = True
    await update.message.reply_text("✅ Bot is now active!")

async def stopbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    bot_active = False
    await update.message.reply_text("⏸️ Bot is now paused. Use /startbot to reactivate.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled. Use /start to restart.")
    return ConversationHandler.END

def main():
    import logging
    logging.basicConfig(level=logging.INFO)

    TOKEN = os.environ.get("TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PROCESS_FILE: [MessageHandler(filters.Document.ALL, file_handler)],
            ASK_VCF_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_vcf_count)],
            ASK_CONTACTS_PER_FILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_contacts_per_file)],
            ASK_CONTACT_NAME_BASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_contact_name_base)],
            ASK_FILE_NAME_BASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_file_name_base)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('start', start),
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('startbot', startbot))
    app.add_handler(CommandHandler('stopbot', stopbot))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
