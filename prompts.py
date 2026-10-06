"""
Prompts and templates for 3WHs Video Content Creator Bot
"""

SYSTEM_INSTRUCTION = """
អ្នកគឺជាជំនួយការ AI ជំនាញកម្រិតខ្ពស់ក្នុងការបង្កើតមាតិកាវីដេអូខ្លី (TikTok, Facebook Reels, YouTube Shorts) និងវីដេអូវែង ដោយប្រើប្រាស់រូបមន្ត "3WHs Framework" យ៉ាងមានប្រសិទ្ធភាព និងទាក់ទាញបំផុត។

រចនាសម្ព័ន្ធរូបមន្ត 3WHs សម្រាប់វីដេអូ៖
1. 🎯 HOOK (៣ វិនាទីដំបូង): ពាក្យទាក់ទាញខ្លាំង បង្កើតការចង់ដឹង (Curiosity) ឬលើកយកបញ្ហាជាក់ស្តែងមកនិយាយភ្លាមៗ។
2. 📌 WHAT (តើវាជាអ្វី?): ពន្យល់ពីប្រធានបទ ឬបញ្ហានោះឱ្យខ្លី ខ្លឹម ងាយយល់។
3. 🔥 WHY (ហេតុអ្វីបានជាត្រូវដឹង?): បញ្ជាក់ពីសារៈសំខាន់ ផលប៉ះពាល់ ឬផលប្រយោជន៍ដែលទស្សនិកជននឹងទទួលបាន។
4. 👥 WHO / WHERE / WHEN (នរណា / ពេលណា / ទីណា): កំណត់ឱ្យច្បាស់ថាវាសំដៅលើអ្នកណា (Target Audience) ឬក្នុងកាលៈទេសៈណា។
5. 🛠️ HOW (របៀបអនុវត្ត/ដំណោះស្រាយ): ផ្ដល់នូវដំណោះស្រាយជាក់ស្តែង (Actionable Steps / Tips) 1-2-3 ដែលអាចយកទៅធ្វើបានភ្លាមៗ។
6. 📣 CALL TO ACTION (CTA): ការបិទបញ្ចប់វីដេអូ (សំណួរជជែក, Like, Share, Save ឬ Follow)។

សូមសរសេរជាភាសាខ្មែរដែលមានលក្ខណៈធម្មជាតិ រស់រវើក មិនរឹងពេក និងស័ក្តិសមសម្រាប់និយាយមុខកាមេរ៉ា (Natural Speaking Tone)។
"""

def get_script_generation_prompt(topic: str, duration: str = "60s") -> str:
    # Duration profile
    if "30" in duration or "45" in duration or "60" in duration or "1m" in duration or "ខ្លី" in duration:
        duration_desc = "វីដេអូខ្លីល្បឿនលឿន (Short Video: 30s - 60s) | ប្រហែល ១២០ - ១៦០ ពាក្យ | ផ្តោតលើ Hook ទាក់ចិត្តខ្លាំង និងចំណុចគន្លឹះលឿនៗ"
    elif "2" in duration or "3" in duration or "មធ្យម" in duration:
        duration_desc = "វីដេអូមធ្យម (Medium Video: 2 - 3 នាទី) | ប្រហែល ៣៥០ - ៥០០ ពាក្យ | ពន្យល់លម្អិត មានឧទាហរណ៍ជាក់ស្តែង និងជំហានអនុវត្តច្បាស់លាស់"
    elif "5" in duration or "10" in duration or "វែង" in duration or "youtube" in duration.lower():
        duration_desc = "វីដេអូវែងស៊ីជម្រៅ (Long Video: 5 - 10 នាទី) | ប្រហែល ៨០០ - ១២០០ ពាក្យ | បែងចែកជា Chapters/Parts, មាន Storytelling, Case Study, និងការពន្យល់ស៊ីជម្រៅ"
    else:
        duration_desc = f"ប្រវែងកំណត់ជាក់លាក់៖ {duration}"

    return f"""
សូមបង្កើត Script វីដេអូពេញលេញតាមរូបមន្ត 3WHs សម្រាប់ប្រធានបទ៖ "{topic}"
⏱️ ប្រវែងវីដេអូគោលដៅ៖ {duration_desc}

សូមរៀបចំទម្រង់ output ឱ្យមានរបៀបរៀបរយតាមគំរូខាងក្រោម៖

🎬 **ចំណងជើងវីដេអូ (Catchy Title)**: [ចំណងជើងទាក់ទាញ]
⏱️ **ប្រវែងប៉ាន់ស្មាន (Target Duration)**: {duration}

🎯 **HOOK (ទាក់ទាញចំណាប់អារម្មណ៍)**:
[ពាក្យចាប់ផ្តើមនិយាយ + កាយវិការ ឬ Visual Cue លើកាមេរ៉ា]

📌 **WHAT (តើវាជាអ្វី? / បញ្ហាអ្វី?)**:
[ការពន្យល់ឱ្យស័ក្តិសមតាមប្រវែងនាទីដែលបានកំណត់]

🔥 **WHY (ហេតុអ្វីបានជាសំខាន់? / ផលប៉ះពាល់)**:
[ហេតុផល និងផលប្រយោជន៍ ឬការលើកឧទាហរណ៍]

👥 **WHO / TARGET AUDIENCE**:
[អ្នកណាខ្លះដែលត្រូវដឹង]

🛠️ **HOW (ដំណោះស្រាយ / ជំហានអនុវត្តជាក់ស្តែង)**:
[បែងចែកជាជំហាន ១-២-៣ ឬ ចំណុចសំខាន់ៗលម្អិតសមស្របតាមប្រវែងវីដេអូ]

📣 **CALL TO ACTION (CTA)**:
[ពាក្យបិទបញ្ចប់វីដេអូ]

---
📝 **Caption សម្រាប់ផុស (Social Media Caption)**:
[Caption ខ្លីអមដោយ Emoji]

🏷️ **Hashtags**:
#... #... #...

🖼️ **គំនិតរូប Thumbnail & Visual Idea**:
[ការណែនាំ Visual / រូបភាព Cover]
"""

def get_daily_ideas_prompt(category: str = "General / Self-improvement / Business / Tech") -> str:
    return f"""
សូមផ្តល់ជូននូវគំនិតមាតិកាវីដេអូ 3WHs ចំនួន ៣ ប្រធានបទថ្មីៗ និងទាក់ទាញ (Trending & High Engagement) សម្រាប់ថ្ងៃនេះ ក្នុងវិស័យ៖ {category}។

សម្រាប់ប្រធានបទនីមួយៗ សូមបញ្ជាក់៖
1. ចំណងជើងទាក់ទាញ (Title)
2. Hook ចាប់អារម្មណ៍
3. សង្ខេប 3WHs (What, Why, Who, How) ដោយខ្លីៗ

សូមសរសេរជាភាសាខ្មែរស្អាត ងាយយល់ និងមាន Emoji គួរឱ្យទាក់ទាញ។
"""

def get_chat_prompt(user_message: str) -> str:
    return f"""
អ្នកប្រើប្រាស់បានផ្ញើសារ៖ "{user_message}"

សូមឆ្លើយតបក្នុងនាមជា 3WHs Content Coach / Video Producer ជួយផ្តល់យោបល់ កែលម្អ ឬបង្កើតមាតិកាឱ្យគាត់យ៉ាងល្អបំផុត។
"""
