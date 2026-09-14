demo:
1. eski kayıtları silme ve yeni kayıt ekleme
Remove-Item -Recurse -Force test_files -ErrorAction SilentlyContinue
Remove-Item baseline.json -ErrorAction SilentlyContinue
Remove-Item fim.log -ErrorAction SilentlyContinue
Remove-Item fim_report_*.html -ErrorAction SilentlyContinue

mkdir test_files | Out-Null
"kritik sistem log kaydi" | Out-File -Encoding utf8 test_files\log.txt
"veritabani sifresi: 12345" | Out-File -Encoding utf8 test_files\config.ini

2. baseline oluşturma ve hash, son güncelleme terihi vb kaydı
python fim.py --init test_files
type baseline.json

3. değişiklik kontrolü 
python fim.py --check test_files

4. başka bir terminalde değişiklik yapma ve bunun tespiti
"BU DOSYA SALDIRGAN TARAFINDAN DEGISTIRILDI" | Out-File -Encoding utf8 test_files\log.txt
python fim.py --check test_files

5. boyut aynı hash farklı durumu, birini değiştirme ama hashı aynı tutma
Remove-Item -Recurse -Force test_files -ErrorAction SilentlyContinue
Remove-Item baseline.json -ErrorAction SilentlyContinue
mkdir test_files | Out-Null
"AAAA" | Out-File -NoNewline -Encoding utf8 test_files\a.txt
"BBBB" | Out-File -NoNewline -Encoding utf8 test_files\b.txt
python fim.py --init test_files
Get-Item test_files\a.txt, test_files\b.txt | Select-Object Name, Length
"CCCC" | Out-File -NoNewline -Encoding utf8 test_files\a.txt
python fim.py --check test_files

6. html rapor
python fim.py --check test_files --html report.html
start report.html

7. sürekli izleme ve eposta alarmı
$env:FIM_EMAIL_USER="sevvalulkubilgi@gmail.com"
$env:FIM_EMAIL_PASS="ocvb qjmv yrnw gyog"
$env:FIM_EMAIL_TO="sevvalulkubilgi@gmail.com"
$env:FIM_SMTP_HOST="smtp.gmail.com"
$env:FIM_SMTP_PORT="587"
python fim.py --monitor test_files --interval 15
"test" | Out-File -Append -Encoding utf8 test_files\a.txt

8. tkinter
python fim.py --gui
gözat> test.files> baseline al> izlemeyi başlat> başka terminlade dosyayı değiştir