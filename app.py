import os
import re
import io
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
from google.cloud import vision
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

app = Flask(__name__)
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"

if not CREDENTIALS_FILE.exists():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        CREDENTIALS_FILE.write_text(creds_json)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(CREDENTIALS_FILE)

SPREADSHEET_ID = "105ZaHH47MV07b_rBNZQd427RGmbKd5B-_QNCZS4tdxw"
SHEET_NAME = "工作表1"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheets_service():
    creds = Credentials.from_service_account_file(str(CREDENTIALS_FILE), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>名片掃描器</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f0f4f8; min-height: 100vh; padding: 20px; }
    .container { max-width: 480px; margin: 0 auto; }
    h1 { text-align: center; color: #1a202c; margin-bottom: 24px; font-size: 24px; }
    .card { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 2px 16px rgba(0,0,0,0.08); margin-bottom: 16px; }
    .upload-area { border: 2px dashed #4299e1; border-radius: 12px; padding: 32px; text-align: center; cursor: pointer; transition: all 0.2s; position: relative; }
    .upload-area input[type=file] { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
    .upload-area .icon { font-size: 48px; margin-bottom: 12px; }
    .upload-area p { color: #4a5568; font-size: 14px; }
    .upload-area strong { color: #2b6cb0; display: block; margin-bottom: 4px; font-size: 16px; }
    .btn { width: 100%; padding: 14px; background: #4299e1; color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.2s; margin-top: 12px; }
    .btn:hover { background: #2b6cb0; }
    .btn:disabled { background: #a0aec0; cursor: not-allowed; }
    .btn-green { background: #48bb78; }
    .btn-green:hover { background: #276749; }
    .btn-gray { background: #718096; }
    .btn-gray:hover { background: #4a5568; }
    .result { display: none; }
    .field { margin-bottom: 12px; }
    .field label { display: block; font-size: 12px; color: #718096; margin-bottom: 4px; font-weight: 500; }
    .field input { width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; color: #1a202c; }
    .field input:focus { outline: none; border-color: #4299e1; box-shadow: 0 0 0 3px rgba(66,153,225,0.15); }
    .status { text-align: center; padding: 12px; border-radius: 8px; font-size: 14px; margin-top: 12px; display: none; }
    .status.loading { background: #ebf8ff; color: #2b6cb0; }
    .status.success { background: #f0fff4; color: #276749; }
    .status.error { background: #fff5f5; color: #c53030; }
    .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid currentColor; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 6px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .category-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
    .category-btn { padding: 8px 16px; border: 2px solid #e2e8f0; border-radius: 20px; background: white; font-size: 14px; cursor: pointer; transition: all 0.2s; color: #4a5568; }
    .category-btn.selected { border-color: #4299e1; background: #ebf8ff; color: #2b6cb0; font-weight: 600; }
    .category-label { font-size: 12px; color: #718096; font-weight: 500; margin-bottom: 4px; display: block; }
    .cropper-wrap { display: none; margin-top: 16px; }
    .cropper-wrap img { max-width: 100%; }
    #cropPreview { width: 100%; max-height: 280px; object-fit: contain; border-radius: 8px; display: none; margin-top: 12px; }
    .crop-actions { display: flex; gap: 8px; margin-top: 12px; }
    .crop-actions .btn { margin-top: 0; flex: 1; }
  </style>
</head>
<body>
  <div class="container">
    <h1>📇 名片掃描器</h1>

    <div class="card">
      <div class="upload-area" id="uploadArea">
        <div class="icon">📷</div>
        <strong>拍照或選擇名片圖片</strong>
        <p>支援 JPG、PNG 格式</p>
        <input type="file" id="fileInput" accept="image/*">
      </div>

      <div class="cropper-wrap" id="cropperWrap">
        <p style="font-size:13px;color:#718096;margin-bottom:8px;">✂️ 拖曳框線裁切名片範圍</p>
        <img id="cropImg" src="">
        <div class="crop-actions">
          <button class="btn btn-gray" onclick="resetCrop()">重選圖片</button>
          <button class="btn" onclick="confirmCrop()">確認裁切</button>
        </div>
      </div>

      <img id="cropPreview" alt="名片預覽">
      <div class="status" id="scanStatus"></div>
      <button class="btn" id="scanBtn" style="display:none;" onclick="scanCard()">🔍 辨識名片</button>
    </div>

    <div class="card result" id="resultCard">
      <h2 style="margin-bottom:16px; font-size:16px; color:#2d3748;">📝 辨識結果（可編輯後儲存）</h2>
      <div id="fields"></div>
      <div style="margin-top:16px;">
        <span class="category-label">📂 請選擇分類</span>
        <div class="category-group" id="categoryGroup">
          <button class="category-btn" onclick="selectCategory(this, 'Will BNI')">Will BNI</button>
          <button class="category-btn" onclick="selectCategory(this, '南翔')">南翔</button>
          <button class="category-btn" onclick="selectCategory(this, '芯創')">芯創</button>
          <button class="category-btn" onclick="selectCategory(this, 'Julia')">Julia</button>
          <button class="category-btn" onclick="selectCategory(this, 'Other')">Other</button>
        </div>
      </div>
      <div class="status" id="saveStatus"></div>
      <button class="btn btn-green" onclick="saveCard()">✅ 儲存到 Google Sheets</button>
    </div>
  </div>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js"></script>
  <script>
    let cropper = null;
    let croppedBlob = null;
    let selectedCategory = '';

    document.getElementById('fileInput').addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      const img = document.getElementById('cropImg');
      img.src = url;
      document.getElementById('cropperWrap').style.display = 'block';
      document.getElementById('scanBtn').style.display = 'none';
      document.getElementById('cropPreview').style.display = 'none';
      document.getElementById('resultCard').style.display = 'none';
      if (cropper) { cropper.destroy(); cropper = null; }
      setTimeout(() => {
        cropper = new Cropper(img, { aspectRatio: NaN, viewMode: 1, movable: true, zoomable: true, rotatable: false, scalable: false });
      }, 100);
    });

    function resetCrop() {
      if (cropper) { cropper.destroy(); cropper = null; }
      document.getElementById('cropperWrap').style.display = 'none';
      document.getElementById('scanBtn').style.display = 'none';
      document.getElementById('cropPreview').style.display = 'none';
      document.getElementById('fileInput').value = '';
    }

    function confirmCrop() {
      if (!cropper) return;
      cropper.getCroppedCanvas({ maxWidth: 1200, maxHeight: 800 }).toBlob(blob => {
        croppedBlob = blob;
        const url = URL.createObjectURL(blob);
        const preview = document.getElementById('cropPreview');
        preview.src = url;
        preview.style.display = 'block';
        document.getElementById('cropperWrap').style.display = 'none';
        document.getElementById('scanBtn').style.display = 'block';
        cropper.destroy(); cropper = null;
      }, 'image/jpeg', 0.92);
    }

    function selectCategory(btn, value) {
      document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedCategory = value;
    }

    function setStatus(id, type, message) {
      const el = document.getElementById(id);
      el.className = 'status ' + type;
      el.innerHTML = message;
      el.style.display = 'block';
    }

    async function scanCard() {
      if (!croppedBlob) { alert('請先裁切名片'); return; }
      const btn = document.getElementById('scanBtn');
      btn.disabled = true;
      setStatus('scanStatus', 'loading', '<span class="spinner"></span>AI 辨識中，請稍候...');
      const formData = new FormData();
      formData.append('image', croppedBlob, 'card.jpg');
      try {
        const res = await fetch('/scan', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        selectedCategory = '';
        document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('selected'));
        renderFields(data);
        document.getElementById('resultCard').style.display = 'block';
        document.getElementById('resultCard').scrollIntoView({ behavior: 'smooth' });
        setStatus('scanStatus', 'success', '✅ 辨識完成！請確認資料並選擇分類後儲存');
      } catch (e) {
        setStatus('scanStatus', 'error', '❌ 辨識失敗：' + e.message);
      } finally {
        btn.disabled = false;
      }
    }

    function renderFields(data) {
      const keys = ['name','title','organization','mobile','email','phone','address','line'];
      const labels = ['姓名','抬頭','所屬單位','手機','Email','電話','地址','Line'];
      const container = document.getElementById('fields');
      container.innerHTML = '';
      keys.forEach((key, i) => {
        container.innerHTML += `
          <div class="field">
            <label>${labels[i]}</label>
            <input type="text" id="field_${key}" value="${(data[key] || '').replace(/"/g, '&quot;')}">
          </div>`;
      });
    }

    async function saveCard() {
      if (!selectedCategory) {
        setStatus('saveStatus', 'error', '❌ 請先選擇分類！');
        return;
      }
      const keys = ['name','title','organization','mobile','email','phone','address','line'];
      const payload = { category: selectedCategory };
      keys.forEach(k => payload[k] = document.getElementById('field_' + k).value);
      setStatus('saveStatus', 'loading', '<span class="spinner"></span>儲存到 Google Sheets 中...');
      try {
        const res = await fetch('/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        setStatus('saveStatus', 'success', '✅ 已儲存到 Google Sheets！<br><a href="https://docs.google.com/spreadsheets/d/105ZaHH47MV07b_rBNZQd427RGmbKd5B-_QNCZS4tdxw" target="_blank" style="color:#276749;font-weight:600;">📊 開啟 Google Sheets 查看</a>');
      } catch (e) {
        setStatus('saveStatus', 'error', '❌ 儲存失敗：' + e.message);
      }
    }
  </script>
</body>
</html>
"""

def parse_card_text(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    result = {"name": "", "title": "", "organization": "", "mobile": "", "email": "", "phone": "", "address": "", "line": ""}

    for line in lines:
        if re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", line):
            result["email"] = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", line).group()
        elif re.search(r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}", line):
            result["mobile"] = re.search(r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}", line).group()
        elif re.search(r"\(0[2-8]\)|0[2-8]\d[-\s]?\d{3,4}[-\s]?\d{3,4}", line):
            m = re.search(r"[\d\-\(\)\s]{8,}", line)
            if m and not result["phone"]:
                result["phone"] = m.group().strip()
        elif re.search(r"\d+號|\d+樓|路|街|區|市|縣", line):
            if not result["address"]:
                result["address"] = line
        elif re.search(r"[Ll]ine\s*[:：ID]?\s*\S+", line):
            m = re.search(r"[Ll]ine\s*[:：ID]?\s*(\S+)", line)
            if m: result["line"] = m.group(1)
        elif re.search(r"http|www\.", line):
            pass

    remaining = []
    for line in lines:
        skip = False
        for v in result.values():
            if v and v in line:
                skip = True
                break
        if skip or re.search(r"http|www\.|@|\d{4,}", line):
            continue
        remaining.append(line)

    for line in remaining:
        if re.search(r"公司|中心|研究|工業|科技|企業|集團|有限|股份|財團|法人|協會|基金|事業", line):
            if not result["organization"]:
                result["organization"] = line
        elif re.search(r"總|副|經理|董|長|主任|專員|顧問|業務|處|部|課|組|科|室|代表", line):
            if not result["title"]:
                result["title"] = line
        elif len(line) <= 8 and not result["name"] and not re.search(r"[A-Z]{2,}|MIRDC|ISO", line):
            result["name"] = line

    return result

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/scan", methods=["POST"])
def scan():
    if "image" not in request.files:
        return jsonify({"error": "未收到圖片"}), 400
    image_bytes = request.files["image"].read()
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)
        if response.error.message:
            return jsonify({"error": response.error.message}), 500
        full_text = response.full_text_annotation.text if response.full_text_annotation else ""
        print(f"[OCR TEXT]\n{full_text}")
        data = parse_card_text(full_text)
        return jsonify(data)
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/save", methods=["POST"])
def save():
    try:
        data = request.get_json()
        row = [
            data.get("category", ""),
            data.get("name", ""),
            data.get("title", ""),
            data.get("organization", ""),
            data.get("mobile", ""),
            data.get("email", ""),
            data.get("phone", ""),
            data.get("address", ""),
            data.get("line", ""),
        ]
        service = get_sheets_service()
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:I",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()
        print(f"[SAVED TO SHEETS] {data.get('name')}")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=== 名片掃描器啟動 ===")
    print(f"手機請在同一 Wi-Fi 下，瀏覽器開啟：http://[電腦IP]:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
