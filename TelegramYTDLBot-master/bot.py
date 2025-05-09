import os
import telebot
import yt_dlp
import socket
import urllib3
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

# تنظیمات پایه
TOKEN = "8043273209:AAHYz7Wiabbz-ARgUN6dfaUnwoibybradyo"
DOWNLOAD_DIR = "downloads"
MAX_RETRIES = 3
TIMEOUT = 30

# تنظیمات پروکسی (برای کاربران ایرانی ضروری)
PROXY = {
    'http': 'http://185.199.229.156:7492',  # پروکسی رایگان نمونه
    'https': 'http://185.199.229.156:7492'
}

# ایجاد پوشه دانلود
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# تنظیمات yt-dlp
ydl_opts = {
    'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': TIMEOUT,
    'retries': MAX_RETRIES,
    'proxy': PROXY['http'],
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/'
    },
    'extract_flat': True,
    'force_ipv4': True,
    'ratelimit': 1000000,  # محدودیت سرعت دانلود (1MB/s)
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
executor = ThreadPoolExecutor(max_workers=4)

# دکوراتور مدیریت خطاها
def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except yt_dlp.DownloadError as e:
            if "HTTP Error 403" in str(e):
                return "⚠️ خطای دسترسی (403)\nلطفاً از VPN استفاده کنید"
            elif "HTTP Error 404" in str(e):
                return "❌ ویدیو یافت نشد (404)"
            return f"❌ خطای دانلود: {str(e)}"
        except (socket.timeout, urllib3.exceptions.TimeoutError):
            return "⏳ زمان اتصال به پایان رسید\nلطفاً دوباره تلاش کنید"
        except Exception as e:
            return f"❌ خطای غیرمنتظره: {str(e)}"
    return wrapper

@handle_errors
def download_video(url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # بررسی محدودیت‌ها
        if info.get('age_limit', 0) >= 18:
            return "🔞 این ویدیو محدودیت سنی دارد"
        
        if info.get('is_live', False):
            return "📡 ویدیوی زنده قابل دانلود نیست"
        
        # دانلود واقعی
        ydl.download([url])
        return info

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_msg = """
🎬 <b>ربات دانلود از یوتیوب</b>

🔹 لینک ویدیوی یوتیوب را ارسال کنید
🔹 حداکثر کیفیت: 720p
🔹 حداکثر حجم: 2GB

🛠 <i>پشتیبانی: @dev00111</i>
"""
    bot.reply_to(message, welcome_msg)

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    url = message.text.strip()
    
    # اعتبارسنجی لینک
    if not is_valid_url(url):
        bot.reply_to(message, "⚠️ لینک معتبر یوتیوب وارد کنید")
        return
    
    # ارسال پیام وضعیت
    status_msg = bot.reply_to(message, "🔍 در حال بررسی ویدیو...")
    
    # اجرای دانلود در پس‌زمینه
    def download_task():
        try:
            result = download_video(url)
            if isinstance(result, str):  # خطا
                bot.edit_message_text(result, message.chat.id, status_msg.message_id)
            else:  # موفق
                file_path = os.path.join(DOWNLOAD_DIR, f"{result['title']}.{result['ext']}")
                with open(file_path, 'rb') as f:
                    bot.send_video(
                        chat_id=message.chat.id,
                        video=f,
                        caption=f"🎬 {result['title']}\n🕒 مدت: {result.get('duration_string', '?')}",
                        reply_to_message_id=message.message_id
                    )
                os.remove(file_path)
        except Exception as e:
            bot.edit_message_text(f"❌ خطای سیستمی: {str(e)}", message.chat.id, status_msg.message_id)
    
    executor.submit(download_task)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and \
               any(d in result.netloc for d in ['youtube.com', 'youtu.be'])
    except:
        return False

if __name__ == '__main__':
    print("✅ ربات آماده به کار است...")
    bot.infinity_polling()
