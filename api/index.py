from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import sqlite3
import json
import os
import html
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='../static')
app.secret_key = 'cok_gizli_bir_anahtar_rastgele_yazabilirsin'

# --- AYARLAR VE DB YOLLARI ---
DB_FILE = '/tmp/database.db' if os.path.exists('/tmp') else 'database.db'
CONFIG_FILE = '/tmp/config.json' if os.path.exists('/tmp') else 'config.json'

DEFAULT_CONFIG = {
    "gunluk_limit": 2, "haftalik_limit": 0, "aylik_limit": 0, 
    "max_ileri_gun": 7,
    "admin_sifresi": "admin123", 
    "baslangic_saati": 7, "bitis_saati": 23,
    "seans_suresi": 150, "guv_sorusu_aktif": True
}

def get_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f: json.dump(DEFAULT_CONFIG, f)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    except: return DEFAULT_CONFIG

def save_config_file(new_config):
    with open(CONFIG_FILE, 'w') as f: json.dump(new_config, f)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS randevular 
                 (tarih TEXT, makine INTEGER, saat_index INTEGER, isim TEXT, sifre TEXT, 
                  guvenlik_sorusu TEXT, guvenlik_cevabi TEXT, is_admin INTEGER)''')
    c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_tekil_randevu 
                 ON randevular (tarih, makine, saat_index)''')
    conn.commit()
    conn.close()

init_db()

# --- HTML ŞABLONU ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Yurt Çamaşırhanesi</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<style>
    body { margin: 0; padding-top: 80px; font-family: 'Poppins', sans-serif; background-color: #f0f2f5; -webkit-tap-highlight-color: transparent; }
    
    .navbar { 
        position: fixed; top: 0; left: 0; width: 100%; height: 70px; 
        background-color: #ffffff; border-bottom: 2px solid #e1e4e8; 
        display: flex; justify-content: space-between; align-items: center; 
        padding: 0 20px; box-sizing: border-box; z-index: 1000; 
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    .logo-area { display: flex; align-items: center; gap: 10px; }
    .logo-img { height: 40px; width: auto; }
    .baslik { font-size: 1.3rem; color: #1a1a1a; font-weight: 600; white-space: nowrap; }
    
    .nav-right { display: flex; align-items: center; gap: 15px; }
    .tarih-gosterge { font-size: 0.9rem; color: #555; font-weight: 600; display: none; }
    
    .btn-small { 
        padding: 6px 12px; border-radius: 6px; border: 1px solid #ccc; 
        background: #fff; cursor: pointer; font-size: 0.85rem; transition: 0.2s;
        text-decoration: none; color: #333; display: inline-block;
    }
    .btn-admin-login { background-color: #333; color: #fff; border: none; }
    .btn-logout { background-color: #dc3545; color: #fff; border: none; }

    .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
    
    .kontrol-paneli { 
        background: white; padding: 15px; border-radius: 12px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px; 
        display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
    }
    .date-picker { padding: 8px; border: 1px solid #ddd; border-radius: 6px; font-family: inherit; }

    .tablo-alani { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
    .makine-sutunu { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .makine-adi { background: #2c3e50; color: white; padding: 12px; text-align: center; font-weight: 600; }
    
    .saat-kutu { 
        padding: 15px; text-align: center; border-bottom: 1px solid #f0f0f0; 
        cursor: pointer; transition: all 0.2s; position: relative; 
    }
    .saat-kutu:hover { background-color: #fafafa; }
    .saat-kutu:active { background-color: #e0e0e0; }
    
    .bos { border-left: 5px solid #2ecc71; color: #27ae60; }
    .dolu { border-left: 5px solid #e74c3c; color: #c0392b; background-color: #fff5f5; }
    .yetkili-dolu { border-left: 5px solid #3498db; color: #2980b9; background-color: #f0f8ff; }

    .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; justify-content: center; align-items: center; }
    .modal-kutu { background: white; padding: 25px; border-radius: 16px; width: 90%; max-width: 400px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.2); max-height: 90vh; overflow-y: auto; }
    
    input, select { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; font-family: inherit; }
    button.action-btn { width: 100%; padding: 12px; margin-top: 10px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 1rem; transition: 0.2s; }
    
    .btn-primary { background: #3498db; color: white; }
    .btn-danger { background: #e74c3c; color: white; }
    .btn-secondary { background: #95a5a6; color: white; }
    .settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; text-align: left; }
    .settings-grid label { font-size: 0.85rem; color: #666; display: block; margin-top: 5px; }

    footer { text-align: center; padding: 30px; color: #888; font-size: 0.9rem; }

    @media (min-width: 769px) { .tarih-gosterge { display: block; } }
    @media (max-width: 768px) {
        .baslik { font-size: 1.1rem; }
        .logo-img { height: 32px; }
        .tablo-alani { grid-template-columns: 1fr; }
        .navbar { padding: 0 15px; }
    }
</style>
</head>
<body>

<nav class="navbar">
    <div class="logo-area">
        <img src="/static/logo.png" alt="Logo" class="logo-img">
        <div class="baslik">Yurt Çamaşırhanesi</div>
    </div>
    <div class="nav-right">
        <div class="tarih-gosterge" id="header-tarih"></div>
        {% if session.get('admin_logged_in') %}
            <button class="btn-small btn-logout" onclick="adminLogout()">Çıkış Yap</button>
            <button class="btn-small" onclick="openSettings()">Ayarlar</button>
        {% else %}
            <button class="btn-small btn-admin-login" onclick="openLoginModal()">Yönetici</button>
        {% endif %}
    </div>
</nav>

<div class="container">
    <div class="kontrol-paneli">
        <div>
            <label style="font-weight:600; margin-right:10px;">Tarih Seç:</label>
            <input type="date" id="tarihSecici" class="date-picker">
        </div>
        <div id="status-text" style="color:green; font-size:0.9rem;">
            {% if session.get('admin_logged_in') %}
            ● YÖNETİCİ MODU AKTİF
            {% else %}
            ● Sistem Çevrimiçi
            {% endif %}
        </div>
    </div>
    <div class="tablo-alani" id="anaTablo"><p style="text-align:center; width:100%;">Yükleniyor...</p></div>
</div>

<footer>&copy; 2025 Yurt Çamaşırhane Sistemi</footer>

<div class="modal" id="modal-login">
    <div class="modal-kutu">
        <h3>Yönetici Girişi</h3>
        <input type="password" id="admin-pass-input" placeholder="Yönetici Şifresi">
        <button class="action-btn btn-primary" onclick="adminLogin()">Giriş Yap</button>
        <button class="action-btn btn-secondary" onclick="closeModal('modal-login')">Kapat</button>
    </div>
</div>

<div class="modal" id="modal-settings">
    <div class="modal-kutu" style="max-width:500px;">
        <h3>Sistem Ayarları</h3>
        <div class="settings-grid">
            <div><label>Günlük Limit</label><input type="number" id="set-gunluk"></div>
            <div><label>Haftalık Limit</label><input type="number" id="set-haftalik"></div>
            <div><label>Aylık Limit</label><input type="number" id="set-aylik"></div>
            <div><label>İleri Gün Sınırı</label><input type="number" id="set-ileri"></div>
            <div><label>Açılış Saati</label><input type="number" id="set-bas"></div>
            <div><label>Kapanış Saati</label><input type="number" id="set-bit"></div>
            <div><label>Seans (Dk)</label><input type="number" id="set-sure"></div>
            <div><label>Güvenlik Sorusu</label>
                <select id="set-guv"><option value="1">Aktif</option><option value="0">Pasif</option></select>
            </div>
        </div>
        <label>Admin Şifresi (Değiştirmek için)</label>
        <input type="text" id="set-pass">
        <button class="action-btn btn-primary" onclick="saveSettings()">Kaydet</button>
        <button class="action-btn btn-secondary" onclick="closeModal('modal-settings')">Kapat</button>
    </div>
</div>

<div class="modal" id="modal-islem">
    <div class="modal-kutu">
        <h3 id="modal-title">İşlem</h3>
        <p id="modal-desc" style="color:#666; margin-bottom:15px;"></p>
        
        <div id="form-al" style="display:none;">
            <input type="text" id="inp-isim" placeholder="Adınız Soyadınız (Zorunlu)">
            <input type="password" id="inp-sifre" placeholder="PIN Kodu (4-6 hane)" maxlength="6">
            
            <div id="div-guv">
                <select id="inp-soru">
                    <option>İlkokul öğretmeninizin adı?</option>
                    <option>Hangi şehirde doğdunuz?</option>
                    <option>En sevdiğiniz yemek?</option>
                    <option>Tuttuğunuz takım?</option>
                </select>
                <input type="text" id="inp-cevap" placeholder="Cevabınız">
            </div>
            <button class="action-btn btn-primary" onclick="randevuIslem('al')">Randevu Oluştur</button>
        </div>

        <div id="form-iptal" style="display:none;">
            {% if session.get('admin_logged_in') %}
                <p style="color:red; font-weight:bold;">Yönetici Yetkisi ile Silinecek</p>
                <button class="action-btn btn-danger" onclick="randevuIslem('sil_admin')">ZORLA SİL (YÖNETİCİ)</button>
            {% else %}
                <p>İptal etmek için PIN kodunuzu girin:</p>
                <input type="password" id="inp-iptal-sifre" placeholder="PIN Kodu" maxlength="6">
                <button class="action-btn btn-danger" onclick="randevuIslem('sil')">Randevuyu İptal Et</button>
                <hr style="margin:15px 0; border:0; border-top:1px solid #eee;">
                
                <button class="action-btn btn-secondary" onclick="showRecover()" id="btn-forgot">Şifremi Unuttum</button>
                <div id="div-recover" style="display:none; margin-top:10px;">
                    <p style="font-size:0.9rem; color:#555;">Güvenlik Sorusu:</p>
                    <p id="rec-q" style="font-weight:bold; color:#333; margin:5px 0;"></p>
                    <input type="text" id="rec-ans" placeholder="Cevabınız">
                    <button class="action-btn btn-secondary" onclick="randevuIslem('kurtar')">Doğrula ve Sil</button>
                </div>
            {% endif %}
        </div>

        <button class="action-btn btn-secondary" style="margin-top:15px;" onclick="closeModal('modal-islem')">Kapat</button>
    </div>
</div>

<script>
    let config = {};
    let seciliTarih = new Date().toISOString().split('T')[0];
    let selectedSlot = {};
    let isAdmin = {{ 'true' if session.get('admin_logged_in') else 'false' }};

    window.onload = () => {
        document.getElementById('tarihSecici').value = seciliTarih;
        loadConfig();
        loadData();
    };

    document.getElementById('tarihSecici').addEventListener('change', (e) => {
        seciliTarih = e.target.value;
        loadData();
    });

    function loadConfig() {
        fetch('/api/get_settings').then(r=>r.json()).then(d => { config = d; });
    }

    function loadData() {
        fetch(`/api/get_randevular?tarih=${seciliTarih}&t=${Date.now()}`)
        .then(r=>r.json())
        .then(data => drawTable(data));
        
        const d = new Date(seciliTarih);
        const dateStr = d.toLocaleDateString('tr-TR', {weekday:'long', day:'numeric', month:'long'});
        document.getElementById('header-tarih').innerText = dateStr;
        
        // Mobilde de görebilmek için document title'a tarih eklenebilir ama opsiyonel
    }

    function drawTable(data) {
        const div = document.getElementById('anaTablo');
        div.innerHTML = "";
        
        let slots = [];
        let bas = config.baslangic_saati * 60;
        let bit = config.bitis_saati * 60;
        if (bit <= bas) bit += 1440;
        let cur = bas;
        while(cur + config.seans_suresi <= bit) {
            let s1 = formatTime(cur);
            let s2 = formatTime(cur + config.seans_suresi);
            slots.push(`${s1} - ${s2}`);
            cur += config.seans_suresi;
        }

        for(let m=1; m<=4; m++) {
            let col = `<div class="makine-sutunu"><div class="makine-adi">${m}. Makine</div>`;
            slots.forEach((saat, idx) => {
                let key = `m${m}_s${idx}`;
                let info = data[key];
                let css = "bos";
                let text = `<strong>${saat}</strong><br><small>Müsait</small>`;
                let action = `openSlot(${m}, ${idx}, '${saat}', 'bos')`;

                if(info) {
                    css = info.is_admin ? "yetkili-dolu" : "dolu";
                    let name = info.isim;
                    let label = info.is_admin ? 'YÖNETİCİ' : 'Dolu';
                    text = `<strong>${name}</strong><br><small>${label}</small>`;
                    action = `openSlot(${m}, ${idx}, '${saat}', 'dolu', '${name}')`;
                }
                col += `<div class="saat-kutu ${css}" onclick="${action}">${text}</div>`;
            });
            col += "</div>";
            div.innerHTML += col;
        }
    }

    function formatTime(d) {
        if(d >= 1440) d -= 1440;
        let hh = Math.floor(d/60).toString().padStart(2,'0');
        let mm = Math.round(d%60).toString().padStart(2,'0');
        return `${hh}:${mm}`;
    }

    function openSlot(m, s, txt, type, name="") {
        selectedSlot = {m, s};
        document.getElementById('modal-islem').style.display = 'flex';
        document.getElementById('form-al').style.display = 'none';
        document.getElementById('form-iptal').style.display = 'none';
        
        if (type === 'bos') {
            document.getElementById('modal-title').innerText = isAdmin ? "Yönetici Randevusu" : "Randevu Al";
            document.getElementById('modal-desc').innerText = `${m}. Makine | ${txt}`;
            document.getElementById('form-al').style.display = 'block';
            document.getElementById('div-guv').style.display = (config.guv_sorusu_aktif && !isAdmin) ? 'block' : 'none';
            // Formu temizle
            document.getElementById('inp-isim').value = "";
            document.getElementById('inp-sifre').value = "";
            document.getElementById('inp-cevap').value = "";
        } else {
            document.getElementById('modal-title').innerText = "Detaylar";
            document.getElementById('modal-desc').innerHTML = `<b>${name}</b><br>${m}. Makine | ${txt}`;
            document.getElementById('form-iptal').style.display = 'block';
            // Şifremi unuttum alanını gizle (açılışta)
            if(!isAdmin) {
                document.getElementById('div-recover').style.display = 'none';
                document.getElementById('btn-forgot').style.display = 'block';
                document.getElementById('inp-iptal-sifre').value = "";
            }
        }
    }

    function randevuIslem(action) {
        let payload = {
            tarih: seciliTarih,
            makine: selectedSlot.m,
            saat: selectedSlot.s,
            action: action
        };

        if(action === 'al') {
            let isim = document.getElementById('inp-isim').value;
            let sifre = document.getElementById('inp-sifre').value;
            
            if(!isim || isim.trim().length < 3) return alert("Lütfen geçerli bir isim girin.");
            if(!sifre || sifre.length < 4 || sifre.length > 6) return alert("PIN Kodu 4 ile 6 hane arasında olmalı!");
            
            payload.isim = isim;
            payload.sifre = sifre;
            payload.soru = document.getElementById('inp-soru').value;
            payload.cevap = document.getElementById('inp-cevap').value;
        } else if (action === 'sil') {
            let sifre = document.getElementById('inp-iptal-sifre').value;
            if(!sifre) return alert("Şifre girin");
            payload.sifre = sifre;
        } else if (action === 'kurtar') {
            let cvp = document.getElementById('rec-ans').value;
            if(!cvp) return alert("Cevap girin");
            payload.cevap = cvp;
        }

        fetch('/api/islem', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(r=>r.json()).then(d => {
            if(d.success) {
                alert("İşlem Başarılı");
                closeModal('modal-islem');
                loadData();
            } else {
                alert("Hata: " + d.message);
            }
        });
    }

    function showRecover() {
        fetch(`/api/get_question?tarih=${seciliTarih}&makine=${selectedSlot.m}&saat=${selectedSlot.s}`)
        .then(r=>r.json()).then(d => {
            if(d.success) {
                document.getElementById('div-recover').style.display = 'block';
                document.getElementById('rec-q').innerText = d.soru;
                document.getElementById('btn-forgot').style.display = 'none';
            } else {
                alert("Bu kayıt için güvenlik sorusu bulunamadı (veya yönetici kaydı).");
            }
        });
    }

    // --- ADMIN ---
    function openLoginModal() { document.getElementById('modal-login').style.display = 'flex'; }
    function adminLogin() {
        let pwd = document.getElementById('admin-pass-input').value;
        fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password: pwd})
        }).then(r=>r.json()).then(d => {
            if(d.success) location.reload();
            else alert("Şifre Yanlış!");
        });
    }
    function adminLogout() { fetch('/api/logout').then(() => location.reload()); }

    // --- SETTINGS ---
    function openSettings() {
        document.getElementById('modal-settings').style.display = 'flex';
        document.getElementById('set-gunluk').value = config.gunluk_limit;
        document.getElementById('set-haftalik').value = config.haftalik_limit;
        document.getElementById('set-aylik').value = config.aylik_limit;
        document.getElementById('set-ileri').value = config.max_ileri_gun;
        document.getElementById('set-bas').value = config.baslangic_saati;
        document.getElementById('set-bit').value = config.bitis_saati;
        document.getElementById('set-sure').value = config.seans_suresi;
        document.getElementById('set-pass').value = config.admin_sifresi;
        document.getElementById('set-guv').value = config.guv_sorusu_aktif ? "1" : "0";
    }

    function saveSettings() {
        let newConf = {
            gunluk_limit: parseInt(document.getElementById('set-gunluk').value),
            haftalik_limit: parseInt(document.getElementById('set-haftalik').value),
            aylik_limit: parseInt(document.getElementById('set-aylik').value),
            max_ileri_gun: parseInt(document.getElementById('set-ileri').value),
            baslangic_saati: parseFloat(document.getElementById('set-bas').value),
            bitis_saati: parseFloat(document.getElementById('set-bit').value),
            seans_suresi: parseInt(document.getElementById('set-sure').value),
            admin_sifresi: document.getElementById('set-pass').value,
            guv_sorusu_aktif: document.getElementById('set-guv').value === "1"
        };
        fetch('/api/update_settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(newConf)
        }).then(r=>r.json()).then(d => {
            if(d.success) { alert("Ayarlar Kaydedildi"); location.reload(); }
            else alert("Hata oluştu");
        });
    }

    function closeModal(id) { document.getElementById(id).style.display = 'none'; }
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/get_settings')
def api_get_settings():
    return jsonify(get_config())

@app.route('/api/get_randevular')
def api_get_randevular():
    tarih = request.args.get('tarih')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT makine, saat_index, isim, is_admin FROM randevular WHERE tarih=?", (tarih,))
    data = c.fetchall()
    conn.close()
    
    res = {}
    for row in data:
        key = f"m{row[0]}_s{row[1]}"
        res[key] = {"isim": html.escape(row[2]), "is_admin": row[3]}
    return jsonify(res)

@app.route('/api/islem', methods=['POST'])
def api_islem():
    data = request.json
    action = data.get('action')
    config = get_config()
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if action == 'al':
        # Validasyonlar
        if not data.get('isim') or len(data['isim'].strip()) < 3:
            return jsonify({"success": False, "message": "İsim en az 3 karakter olmalı."})
        
        sifre = data.get('sifre', '')
        if len(sifre) < 4 or len(sifre) > 6:
            return jsonify({"success": False, "message": "PIN kodu 4-6 hane olmalı."})

        # Tarih ve Limit Kontrol (Kısaltıldı)
        try:
            req_date = datetime.strptime(data['tarih'], "%Y-%m-%d").date()
            if req_date < datetime.now().date():
                return jsonify({"success": False, "message": "Geçmişe randevu alınamaz."})
            # Admin logged in ise limit kontrolü yapma
            if not session.get('admin_logged_in'):
                if config['max_ileri_gun'] > 0 and req_date > datetime.now().date() + timedelta(days=config['max_ileri_gun']):
                    return jsonify({"success": False, "message": "Çok ileri tarih."})
                
                c.execute("SELECT count(*) FROM randevular WHERE isim=? AND tarih=?", (data['isim'].strip(), data['tarih']))
                if config['gunluk_limit'] > 0 and c.fetchone()[0] >= config['gunluk_limit']:
                    return jsonify({"success": False, "message": "Günlük limit doldu."})
        except: return jsonify({"success": False, "message": "Tarih hatası."})

        try:
            is_admin = 1 if session.get('admin_logged_in') else 0
            c.execute("INSERT INTO randevular VALUES (?,?,?,?,?,?,?,?)", 
                      (data['tarih'], int(data['makine']), int(data['saat']), 
                       data['isim'].strip(), data['sifre'], 
                       data.get('soru'), data.get('cevap', '').lower(), is_admin))
            conn.commit()
            return jsonify({"success": True})
        except sqlite3.IntegrityError:
            return jsonify({"success": False, "message": "Dolu!"})
        finally: conn.close()

    elif action == 'sil':
        # İPTAL İÇİN ŞİFRE KONTROLÜ
        # Önce kaydı bulalım
        c.execute("SELECT sifre FROM randevular WHERE tarih=? AND makine=? AND saat_index=?", 
                  (data['tarih'], int(data['makine']), int(data['saat'])))
        record = c.fetchone()
        
        if record and record[0] == data.get('sifre'):
            c.execute("DELETE FROM randevular WHERE tarih=? AND makine=? AND saat_index=?", 
                      (data['tarih'], int(data['makine']), int(data['saat'])))
            conn.commit()
            success = True
            msg = "Silindi"
        else:
            success = False
            msg = "Şifre Hatalı"
        
        conn.close()
        return jsonify({"success": success, "message": msg})

    elif action == 'sil_admin':
        if not session.get('admin_logged_in'): return jsonify({"success": False, "message": "Yetkisiz"})
        c.execute("DELETE FROM randevular WHERE tarih=? AND makine=? AND saat_index=?", 
                  (data['tarih'], int(data['makine']), int(data['saat'])))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

    elif action == 'kurtar':
        c.execute("DELETE FROM randevular WHERE tarih=? AND makine=? AND saat_index=? AND guvenlik_cevabi=?",
                  (data['tarih'], int(data['makine']), int(data['saat']), data['cevap'].lower()))
        conn.commit()
        success = c.rowcount > 0
        conn.close()
        return jsonify({"success": success, "message": "Cevap Yanlış"})

    return jsonify({"success": False})

@app.route('/api/get_question')
def api_get_question():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT guvenlik_sorusu FROM randevular WHERE tarih=? AND makine=? AND saat_index=?", 
              (request.args.get('tarih'), request.args.get('makine'), request.args.get('saat')))
    r = c.fetchone()
    conn.close()
    return jsonify({"success": True, "soru": r[0]}) if r and r[0] else jsonify({"success": False})

@app.route('/api/login', methods=['POST'])
def api_login():
    conf = get_config()
    if request.json.get('password') == conf['admin_sifresi']:
        session['admin_logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/logout')
def api_logout():
    session.pop('admin_logged_in', None)
    return jsonify({"success": True})

@app.route('/api/update_settings', methods=['POST'])
def api_update_settings():
    if not session.get('admin_logged_in'): return jsonify({"success": False})
    save_config_file(request.json)
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)
