# 🎬 3WHs Video Content Creator Telegram Bot (AI Agent)

ជំនួយការឆ្លាតវៃ AI Agent នៅលើ Telegram សម្រាប់បង្កើតមាតិកាវីដេអូខ្លី (TikTok, Facebook Reels, YouTube Shorts) និងវីដេអូវែង តាមរូបមន្ត **3WHs Framework (What, Why, Who/When/Where, How)** ជាមួយ **ផែនការថតតាមពេលវេលា (Timestamped Shooting Plan)** និង **ការប៉ាន់ស្មានរយៈពេលនិយាយជាក់ស្តែង**។

---

## 🌟 មុខងារសំខាន់ៗ (Features)

1. **ស្គ្រីប និងផែនការថតតាមពេលវេលា (Timestamped Shooting Plan)**:
   - គាំទ្រទម្រង់ទាំង ៦៖ 3WHs Hook Script, POV / Storytelling, Myth vs Reality, Before & After, Hot Take, Top List។
   - គាំទ្ររយៈពេលទាំង ៤៖ ៦០ វិនាទី, ២ នាទី, ៣ នាទី និង ៥ នាទី។
   - លម្អិតប្លង់នីមួយៗ (Scene-by-Scene)៖
     - `start_seconds` និង `end_seconds` (ប្លង់បន្តបន្ទាប់គ្មានចន្លោះ Gap ឬ Overlap)
     - `spoken_text_km` (ពាក្យនិយាយជាក់ស្តែង)
     - `shot_size` (Close-Up, Medium Shot, Wide Shot, B-roll...)
     - `camera_action` (Static, Pan, Tilt, Zoom, Tracking, Handheld)
     - `visual_action` (សកម្មភាពលើអេក្រង់ជាក់ស្តែងដែលថតដោយទូរស័ព្ទដៃ)
     - `on_screen_text_km` (អក្សរខ្លីៗលើអេក្រង់)
     - `editing_note` (ការកាត់ត, J-cut, Transition)
     - `audio_note` (SFX, Tone តន្ត្រីគ្មាន Copyright)
   - ភ្ជាប់មកជាមួយ Title, Target Audience, Hook, Caption, Hashtags និង CTA។

2. **ការប៉ាន់ស្មានរយៈពេលនិយាយ (Estimated Speaking Duration)**:
   - មិនរាប់ពាក្យដោយប្រើ Whitespace Splitting ឡើយ (ដោយសារភាសាខ្មែរសរសេរជាប់គ្នាគ្មានដកឃ្លាចន្លោះពាក្យ)។
   - ប្រើប្រាស់រូបមន្តរាប់តួអក្សរ/ព្យាង្គភាសាខ្មែរ (Khmer Dialogue Units Heuristic) សម្រាប់តែពាក្យនិយាយសុទ្ធ។
   - បង្ហាញជា «រយៈពេលនិយាយ៖ ប៉ាន់ស្មាន» ដោយបញ្ជាក់ច្បាស់ថាមិនមែនជាការវាស់វែងសំឡេងពិតប្រាកដឡើយ។
   - ផ្ដល់ការព្រមាន (Warning) ប្រសិនបើពាក្យនិយាយក្នុងប្លង់ណាមួយវែងហួសពីប្រវែងវិនាទីនៃប្លង់នោះ។

3. **ការកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួន (/pace Calibration)**:
   - ពាក្យបញ្ជាគ្មាន AI `/pace <ចំនួនវិនាទី> <អត្ថបទខ្មែរដែលបានអាន>`។
   - គណនាល្បឿនអានជាក់ស្តែងរបស់អ្នក (~តួអក្សរ/វិនាទី) និងរក្សាទុកក្នុង User Settings ដើម្បីយកទៅគណនាក្នុង Script។

4. **ការដឹកនាំប្លង់រូបភាព និងឧបករណ៍សាមញ្ញ (Visual Direction)**:
   - ណែនាំប្លង់ជាក់ស្តែងដែលថតបានដោយទូរស័ព្ទដៃ និងឧបករណ៍ធម្មតា (Ring light, ពន្លឺធម្មជាតិ)។
   - សកម្មភាពបើកក្បាល (Opening Hook) ចាប់អារម្មណ៍ភ្លាមៗ៖ បង្ហាញលទ្ធផល, បង្ហាញកំហុស/បញ្ហា, បង្ហាញវត្ថុ ឬសួរសំណួរ។
   - ដាច់ខាតមិនបង្កើត Testimonials ក្លែងក្លាយ, តួលេខស្ថិតិក្លែងក្លាយ, ឬលទ្ធផល Before/After គ្មានភស្តុតាង។

5. **គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ (News-Grounded Content Ideas)**:
   - ទាញយកព័ត៌មាន ៤៨ ម៉ោងចុងក្រោយពី Public RSS Feeds (Google News, BBC, Al Jazeera) ដោយឥតគិតថ្លៃ។
   - ផ្ទៀងផ្ទាត់ Source IDs ក្នុង Python និងបង្កើត Link ពិតប្រាកដ។
   - ប្រសិនបើគ្មានព័ត៌មានថ្មី ប្ដូរទៅ Honest Fallback «គំនិតមាតិកាទូទៅពី AI - មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ»។

6. **សន្សំសំចៃ Free Quota & Daily Broadcast**:
   - Cache ប្រភពព័ត៌មាន ១ ម៉ោង និង Cache គំនិតប្រចាំថ្ងៃតាមថ្ងៃក្នុងស្រុក (`Asia/Phnom_Penh`) និងតាមវិស័យ។
   - Daily Broadcast បង្កើតគំនិតតែម្តងគត់នៅក្រៅ Loop រួចផ្ញើជូនគ្រប់ Subscribers។
   - Concurrency Lock ការពារការហៅ Gemini ស្ទួនពីសំណើដំណាលគ្នា។

7. **រក្សាសុវត្ថិភាព Script នៅពេល Refine**:
   - នៅពេលកែប្រែ Hook, សង្ខេប Script ឱ្យខ្លី, ឬបង្កើតឡើងវិញ ប្រសិនបើមានបញ្ហា Error នោះ Script ជោគជ័យមុនមិនត្រូវបានលុបបំបាត់ឡើយ។
   - ការត្រឡប់ទៅ Menu ដើម ឬការផ្លាស់ប្តូររយៈពេលវីដេអូ មិនលុប Script ចាស់ឡើយ។

---

## 📱 ពាក្យបញ្ជាលើ Telegram (Bot Commands)

| Command | ការពិពណ៌នា |
|---|---|
| `/start` | បង្ហាញផ្ទាំង Menu និងទម្រង់ Content ទាំង ៦ |
| `/pace <វិនាទី> <អត្ថបទ>` | វាស់ និងកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួន (ឧ. `/pace 10 សួស្តី...`) |
| `/ideas [វិស័យ]` | គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ ៤៨ ម៉ោងចុងក្រោយ (ឧ. `/ideas បច្ចេកវិទ្យា`) |
| `/subscribe` | ចុះឈ្មោះទទួលគំនិតមាតិកាប្រចាំព្រឹក (ម៉ោង 08:00) |
| `/unsubscribe` | ផ្អាកការទទួលសារប្រចាំព្រឹក |
| `/status` | ពិនិត្យមើលស្ថានភាពប្រព័ន្ធ, API Key, រយៈពេលវីដេអូ និងល្បឿននិយាយ |
| `/cancel` | បោះបង់សំណើបច្ចុប្បន្ន និងត្រឡប់ទៅ Menu ដើម |
| `/help` | មើលការណែនាំ និងបញ្ជីពាក្យបញ្ជាទាំងអស់ |

---

## 🚀 របៀបរៀបចំ និងដំណើរការ (Zero Additional Spending Setup)

### ជំហានទី ១៖ បញ្ចូល API Keys ក្នុង file `.env`
បើក file [`.env`](file:///c:/Users/USER/Desktop/bot%203WHs/.env) រួចបំពេញព័ត៌មាន៖
```env
TELEGRAM_BOT_TOKEN=លេខ_Token_ទទួលបានពី_BotFather
GEMINI_API_KEY=លេខ_API_Key_ទទួលបានពី_Google_AI_Studio
DAILY_TIME=08:00
TIMEZONE=Asia/Phnom_Penh
```

### ជំហានទី ២៖ ដំណើរការ Bot
* **របៀបទី ១ (Shortcut)**: Double click លើ file [`run_bot.bat`](file:///c:/Users/USER/Desktop/bot%203WHs/run_bot.bat)
* **របៀបទី ២ (Terminal/PowerShell)**:
  ```powershell
  .\venv\Scripts\python.exe bot.py
  ```

---

## 📂 រចនាសម្ព័ន្ធគម្រោង (Project Architecture)

```
bot-3whs/
├── bot.py                       # Application entry point & service wiring
├── config.py                    # Environment & validated configuration (AppConfig)
├── ai_service.py                # Gemini transport, retries & JSON generation
├── prompts.py                   # Prompts for all 6 formats & comedy
├── script_models.py             # Script/scene schema & strict timeline validation
├── trend_sources.py             # Public RSS news retrieval & caching
│
├── app/
│   ├── __init__.py
│   ├── models.py                # UserKey, Draft, GenerationRequest, SavedScript, EvidenceRecord, Idea
│   ├── callbacks.py             # Compact callback encoding/decoding (<64 bytes)
│   ├── keyboards.py             # Telegram keyboards with Khmer labels
│   ├── views.py                 # Khmer rendering for screens & script views (Read, Shots, Caption)
│   ├── navigation.py            # Screen transitions, history stack & Back/Home navigation
│   ├── storage.py               # SQLite repository with short parameterized transactions
│   ├── task_manager.py          # Per-UserKey request tracking, cancellation & concurrency deduplication
│   ├── telegram_io.py           # Message splitting (<=4000 chars) & safe Markdown fallback
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── commands.py          # /start, /help, /cancel, /ideas, /pace, /status, /subscribe, /unsubscribe
│   │   ├── menu.py              # Main menu routing & format navigation
│   │   ├── creation.py          # Format pick -> Topic input -> Review -> Generate pipeline
│   │   ├── ideas.py             # Category ideas retrieval & selection to draft
│   │   ├── scripts.py           # Script views (Summary, Read, Shots, Caption) & revisions
│   │   ├── settings.py          # Button-based settings (Duration, Pace, Subscription)
│   │   └── comedy.py            # Comedy creation flow (Topic -> Style -> Actors -> Generate)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── generation.py        # Strict JSON/timeline validation & atomic SQLite save
│   │   ├── ideas.py             # News evidence retrieval & strict citation verification
│   │   ├── refinements.py       # Shorten, regenerate & 3 structured hook alternatives
│   │   └── broadcast.py         # Generate general daily ideas once outside subscriber loop
│   │
│   └── jobs.py                  # Telegram JobQueue daily broadcast scheduler
│
├── tests/
│   ├── test_navigation.py       # Screen stack, Back/Home transitions, UserKey isolation
│   ├── test_creation.py         # All 6 formats, comedy, durations, retry snapshot
│   ├── test_ideas_flow.py       # Evidence retrieval, citation validation, draft transfer
│   ├── test_refinements.py      # Shorten, hook generation/application, zero-AI view switching
│   ├── test_settings.py         # Duration setting, pace calibration, subscription toggles
│   ├── test_task_manager.py     # Request tracking, concurrency blocking, cancellation
│   ├── test_storage.py          # SQLite transactions, failure isolation, JSON file migration
│   └── test_callbacks.py        # 64-byte callback limit, token validation, security
│
├── test_timestamped_scripts.py  # Preserved comprehensive shooting plan & validation tests
├── test_news_grounding.py       # Preserved news grounding & citation verification tests
├── requirements.txt
├── .env.example
└── README.md
```

---

## 💾 ការផ្ទុកទិន្នន័យ និងដែនកំណត់ Hosting (Storage & Durability)

- **SQLite Database**: ប្រើប្រាស់ Python standard-library `sqlite3` ជាមួយ Parameterized queries ការពារ SQL injection និងប្រតិបត្តិការក្នុង Short transactions។
- **UserKey Isolation**: គន្លឹះសម្គាល់អ្នកប្រើ `UserKey(chat_id, user_id)` ការពារកុំឱ្យអ្នកប្រើផ្សេងគ្នាក្នុង Group chat ច្រឡំ Draft, Settings ឬ Script ផ្ទាល់ខ្លួន។
- **Atomic Script Saving**: ការរក្សាទុក Script ជោគជ័យ និងការ Update `last_successful_scripts` ប្រព្រឹត្តទៅក្នុង Transaction តែមួយ (Atomic)។ បើមាន Error បរាជ័យ Script ជោគជ័យចាស់មិនត្រូវបានបាត់បង់ឡើយ។
- **Safe JSON Migration**: រៀបចំ Migration ស្វ័យប្រវត្តិតែម្ដងគត់ពី `user_settings.json` និង `subscribers.json` ចាស់ដោយមិនលុប File ដើមឡើយ។
- ⚠️ **ចំណាំអំពី Durability លើ Cloud Hosting**: ការប្រើប្រាស់ SQLite លើ Container Filesystem បណ្តោះអាសន្ន (Ephemeral Filesystem ដូចជា Render.com Free Web Service) គឺ **មិនជាប់ជានិរន្តរ៍ (Not durable)** នៅពេល Server ត្រូវ Replace ឬ Redeploy ឡើយ។ ប្រសិនបើចង់បានទិន្នន័យយូរអង្វែង សូមភ្ជាប់ Persistent Disk ឬកំណត់ `BOT_DB_PATH` ទៅកាន់ Disk ខាងក្រៅ។

---

## 🧪 ការរត់ Unit Tests (Testing & Verification)

រត់ Test ទាំងអស់ដោយគ្មានការចំណាយ និងគ្មានការហៅ Gemini API ផ្ទាល់ (Mocked 100%):

```powershell
# រត់ Tests ទាំងអស់ក្នុងគម្រោង (69 Tests)
.\venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"

# ឬរត់តាម Folder tests/
.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
