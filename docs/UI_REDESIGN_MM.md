# PyonPyin UI ဒီဇိုင်း

ရည်ညွှန်းဒီဇိုင်းများ: `PyonPyin Story World Dashboard.png` နှင့် `PyonPyin Story Management Dashboard.png`။

- Public: အဖြူ/အပြာ၊ ဘေးမီနူး၊ ပင်မ banner၊ ပုံပြင်ကတ်များ၊ ရွေးချယ်ထားသော ပုံပြင်နှင့် အသံ preview။
- Admin: အနက်ရောင်ဘေးမီနူး၊ အဖြူရောင် workspace၊ အမှန်တကယ်အရေအတွက်၊ အဆင့်စစ်ထုတ်မှု၊ recent stories table နှင့် preview။ အသေးစိတ်လုပ်ငန်းစဉ်များကို ခေါက်ထားသောမီနူးတွင် ဆက်သုံးနိုင်သည်။
- Editor: Basic Information / Story Content / Image (Optional) / Audio / Review & Publish။ အဆင့်ပြောင်းလဲရာတွင် မသိမ်းရသေးသောစာသားကို မပျောက်စေပါ။
- ပုံထည့်၊ ပြောင်း၊ ဖယ်ခြင်းနှင့် drag/drop သည် လက်ရှိ image API ကို သုံးသည်။ ပြောင်းလဲမှုသည် ရွေးလိုက်သည်နှင့် သိမ်းသည်။
- Backend၊ database၊ publication gate နှင့် API contract မပြောင်းပါ။
- Favorites၊ ဖတ်ရှုမှတ်တမ်းနှင့် ညဖတ်ပုံစံသည် browser ထဲသာ သိမ်းသည်။ Account sync မချိတ်ထားပါ။
- ထုတ်ဝေထားသောအကြောင်းအရာကိုသာ public တွင်ပြသည်။ နမူနာပုံထဲက views၊ ကြာချိန်၊ နာမည်၊ ရက်စွဲနှင့် အရေအတွက်များကို မဖန်တီးပါ။ ဖတ်ချိန်သည် စာသားအရှည်မှ ခန့်မှန်းထားသည်။
- Mobile တွင် sidebar ကို မီနူးခလုတ်ဖြင့်ဖွင့်နိုင်ပြီး ကတ်များနှင့် editor အဆင့်များသည် မျက်နှာပြင်အရွယ်အစားအလိုက် ပြောင်းသည်။

## Banner asset နှင့် prompt

Built-in ImageGen ဖြင့် ဖန်တီးထားသည်။ မူရင်းပုံ: `C:/Users/saksi/.codex/generated_images/01a1729c-6871-77f0-ae52-9f6bcbbeb474/exec-f691405a-92f1-4623-b839-c8addc4348d8.png`။

Project asset: `frontend/src/assets/story-world.webp`။ ဖိုင်အရွယ်အစားချုံ့ရန် WebP သို့ ပြောင်းထားသည်။ Vite က build ထဲသို့ ထည့်ပေးသည်။ သုံးစွဲသူ upload ပုံရှိလျှင် ဦးစားပေးပြပြီး မရှိမှသာ ဤပုံကို သုံးသည်။

Prompt:

> Create a polished wide landscape background illustration asset for a Burmese story-reading website. No text, no letters, no UI, no logo, no border. Delightful painterly high quality 3D animated family film storybook illustration of an enchanted floating island with a majestic gold-roof and blue-roof castle in the RIGHT HALF, cascading waterfalls, lush green trees, distant blue mountains, soft fluffy clouds and flying birds. Bright warm morning sunlight, sky blue and turquoise palette, a sense of wonder. LEFT HALF is quiet deep-blue atmospheric sky and mist with very little detail so white HTML headings can be placed on top. Cinematic wide panoramic composition ideally 16:7. Reference mood: whimsical magical adventure, warm and welcoming, highly detailed but clean and uncluttered. This image will be saved as a reusable website hero and fallback artwork asset.

## စစ်ဆေးမှု

Frontend tests တွင် favorites၊ category filtering၊ audio preview၊ reading history၊ dashboard stages နှင့် editor အဆင့်ပြောင်းရာတွင် မသိမ်းရသေးသောစာသား မပျောက်ကြောင်း စစ်ထားသည်။ Browser connector မရရှိသဖြင့် screenshot ဖြင့် visual QA မလုပ်နိုင်ခဲ့ပါ။

## စာဖတ်သူ Settings

Settings ကို အပြင်အဆင် / စာဖတ်ခြင်း / အသံ / ကိုယ်ပိုင်မှတ်တမ်း ဟူ၍ အပိုင်းလေးခု ခွဲထားသည်။ Live preview ပါဝင်ပြီး စက်အရွယ်အစားအလိုက် ပြောင်းသည်။

လုပ်ဆောင်ချက်များ:
1. နေ့အလင်း၊ ညအမှောင်၊ စက္ကူရောင်နှင့် စက်၏ theme ကို လိုက်သုံးခြင်း။
2. အပြာ၊ ခရမ်း၊ အစိမ်း အဓိကအရောင် ရွေးခြင်း။
3. စာလုံးအရွယ် 14–26px ပြောင်းခြင်း။
4. စာကြောင်းကြား အကွာအဝေး ပြောင်းခြင်း။
5. စာလုံးပုံစံ ရွေးခြင်း။ Font သည် စက်တွင် ရှိသည့် font များကို အခြေခံသည်။
6. စာဖတ်မျက်နှာပြင်အကျယ် ရွေးခြင်း။
7. ပုံပြင်ဖတ်ချိန် အာရုံစိုက်ပုံစံ။
8. အသံဖတ်နှုန်း ပြောင်းခြင်း။
9. အသံအတိုးအကျယ် သတ်မှတ်ခြင်း။
10. 5 / 15 / 30 / 60 မိနစ် sleep timer။ Browser ဖွင့်ထားချိန်တွင် အလုပ်လုပ်သည်။
11. UI animation လျှော့ခြင်း။
12. ဖတ်ရှုမှုမှတ်တမ်း သိမ်းခြင်း ဖွင့်/ပိတ်။
13. Settings၊ Favorites၊ History ကို JSON backup သိမ်း/ပြန်ထည့်ခြင်း။ Import သည် ဤ browser ရှိ စာရင်းများကို အစားထိုးသည်။
14. Favorites / History ကို အတည်ပြုပြီး ရှင်းခြင်းနှင့် setting ကို မူလအတိုင်း ပြန်ထားခြင်း။ Reset သည် Favorites / History ကို မဖျက်ပါ။

အချက်အလက်များကို browser local storage ထဲတွင်သာ သိမ်းသည်။ Account sync မပါသေးပါ။ Storage ပိတ်ထားလျှင် လက်ရှိစာမျက်နှာတွင် ပြောင်းနိုင်သော်လည်း ပြန်ဖွင့်ချိန် ဆက်သိမ်းထားမရကြောင်း UI တွင် ပြသည်။ အသံတစ်ခုဖွင့်လျှင် အခြားဖွင့်ထားသော reader player ကို ရပ်ပေးသည်။
