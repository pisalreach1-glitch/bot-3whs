"""
Prompts and templates for 3WHs Video Content Creator Bot
Includes: 3WHs Hook, POV Story, Myth vs Reality, Before/After, Hot Take, Top List
"""

SYSTEM_INSTRUCTION = """
អ្នកគឺជាជំនួយការ AI និងជា Creative Director ជំនាញកម្រិតខ្ពស់ក្នុងការបង្កើតមាតិកាវីដេអូខ្លី (TikTok, Facebook Reels, YouTube Shorts) និងវីដេអូវែង ដោយប្រើប្រាស់រូបមន្ត "3WHs Framework" យ៉ាងមានប្រសិទ្ធភាព ទាក់ទាញ និងងាយយល់បំផុត។

រូបមន្ត 3WHs រួមមាន៖
1. 🎯 HOOK: ពាក្យទាក់ទាញខ្លាំងក្នុង ៣ វិនាទីដំបូង
2. 📌 WHAT: បញ្ជាក់ពីប្រធានបទ ឬបញ្ហាឱ្យចំៗ ខ្លី ខ្លឹម
3. 🔥 WHY: ហេតុអ្វីបានជាសំខាន់? បើដឹងចំណេញអ្វី បើមិនដឹងខាតអ្វី?
4. 👥 WHO: អ្នកណាខ្លះត្រូវដឹង (Target Audience)
5. 🛠️ HOW: ដំណោះស្រាយ ឬជំហានអនុវត្តជាក់ស្តែង 1-2-3
6. 📣 CTA: ពាក្យបិទបញ្ចប់វីដេអូជំរុញឱ្យទស្សនិកជនធ្វើសកម្មភាព

⛔ ច្បាប់តឹងរ៉ឹងបំផុត (STRICT RULE - NO THAI REFERENCES):
- ដាច់ខាតមិនត្រូវលើកឡើង ឬយកមុខម្ហូប ឈ្មោះ ឬឯកសារយោងណាដែលទាក់ទងនឹងប្រទេសថៃ (Thailand / Thai food) ជាដាច់ខាត!
- សម្រាប់មុខម្ហូប៖ ផ្តោតលើ "មុខម្ហូបខ្មែរប្រពៃណី" ឬប្រទេសផ្សេង (បារាំង, ជប៉ុន, កូរ៉េ, ចិន, អ៊ីតាលី) លើកលែងតែប្រទេសថៃ។

សូមសរសេរជាភាសាខ្មែរធម្មជាតិ រស់រវើក ដូចមនុស្សកំពុងនិយាយមុខកាមេរ៉ា (Natural Speaking Tone)។
"""

# ─────────────────────────────────────────────────────────────────
# CONTENT TYPE: 1 — 3WHs Hook Script (Original)
# ─────────────────────────────────────────────────────────────────
def get_script_generation_prompt(topic: str, duration: str = "60s") -> str:
    if "30" in duration or "45" in duration or "60" in duration or "1m" in duration or "ខ្លី" in duration:
        duration_desc = "វីដេអូខ្លីរហ័ស (30s - 60s) | ~១២០-១៦០ ពាក្យ | ផ្តោតលើ Hook ទាក់ចិត្ត + គន្លឹះខ្លីៗ"
    elif "2" in duration or "3" in duration or "មធ្យម" in duration:
        duration_desc = "វីដេអូមធ្យម (2-3 នាទី) | ~៣៥០-៥០០ ពាក្យ | ពន្យល់លម្អិត + ជំហានជាក់ស្ដែង"
    elif "5" in duration or "10" in duration or "វែង" in duration or "youtube" in duration.lower():
        duration_desc = "វីដេអូវែង (5-10 នាទី) | ~៨០០-១២០០ ពាក្យ | Chapters + Storytelling + Case Study"
    else:
        duration_desc = f"ប្រវែងកំណត់ជាក់លាក់៖ {duration}"

    return f"""
សូមបង្កើត Script វីដេអូពេញលេញតាមរូបមន្ត 3WHs សម្រាប់ប្រធានបទ៖ "{topic}"
⏱️ ប្រវែងវីដេអូ៖ {duration_desc}

━━━━━━━━━━━━━━━━━━━━━
🎬 **ចំណងជើងវីដេអូ (Video Title)**
👉 [ចំណងជើងទាក់ទាញ]
⏱️ **ប្រវែង**: {duration}
━━━━━━━━━━━━━━━━━━━━━

🎯 **១. HOOK (៣ វិនាទីដំបូង)**
🗣️ **ពាក្យ**: "[ពាក្យ Hook ខ្លាំង]"
🎥 **កាយវិការ**: [Visual Cue / Action]

📌 **២. WHAT (តើវាជាអ្វី?)**
🗣️ **ពាក្យ**: "[ការពន្យល់ខ្លីខ្លឹម]"

🔥 **៣. WHY (ហេតុអ្វីបានជាសំខាន់?)**
🗣️ **ពាក្យ**: "[ផលចំណេញ ឬផលប៉ះពាល់]"

👥 **៤. WHO (Target Audience)**
🗣️ **ពាក្យ**: "[Target ឱ្យចំ]"

🛠️ **៥. HOW (ជំហានអនុវត្ត)**
🗣️ **ពាក្យ**:
• **ជំហានទី ១**: ...
• **ជំហានទី ២**: ...
• **ជំហានទី ៣**: ...

📣 **៦. CALL TO ACTION**
🗣️ **ពាក្យ**: "[CTA បិទចប់]"

━━━━━━━━━━━━━━━━━━━━━
📝 **Caption Social Media**
[Caption ទាក់ទាញ + Emoji]

🏷️ **Hashtags**
#... #... #...

🖼️ **Thumbnail / Cover Idea**
[ការណែនាំ Visual + អក្សរធំ]
━━━━━━━━━━━━━━━━━━━━━
"""

# ─────────────────────────────────────────────────────────────────
# CONTENT TYPE: 2 — POV / Storytelling
# ─────────────────────────────────────────────────────────────────
def get_pov_story_prompt(situation: str, niche: str, duration: str = "60 វិនាទី") -> str:
    return f"""
សូមបង្កើត Script វីដេអូ POV / Storytelling Format ដ៏ Viral និងទាក់ទាញ!

📂 វិស័យ: {niche}
🎭 POV / ស្ថានភាព: "{situation}"
⏱️ រយៈពេល: {duration}

Format POV ដែល Viral ខ្លាំង (Watch Time ខ្ពស់):
- ចាប់ផ្ដើមជាមួយ "POV: ..." ឬ "ពេលដែរ..." ឬ "ថ្ងៃដែរខ្ញុំ..."
- ប្រើទស្សនៈ First Person (ខ្ញុំ, យើង)
- បង្ហាញ Emotion ពិត: ភ្ញាក់ផ្អើល, ភ័យ, ស្រឡាញ់, ស្ទើរចាញ់...
- បញ្ចប់ជាមួយ Twist ឬ Lesson ដែល Relatable

━━━━━━━━━━━━━━━━━━━━━
🎭 **POV Script: {situation}**
━━━━━━━━━━━━━━━━━━━━━

🎯 **HOOK (Opening — ចាប់ Scroll ភ្លាម)**
🗣️ "[ពាក្យ POV ចាប់ Emotion ភ្លាម]"
🎥 **Visual**: [ការណែនាំ Setting / Facial Expression]

📖 **STORY BODY (ខ្លឹមសារ Story)**
🗣️ "[Story ចូលដើម — ស្ថានភាព]"
🗣️ "[ការរីកចម្រើន — Problem / Conflict]"
🗣️ "[ថ្ងៃ / ពេលវេលា Turning Point]"

💡 **LESSON / TWIST (Relatable Ending)**
🗣️ "[ការបញ្ចប់ប្រទាក់ចិត្ត / ដែលគ្រប់គ្នា Feel ដូចគ្នា]"

📣 **CTA**
🗣️ "[ពាក្យ CTA ជំរុញ Comment / Share]"

━━━━━━━━━━━━━━━━━━━━━
📝 **Caption**
[Caption Storytelling ដែល Relatable]

🏷️ **Hashtags**
#POV #Story #... #...

🖼️ **Thumbnail Idea**
[Facial Expression / Reaction Shot ដែល Curious]
━━━━━━━━━━━━━━━━━━━━━
"""

# ─────────────────────────────────────────────────────────────────
# CONTENT TYPE: 3 — Myth vs Reality
# ─────────────────────────────────────────────────────────────────
def get_myth_reality_prompt(myth: str, niche: str, duration: str = "60 វិនាទី") -> str:
    return f"""
សូមបង្កើត Script វីដេអូ "Myth vs Reality / ការបំបែកការយល់ច្រឡំ" ដ៏ Viral!

📂 វិស័យ: {niche}
⚡ Myth / ការយល់ច្រឡំ: "{myth}"
⏱️ រយៈពេល: {duration}

ហេតុអ្វីបាន Viral: Hook ភ្ញាក់ → Comment Debate → Share ថ្លែងមតិ → Algorithm Boost

━━━━━━━━━━━━━━━━━━━━━
⚡ **Myth vs Reality: {myth}**
━━━━━━━━━━━━━━━━━━━━━

🎯 **HOOK (ចាប់ Attention ភ្លាម)**
🗣️ "[ពាក្យចាប់ Attention — «អ្នកខ្លះគិតថា... ប៉ុន្តែ...» ឬ «Stop! ការយល់ច្រឡំទី ១ ដែរ...»]"
🎥 **Visual**: [Reaction / Text on Screen]

❌ **MYTH (ការយល់ច្រឡំ — អ្វីដែរមនុស្សជឿ)**
🗣️ "មនុស្សច្រើនគិតថា [Myth ច្បាស់ + ហេតុផលពួកគេជឿ]..."
🎥 **Visual**: [❌ អក្សរ MYTH / Wrong Icon]

✅ **REALITY (ការពិត — ដ៏ Surprising)**
🗣️ "ការពិតគឺ... [Reality ជាក់ស្ដែង + ភ័ស្ដុតាង / ឧទាហរណ៍]"
🎥 **Visual**: [✅ អក្សរ REALITY / Facts]

💡 **WHY IT MATTERS**
🗣️ "[ហេតុអ្វីការដឹងការពិតនេះ ជួយ / ផ្លាស់ប្ដូរជីវិត / ការធ្វើ]"

📣 **CTA — Debate Trigger**
🗣️ "[ពាក្យ CTA ដែលជំរុញ Comment: «Comment ប្រាប់ខ្ញុំ...» ឬ «Share ទៅបង្ហាញ...»]"

━━━━━━━━━━━━━━━━━━━━━
📝 **Caption (ទាក់ Comment)**
[Caption ដែល Provocative + ជំរុញ Debate]

🏷️ **Hashtags**
#MythVsFact #... #...

🖼️ **Thumbnail Idea**
[❌ vs ✅ Side by Side / Shocked Face + Text «ការយល់ច្រឡំ!»]
━━━━━━━━━━━━━━━━━━━━━
"""

# ─────────────────────────────────────────────────────────────────
# CONTENT TYPE: 4 — Before & After / Transformation
# ─────────────────────────────────────────────────────────────────
def get_before_after_prompt(transformation: str, niche: str, duration: str = "60 វិនាទី") -> str:
    return f"""
សូមបង្កើត Script វីដេអូ "Before & After / Transformation" ដ៏ Visual និង Viral!

📂 វិស័យ: {niche}
🔄 Transformation: "{transformation}"
⏱️ រយៈពេល: {duration}

ហេតុអ្វីបាន Viral: Save Video ច្រើន (Reference) + Share ទៅបង្ហាញ + Dopamine Hit

━━━━━━━━━━━━━━━━━━━━━
🔄 **Before & After: {transformation}**
━━━━━━━━━━━━━━━━━━━━━

🎯 **HOOK — Tease The Result**
🗣️ "[ចាប់ Attention ដោយ Tease លទ្ធផល: «មើលការផ្លាស់ប្ដូរ...» ឬ «XYZ ថ្ងៃ → នេះ!»]"
🎥 **Visual**: [Flash Result / End Result Preview]

😰 **BEFORE (ស្ថានភាពចាស់ — Pain Point)**
🗣️ "[ពណ៌នាស្ថានភាពមុន — ជាក់ស្ដែង មានអារម្មណ៍]"
🎥 **Visual**: [Before Shot / Struggle Moment]

⚡ **THE TURNING POINT**
🗣️ "[ក្រឡេកមើលចំណុចផ្លាស់ប្ដូរ — ហេតុអ្វី? / វិធីណា?]"

✨ **AFTER (លទ្ធផល — WOW Moment)**
🗣️ "[ពណ៌នាស្ថានភាពក្រោយ — លម្អិតជាក់ស្ដែង]"
🎥 **Visual**: [After Shot / Before-After Split / Results Stats]

💡 **KEY LESSON / SECRET**
🗣️ "[គន្លឹះ ១ ដែលជួយបាន Transformation នេះ]"

📣 **CTA — Inspire Action**
🗣️ "[CTA ជំរុញ: «អ្នកក៏ធ្វើបាន...» ឬ «Save វីដេអូនេះ...»]"

━━━━━━━━━━━━━━━━━━━━━
📝 **Caption**
[Transformation Story ខ្លី + ជំរុញ Save]

🏷️ **Hashtags**
#BeforeAfter #Transformation #Glow Up #...

🖼️ **Thumbnail Idea**
[Before / After Split Screen + Number (ឧ: «30 Days»)]
━━━━━━━━━━━━━━━━━━━━━
"""

# ─────────────────────────────────────────────────────────────────
# CONTENT TYPE: 5 — Hot Take / Opinion
# ─────────────────────────────────────────────────────────────────
def get_hot_take_prompt(opinion: str, niche: str, duration: str = "60 វិនាទី") -> str:
    return f"""
សូមបង្កើត Script វីដេអូ "Hot Take / Controversial Opinion" ដ៏ Debate-Worthy!

📂 វិស័យ: {niche}
🌶️ Opinion / Hot Take: "{opinion}"
⏱️ រយៈពេល: {duration}

ហេតុអ្វីបាន Viral: Disagree → Comment ច្រើន → Debate → Algorithm Boost ដោយឥតគិតថ្លៃ

━━━━━━━━━━━━━━━━━━━━━
🌶️ **Hot Take: {opinion}**
━━━━━━━━━━━━━━━━━━━━━

🎯 **HOOK — Drop The Bomb**
🗣️ "[ពាក្យ Controversial ដោយមិន Filter: «មតិខ្ញុំ...» ឬ «គ្រប់គ្នានឹង Disagree...» ឬ «Nobody Wants To Hear This But...»]"
🎥 **Visual**: [Confident Expression / Point To Camera]

💭 **THE TAKE (មតិ + ហេតុផល ១)**
🗣️ "[Hot Take ច្បាស់ + ហេតុផលទី ១ ជាក់ស្ដែង]"

💭 **BACKUP POINT (ហេតុផល ២)**
🗣️ "[ហេតុផលទី ២ ដែលកាន់តែ Shocking / ភ្ញាក់ផ្អើល]"

🤝 **FAIR COUNTER (ទទួលស្គាល់ Side ម្ខាង)**
🗣️ "[ទទួលស្គាល់ Point ម្ខាង ប៉ុន្ដែ... «ខ្ញុំយល់ថា... ប៉ុន្ដែ...»]"

📣 **CTA — Trigger Debate**
🗣️ "[«Comment ប្រាប់ខ្ញុំ Agree ឬ Disagree?» ឬ «Share ទៅបង្ហាញមើល...»]"

━━━━━━━━━━━━━━━━━━━━━
📝 **Caption (Debate Starter)**
[Caption Controversial ដែលជំរុញ Comment]

🏷️ **Hashtags**
#HotTake #Opinion #Unpopular #...

🖼️ **Thumbnail Idea**
[Confident / Serious Face + Bold Text «មតិខ្ញុំ...» + 🔥]
━━━━━━━━━━━━━━━━━━━━━
"""

# ─────────────────────────────────────────────────────────────────
# CONTENT TYPE: 6 — Top List / Ranking
# ─────────────────────────────────────────────────────────────────
def get_top_list_prompt(topic: str, niche: str, duration: str = "60 វិនាទី") -> str:
    return f"""
សូមបង្កើត Script វីដេអូ "Top List / Ranking" ដ៏ Save-Worthy និង Share ច្រើន!

📂 វិស័យ: {niche}
📋 ប្រធានបទ List: "{topic}"
⏱️ រយៈពេល: {duration}

ហេតុអ្វីបាន Viral: Save ច្រើន (Reference) + Comment "Missing #X" + Share

━━━━━━━━━━━━━━━━━━━━━
📋 **Top List: {topic}**
━━━━━━━━━━━━━━━━━━━━━

🎯 **HOOK — Tease The List**
🗣️ "[ចាប់ Attention: «Top X [Topic] ដែរ...» ឬ «X Mistakes ដែរអ្នក...» ឬ «X Things You Didn't Know...»]"
🎥 **Visual**: [Counter / Number on Screen]

📝 **THE LIST (Item by Item — ចាប់ពី End → ១)**
*(ចាប់ពីចំណាត់ថ្នាក់ក្រោយ → ទៅ #1 ដើម្បី Watch Time ខ្ពស់)*

🔢 **[ចំណាត់ No. X]**: "[ឈ្មោះ Item] — [ហេតុអ្វី? ១ ឃ្លាខ្លី]"
🔢 **[ចំណាត់ No. ...]**: "..."
🔢 **🏆 [ចំណាត់ No. 1]**: "[Item ល្អបំផុត — ពន្យល់ច្បាស់]"

💡 **BONUS TIP**
🗣️ "[Bonus Item / Secret ដែរមិនបានរាប់ក្នុង List]"

📣 **CTA — Start Debate**
🗣️ "[«Comment ប្រាប់ #1 របស់អ្នក...» ឬ «Save វីដេអូនេះ ព្រោះ...»]"

━━━━━━━━━━━━━━━━━━━━━
📝 **Caption**
[List Caption + «Save ដើម្បីចំណាំ!»]

🏷️ **Hashtags**
#Top5 #BestOf #Ranking #...

🖼️ **Thumbnail Idea**
[Number Bold «TOP 5» + Items Grid / Trophy 🏆]
━━━━━━━━━━━━━━━━━━━━━
"""

# ─────────────────────────────────────────────────────────────────
# CONTENT TYPE: Daily Ideas (Auto Generate)
# ─────────────────────────────────────────────────────────────────
def get_daily_ideas_prompt(category: str = "General / Self-improvement / Business / Tech") -> str:
    return f"""
សូមផ្ដល់ជូននូវគំនិតមាតិកាវីដេអូ 3WHs ចំនួន ៣ ប្រធានបទថ្មីៗ និងទាក់ទាញ (Trending & High Engagement) សម្រាប់ថ្ងៃនេះ ក្នុងវិស័យ៖ {category}

━━━━━━━━━━━━━━━━━━━━━
💡 **គំនិតមាតិកា 3WHs សម្រាប់ថ្ងៃនេះ**
━━━━━━━━━━━━━━━━━━━━━

🔥 **ប្រធានបទទី ១៖ [ចំណងជើងទាក់ទាញ]**
• 🎯 **Hook**: [ពាក្យ Hook ចាប់អារម្មណ៍]
• 📌 **What**: [តើវាជាអ្វី?]
• 🛠️ **How**: [គន្លឹះអនុវត្តសង្ខេប]
• 📋 **Format ណែនាំ**: [3WHs / POV / Myth / List...]

🔥 **ប្រធានបទទី ២៖ [ចំណងជើងទាក់ទាញ]**
• 🎯 **Hook**: [ពាក្យ Hook ចាប់អារម្មណ៍]
• 📌 **What**: [តើវាជាអ្វី?]
• 🛠️ **How**: [គន្លឹះអនុវត្តសង្ខេប]
• 📋 **Format ណែនាំ**: [3WHs / POV / Myth / List...]

🔥 **ប្រធានបទទី ៣៖ [ចំណងជើងទាក់ទាញ]**
• 🎯 **Hook**: [ពាក្យ Hook ចាប់អារម្មណ៍]
• 📌 **What**: [តើវាជាអ្វី?]
• 🛠️ **How**: [គន្លឹះអនុវត្តសង្ខេប]
• 📋 **Format ណែនាំ**: [3WHs / POV / Myth / List...]
━━━━━━━━━━━━━━━━━━━━━
💡 *ជ្រើស Project → Content Type → ចុចប៊ូតុង ដើម្បីបង្កើត Script ពេញលេញ!*
"""

# ─────────────────────────────────────────────────────────────────
# CHAT (Free Text)
# ─────────────────────────────────────────────────────────────────
def get_chat_prompt(user_message: str) -> str:
    return f"""
អ្នកប្រើប្រាស់បានផ្ញើសារ៖ "{user_message}"

សូមឆ្លើយតបជាភាសាខ្មែរ ក្នុងនាមជា 3WHs Content Coach / Video Producer ជំនាញ
ជួយផ្ដល់យោបល់ កែលម្អ ឬបង្កើតមាតិការ​ឱ្យ​គាត់​យ៉ាងល្អ​ (មិនលើកឡើងប្រទេសថៃ ឬម្ហូបថៃ​ជាដាច់ខាត)។
"""
