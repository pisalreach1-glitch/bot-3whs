# 🎬 3WHs Video Content Creator Telegram Bot (AI Agent)

ជំនួយការឆ្លាតវៃ AI Agent នៅលើ Telegram សម្រាប់បង្កើតមាតិកាវីដេអូខ្លី (TikTok, Facebook Reels, YouTube Shorts) និងវីដេអូវែង តាមរូបមន្ត **3WHs Framework (What, Why, Who/When/Where, How)**។

---

## 🌟 មុខងារសំខាន់ៗ (Features)
1. **បង្កើត Script វីដេអូ 3WHs ពេញលេញ**: ផ្តល់ជូននូវ Title, Hook (៣ វិនាទីដំបូង), What, Why, How, Call to Action (CTA), Caption, Hashtags និង Thumbnail Idea សម្រាប់ទម្រង់ទាំង ៦ (3WHs Script, POV/Storytelling, Myth vs Reality, Before & After, Hot Take, Top List)។
2. **គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ (News-Grounded Content Ideas)**: ផ្ដល់គំនិតប្រធានបទមាតិកា ៣ បែប ដោយផ្អែកលើព័ត៌មានជាក់ស្ដែងដែលទើបចុះផ្សាយក្នុងរយៈពេល ៤៨ ម៉ោងចុងក្រោយ។
3. **ផ្ញើសារស្វ័យប្រវត្តិតាមម៉ោងកំណត់ (Daily Broadcast Scheduler)**: បង្កើតគំនិតមាតិកាម្តង និងផ្ញើជូនអ្នក Subscribe ទាំងអស់រៀងរាល់ព្រឹក (ម៉ោង 08:00 ព្រឹក) ដោយស្វ័យប្រវត្តិ។
4. **ឧបករណ៍កែលម្អ Script (Refinement Tools)**: ប្ដូរ Hook ថ្មី ៣ បែប, សង្ខេបឱ្យខ្លីខ្លឹម, បង្កើតឡើងវិញ ឬជ្រើសរើសរយៈពេលវីដេអូ (៦០វិនាទី ដល់ ៥នាទី)។
5. **ជជែកពិភាក្សាដោយសេរី (Interactive Chat)**: ជជែក ឬពិគ្រោះយោបល់ជាមួយ AI Content Coach។

---

## 📰 ប្រភពព័ត៌មាន និងការកំណត់ (News Sources & Transparency)

### ប្រភព RSS សាធារណៈ (Public RSS Feeds)
ប្រព័ន្ធទាញយកអត្ថបទព័ត៌មានដោយផ្ទាល់តាមរយៈ Public RSS Feeds ដែលមិនទាមទារ API key ឬការចំណាយបន្ថែម៖
- **Google News**: Cambodia News, World Asia, Business, Technology
- **BBC News**: World Asia RSS
- **Al Jazeera**: World News RSS

### ដែនកំណត់ និងភាពស្មោះត្រង់ (Limitations & Transparency)
- **មិនមែនជាការវាស់ស្ទង់ Viral លើ Social Media**: ចំនួនអត្ថបទព័ត៌មានមិនមែនជាភស្តុតាងបញ្ជាក់ពីភាពល្បីល្បាញលើ TikTok ឬ Facebook ឡើយ។ មុខងារនេះផ្ដល់គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗប៉ុណ្ណោះ។
- **ការចម្រាញ់ភាពថ្មី (Freshness Filter)**: Bot ផ្ដល់អាទិភាពលើអត្ថបទដែលបានចុះផ្សាយក្នុងរយៈពេល ៤៨ ម៉ោងចុងក្រោយ (`timezone-aware`)។ អត្ថបទដែលគ្មានកាលបរិច្ឆេទច្បាស់លាស់នឹងមិនត្រូវបានរាប់បញ្ចូលក្នុងភាពថ្មីឡើយ។
- **ប្រព័ន្ធ Cache ក្នុងអង្គចងចាំ (In-Memory Caching)**:
  - ប្រភព RSS ត្រូវបាន Cache រយៈពេល ១ ម៉ោង ដើម្បីកាត់បន្ថយ Network request និងរក្សា Free quota។
  - គំនិតមាតិកាប្រចាំថ្ងៃត្រូវបាន Cache តាមកាលបរិច្ឆេទក្នុងស្រុក (`Asia/Phnom_Penh`) និងតាម Category។
  - *សម្គាល់:* Cache ត្រូវបានរក្សាទុកក្នុង RAM (In-Memory) ដូច្នេះរាល់ពេល Restart bot ទិន្នន័យ Cache នឹងចាប់ផ្ដើមឡើងវិញ។
- **Honest Fallback (ប្រព័ន្ធជំនួសដោយស្មោះត្រង់)**: ប្រសិនបើការទាញយកព័ត៌មានបរាជ័យ ឬមិនមានព័ត៌មានថ្មីៗទាក់ទងនឹងវិស័យដែលបានស្នើសុំ Bot នឹងប្ដូរទៅប្រើ «គំនិតមាតិកាទូទៅពី AI» ដោយបញ្ជាក់យ៉ាងច្បាស់ថា «មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ» ដោយមិនបង្កើតតំណភ្ជាប់ ឬប្រភពក្លែងក្លាយឡើយ។

---

## 🚀 របៀបរៀបចំ និងដំណើរការ (Setup & Run)

### ជំហានទី ១៖ បញ្ចូល API Keys ក្នុង file `.env`
បើក file [`.env`](file:///c:/Users/USER/Desktop/bot%203WHs/.env) រួចបំពេញព័ត៌មាន (Zero-cost setup):
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
| `/start` | បង្ហាញផ្ទាំង Menu និងទម្រង់ Content ទាំង ៦ |
| `/ideas [វិស័យ]` | គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ ៤៨ ម៉ោងចុងក្រោយ (ឧ. `/ideas បច្ចេកវិទ្យា`) |
| `/subscribe` | ចុះឈ្មោះទទួលគំនិតមាតិកាប្រចាំព្រឹក (ម៉ោង 08:00) |
| `/unsubscribe` | ផ្អាកការទទួលសារប្រចាំព្រឹក |
| `/status` | ពិនិត្យមើលស្ថានភាពនៃការតភ្ជាប់, API និងម៉ោង Schedule |
| `/cancel` | បោះបង់សំណើដែលកំពុងធ្វើ ហើយត្រឡប់ទៅ Menu ដើម |
| `/help` | មើលការណែនាំ និងបញ្ជីពាក្យបញ្ជាទាំងអស់ |

---

## 📂 រចនាសម្ព័ន្ធ Folder (Project Structure)
- [`bot.py`](file:///c:/Users/USER/Desktop/bot%203WHs/bot.py) : កូដមេរបស់ Telegram Bot, Handlers & Daily Broadcast
- [`trend_sources.py`](file:///c:/Users/USER/Desktop/bot%203WHs/trend_sources.py) : ម៉ូឌុលទាញយក និង Parse Public RSS News (Google News, BBC, Al Jazeera) ដោយមិនគិតថ្លៃ
- [`ai_service.py`](file:///c:/Users/USER/Desktop/bot%203WHs/ai_service.py) : កូដគ្រប់គ្រង Google Gemini AI, Validation, Link Building & Caching
- [`prompts.py`](file:///c:/Users/USER/Desktop/bot%203WHs/prompts.py) : System Prompts, រូបមន្ត 3WHs & Grounded Prompt Injection Guard
- [`.env`](file:///c:/Users/USER/Desktop/bot%203WHs/.env) : កន្លែងកំណត់ Environment Variables
- [`run_bot.bat`](file:///c:/Users/USER/Desktop/bot%203WHs/run_bot.bat) : Shortcut សម្រាប់ដំណើរការ Bot
