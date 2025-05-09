import os
import telebot
import threading
from pytube import YouTube
from dotenv import load_dotenv
from queue import Queue
from urllib.parse import urlparse, parse_qs

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیم توکن ربات
TOKEN = ("8043273209:AAHYz7Wiabbz-ARgUN6dfaUnwoibybradyo")
if not TOKEN:
    raise ValueError("لطفا توکن ربات را در فایل .env تنظیم کنید")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# صف دانلود
download_queue = Queue()

def download_worker(bot, queue):
    """تابع کارگر برای پردازش صف دانلود"""
    while True:
        message, video_url, quality = queue.get()
        try:
            # دانلود ویدیو
            yt = YouTube(video_url)
            
            # انتخاب بهترین کیفیت موجود اگر کیفیت درخواستی موجود نباشد
            if quality == "high":
                stream = yt.streams.get_highest_resolution()
            elif quality == "low":
                stream = yt.streams.get_lowest_resolution()
            else:  # medium
                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            
            if not stream:
                bot.send_message(message.chat.id, "⚠️ کیفیت درخواستی یافت نشد. در حال دانلود با بهترین کیفیت موجود...")
                stream = yt.streams.get_highest_resolution()
            
            # دانلود ویدیو
            file_path = stream.download(output_path="downloads")
            
            # ارسال ویدیو به کاربر
            with open(file_path, 'rb') as video_file:
                bot.send_video(message.chat.id, video_file, caption=f"✅ {yt.title}\nکیفیت: {stream.resolution}")
            
            # حذف فایل موقت
            os.remove(file_path)
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در دانلود: {str(e)}")
        finally:
            queue.task_done()

# راه اندازی کارگر دانلود
download_thread = threading.Thread(target=download_worker, args=(bot, download_queue))
download_thread.daemon = True
download_thread.start()

def is_youtube_url(url):
    """بررسی معتبر بودن لینک یوتیوب"""
    parsed = urlparse(url)
    if parsed.hostname in ('youtube.com', 'www.youtube.com', 'youtu.be'):
        if parsed.hostname == 'youtu.be':
            return True
        if parsed.path == '/watch':
            query = parse_qs(parsed.query)
            if 'v' in query:
                return True
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """خوشآمدگویی به کاربر"""
    bot.reply_to(
        message, 
        "سلام، من یک ربات دانلود از یوتیوب هستم! 👋\n\n"
        "برای شروع کافیست لینک ویدیوی یوتیوب را برای من بفرستید."
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    """ارسال راهنمای استفاده"""
    bot.reply_to(
        message,
        """
<b>راهنمای استفاده:</b>
1. لینک ویدیوی یوتیوب را برای من بفرستید
2. کیفیت مورد نظر را انتخاب کنید
3. منتظر بمانید تا ویدیو دانلود شود

<i>توسعه دهنده: @dev00111
کد منبع: <a href="https://github.com/hansanaD/TelegramYTDLBot">TelegramYTDLBot</a></i>
        """, 
        disable_web_page_preview=True
    )

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    """پردازش لینک دریافتی"""
    if is_youtube_url(message.text):
        # ایجاد منوی انتخاب کیفیت
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("کیفیت پایین", callback_data=f"low#{message.text}"),
            telebot.types.InlineKeyboardButton("کیفیت متوسط", callback_data=f"medium#{message.text}")
        )
        markup.row(telebot.types.InlineKeyboardButton("کیفیت بالا", callback_data=f"high#{message.text}"))
        
        bot.send_message(
            message.chat.id,
            "لطفاً کیفیت مورد نظر را انتخاب کنید:",
            reply_markup=markup
        )
    else:
        bot.reply_to(message, "⚠️ لطفاً یک لینک معتبر یوتیوب ارسال کنید.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """پردازش انتخاب کیفیت توسط کاربر"""
    try:
        quality, video_url = call.data.split('#')
        bot.answer_callback_query(call.id, f"کیفیت {quality} انتخاب شد.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        # اضافه کردن به صف دانلود
        download_queue.put((call.message, video_url, quality))
        queue_size = download_queue.qsize()
        
        if queue_size == 1:
            bot.send_message(call.message.chat.id, "دانلود شروع شد...")
        else:
            bot.send_message(call.message.chat.id, f"دانلود شما در صف قرار گرفت. موقعیت: #{queue_size}")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"خطا: {str(e)}")

# ایجاد پوشه دانلود اگر وجود نداشته باشد
if not os.path.exists("downloads"):
    os.makedirs("downloads")

print("ربات در حال اجراست...")
bot.infinity_polling()
