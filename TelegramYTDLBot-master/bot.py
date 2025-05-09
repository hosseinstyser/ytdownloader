import os
import telebot
import threading
import yt_dlp
from queue import Queue
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیم توکن ربات
TOKEN = ("8043273209:AAHYz7Wiabbz-ARgUN6dfaUnwoibybradyo")
if not TOKEN:
    raise ValueError("لطفا توکن ربات را در فایل .env تنظیم کنید")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# صف دانلود
download_queue = Queue()

def select_format(quality):
    """انتخاب فرمت بر اساس کیفیت درخواستی"""
    quality_map = {
        'low': 'worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst',
        'medium': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best',
        'high': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    }
    return quality_map.get(quality, 'best')

def download_worker(bot, queue):
    """تابع کارگر برای پردازش صف دانلود"""
    while True:
        message, video_url, quality = queue.get()
        try:
            ydl_opts = {
                'proxy': 'http://127.0.0.1:8080',
                'format': select_format(quality),
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True,
                'noplaylist': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                file_path = ydl.prepare_filename(info)
                ydl.download([video_url])

                # ارسال ویدیو به کاربر
                with open(file_path, 'rb') as video_file:
                    bot.send_video(
                        chat_id=message.chat.id,
                        video=video_file,
                        caption=f"🎬 {info['title']}\n"
                                f"📊 کیفیت: {quality}\n"
                                f"⏳ مدت: {info['duration_string']}",
                        supports_streaming=True
                    )

                # حذف فایل موقت
                os.remove(file_path)

        except yt_dlp.DownloadError as e:
            error_msg = f"❌ خطا در دانلود:\n{str(e)}"
            if "HTTP Error 400" in str(e):
                error_msg += "\n\n⚠️ لطفا از VPN استفاده کنید یا دوباره امتحان کنید."
            bot.send_message(message.chat.id, error_msg)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطای غیرمنتظره:\n{str(e)}")
        finally:
            queue.task_done()

# راه اندازی کارگر دانلود
download_thread = threading.Thread(target=download_worker, args=(bot, download_queue))
download_thread.daemon = True
download_thread.start()

def is_youtube_url(url):
    """بررسی معتبر بودن لینک یوتیوب"""
    domains = ('youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com')
    try:
        parsed = urlparse(url)
        if parsed.hostname.replace('www.', '') in domains:
            if parsed.hostname == 'youtu.be':
                return True
            if parsed.path == '/watch':
                query = parse_qs(parsed.query)
                if 'v' in query:
                    return True
            return True
        return False
    except:
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """خوشآمدگویی به کاربر"""
    welcome_text = (
        "سلام! 👋\n"
        "من ربات دانلود از یوتیوب هستم.\n\n"
        "کافیست لینک ویدیوی یوتیوب را برای من بفرستید تا آن را برای شما دانلود کنم.\n\n"
        "برای اطلاعات بیشتر /help را بفرستید."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def send_help(message):
    """ارسال راهنمای استفاده"""
    help_text = (
        "📚 راهنمای استفاده:\n\n"
        "1. لینک ویدیوی یوتیوب را برای من بفرستید\n"
        "2. کیفیت مورد نظر را انتخاب کنید\n"
        "3. منتظر بمانید تا ویدیو برای شما ارسال شود\n\n"
        "⚙️ کیفیت‌های موجود:\n"
        "- کیفیت پایین (سریعتر)\n"
        "- کیفیت متوسط (تعادلی)\n"
        "- کیفیت بالا (بهترین کیفیت)\n\n"
        "🔧 در صورت بروز مشکل از دستور /support استفاده کنید\n\n"
        "<i>توسعه دهنده: @dev00111\n"
        "کد منبع: <a href='https://github.com/hansanaD/TelegramYTDLBot'>GitHub</a></i>"
    )
    bot.reply_to(message, help_text, disable_web_page_preview=True)

@bot.message_handler(commands=['support'])
def send_support(message):
    """ارسال اطلاعات پشتیبانی"""
    support_text = (
        "🛠 پشتیبانی فنی:\n\n"
        "اگر با خطایی مواجه شدید:\n"
        "1. از صحیح بودن لینک مطمئن شوید\n"
        "2. با VPN امتحان کنید\n"
        "3. کیفیت دیگری را انتخاب کنید\n\n"
        "اگر مشکل persist داشت، به آیدی @dev00111 پیام دهید."
    )
    bot.reply_to(message, support_text)

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    """پردازش لینک دریافتی"""
    if is_youtube_url(message.text):
        # ایجاد منوی انتخاب کیفیت
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("کیفیت پایین 🐢", callback_data=f"low#{message.text}"),
            telebot.types.InlineKeyboardButton("کیفیت متوسط 🚶", callback_data=f"medium#{message.text}")
        )
        markup.row(telebot.types.InlineKeyboardButton("کیفیت بالا 🚀", callback_data=f"high#{message.text}"))
        
        bot.send_message(
            message.chat.id,
            "لطفاً کیفیت مورد نظر را انتخاب کنید:",
            reply_markup=markup
        )
    else:
        bot.reply_to(message, "⚠️ لطفاً یک لینک معتبر یوتیوب ارسال کنید.\nمثال:\nhttps://youtu.be/dQw4w9WgXcQ")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """پردازش انتخاب کیفیت توسط کاربر"""
    try:
        quality, video_url = call.data.split('#')
        quality_names = {
            'low': 'پایین',
            'medium': 'متوسط',
            'high': 'بالا'
        }
        
        bot.answer_callback_query(call.id, f"کیفیت {quality_names[quality]} انتخاب شد")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        # اضافه کردن به صف دانلود
        download_queue.put((call.message, video_url, quality))
        queue_size = download_queue.qsize()
        
        if queue_size == 1:
            status_msg = "⏳ دانلود شروع شد... لطفا صبر کنید"
        else:
            status_msg = f"⏳ دانلود شما در صف قرار گرفت. موقعیت: #{queue_size}"
            
        bot.send_message(call.message.chat.id, status_msg)
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ خطا در پردازش درخواست:\n{str(e)}")

# ایجاد پوشه دانلود اگر وجود نداشته باشد
if not os.path.exists("downloads"):
    os.makedirs("downloads")

print("✅ ربات آماده به کار است...")
bot.infinity_polling()
