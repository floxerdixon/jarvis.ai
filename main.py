import os
import sys
import asyncio
import subprocess
import tempfile
import re
import urllib.request

# --- Renk kodları (terminal) ---
CYAN  = "\033[96m"
GREEN = "\033[92m"
YELLOW= "\033[93m"
RED   = "\033[91m"
RESET = "\033[0m"
BOLD  = "\033[1m"

def banner():
    print(f"""
{CYAN}{BOLD}
   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
   ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
   ██║███████║██████╔╝██║   ██║██║███████╗
██ ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
{RESET}
{CYAN}   Ücretsiz Yapay Zeka Asistanı — Groq + Resim{RESET}
{YELLOW}   Çıkmak: 'quit' | Ses: 'ses aç' | Resim: 'resim yap: ...' {RESET}
""")

def check_packages():
    packages = {
        "groq": "groq",
        "duckduckgo_search": "duckduckgo-search",
        "sympy": "sympy",
        "edge_tts": "edge-tts",
        "dotenv": "python-dotenv",
        "PIL": "Pillow",
    }
    missing = []
    for module, package in packages.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    if missing:
        print(f"{YELLOW}Eksik paketler yükleniyor: {', '.join(missing)}{RESET}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{GREEN}✓ Paketler yüklendi{RESET}")

check_packages()

from groq import Groq
from duckduckgo_search import DDGS
from sympy import solve, sympify
import edge_tts
import speech_recognition as sr

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# --- API Anahtarı ---
API_KEY = os.getenv("GROQ_API_KEY", "")
if not API_KEY:
    print(f"\n{YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{BOLD}Groq API Anahtarı Gerekli{RESET}")
    print(f"1. {CYAN}https://console.groq.com{RESET} adresine git")
    print(f"2. Ücretsiz hesap aç (kart gerekmez!)")
    print(f"3. 'API Keys' → 'Create API Key' → kopyala")
    print(f"{YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}\n")
    API_KEY = input(f"{GREEN}API anahtarını buraya yapıştır: {RESET}").strip()
    if API_KEY:
        with open(".env", "a") as f:
            f.write(f"\nGROQ_API_KEY={API_KEY}\n")
        print(f"{GREEN}✓ Kaydedildi!{RESET}\n")

client = Groq(api_key=API_KEY)

sesli_mod = False
konusma_gecmisi = []

SISTEM_MESAJI = """Sen Jarvis'sin — zeki, hızlı ve yardımcı bir Türkçe yapay zeka asistanısın.
Soruları net ve anlaşılır yanıtla. Matematik problemlerini adım adım çöz. Kısa ve öz ol. Türkçe konuş."""

# --- Web Arama ---
def web_ara(sorgu, max_sonuc=3):
    try:
        print(f"  {YELLOW}🌐 Web'de aranıyor...{RESET}")
        with DDGS() as ddgs:
            sonuclar = list(ddgs.text(sorgu, max_results=max_sonuc))
        if not sonuclar:
            return "Web araması sonuç vermedi."
        metin = f"Web arama sonuçları:\n\n"
        for i, s in enumerate(sonuclar, 1):
            metin += f"{i}. {s.get('title','')}\n{s.get('body','')}\n\n"
        return metin
    except Exception as e:
        return f"Web araması başarısız: {e}"

# --- Matematik ---
def matematik_coz(ifade):
    try:
        if "=" in ifade:
            taraflar = ifade.split("=")
            sol = sympify(taraflar[0].strip())
            sag = sympify(taraflar[1].strip())
            degiskenler = list(sol.free_symbols | sag.free_symbols)
            if degiskenler:
                cozum = solve(sol - sag, degiskenler[0])
                return f"Çözüm: {degiskenler[0]} = {cozum}"
        else:
            sonuc = sympify(ifade)
            return f"Sonuç: {float(sonuc):.6g}"
    except Exception as e:
        return f"Matematik hatası: {e}"

# --- Türkçe → İngilizce Çeviri (Groq ile) ---
def turkce_ingilizce_cevir(metin):
    try:
        yanit = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Translate the following Turkish text to English. Only return the translation, nothing else."},
                {"role": "user", "content": metin}
            ],
            max_tokens=200,
            temperature=0.3,
        )
        return yanit.choices[0].message.content.strip()
    except:
        return metin

# --- Resim Yapma (Pollinations AI - Ücretsiz & Sınırsız) ---
def resim_yap(prompt):
    import urllib.parse
    import urllib.request
    import time

    # Türkçe mi kontrol et, İngilizceye çevir
    turkce_harfler = set("çğışöüÇĞİŞÖÜ")
    if any(h in prompt for h in turkce_harfler) or any(w in prompt.lower() for w in ["bir", "ve", "ile", "olan", "gece", "gündüz", "dağ", "deniz", "şehir"]):
        print(f"  {YELLOW}🌍 Türkçe prompt İngilizceye çevriliyor...{RESET}")
        prompt_en = turkce_ingilizce_cevir(prompt)
        print(f"  {GREEN}✓ Çeviri: {prompt_en}{RESET}")
    else:
        prompt_en = prompt

    print(f"  {YELLOW}🎨 Resim yapılıyor: {prompt_en}{RESET}")

    prompt_enc = urllib.parse.quote(prompt_en)
    seed = int(time.time())

    urls = [
        f"https://image.pollinations.ai/prompt/{prompt_enc}?seed={seed}&width=1024&height=1024&nologo=true",
        f"https://image.pollinations.ai/prompt/{prompt_enc}?seed={seed}&width=512&height=512",
    ]

    # Tarz seç
    print(f"\n  {CYAN}🎨 Resim tarzı seç:{RESET}")
    print(f"  1. Gerçekçi fotoğraf (photorealistic)")
    print(f"  2. Anime / çizgi film")
    print(f"  3. Sanatsal / yağlı boya")
    print(f"  4. Bilim kurgu / fantezi")
    print(f"  5. Tarz yok (sade)")
    tarz = input(f"  Tarz (1-5, Enter=Gerçekçi): ").strip()

    tarz_ekler = {
        "1": "photorealistic, ultra detailed, 8k, professional photography, sharp focus",
        "2": "anime style, manga, vibrant colors, detailed illustration",
        "3": "oil painting, artistic, masterpiece, detailed brushwork, fine art",
        "4": "sci-fi, fantasy, cinematic, epic, detailed, dramatic lighting",
        "5": ""
    }
    tarz_str = tarz_ekler.get(tarz, tarz_ekler["1"])
    if tarz_str:
        prompt_en = f"{prompt_en}, {tarz_str}"

    # Kayıt yeri sor
    print(f"\n  {CYAN}📁 Resmi nereye kaydetmek istersin?{RESET}")
    print(f"  1. Masaüstü (varsayılan)")
    print(f"  2. Belgeler")
    print(f"  3. İndirilenler")
    print(f"  4. Bu klasör (jarvis claude)")
    secim = input(f"  Seçim (1-4, Enter=Masaüstü): ").strip()

    if secim == "2":
        klasor = os.path.join(os.path.expanduser("~"), "Documents")
    elif secim == "3":
        klasor = os.path.join(os.path.expanduser("~"), "Downloads")
    elif secim == "4":
        klasor = os.getcwd()
    else:
        klasor = os.path.join(os.path.expanduser("~"), "Desktop")

    os.makedirs(klasor, exist_ok=True)
    dosya_adi = os.path.join(klasor, f"jarvis_resim_{seed}.jpg")

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                with open(dosya_adi, "wb") as f:
                    f.write(r.read())

            if os.path.getsize(dosya_adi) > 1000:
                if sys.platform == "win32":
                    os.startfile(dosya_adi)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", dosya_adi])
                else:
                    subprocess.Popen(["xdg-open", dosya_adi])
                return f"✓ Resim yapıldı!\n  📁 Kaydedildi: {dosya_adi}"
        except Exception:
            continue

    return f"Resim yapılamadı. Tarayıcıda şu adresi aç:\nhttps://image.pollinations.ai/prompt/{prompt_enc}"

# --- Wake Word Dinleme (Hey Jarvis) ---
def wake_word_dinle():
    taniyici = sr.Recognizer()
    try:
        with sr.Microphone(device_index=5) as kaynak:
            taniyici.adjust_for_ambient_noise(kaynak, duration=0.3)
            ses = taniyici.listen(kaynak, timeout=5, phrase_time_limit=4)
        metin = taniyici.recognize_google(ses, language="tr-TR").lower()
        if any(w in metin for w in ["hey jarvis", "jarvis", "hey jarwis", "merhaba jarvis"]):
            return True
        return False
    except:
        return False

# --- Mikrofon Dinleme ---
def mikrofon_dinle():
    taniyici = sr.Recognizer()
    try:
        with sr.Microphone(device_index=5) as kaynak:
            print(f"  {CYAN}🎤 Dinliyorum... (konuş){RESET}", end="\r")
            taniyici.adjust_for_ambient_noise(kaynak, duration=0.5)
            ses = taniyici.listen(kaynak, timeout=8, phrase_time_limit=15)
        print(f"  {'':40}", end="\r")
        metin = taniyici.recognize_google(ses, language="tr-TR")
        print(f"  {GREEN}🎤 Sen (sesli): {metin}{RESET}")
        return metin
    except sr.WaitTimeoutError:
        print(f"  {YELLOW}Ses algılanamadı, tekrar dene.{RESET}    ")
        return None
    except sr.UnknownValueError:
        print(f"  {YELLOW}Anlaşılamadı, tekrar dene.{RESET}    ")
        return None
    except Exception as e:
        print(f"  {RED}Mikrofon hatası: {e}{RESET}    ")
        return None

# --- Sesli Yanıt ---
async def sesli_oku(metin):
    try:
        temiz = re.sub(r'[*#`]', '', metin)[:500]
        iletisim = edge_tts.Communicate(temiz, voice="tr-TR-AhmetNeural")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            dosya = f.name
        await iletisim.save(dosya)
        if sys.platform == "win32":
            os.startfile(dosya)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", dosya])
        else:
            subprocess.Popen(["mpg123", dosya], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"  {RED}Ses hatası: {e}{RESET}")
        return False

# --- Ana Yanıt Motoru ---
def jarvis_yanit(kullanici_mesaji):
    global konusma_gecmisi
    mesaj_lower = kullanici_mesaji.lower()

    web_tetik = ["ara ", "araştır", "internette", "web'de", "güncel", "haber", "ne zaman", "kim ", "nerede"]
    matematik_tetik = ["hesapla", "çöz", "=", "denklem", "integral", "türev"]

    ek_bilgi = ""
    if any(t in mesaj_lower for t in web_tetik):
        ek_bilgi = web_ara(kullanici_mesaji)
    elif any(t in mesaj_lower for t in matematik_tetik):
        mat_sonuc = matematik_coz(kullanici_mesaji)
        if "hata" not in mat_sonuc.lower():
            ek_bilgi = f"Matematiksel hesaplama: {mat_sonuc}"

    konusma_gecmisi.append({"role": "user", "content": kullanici_mesaji})
    if ek_bilgi:
        konusma_gecmisi[-1]["content"] += f"\n\n[Ek bilgi]: {ek_bilgi}"

    gecmis_kismi = konusma_gecmisi[-10:]
    yanit = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # Hızlı model
        messages=[{"role": "system", "content": SISTEM_MESAJI}] + gecmis_kismi,
        temperature=0.7,
        max_tokens=1024,
    )
    asistan_yanit = yanit.choices[0].message.content
    konusma_gecmisi.append({"role": "assistant", "content": asistan_yanit})
    return asistan_yanit

# --- Ana Döngü ---
def main():
    global sesli_mod
    import urllib.parse

    live_mod = False

    banner()
    print(f"{GREEN}Jarvis hazır!{RESET}\n")
    print(f"{YELLOW}İpuçları:{RESET}")
    print(f"  • 'live mod' → 'Hey Jarvis' deyince uyanır")
    print(f"  • 'ses aç' → Jarvis seni dinler ve sesli yanıtlar")
    print(f"  • 'İstanbul hava durumu ara' → web'de arar")
    print(f"  • '2x + 5 = 11 çöz' → denklemi çözer")
    print(f"  • 'resim yap: uzay gemisi' → resim üretir")
    print(f"  • 'ses kapat' → sessiz moda geçer\n")

    while True:
        # Live mod — Hey Jarvis bekleniyor
        if live_mod:
            print(f"  {CYAN}💤 Bekliyorum... ('Hey Jarvis' de){RESET}", end="\r")
            if wake_word_dinle():
                print(f"  {GREEN}✓ Sizi duydum! Buyrun...{RESET}        ")
                asyncio.run(sesli_oku("Buyrun efendim"))
                soru = mikrofon_dinle()
                if not soru:
                    continue
                soru_lower = soru.lower()
            else:
                continue

        else:
            try:
                soru = input(f"{CYAN}{BOLD}Sen:{RESET} ").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{CYAN}Görüşürüz!{RESET}")
                break
            if not soru:
                continue
            soru_lower = soru.lower()

        if soru_lower in ("quit", "çıkış", "exit", "q"):
            print(f"{CYAN}Görüşürüz!{RESET}")
            break

        if soru_lower == "live mod":
            live_mod = True
            sesli_mod = True
            print(f"{GREEN}✓ Live mod açık! 'Hey Jarvis' de, seni dinleyeyim.{RESET}\n")
            continue

        if soru_lower == "live kapat":
            live_mod = False
            sesli_mod = False
            print(f"{YELLOW}✓ Live mod kapalı{RESET}\n")
            continue

        if soru_lower == "ses aç":
            sesli_mod = True
            print(f"{GREEN}✓ Sesli mod açık — Jarvis seni dinleyecek ve konuşacak!{RESET}\n")
            continue

        if soru_lower == "ses kapat":
            sesli_mod = False
            print(f"{YELLOW}✓ Sesli mod kapalı{RESET}\n")
            continue

        # Sesli modda (live mod değilken) mikrofonu dinle
        if sesli_mod and not live_mod:
            mikrofon_soru = mikrofon_dinle()
            if mikrofon_soru:
                soru = mikrofon_soru
                soru_lower = soru.lower()

        if soru_lower == "geçmişi temizle":
            konusma_gecmisi.clear()
            print(f"{GREEN}✓ Temizlendi{RESET}\n")
            continue

        # Resim yapma komutu
        if soru_lower.startswith("resim yap:"):
            prompt = soru[10:].strip()
            if not prompt:
                print(f"  {YELLOW}Örnek: resim yap: uzay gemisi, gece, neon ışıklar{RESET}\n")
                continue
            sonuc = resim_yap(prompt)
            print(f"{GREEN}{BOLD}Jarvis:{RESET} {sonuc}\n")
            continue

        print(f"  {YELLOW}⏳ Düşünüyor...{RESET}", end="\r")
        yanit = jarvis_yanit(soru)
        print(f"  {'':30}")
        print(f"{GREEN}{BOLD}Jarvis:{RESET} {yanit}\n")

        if sesli_mod:
            asyncio.run(sesli_oku(yanit))

if __name__ == "__main__":
    main()
