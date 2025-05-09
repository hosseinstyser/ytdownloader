import os
import telebot
import threading
import yt_dlp
from queue import Queue
from urllib.parse import urlparse, parse_qs

# تنظیمات اولیه
TOKEN = "8043273209:AAHYz7Wiabbz-ARgUN6dfaUnwoibybradyo"
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 2000 * 1024 * 1024  # حداکثر حجم فایل: 2GB

# ایجاد پوشه دانلود اگر وجود نداشته باشد
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# تنظیمات yt-dlp برای جلوگیری از خطاهای 403
ydl_opts_base = {
    'quiet': True,
    'no_warnings': True,
    'restrictfilenames': True,
    'noplaylist': True,
    'socket_timeout': 30,
    'retries': 10,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    },
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
download_queue = Queue()

def get_video_info(video_url):
    """دریافت اطلاعات ویدیو بدون دانلود"""
    with yt_dlp.YoutubeDL(ydl_opts_base) as ydl:
        try:
            return ydl.extract_info(video_url, download=False)
        except Exception as e:
            raise Exception(f"خطا در دریافت اطلاعات ویدیو: {str(e)}")

def download_video(video_url, quality):
    """دانلود ویدیو با کیفیت مشخص"""
    ydl_opts = ydl_opts_base.copy()
    
    # تنظیم کیفیت
    if quality == 'low':
        ydl_opts['format'] = 'worst[height<=360][ext=mp4]'
    elif quality == 'medium':
        ydl_opts['format'] = 'best[height<=720][ext=mp4]'
    else:  # high
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'
    
    # محدودیت حجم فایل
    ydl_opts['max_filesize'] = MAX_FILE_SIZE
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
            file_path = ydl.prepare_filename(info)
            ydl.download([video_url])
            return file_path, info
        except yt_dlp.DownloadError as e:
            if "HTTP Error 403" in str(e):
                raise Exception("خطای دسترسی (403) - ممکن است نیاز به VPN داشته باشید")
            raise Exception(f"خطا در دانلود: {str(e)}")

def download_worker():
    """پردازشگر صف دانلود"""
    while True:
        message, video_url, quality = download_queue.get()
        try:
            file_path, info = download_video(video_url, quality)
            
            # ارسال ویدیو
            with open(file_path, 'rb') as video_file:
                bot.send_video(
                    chat_id=message.chat.id,
                    video=video_file,
                    caption=f"🎬 {info['title']}\n"
                           f"🕒 مدت: {info.get('duration_string', 'نامعلوم')}\n"
                           f"📊 کیفیت: {quality}",
                    supports_streaming=True,
                    timeout=300
                )
            
            # حذف فایل موقت
            os.remove(file_path)
            
        except Exception as e:
            error_msg = f"❌ خطا در پردازش درخواست:\n{str(e)}"
            if "HTTP Error" in str(e):
                error_msg += "\n\n🔧 راهکار:\n1. از VPN استفاده کنید\n2. لینک را بررسی کنید\n3. دوباره امتحان کنید"
            bot.send_message(message.chat.id, error_msg)
        finally:
            download_queue.task_done()

# راه اندازی کارگر دانلود
threading.Thread(target=download_worker, daemon=True).start()

def is_youtube_url(url):
    """بررسی اعتبار لینک یوتیوب"""
    try:
        domains = ('youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com')
        parsed = urlparse(url)
        if any(domain in parsed.netloc for domain in domains):
            return True
        return False
    except:
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """پیام خوشآمدگویی"""
    bot.reply_to(message, 
        "🤖 ربات دانلود از یوتیوب\n\n"
        "لینک ویدیوی یوتیوب را برای من بفرستید\n\n"
        "برای راهنمایی /help را بفرستید")

@bot.message_handler(commands=['help'])
def send_help(message):
    """راهنمای استفاده"""
    bot.reply_to(message,
        "📚 راهنمای استفاده:\n\n"
        "1. لینک ویدیو را ارسال کنید\n"
        "2. کیفیت مورد نظر را انتخاب کنید\n"
        "3. منتظر بمانید تا ویدیو ارسال شود\n\n"
        "⚙️ کیفیت‌های قابل انتخاب:\n"
        "- کیفیت پایین (سریع)\n"
        "- کیفیت متوسط (متوازن)\n"
        "- کیفیت بالا (بهترین)\n\n"
        "⚠️ توجه: ویدیوهای بیش از 2GB دانلود نمی‌شوند",
        disable_web_page_preview=True)

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    """پردازش لینک دریافتی"""
    if not is_youtube_url(message.text):
        bot.reply_to(message, "⚠️ لطفاً یک لینک معتبر یوتیوب ارسال کنید")
        return
    
    try:
        # بررسی اولیه ویدیو
        info = get_video_info(message.text)
        if info.get('filesize_approx', 0) > MAX_FILE_SIZE:
            bot.reply_to(message, "⚠️ حجم ویدیو بیش از حد مجاز (2GB) است")
            return
        
        # ایجاد منوی کیفیت
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("کیفیت پایین", callback_data=f"low#{message.text}"),
            telebot.types.InlineKeyboardButton("کیفیت متوسط", callback_data=f"medium#{message.text}")
        )
        markup.row(telebot.types.InlineKeyboardButton("کیفیت بالا", callback_data=f"high#{message.text}"))
        
        bot.send_message(
            message.chat.id,
            f"📹 {info['title']}\n"
            f"🕒 مدت: {info.get('duration_string', 'نامعلوم')}\n\n"
            "لطفاً کیفیت مورد نظر را انتخاب کنید:",
            reply_markup=markup
        )
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {str(e)}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """پردازش انتخاب کیفیت"""
    try:
        quality, video_url = call.data.split('#')
        bot.answer_callback_query(call.id, "در حال پردازش...")
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        # اضافه به صف دانلود
        download_queue.put((call.message, video_url, quality))
        queue_size = download_queue.qsize()
        
        if queue_size == 1:
            bot.send_message(call.message.chat.id, "⏳ دانلود شروع شد...")
        else:
            bot.send_message(call.message.chat.id, f"⏳ در صف دانلود: موقعیت #{queue_size}")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ خطا: {str(e)}")

print("✅ ربات آماده به کار است...")
bot.infinity_polling()
