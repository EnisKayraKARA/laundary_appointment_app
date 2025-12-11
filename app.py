from flask import Flask, render_template, request, jsonify
import sqlite3
import json
import os
import sys
import html
from datetime import datetime, timedelta

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
DB_PATH = os.path.join(BASE_DIR, 'database.db')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

template_dir = os.path.join(sys._MEIPASS, 'templates') if getattr(sys, 'frozen', False) else 'templates'
app = Flask(__name__, template_folder=template_dir)

def get_config():
    defaults = {
        "gunluk_limit": 2, "haftalik_limit": 0, "aylik_limit": 0, 
        "max_ileri_gun": 7,
        "admin_sifresi": "admin123", "baslangic_saati": 7, "bitis_saati": 23,
        "seans_suresi": 150, "port": 80, "oto_baslat_app": False,
        "windows_baslat": False, "guv_sorusu_aktif": True
    }
    if not os.path.exists(CONFIG_PATH):
        return defaults
    try:
        with open(CONFIG_PATH, 'r') as f:
            settings = json.load(f)
            for key, val in defaults.items():
                if key not in settings:
                    settings[key] = val
            return settings
    except (json.JSONDecodeError, IOError):
        return defaults

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS randevular 
                 (tarih TEXT, makine INTEGER, saat_index INTEGER, isim TEXT, sifre TEXT, 
                  guvenlik_sorusu TEXT, guvenlik_cevabi TEXT, is_admin INTEGER)''')
    c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_tekil_randevu 
                 ON randevular (tarih, makine, saat_index)''')
    conn.commit()
    conn.close()

init_db()

def limit_kontrol(isim, tarih_str, config):
    if config['gunluk_limit'] == 0 and config['haftalik_limit'] == 0 and config['aylik_limit'] == 0:
        return True, ""
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT tarih FROM randevular WHERE isim=? AND is_admin=0", (isim,))
    randevular = [row[0] for row in c.fetchall()]
    conn.close()

    try:
        hedef_tarih = datetime.strptime(tarih_str, "%Y-%m-%d")
    except ValueError:
        return False, "DATE_ERROR"

    gunluk = 0
    haftalik = 0
    aylik = 0

    for r_tarih_str in randevular:
        try:
            r_tarih = datetime.strptime(r_tarih_str, "%Y-%m-%d")
            if r_tarih_str == tarih_str:
                gunluk += 1
            start_week = hedef_tarih - timedelta(days=hedef_tarih.weekday())
            end_week = start_week + timedelta(days=6)
            if start_week <= r_tarih <= end_week:
                haftalik += 1
            if r_tarih.year == hedef_tarih.year and r_tarih.month == hedef_tarih.month:
                aylik += 1
        except ValueError:
            continue

    if config['gunluk_limit'] > 0 and gunluk >= config['gunluk_limit']:
        return False, "LIMIT_DAY"
    if config['haftalik_limit'] > 0 and haftalik >= config['haftalik_limit']:
        return False, "LIMIT_WEEK"
    if config['aylik_limit'] > 0 and aylik >= config['aylik_limit']:
        return False, "LIMIT_MONTH"
    return True, ""

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_settings')
def get_settings():
    return jsonify(get_config())

@app.route('/get_randevular')
def get_randevular():
    tarih = request.args.get('tarih')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT makine, saat_index, isim, is_admin FROM randevular WHERE tarih=?", (tarih,))
    kayitlar = c.fetchall()
    conn.close()
    sonuc = {}
    for k in kayitlar:
        anahtar = f"m{k[0]}_s{k[1]}"
        sonuc[anahtar] = {"isim": html.escape(k[2]), "is_admin": k[3]}
    return jsonify(sonuc)

@app.route('/add_randevu', methods=['POST'])
def add_randevu():
    data = request.json
    config = get_config()
    
    if not (1 <= data.get('makine', 0) <= 4):
        return jsonify({"success": False, "code": "INVALID_MACHINE"})

    try:
        req_date = datetime.strptime(data['tarih'], "%Y-%m-%d").date()
        today = datetime.now().date()
        
        if req_date < today:
             return jsonify({"success": False, "code": "PAST_DATE"})
        
        if config['max_ileri_gun'] > 0:
            max_date = today + timedelta(days=config['max_ileri_gun'])
            if req_date > max_date:
                return jsonify({"success": False, "code": "DATE_TOO_FAR"})

    except ValueError:
        return jsonify({"success": False, "code": "DATE_ERROR"})

    if len(data.get('isim', '')) > 30:
        return jsonify({"success": False, "code": "NAME_TOO_LONG"})

    conn = get_db()
    c = conn.cursor()
    is_admin = 0
    
    if data.get('admin_mode') == True:
        if data['sifre'] != config['admin_sifresi']:
            conn.close()
            return jsonify({"success": False, "code": "ADMIN_PASS_ERROR"})
        is_admin = 1
    else:
        isim_temiz = data['isim'].strip()
        uygun, err_code = limit_kontrol(isim_temiz, data['tarih'], config)
        if not uygun:
            conn.close()
            return jsonify({"success": False, "code": err_code})

    try:
        guv_cevap = html.escape(data.get('guvenlik_cevabi', '').strip().lower())
        isim_final = html.escape(data['isim'].strip())
        c.execute("INSERT INTO randevular VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                  (data['tarih'], data['makine'], data['saat'], isim_final, data['sifre'], 
                   data.get('guvenlik_sorusu'), guv_cevap, is_admin))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "code": "SLOT_FULL"})
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "code": "DB_ERROR", "msg": str(e)})
        
    conn.close()
    return jsonify({"success": True})

@app.route('/delete_randevu', methods=['POST'])
def delete_randevu():
    data = request.json
    config = get_config()
    conn = get_db()
    c = conn.cursor()
    
    if data.get('admin_mode') == True:
        if data['sifre'] == config['admin_sifresi']:
            c.execute("DELETE FROM randevular WHERE tarih=? AND makine=? AND saat_index=?", 
                      (data['tarih'], data['makine'], data['saat']))
            basari = True
            code = "DELETE_SUCCESS"
        else:
            basari = False
            code = "ADMIN_PASS_ERROR"
    else:
        c.execute("DELETE FROM randevular WHERE tarih=? AND makine=? AND saat_index=? AND sifre=?", 
                  (data['tarih'], data['makine'], data['saat'], data['sifre']))
        if c.rowcount > 0:
            basari = True
            code = "DELETE_SUCCESS"
        else:
            basari = False
            code = "PASS_ERROR"
    conn.commit()
    conn.close()
    return jsonify({"success": basari, "code": code})

@app.route('/recover_randevu', methods=['POST'])
def recover_randevu():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    gelen_cevap = html.escape(data.get('cevap', '').strip().lower())
    c.execute("DELETE FROM randevular WHERE tarih=? AND makine=? AND saat_index=? AND guvenlik_cevabi=?", 
              (data['tarih'], data['makine'], data['saat'], gelen_cevap))
    if c.rowcount > 0:
        res = {"success": True, "code": "DELETE_SUCCESS"}
    else:
        res = {"success": False, "code": "SEC_ANSWER_WRONG"}
    conn.commit()
    conn.close()
    return jsonify(res)

@app.route('/get_security_question', methods=['GET'])
def get_security_question():
    tarih = request.args.get('tarih')
    makine = request.args.get('makine')
    saat = request.args.get('saat')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT guvenlik_sorusu FROM randevular WHERE tarih=? AND makine=? AND saat_index=?", 
              (tarih, makine, saat))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return jsonify({"success": True, "soru": row[0]})
    else:
        return jsonify({"success": False, "code": "NO_QUESTION"})

if __name__ == '__main__':
    conf = get_config()
    app.run(host='0.0.0.0', port=conf['port'])