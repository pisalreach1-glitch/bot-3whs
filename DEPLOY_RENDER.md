# 🚀 របៀបដាក់ Bot ឱ្យដំណើរការ ២៤/៧ លើ Render.com (Free 100%)

ការដាក់ Bot លើ [Render.com](https://render.com) នឹងជួយឱ្យ Bot របស់អ្នកដំណើរការរហូត ២៤ ម៉ោង / ៧ ថ្ងៃ ទោះបីអ្នកបិទកុំព្យូទ័រក៏ដោយ។

---

### ជំហានទី ១៖ បង្កើត Repository លើ GitHub
1. ចូលទៅកាន់ [GitHub.com](https://github.com) ហើយបង្កើត **New Repository** មួយ (ឧ. ឈ្មោះ `bot-3whs`)
2. Push កូដក្នុង folder `bot 3WHs` នេះឡើងទៅកាន់ GitHub Repository នោះ (មិនបាច់បារម្ភរឿងបែកធ្លាយ Token ទេ ព្រោះ file `.env` ត្រូវបាន block ដោយ `.gitignore` រួចហើយ)

---

### ជំហានទី ២៖ ភ្ជាប់ជាមួយ Render.com
1. ចូលទៅកាន់ [Render.com](https://dashboard.render.com/) ហើយចុះឈ្មោះ/Login តាម GitHub
2. ចុចប៊ូតុង **"New +"** -> ជ្រើសរើស **"Web Service"**
3. ជ្រើសរើស Repository GitHub `bot-3whs` របស់អ្នក រួចចុច **Connect**
4. បំពេញការកំណត់ដូចខាងក្រោម៖
   * **Name**: `bot-3whs-agent` (ឬឈ្មោះតាមចិត្ត)
   * **Language**: `Python 3`
   * **Branch**: `main` (ឬ `master`)
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `python bot.py`
   * **Instance Type**: ជ្រើសរើស **Free**

---

### ជំហានទី ៣៖ បន្ថែម Environment Variables
នៅទំព័រដដែល សូមរំកិលចុះក្រោមទៅកាន់ផ្នែក **Environment Variables** រួចចុច **"Add Environment Variable"** ដើម្បីបញ្ចូល៖

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `your_telegram_bot_token_here` |
| `GEMINI_API_KEY` | `your_gemini_api_key_here` |
| `DAILY_TIME` | `08:00` |
| `TIMEZONE` | `Asia/Phnom_Penh` |

5. ចុច **"Create Web Service"** រួចរង់ចាំប្រហែល ១-២ នាទី Render នឹង Build និង Deploy ដោយស្វ័យប្រវត្តិ។

---

### 💡 គន្លឹះបន្ថែមដើម្បីកុំឱ្យ Render Free Sleep (Keep Alive 24/7):
Render Free Web Service អាចនឹង Sleep ប្រសិនបើគ្មានអ្នកចូលមើល Web លើសពី ១៥ នាទី។ ដើម្បីកុំឱ្យវា Sleep៖
1. ចម្លងយក URL របស់ Web Service ដែល Render ផ្ដល់ឱ្យ (ឧ. `https://bot-3whs-agent.onrender.com`)
2. ចូលទៅកាន់ [UptimeRobot.com](https://uptimerobot.com) (Free)
3. បង្កើត **HTTP Monitor** ដាក់ URL នោះ ហើយកំណត់ឱ្យវា Ping រៀងរាល់ **5 នាទី** ម្តង។
👉 នោះ Bot របស់អ្នកនឹងដំណើរការរហូត ២៤/៧ ឥតគិតថ្លៃ ១០០%!
