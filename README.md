# 🎬 3WHs Video Content Creator Telegram Bot (AI Agent)

ជំនួយការឆ្លាតវៃ AI Agent នៅលើ Telegram សម្រាប់បង្កើតមាតិកាវីដេអូខ្លី (TikTok, Facebook Reels, YouTube Shorts) និងវីដេអូវែង តាមរូបមន្ត **3WHs Framework (What, Why, Who/When/Where, How)** ជារៀងរាល់ថ្ងៃ។

---

## 🌟 មុខងារសំខាន់ៗ (Features)
1. **បង្កើត Script វីដេអូ 3WHs ពេញលេញ**: ផ្តល់ជូននូវ Title, Hook (៣ វិនាទីដំបូង), What, Why, Who, How (ជំហានអនុវត្ត 1-2-3), Call to Action (CTA), Caption, Hashtags និង Thumbnail Idea។
2. **ស្វែងរកគំនិតមាតិកាប្រចាំថ្ងៃ (Daily Trending Ideas)**: ផ្ដល់គំនិតប្រធានបទ 3WHs ថ្មីៗ និងទាក់ទាញ តាមវិស័យនីមួយៗ។
3. **ផ្ញើសារស្វ័យប្រវត្តិតាមម៉ោងកំណត់ (Daily Broadcast Scheduler)**: ផ្ញើគំនិតមាតិកា និង Script មកកាន់ Telegram របស់អ្នករៀងរាល់ព្រឹក (ឧទាហរណ៍ ម៉ោង 8:00 ព្រឹក) ដោយស្វ័យប្រវត្តិ។
4. **ជជែកពិភាក្សាដោយសេរី (Interactive Chat)**: ជជែក ឬពិគ្រោះយោបល់ជាមួយ AI Content Coach គ្រប់ពេលវេលា។

---

## 🚀 របៀបរៀបចំ និងដំណើរការ (Setup & Run)

### ជំហានទី ១៖ បញ្ចូល API Keys ក្នុង file `.env`
បើក file [`.env`](file:///c:/Users/USER/Desktop/bot%203WHs/.env) រួចបំពេញព័ត៌មាន៖
```env
TELEGRAM_BOT_TOKEN=លេខ_Token_ទទួលបានពី_BotFather
GEMINI_API_KEY=លេខ_API_Key_ទទួលបានពី_Google_AI_Studio
DAILY_TIME=08:00
TIMEZONE=Asia/Phnom_Penh
```

### ជំហានទី ២៖ ដំណើរការ Bot
អ្នកអាចដំណើរការបានតាម ២ របៀប៖
* **របៀបទី ១ (ងាយស្រួលបំផុត)**: Double click លើ file [`run_bot.bat`](file:///c:/Users/USER/Desktop/bot%203WHs/run_bot.bat)
* **របៀបទី ២ (តាម Terminal/PowerShell)**:
  ```powershell
  .\venv\Scripts\python.exe bot.py
  ```

---

## 📱 ពាក្យបញ្ជាលើ Telegram (Bot Commands)

| Command | ការពិពណ៌នា |
|---|---|
| `/start` | បង្ហាញផ្ទាំងដើម និងប៊ូតុងមុខងាររហ័ស |
| `/script <ប្រធានបទ>` | បង្កើត Script 3WHs ពេញលេញភ្លាមៗ (ឧ. `/script វិធីសន្សំលុយ`) |
| `/ideas [វិស័យ]` | សុំគំនិតប្រធានបទ 3WHs ថ្មីៗសម្រាប់ថ្ងៃនេះ |
| `/subscribe` | ចុះឈ្មោះទទួល Script វីដេអូស្វ័យប្រវត្តិតាមម៉ោងកំណត់រាល់ព្រឹក |
| `/unsubscribe` | ផ្អាកការទទួលមាតិកាប្រចាំថ្ងៃ |
| `/status` | ពិនិត្យមើលស្ថានភាពនៃការតភ្ជាប់ និងម៉ោង Schedule |
| `/help` | មើលការណែនាំ និងបញ្ជីពាក្យបញ្ជាទាំងអស់ |

---

## 📂 រចនាសម្ព័ន្ធ Folder (Project Structure)
- [`bot.py`](file:///c:/Users/USER/Desktop/bot%203WHs/bot.py) : កូដមេរបស់ Telegram Bot & Daily Scheduler
- [`ai_service.py`](file:///c:/Users/USER/Desktop/bot%203WHs/ai_service.py) : កូដសម្រាប់ភ្ជាប់ និងបញ្ជា Google Gemini AI
- [`prompts.py`](file:///c:/Users/USER/Desktop/bot%203WHs/prompts.py) : System Prompts & រូបមន្ត 3WHs Video Framework
- [`.env`](file:///c:/Users/USER/Desktop/bot%203WHs/.env) : កន្លែងដាក់ Bot Token & Gemini API Key
- [`run_bot.bat`](file:///c:/Users/USER/Desktop/bot%203WHs/run_bot.bat) : Shortcut សម្រាប់ចុចដំណើរការ Bot ភ្លាមៗ
