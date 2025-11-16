# 🧠 Resistor Reader — AI‑Powered Resistor Value Detector

Resistor Reader is a powerful web & mobile‑friendly application that reads resistor color bands from a photo and accurately predicts the resistance value using **Google Gemini AI**.

This project was built with:
- 🔥 **FastAPI** backend  
- 🎨 **HTML/CSS/JS frontend (mobile‑friendly UI)**  
- 🤖 **Gemini 2.5 Flash Vision** for color‑band extraction  
- 📸 Camera & file upload support  
- 📱 Works on PC and phone (same Wi‑Fi)

---

## 🚀 Features

### ✔️ High Accuracy via Google Gemini  
Automatically detects:
- Band colors  
- Multiplier  
- Tolerance  
- Band orientation (left ↔ right auto‑fix)  
- Standard resistor values  
- Snapped E‑series (E24) recommended value  

### ✔️ Advanced Color Normalization  
Handles:
- Faded bands  
- Damaged resistors  
- Low‑light photos  
- Blue/green body resistors  
- Metallic gold/silver bands  

### ✔️ Fully Mobile Compatible  
- Works on any phone on the same Wi‑Fi  
- Open frontend in mobile browser  
- Analyze directly from phone camera  

---

## 📁 Project Structure

```
registor-reader/
│
├── server/
│   ├── venv/                 # Python virtual environment
│   ├── main.py               # FastAPI backend + Gemini vision processing
│   ├── run-server.ps1        # One-click launcher for Windows
│   └── requirements.txt
│
└── web/
    └── index.html            # Advanced frontend UI
```

---

## 🧩 How It Works

### 1️⃣ User uploads/takes a resistor photo  
The web UI compresses image → sends to FastAPI.

### 2️⃣ Backend sends image to Gemini Vision  
Gemini returns:
- JSON with band list  
- Color names  
- Digit/multiplier/tolerance roles  
- Confidence  

### 3️⃣ Backend computes resistor value  
Using standard resistor tables.

### 4️⃣ UI displays results  
Including:
- Raw value  
- Snapped E24 value  
- Tolerance  
- Band chips  
- Mode used (Gemini SDK / REST fallback)

---

## 🛠 Installation

### 1️⃣ Clone project
```
git clone https://github.com/YOUR_USERNAME/resistor-reader.git
cd resistor-reader
```

### 2️⃣ Install server dependencies
```
cd server
python -m venv venv
venv\Scriptsctivate
pip install -r requirements.txt
```

### 3️⃣ Edit your Google Gemini API key  
Open:
```
server/run-server.ps1
```
Add your key:
```
$env:GOOGLE_API_KEY="YOUR_API_KEY"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

### 4️⃣ Start backend + frontend auto-hosting
```
.
un-server.ps1
```

You will see:
```
Backend:  http://YOUR_PC_IP:8000/
Frontend: http://YOUR_PC_IP:5500/?api=http://YOUR_PC_IP:8000
```

---

## 📱 Run on Mobile

1. Connect your **PC & mobile to same Wi‑Fi**
2. Open the frontend URL on your phone:
```
http://YOUR_PC_IP:5500/
```
Works instantly.

---

## 📝 Example Output

- Colors detected: **brown, black, black, red, brown**
- Value: **10.00 kΩ**
- Tolerance: **1%**
- Snapped E24: **10 kΩ**

---

## 🛡 Troubleshooting

### ❌ “Failed to fetch”  
Cause: Phone can’t reach backend.  
Fix:
- Ensure backend runs with `--host 0.0.0.0`
- Allow Windows Firewall incoming on port **8000**
- Phone + PC must be on same Wi‑Fi

### ❌ “Gemini could not read bands”  
Fix:
- Check API key  
- Camera focus better  
- Use white background  

---

## ⭐ Future Improvements  
- Full PWA mobile app  
- Auto-rotate fix  
- Batch resistor analysis  
- On-device ML fallback  

---

## 🏆 Author  
**Shad**  
Intern — UIU Mars Rover Team (Autonomous Subteam)
---

## 📜 License  
MIT License.
