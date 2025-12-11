from flask import Flask, render_template_string, request, redirect, url_for
import random

app = Flask(__name__)

# --- BASİT VERİTABANI (RAM ÜZERİNDE) ---
# Program kapatılınca veriler silinir. Kalıcı olması için veritabanı gerekir 
# ama şimdilik senin işini bu görür.
RANDEVULAR = []

# --- HTML TASARIMLARI (TEK DOSYA OLMASI İÇİN BURAYA GÖMDÜK) ---

# 1. KULLANICI SAYFASI HTML
HTML_KULLANICI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Çamaşırhane Randevu</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 30px auto; padding: 20px; background-color: #f4f4f9; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h2 { color: #333; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background-color: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #218838; }
        .error { color: red; text-align: center; margin-bottom: 15px; }
        .success { color: green; text-align: center; margin-bottom: 15px; }
        .footer { margin-top: 20px; text-align: center; font-size: 12px; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🧺 Randevu Oluştur</h2>
        
        {% if mesaj %}
            <div class="{{ tur }}">{{ mesaj }}</div>
        {% endif %}

        <form action="/" method="POST">
            <div class="form-group">
                <label>Ad Soyad:</label>
                <input type="text" name="isim" placeholder="Örn: Ahmet Yılmaz" required>
            </div>
            
            <div class="form-group">
                <label>Makine Seçimi:</label>
                <select name="makine">
                    <option value="Makine 1">Makine 1</option>
                    <option value="Makine 2">Makine 2</option>
                    <option value="Makine 3">Makine 3</option>
                </select>
            </div>

            <div class="form-group">
                <label>Saat:</label>
                <select name="saat">
                    <option value="09:00 - 11:00">09:00 - 11:00</option>
                    <option value="11:00 - 13:00">11:00 - 13:00</option>
                    <option value="13:00 - 15:00">13:00 - 15:00</option>
                </select>
            </div>

            <div class="form-group">
                <label>Şifre (4-8 Karakter):</label>
                <input type="password" name="sifre" placeholder="****" required minlength="4" maxlength="8">
            </div>

            <button type="submit">Randevu Al</button>
        </form>
        
        <div class="footer">
            <p>Yönetici misin? <a href="/admin">Admin Paneline Git</a></p>
        </div>
    </div>
</body>
</html>
"""

# 2. ADMIN PANELİ HTML
HTML_ADMIN = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Admin Paneli</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 30px auto; padding: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #333; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .btn-sil { background-color: #dc3545; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; }
        .header { display: flex; justify-content: space-between; align-items: center; }
        .home-link { background-color: #007bff; color: white; padding: 10px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Admin Paneli</h1>
        <a href="/" class="home-link">← Ana Sayfaya Dön</a>
    </div>
    
    <p>Toplam Randevu: <strong>{{ randevular|length }}</strong></p>

    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>İsim</th>
                <th>Makine</th>
                <th>Saat</th>
                <th>Şifre</th>
                <th>İşlem</th>
            </tr>
        </thead>
        <tbody>
            {% for r in randevular %}
            <tr>
                <td>{{ r.id }}</td>
                <td>{{ r.isim }}</td>
                <td>{{ r.makine }}</td>
                <td>{{ r.saat }}</td>
                <td>{{ r.sifre }}</td>
                <td>
                    <a href="/sil/{{ r.id }}" class="btn-sil" onclick="return confirm('Silmek istediğine emin misin?')">İptal Et</a>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="6" style="text-align:center;">Henüz hiç randevu yok.</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

# --- BACKEND (SUNUCU KODLARI) ---

@app.route('/', methods=['GET', 'POST'])
def index():
    mesaj = None
    tur = None

    if request.method == 'POST':
        isim = request.form.get('isim', '').strip()
        makine = request.form.get('makine')
        saat = request.form.get('saat')
        sifre = request.form.get('sifre', '').strip()

        # 1. VALIDASYON (KONTROL)
        if not isim or not sifre:
            mesaj = "HATA: İsim ve şifre boş bırakılamaz!"
            tur = "error"
        elif len(sifre) < 4 or len(sifre) > 8:
            mesaj = "HATA: Şifre en az 4, en çok 8 karakter olmalıdır!"
            tur = "error"
        else:
            # 2. ÇAKIŞMA KONTROLÜ
            cakisma = False
            for r in RANDEVULAR:
                if r['makine'] == makine and r['saat'] == saat:
                    cakisma = True
                    break
            
            if cakisma:
                mesaj = "HATA: Bu makine bu saatte zaten dolu!"
                tur = "error"
            else:
                # 3. KAYDETME
                yeni_randevu = {
                    'id': random.randint(1000, 9999), # Benzersiz ID
                    'isim': isim,
                    'makine': makine,
                    'saat': saat,
                    'sifre': sifre
                }
                RANDEVULAR.append(yeni_randevu)
                mesaj = "BAŞARILI: Randevunuz oluşturuldu!"
                tur = "success"

    return render_template_string(HTML_KULLANICI, mesaj=mesaj, tur=tur)

@app.route('/admin')
def admin():
    # Admin sayfasını gösterirken randevu listesini de gönderiyoruz
    return render_template_string(HTML_ADMIN, randevular=RANDEVULAR)

@app.route('/sil/<int:id>')
def sil(id):
    # ID'si eşleşen randevuyu bul ve listeden çıkar
    global RANDEVULAR
    RANDEVULAR = [r for r in RANDEVULAR if r['id'] != id]
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
