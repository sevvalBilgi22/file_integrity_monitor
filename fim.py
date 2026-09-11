import hashlib
import os
import json
import argparse
from datetime import datetime
import logging
import time
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import threading

#E-POSTA YAPILANDIRMASI
#Kimlik bilgileri koda gömülmez, ortam değişkenlerinden okunur.

def get_smtp_config():
    return {
        'host': os.getenv('FIM_SMTP_HOST', 'smtp.gmail.com'),
        'port': int(os.getenv('FIM_SMTP_PORT', '587')),
        'user': os.getenv('FIM_EMAIL_USER', ''),
        'password': os.getenv('FIM_EMAIL_PASS', ''),
        'to': os.getenv('FIM_EMAIL_TO', '')
    }

def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (PermissionError, FileNotFoundError) as e:
        print(f"[!] Hata: {file_path} - {e}")
        return None

def create_baseline(directory, output_file='baseline.json'):
    baseline = {}
    for root, _, files in os.walk(directory):
        for file in files:
            full_path = os.path.join(root, file)
            file_hash = calculate_sha256(full_path)
            if file_hash:
                baseline[full_path] = {
                    'hash': file_hash,
                    'size': os.path.getsize(full_path),
                    'mtime': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                }
    with open(output_file, 'w') as f:
        json.dump(baseline, f, indent=4)
    print(f"[+] Baseline oluşturuldu: {output_file} ({len(baseline)} dosya)")


def load_baseline(baseline_file='baseline.json'):
    """Baseline dosyasını okur ve dict olarak döner."""
    if not os.path.exists(baseline_file):
        print(f"[!] Baseline bulunamadı: {baseline_file}")
        print("[i] Önce '--init <dizin>' ile baseline oluşturmalısın.")
        return None
    try:
        with open(baseline_file, 'r', encoding='utf-8') as f:
            baseline = json.load(f)
        print(f"[+] Baseline yüklendi: {len(baseline)} kayıt")
        return baseline
    except json.JSONDecodeError:
        print("[!] Baseline dosyası bozuk veya üzerinde oynanmış (JSON hatası).")
        return None

def scan_directory(directory):
    """Dizini tarar ve {path: {hash, size, mtime}} sözlüğü döner."""
    current = {}
    for root, _, files in os.walk(directory):
        for file in files:
            full_path = os.path.join(root, file)
            file_hash = calculate_sha256(full_path)
            if file_hash:
                current[full_path] = {
                    'hash': file_hash,
                    'size': os.path.getsize(full_path),
                    'mtime': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                }
    return current


def compare_baseline(baseline, current):
    """Baseline ile güncel durumu karşılaştırır, değişiklikleri döner."""
    changes = {
        'modified': [],
        'deleted': [],
        'added': []
    }

    #Baselinedaki her dosya için kontrol
    for path, old_info in baseline.items():
        if path not in current:
            changes['deleted'].append(path)
        elif current[path]['hash'] != old_info['hash']:
            changes['modified'].append({
                'path': path,
                'old_hash': old_info['hash'],
                'new_hash': current[path]['hash'],
                'old_mtime': old_info['mtime'],
                'new_mtime': current[path]['mtime']
            })

    #Baselineda olmayan yeni dosyalar
    for path in current:
        if path not in baseline:
            changes['added'].append(path)

    return changes        

def print_report(changes):
    """Değişiklikleri okunabilir formatta yazdırır."""
    total = len(changes['modified']) + len(changes['deleted']) + len(changes['added'])

    print("\n" + "="*60)
    print(f" BÜTÜNLÜK RAPORU - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    if total == 0:
        print("[✓] Hiçbir değişiklik yok. Sistem temiz.")
        return

    if changes['modified']:
        print(f"\n[!] DEĞİŞTİRİLMİŞ DOSYALAR ({len(changes['modified'])}):")
        for item in changes['modified']:
            print(f"  → {item['path']}")
            print(f"      Eski hash : {item['old_hash']}")
            print(f"      Yeni hash : {item['new_hash']}")
            print(f"      Eski mtime: {item['old_mtime']}")
            print(f"      Yeni mtime: {item['new_mtime']}")

    if changes['deleted']:
        print(f"\n[!] SİLİNMİŞ DOSYALAR ({len(changes['deleted'])}):")
        for path in changes['deleted']:
            print(f"  ✗ {path}")

    if changes['added']:
        print(f"\n[i] YENİ DOSYALAR ({len(changes['added'])}):")
        for path in changes['added']:
            print(f"  + {path}")

    print("\n" + "="*60)

def generate_html_report(changes, scanned_dir, output_file='fim_report.html'):
    """Değişiklikleri HTML raporu olarak kaydeder."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total = sum(len(v) for v in changes.values())

    #Değişiklik satırlarını HTMLe dönüştür
    modified_rows = ""
    for m in changes['modified']:
        modified_rows += f"""
        <tr class="danger">
            <td>{m['path']}</td>
            <td><code>{m['old_hash'][:16]}...</code></td>
            <td><code>{m['new_hash'][:16]}...</code></td>
            <td>{m['old_mtime']}</td>
            <td>{m['new_mtime']}</td>
        </tr>"""

    deleted_rows = "".join(
        f'<tr class="warning"><td>{p}</td></tr>' for p in changes['deleted']
    )
    added_rows = "".join(
        f'<tr class="info"><td>{p}</td></tr>' for p in changes['added']
    )

    status_class = "clean" if total == 0 else "alert"
    status_text = "TEMİZ" if total == 0 else f"{total} DEĞİŞİKLİK"

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>FIM Raporu - {now}</title>
<style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 24px; color: #222; }}
    .container {{ max-width: 1100px; margin: 0 auto; background: #fff; border-radius: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.08); overflow: hidden; }}
    header {{ background: #1e2a44; color: #fff; padding: 24px 32px; }}
    header h1 {{ margin: 0 0 6px 0; font-size: 22px; }}
    header .meta {{ font-size: 13px; opacity: 0.8; }}
    .status {{ display: inline-block; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 13px; margin-top: 12px; }}
    .status.clean {{ background: #1f9d55; color: #fff; }}
    .status.alert {{ background: #e3342f; color: #fff; }}
    section {{ padding: 20px 32px; border-bottom: 1px solid #eee; }}
    section h2 {{ font-size: 16px; margin: 0 0 12px 0; color: #1e2a44; border-left: 4px solid #1e2a44; padding-left: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ text-align: left; padding: 10px; background: #f0f2f7; color: #333; border-bottom: 2px solid #ddd; }}
    td {{ padding: 10px; border-bottom: 1px solid #eee; word-break: break-all; }}
    tr.danger td:first-child {{ color: #c53030; font-weight: 600; }}
    tr.warning td:first-child {{ color: #b7791f; font-weight: 600; }}
    tr.info td:first-child {{ color: #2b6cb0; font-weight: 600; }}
    code {{ background: #edf2f7; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace; font-size: 12px; }}
    footer {{ padding: 16px 32px; font-size: 12px; color: #777; text-align: center; }}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>🔐 Dosya Bütünlüğü İzleyici Raporu</h1>
        <div class="meta">İzlenen dizin: <strong>{scanned_dir}</strong> &nbsp;|&nbsp; Tarih: <strong>{now}</strong></div>
        <div class="status {status_class}">{status_text}</div>
    </header>

    <section>
        <h2>Özet</h2>
        <table>
            <tr><th>Kategori</th><th>Sayı</th></tr>
            <tr><td>Değiştirilmiş dosya</td><td>{len(changes['modified'])}</td></tr>
            <tr><td>Silinmiş dosya</td><td>{len(changes['deleted'])}</td></tr>
            <tr><td>Yeni eklenen dosya</td><td>{len(changes['added'])}</td></tr>
        </table>
    </section>

    <section>
        <h2>Değiştirilmiş Dosyalar ({len(changes['modified'])})</h2>
        <table>
            <tr><th>Dosya</th><th>Eski Hash</th><th>Yeni Hash</th><th>Eski mtime</th><th>Yeni mtime</th></tr>
            {modified_rows or '<tr><td colspan="5">Yok</td></tr>'}
        </table>
    </section>

    <section>
        <h2>Silinmiş Dosyalar ({len(changes['deleted'])})</h2>
        <table>
            <tr><th>Dosya</th></tr>
            {deleted_rows or '<tr><td>Yok</td></tr>'}
        </table>
    </section>

    <section>
        <h2>Yeni Eklenen Dosyalar ({len(changes['added'])})</h2>
        <table>
            <tr><th>Dosya</th></tr>
            {added_rows or '<tr><td>Yok</td></tr>'}
        </table>
    </section>

    <footer>FIM v1.0 — Adli Bilişim Bütünlük Kontrol Aracı</footer>
</div>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[+] HTML rapor oluşturuldu: {output_file}")
    return output_file    

def setup_logger(log_file='fim.log'):
    """Hem dosyaya hem konsola yazan logger kurar."""
    logger = logging.getLogger('FIM')
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    #Dosya handler
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    #Konsol handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

def send_email_alert(subject, body, attachment_path=None):
    """Alarm durumunda eposta gönderir. Config eksikse atlar."""
    config = get_smtp_config()

    if not all([config['user'], config['password'], config['to']]):
        print("[i] E-posta yapılandırması eksik, alarm gönderilmedi.")
        return False

    msg = MIMEMultipart()
    msg['From'] = config['user']
    msg['To'] = config['to']
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
        msg.attach(part)

    try:
        with smtplib.SMTP(config['host'], config['port']) as server:
            server.starttls()
            server.login(config['user'], config['password'])
            server.send_message(msg)
        print(f"[+] Alarm e-postası gönderildi: {config['to']}")
        return True
    except Exception as e:
        print(f"[!] E-posta gönderilemedi: {e}")
        return False

def monitor(directory, baseline_file, interval=30):
    """Belirtilen aralıkla bütünlük kontrolü yapar değişiklikte HTML rapor üretip eposta gönderir."""
    logger = setup_logger()
    baseline = load_baseline(baseline_file)
    if not baseline:
        return

    logger.info(f"[+] İzleme başladı: {directory} (her {interval} sn)")

    try:
        while True:
            current = scan_directory(directory)
            changes = compare_baseline(baseline, current)
            total = sum(len(v) for v in changes.values())

            if total > 0:
                logger.warning(f"[!] {total} değişiklik tespit edildi!")

                #E-posta gövdesini hazırla
                email_lines = [
                    f"FIM ALARMI - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"İzlenen dizin: {directory}",
                    f"Toplam değişiklik: {total}",
                    ""
                ]

                for m in changes['modified']:
                    logger.warning(f"  DEĞİŞTİ: {m['path']}")
                    email_lines.append(f"[DEĞİŞTİ] {m['path']}")
                    email_lines.append(f"   Eski hash: {m['old_hash']}")
                    email_lines.append(f"   Yeni hash: {m['new_hash']}")

                for d in changes['deleted']:
                    logger.warning(f"  SİLİNDİ: {d}")
                    email_lines.append(f"[SİLİNDİ] {d}")

                for a in changes['added']:
                    logger.warning(f"  EKLENDİ: {a}")
                    email_lines.append(f"[EKLENDİ] {a}")

                #HTML raporu üret
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                html_file = f"fim_report_{timestamp}.html"
                generate_html_report(changes, directory, html_file)

                #Epostayı HTML ekli olarak gönder
                send_email_alert(
                    subject=f"[FIM ALARM] {total} değişiklik tespit edildi!",
                    body="\n".join(email_lines),
                    attachment_path=html_file
                )
            else:
                logger.info("[✓] Değişiklik yok.")

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("[i] İzleme kullanıcı tarafından durduruldu.")

def launch_gui():
    """Basit bir Tkinter arayüzü başlatır"""
    import tkinter as tk
    from tkinter import filedialog, scrolledtext, messagebox

    root = tk.Tk()
    root.title("FIM — Dosya Bütünlüğü İzleyici")
    root.geometry("820x560")
    root.configure(bg="#f4f6f9")

    selected_dir = tk.StringVar(value="")
    baseline_file = tk.StringVar(value="baseline.json")
    interval_var = tk.IntVar(value=15)
    monitoring = {"active": False, "stop": False}

    #Üst panel
    top = tk.Frame(root, bg="#1e2a44", pady=12)
    top.pack(fill="x")
    tk.Label(top, text="🔐 FIM — Dosya Bütünlüğü İzleyici",
             bg="#1e2a44", fg="white",
             font=("Segoe UI", 14, "bold")).pack()

    #Klasör seçimi
    dir_frame = tk.Frame(root, pady=10, padx=10, bg="#f4f6f9")
    dir_frame.pack(fill="x")
    tk.Label(dir_frame, text="İzlenecek Dizin:", bg="#f4f6f9").pack(side="left")
    tk.Entry(dir_frame, textvariable=selected_dir, width=55).pack(side="left", padx=6)

    def pick_dir():
        d = filedialog.askdirectory()
        if d:
            selected_dir.set(d)

    tk.Button(dir_frame, text="Gözat...", command=pick_dir).pack(side="left")

    #Baseline + Interval
    opt_frame = tk.Frame(root, pady=4, padx=10, bg="#f4f6f9")
    opt_frame.pack(fill="x")
    tk.Label(opt_frame, text="Baseline dosyası:", bg="#f4f6f9").pack(side="left")
    tk.Entry(opt_frame, textvariable=baseline_file, width=25).pack(side="left", padx=6)
    tk.Label(opt_frame, text="Aralık (sn):", bg="#f4f6f9").pack(side="left", padx=(20, 4))
    tk.Entry(opt_frame, textvariable=interval_var, width=6).pack(side="left")

    #Log alanı
    log_area = scrolledtext.ScrolledText(root, height=20, font=("Consolas", 9),
                                         bg="#0f172a", fg="#e2e8f0",
                                         insertbackground="white")
    log_area.pack(fill="both", expand=True, padx=10, pady=10)
    log_area.tag_config("danger", foreground="#f87171")
    log_area.tag_config("warning", foreground="#fbbf24")
    log_area.tag_config("info", foreground="#93c5fd")
    log_area.tag_config("clean", foreground="#4ade80")

    def gui_log(message, tag="info"):
        log_area.insert("end", message + "\n", tag)
        log_area.see("end")

    #Buton işlemleri
    def do_init():
        d = selected_dir.get()
        if not d or not os.path.isdir(d):
            messagebox.showerror("Hata", "Geçerli bir dizin seç.")
            return
        gui_log(f"[*] Baseline oluşturuluyor: {d}", "info")
        create_baseline(d, baseline_file.get())
        gui_log("[+] Baseline hazır.", "clean")

    def do_check():
        d = selected_dir.get()
        if not d or not os.path.isdir(d):
            messagebox.showerror("Hata", "Geçerli bir dizin seç.")
            return
        b = load_baseline(baseline_file.get())
        if not b:
            return
        current = scan_directory(d)
        changes = compare_baseline(b, current)
        total = sum(len(v) for v in changes.values())

        if total == 0:
            gui_log(f"[✓] {datetime.now().strftime('%H:%M:%S')} — Değişiklik yok.", "clean")
        else:
            gui_log(f"[!] {total} değişiklik tespit edildi!", "danger")
            for m in changes['modified']:
                gui_log(f"    DEĞİŞTİ : {m['path']}", "warning")
            for dd in changes['deleted']:
                gui_log(f"    SİLİNDİ : {dd}", "danger")
            for a in changes['added']:
                gui_log(f"    EKLENDİ : {a}", "info")

    def monitor_loop():
        d = selected_dir.get()
        b = load_baseline(baseline_file.get())
        if not b:
            monitoring["active"] = False
            return
        while not monitoring["stop"]:
            current = scan_directory(d)
            changes = compare_baseline(b, current)
            total = sum(len(v) for v in changes.values())
            if total == 0:
                gui_log(f"[✓] {datetime.now().strftime('%H:%M:%S')} — temiz", "clean")
            else:
                gui_log(f"[!] {datetime.now().strftime('%H:%M:%S')} — {total} değişiklik!", "danger")
                for m in changes['modified']:
                    gui_log(f"    DEĞİŞTİ : {m['path']}", "warning")
                for dd in changes['deleted']:
                    gui_log(f"    SİLİNDİ : {dd}", "danger")
                for a in changes['added']:
                    gui_log(f"    EKLENDİ : {a}", "info")
            for _ in range(interval_var.get()):
                if monitoring["stop"]:
                    break
                time.sleep(1)
        gui_log("[i] İzleme durduruldu.", "info")

    def toggle_monitor():
        if not monitoring["active"]:
            monitoring["active"] = True
            monitoring["stop"] = False
            gui_log(f"[+] İzleme başladı (her {interval_var.get()} sn).", "info")
            t = threading.Thread(target=monitor_loop, daemon=True)
            t.start()
        else:
            monitoring["stop"] = True
            monitoring["active"] = False

    #Butonlar
    btn_frame = tk.Frame(root, pady=10, bg="#f4f6f9")
    btn_frame.pack()
    tk.Button(btn_frame, text="Baseline Al", width=15, command=do_init,
              bg="#2b6cb0", fg="white", relief="flat").pack(side="left", padx=4)
    tk.Button(btn_frame, text="Kontrol Et", width=15, command=do_check,
              bg="#1f9d55", fg="white", relief="flat").pack(side="left", padx=4)
    tk.Button(btn_frame, text="İzlemeyi Başlat/Durdur", width=20, command=toggle_monitor,
              bg="#b7791f", fg="white", relief="flat").pack(side="left", padx=4)

    gui_log("[i] FIM GUI hazır. Başlamak için dizin seç ve 'Baseline Al'.", "info")
    root.mainloop()

#MAIN BLOĞU

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dosya Bütünlüğü İzleyici (FIM)")

    #Argüman tanımları
    parser.add_argument('--init', metavar='DIR',
                        help='Baseline oluşturulacak dizin')
    parser.add_argument('--check', metavar='DIR',
                        help='Baseline ile karşılaştırılacak dizin')
    parser.add_argument('--baseline', default='baseline.json',
                        help='Baseline dosyası (varsayılan: baseline.json)')
    parser.add_argument('--monitor', metavar='DIR',
                        help='Sürekli izleme modu')
    parser.add_argument('--interval', type=int, default=30,
                        help='İzleme aralığı (saniye, varsayılan: 30)')
    parser.add_argument('--html', metavar='FILE', default=None,
                        help='HTML rapor dosyası (ör. report.html)')
    parser.add_argument('--gui', action='store_true',
                        help='Tkinter arayüzünü başlat')
    
    args = parser.parse_args()

    #Mod seçimi
    if args.gui:
        launch_gui()

    elif args.init:
        create_baseline(args.init, args.baseline)

    elif args.check:
        baseline = load_baseline(args.baseline)
        if baseline:
            current = scan_directory(args.check)
            changes = compare_baseline(baseline, current)
            print_report(changes)

            if args.html:
                generate_html_report(changes, args.check, args.html)

    elif args.monitor:
        monitor(args.monitor, args.baseline, args.interval)

    else:
        parser.print_help()