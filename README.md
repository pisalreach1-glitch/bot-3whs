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

## 📂 រចនាសម្ព័ន្ធ Folder (Project Structure)
- [`bot.py`](file:///c:/Users/USER/Desktop/bot%203WHs/bot.py) : កូដមេរបស់ Telegram Bot, Handlers, Calibration & Daily Broadcast
- [`script_models.py`](file:///c:/Users/USER/Desktop/bot%203WHs/script_models.py) : Data Models, Timeline Validation, Khmer Speaking Pace Heuristic & Telegram Formatting
- [`ai_service.py`](file:///c:/Users/USER/Desktop/bot%203WHs/ai_service.py) : កូដគ្រប់គ្រង Google Gemini AI, Structured Script JSON, News Grounding, Validation & Caching
- [`prompts.py`](file:///c:/Users/USER/Desktop/bot%203WHs/prompts.py) : System Prompts, Structured JSON Schemas, Visual Direction & 3WHs Formats
- [`trend_sources.py`](file:///c:/Users/USER/Desktop/bot%203WHs/trend_sources.py) : ម៉ូឌុលទាញយក និង Parse Public RSS News ដោយឥតគិតថ្លៃ
- [`.env`](file:///c:/Users/USER/Desktop/bot%203WHs/.env) : កន្លែងកំណត់ Environment Variables
- [`run_bot.bat`](file:///c:/Users/USER/Desktop/bot%203WHs/run_bot.bat) : Shortcut សម្រាប់ដំណើរការ Bot
