# MVP အသုံးပြုရန်နှင့် account/key ထည့်ရန်

ယခု MVP သည် **တစ်ဦးတည်းစီမံသည့်၊ server တစ်လုံးပေါ်တွင် database/audio သိမ်းသောပုံစံ** ဖြစ်သည်။ Public reader နှင့် admin API များ သီးခြားရှိသဖြင့် နောက်တစ်ဆင့်တွင် website UI နှင့် dashboard UI ကို ပြန်ရေး၍ API တစ်ခုတည်းကို သုံးနိုင်သည်။ ယခု UI မှာ လုပ်ငန်းစဉ်စမ်းရန် control များသာ ဖြည့်ထားသည်။

## သင်ဖွင့်ရန်လိုသော account များ

| အသုံး | လိုအပ်သော account / key | လက်ရှိ code တွင် ထည့်ရမည့်နေရာ |
| --- | --- | --- |
| ပုံပြင်မူကြမ်း AI | Google AI Studio မှ Gemini API key | `.env` ရှိ `GEMINI_API_KEY` |
| မြန်မာအသံ AI (default) | Gemini API key ကိုပဲ ပြန်သုံးသည်။ Microsoft account မလိုပါ။ | `TTS_PROVIDER=gemini`, `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE` |
| Azure အသံ (optional) | Azure သုံးချင်မှသာ Speech resource Key နှင့် Region လိုသည်။ | `TTS_PROVIDER=azure`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` |
| Database | Account / API key မလိုပါ။ SQLite ပါပြီးသားဖြစ်သည်။ | `PYONPYIN_DATABASE_PATH` |
| Audio storage | Local persistent folder ကိုသုံးသည်။ Account မလိုပါ။ | `AUDIO_OUTPUT_DIR` |
| Google Sheets | Optional legacy integration သာဖြစ်သည်။ SQLite MVP အတွက် မလိုပါ။ | `PYONPYIN_STORAGE=sheets` ဟု သီးခြားရွေးမှသာ |
| GitHub token | Local worker အတွက် မလိုပါ။ GitHub runner နှင့် local SQLite database ကို မမျှဝေပါ။ | SQLite mode တွင် GitHub dispatch ပိတ်ထားသည်။ |
| Hosting/domain | ကိုယ့်စက်တွင် စမ်းရန်မလိုပါ။ Public တင်သည့်အဆင့်တွင် HTTPS + persistent disk ပါသော host လိုသည်။ | `PUBLIC_BASE_URL`, `PYONPYIN_HTTPS` |

Key အစစ်များကို chat၊ Git၊ frontend `VITE_*` settings ထဲ မထည့်ပါနှင့်။ ကိုယ့်စက်က `.env` တွင်သာ ထည့်ပါ။ `.env` နှင့် runtime database/audio များကို Git/Docker build context မှ ဖယ်ထားသည်။

### ၁။ Gemini key ထုတ်ရန်

1. [Google AI Studio API keys](https://aistudio.google.com/apikey) သို့ ဝင်ပါ။
2. ကိုယ့် Google project အတွက် API key ဖန်တီးပါ။ [Official key လမ်းညွှန်](https://ai.google.dev/gemini-api/docs/api-key) ကိုကြည့်နိုင်သည်။
3. `.env` ထဲ `GEMINI_API_KEY=` နောက်တွင် ထည့်ပါ။ Key ကို ကိုယ့်စက်မှာသာထားပါ။
4. Provider ရှိ quota/billing setting ကိုစစ်ပြီး စမ်းရန်အသင့်ဖြစ်မှ `PYONPYIN_GEMINI_AUTOMATION_ENABLED=true` ပြောင်းပါ။
5. `GEMINI_MODEL` ကို ကိုယ့် account တွင် ရနိုင်သော model ဖြင့် ရွေးနိုင်သည်။ Code default က `gemini-3.5-flash-lite` ဖြစ်သည်။ ဤ project ၏ key ဖြင့် မြန်မာ Unicode စာသားအဖြေကို live စမ်းသပ်ပြီးဖြစ်သည်။ Model access နှင့် provider availability သည် account အလိုက် ကွာနိုင်သည်။

### ၂။ မြန်မာအသံကို Gemini ဖြင့်ထုတ်ရန် — အကြံပြု default

ပုံပြင်ရေးရန် သုံးသော Google AI Studio key ကိုပဲ အသံအတွက် ပြန်သုံးနိုင်သည်။ Account အသစ်၊ Microsoft subscription နှင့် Azure region မလိုပါ။ [Google official TTS language support](https://ai.google.dev/gemini-api/docs/speech-generation) တွင် Burmese ပါရှိသော **Gemini 3.8 Flash TTS** ကို adapter ကသုံးသည်။ Flash-Lite ကို ဤ Burmese adapter အတွက် မသုံးပါ။

```dotenv
GEMINI_API_KEY=ကိုယ့်-key-ကို-ဤနေရာတွင်ထည့်ပါ
TTS_PROVIDER=gemini
GEMINI_TTS_MODEL=gemini-3.8-flash-tts
GEMINI_TTS_VOICE=Kore
PYONPYIN_TTS_ENABLED=true
```

Key/account ၏ model access နှင့် quota/billing ကိုစစ်ပြီး စမ်းရန်အသင့်ဖြစ်မှ `PYONPYIN_TTS_ENABLED=true` ပြောင်းပါ။ ပုံပြင်ရေးသည့် `GEMINI_MODEL` နှင့် အသံထုတ်သည့် `GEMINI_TTS_MODEL` သည် သီးခြားဖြစ်သည်။ Google API ကို direct REST ဖြင့် ခေါ်သဖြင့် SDK package ထပ်သွင်းရန် မလိုပါ။ Voice/style ပြောင်းလိုလျှင် prebuilt voice ကိုရွေးနိုင်ပြီး အသံကို လူကနားထောင်စစ်ပြီးမှ READY သတ်မှတ်ရမည်။

Local `.env` ၏ provider ကို Gemini သို့ ပြောင်းထားသည်။ Key ထည့်ပြီးနောက် စာသားနှင့် 3.36 စက္ကန့် မြန်မာအသံနမူနာကို live စမ်းသပ်ပြီးဖြစ်သည်။ အသံ preview သည် `data/runtime/checks/gemini-greeting.wav` တွင်ရှိသည်။ အသံထွက်အရည်အသွေးကို လူက နားထောင်စစ်ရန်နှင့် actual provider usage/cost ကို account မှကြည့်ရန် ကျန်သည်။ Web/worker နှစ်ခုလုံး restart လုပ်ပြီး Settings မှ configuration ကိုစစ်ပါ။

### Azure Speech ဖွင့်ရန် — optional alternative

1. [Azure Portal](https://portal.azure.com/) တွင် account ဝင်ပြီး Speech resource ဖန်တီးပါ။
2. Resource ၏ **Keys and Endpoint** မှ Key တစ်ခုနှင့် Region ကို မှတ်ပါ။ Region က resource ၏ location identifier ဖြစ်ပြီး endpoint URL မဟုတ်ပါ။ ဥပမာ `eastus` ဖြစ်သော်လည်း ကိုယ်တည်ဆောက်ထားသော resource ၏ region ကိုသာ ထည့်ပါ။
3. `.env` တွင် `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` ထည့်ပါ။ `TTS_PROVIDER=azure` နှင့် `AZURE_SPEECH_VOICE=my-MM-NilarNeural` ကိုသုံးနိုင်သည်။
4. [Microsoft language/voice support](https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support?tabs=tts.) တွင် Burmese voice စာရင်းကို စစ်ပါ။ Code က synthesis မလုပ်မီ configured region ၏ voice list API ဖြင့် voice အမှန်တကယ်ရနိုင်မှုကိုလည်း စစ်သည်။
5. Quota/billing စစ်ပြီးမှ `PYONPYIN_TTS_ENABLED=true` ပြောင်းပါ။ [Official REST API](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech) အတိုင်း server မှခေါ်သည်။
6. အသံထွက်မှန်မှုကို မြန်မာစာနားလည်သူက နားထောင်စစ်ပြီးမှ READY အတည်ပြုပါ။ API အောင်မြင်ရုံဖြင့် အလိုအလျောက်မထုတ်ဝေပါ။

ဤစာတမ်းက free usage သို့မဟုတ် လက်ရှိစျေးနှုန်းကို အာမမခံပါ။ Provider က payment method တောင်းလျှင် plan/usage ကို ကြည့်ပြီးမှ ဆက်လုပ်ပါ။ Account မဖွင့်ရသေးလည်း manual text + upload audio workflow ကို စမ်းနိုင်သည်။

## Windows မှာ စတင်ရန်

Repository root တွင် PowerShell ဖွင့်ပါ။ ရှိပြီးသား `.venv` ရှိလျှင် အသစ်တည်ဆောက်ရန် မလိုပါ။

```powershell
# .venv မရှိသေးလျှင်သာ
python -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pyonpyin.manage init
.\.venv\Scripts\python.exe -m pyonpyin.manage doctor
```

`init` သည် `.env.example` မှ `.env` တည်ဆောက်ပြီး unique admin password နှင့် session secret ကို ထည့်ပေးသည်။ ရှိပြီးသား `.env` ကို မရေးထပ်ပါ။ Password ကို terminal မှမထုတ်ပါ။ `.env` ကို ကိုယ့် editor ထဲဖွင့်ပြီး `PYONPYIN_ADMIN_PASSWORD` တန်ဖိုးဖြင့် login ဝင်ပါ။

`.env` ပြောင်းလဲပြီးတိုင်း web server နှင့် worker နှစ်ခုလုံး restart လုပ်ပါ။ စက်၏ environment variable ထဲတွင် တန်ဖိုးရှိပြီးသားဆိုလျှင် `.env` ထက် ဦးစားပေးသည်။

Frontend ကို build လုပ်ပါ။ Key မရှိသေးလည်း live SQLite workspace ကို ဖွင့်နိုင်သည်။

```powershell
Set-Location frontend
npm.cmd ci
$env:VITE_DEMO_MODE = "false"
npm.cmd run build
Set-Location ..
```

Terminal ၁ — web server:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pyonpyin.web_app
```

Terminal ၂ — job worker:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pyonpyin.worker
```

- Public React site — `http://127.0.0.1:8000/app/`
- Admin React dashboard — `http://127.0.0.1:8000/admin/app/`
- Liveness — `http://127.0.0.1:8000/health`
- Database readiness — `http://127.0.0.1:8000/ready`

Flask development server ကို ကိုယ့်စက်တွင် စမ်းရန်သုံးပါ။ Public production အတွက် အောက်ပါ Docker/Gunicorn ပုံစံနှင့် HTTPS reverse proxy သုံးပါ။

## Key မရှိသေးဘဲ အစမှအဆုံးစမ်းရန်

1. Dashboard **Story Editor** tab မှ **MVP ပုံပြင်ဖန်တီးရန်** ကိုသုံးပါ။ Title၊ audience နှင့် ကိုယ်ပိုင်ရေးထားသောစာသား ထည့်ပါ။
2. ပုံပြင် editor တွင် quiz တစ်ခုနှင့် reflection ထည့်ပြီး မူကြမ်းသိမ်းပါ။ မူလ episode တစ်ခု ပါပြီးသားဖြစ်သည်။
3. **Original review** တွင် reviewer၊ ကိုယ်ပိုင်ရေးသားမှုအထောက်အထား၊ publication permission နှင့် လိုအပ်လျှင် narration permission သတ်မှတ်ပါ။ မူရင်းရင်းမြစ်မသုံးထားလျှင် source translation rights ကို အတုဖြည့်ရန် မလိုပါ။
4. **Content approve** ဖြင့် သိမ်းထားသောစာသားကို အတည်ပြုပါ။ စာသားပြင်ပြီး ပြန်သိမ်းလျှင် review/approval ပြန်လိုသည်။
5. အသံမပါသော text-first ပုံပြင်အတွက် **ထုတ်ဝေရန် အသံဖိုင် မဖြစ်မနေလိုသည်** ကို မရွေးပါနှင့်။ အသစ်ဖန်တီးသော workspace တွင် default optional ဖြစ်သည်။
6. အသံလိုပါက MP3 သို့မဟုတ် PCM WAV ဖိုင် upload လုပ်ပါ။ 25 MiB အထိဖြစ်ပြီး `PENDING_REVIEW` အဖြစ်သာ သိမ်းသည်။ နားထောင်ပြီး reviewer အမည်ဖြင့် အသံအတည်ပြုပါ။ ထိုအချိန်မှ `READY` ဖြစ်သည်။
7. Local publication ကို စမ်းရန် `.env` တွင် `PYONPYIN_PUBLISHING_ENABLED=true` ပြောင်းပြီး web/worker restart လုပ်ပါ။ `PUBLIC_BASE_URL=http://127.0.0.1:8000` သည် local အတွက်ဖြစ်သည်။
8. Editor တွင် reviewer အမည်ဖြည့်ပြီး **ထုတ်ဝေမည်** ကိုရွေးပါ။ Gate မပြည့်လျှင် လိုအပ်သောအကြောင်းရင်း ပြသည်။ Public site တွင် အမှန်တကယ်ပေါ်လာကြောင်း စစ်ပါ။
9. **Public မှ ပြန်ဖယ်ရန်** ဖြင့် unpublish စမ်းပါ။ Public story API နှင့် သိမ်းထားသော audio link တို့ပါ ပြန်ပိတ်သွားရမည်။

## Key ထည့်ပြီး AI စမ်းရန်

လက်ရှိ dashboard ပင်မတွင် **ပုံပြင်အသစ်ရေးရန်** နှင့် **အသံနားထောင်ရန်** ကို တိုက်ရိုက်ရွေးနိုင်သည်။ ပုံပြင်စာမျက်နှာအပေါ်ဆုံးရှိ အသံကတ်က ဖိုင်ရှိလျှင် player ပြပြီး မရှိလျှင် လိုအပ်သောအတည်ပြုချက်များကို ပြသည်။ Audio Studio / အသံနားထောင်ရန် စာမျက်နှာတွင်လည်း အသံဖိုင်များကို တိုက်ရိုက်နားထောင်နိုင်သည်။ Audio URL နှင့် status ကို ကိုယ်တိုင်ဖြည့်ရန် မလိုပါ။

1. Title/audience/theme ထည့်၍ စာသားလွတ်ထားသော workspace ဖန်တီးပါ။
2. Editor အောက်ရှိ **AI မူကြမ်း job စတင်ရန်** ကိုရွေးပါ။ Worker ဖွင့်ထားရမည်။ ဤလမ်းကြောင်းတွင် title/source text ကို Gemini သို့မပို့ဘဲ allowlist theme နှင့် audience ကိုသာ သုံးသည်။
3. Local job history ကို refresh လုပ်ပါ။ Job တစ်ခုသည် ပုံပြင်တစ်ပုဒ်အတွက်သာဖြစ်သည်။ Result ရှိပြီးသားကို generation retry ဖြင့် မရေးထပ်ပါ။
4. မူကြမ်းရလျှင် စာသား/quiz/reflection၊ original provenance နှင့် content review ပြီးအောင်လုပ်ပါ။
5. Narration permission နှင့် content approval ရပြီး ရွေးထားသော TTS provider ၏ settings ဖွင့်ထားမှ **အသံထုတ်ရန် job** လုပ်နိုင်သည်။ Automatic narration က စာလုံး 20,000 အထိ၊ combined audio 25 MiB အထိဖြစ်သည်။ ရှည်သောပုံပြင်အတွက် ကိုယ်တိုင်ပြင်ဆင်ထားသော MP3/WAV ဖိုင်ကို upload လုပ်နိုင်သည်။
6. TTS output ကို နားထောင်စစ်ပြီးမှ အတည်ပြု၊ နောက်မှ publish လုပ်ပါ။

Gemini နှင့် Azure adapter နှစ်ခုလုံးက အပိုင်းတိုများဖြင့် PCM WAV frame များဆက်ပေးသည်။ Failed/timeout ဖြစ်သော synthesis ကို အလိုအလျောက် မထပ်ခေါ်ပါ။ Provider က request လက်ခံထားနိုင်သောကြောင့် usage/job ရလဒ်ကိုစစ်ပြီးမှ retry ရွေးပါ။ Gemini adapter က transcript နှင့် style metadata ကို သီးခြားပို့ပြီး stateless request (`store=false`) ကိုသုံးသည်။

## Job မရွေ့လျှင်

- `QUEUED` — worker terminal ဖွင့်ထားသလား စစ်ပါ။
- `RUNNING` — အလုပ်လုပ်နေသည်။ ပုံပြင်တစ်ပုဒ်တည်းကို ထပ်တန်းစီခြင်းနှင့် ပြင်ဆင်ခြင်းကို ပိတ်ထားသည်။
- `FAILED` — configuration/permissions နှင့် Processing History ကိုစစ်ပါ။ Logs တွင် secret မပါစေရန် exception type ကိုသာ သိမ်းသည်။ ပြင်ပြီးမှ Retry ရွေးပါ။
- `INTERRUPTED` — worker ကို restart လုပ်ထားပြီး lease 15 မိနစ်ကျော်သွားသောအလုပ်ဖြစ်သည်။ အလိုအလျောက် ထပ်မခေါ်ပါ။ Provider ရလဒ်စစ်ပြီး Retry ရွေးပါ။
- Local worker နှင့် web ကို **တူညီသော database path နှင့် audio path** ဖြင့် ဖွင့်ထားရမည်။

SQLite mode တွင် CI/GitHub Actions မှ processing ကို production DB အဖြစ် မသုံးပါနှင့်။ Server နှင့် database မျှဝေသော local worker ကိုသာ သုံးပါ။ Google Sheets ကိုရွေးလျှင် မူလ discovery/generation entrypoint နှင့် optional GitHub dispatch ကို ဆက်သုံးနိုင်သော်လည်း SQLite durable queue အာမခံချက် မရပါ။

## Backup နှင့် public deployment

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pyonpyin.manage backup data/backups/mvp-backup-01.db
```

Database နှင့် `data/runtime/audio` folder **နှစ်ခုလုံး** ကို backup လုပ်ပါ။ Restore လုပ်မည်ဆိုလျှင် web/worker ကိုအရင်ပိတ်ပြီး backup database နှင့် audio ကိုအတူပြန်ထားပါ။ Filename အသစ်ကိုသာ backup target အဖြစ်လက်ခံသည်။

Docker ရှိသောစက်တွင်:

```powershell
docker compose up --build -d
docker compose logs --tail 100 web worker
```

`compose.yaml` သည် web/Gunicorn နှင့် worker ကို shared named volume တစ်ခုဖြင့် ချိတ်သည်။ Docker image အတွင်း secret မထည့်ဘဲ `.env` ကို runtime တွင်ပေးသည်။ Port ကို localhost တွင်သာ bind ထားသည်။ Public တင်ရန် HTTPS reverse proxy/domain ကို သီးခြားတပ်ပြီး `PUBLIC_BASE_URL=https://ကိုယ့်-domain`, `PYONPYIN_HTTPS=true` သတ်မှတ်ပါ။ Shared admin password ပါသော single-editor MVP ဖြစ်သဖြင့် admin access ကို proxy/VPN ဖြင့်ကန့်သတ်ထားပါ။ Login တွင် SQLite-backed attempt limit ပါသည်။

`docker compose down -v` သည် database/audio volume ကို ဖျက်မည်ဖြစ်သောကြောင့် backup မရှိဘဲ မလုပ်ပါနှင့်။ ယခုစက်တွင် Docker မတွေ့သဖြင့် container build/run ကို မစမ်းထားပါ။

## စစ်ဆေးပြီးမှုနှင့် ကျန်သော setup

Real temporary SQLite database ဖြင့် create/edit/review/publish/unpublish၊ audio privacy/range playback၊ worker claims၊ retry၊ backup/rollback နှင့် mocked Azure/Gemini ကို စမ်းထားသည်။ Frontend crash/error handling နှင့် workflow controls အတွက်လည်း tests ရှိသည်။

**လက်ရှိအတည်ပြုပြီးမှု (၂၀၂၆-၁၀-၂၅):** User ထည့်ထားသော key ဖြင့် `gemini-3.5-flash-lite` မှ မြန်မာပုံပြင်၊ ordered episodes၊ quiz ၃ ခုနှင့် reflection ကို live စမ်းပြီးဖြစ်သည်။ `gemini-3.8-flash-tts` မှ 3.36 စက္ကန့် WAV အသံနမူနာလည်း ရရှိသည်။ Local `.env` တွင် manual text/audio jobs ဖွင့်ထားပြီး publishing switch ကို ပိတ်ထားဆဲဖြစ်သည်။

**ကျန်သောအရာ:** Provider account ၏ actual usage/billing ကိုကြည့်ရန်၊ အသံထွက်ကို လူကနားထောင်စစ်ရန်နှင့် public တင်ချိန် hosting/domain ဖြစ်သည်။ Azure ကိုရွေးမှသာ Azure key/region ထပ်လိုသည်။ Public deployment နှင့် Docker build ကို မစမ်းရသေးပါ။
# ပုံပြင်ပုံနှင့် ပင်မစာမျက်နှာပုံ

- Story Editor ထဲက **ပုံပြင် မျက်နှာဖုံးပုံ** တွင် JPG / PNG / WebP ပုံကို ရွေးပါ။ ရွေးလိုက်သည်နှင့် သိမ်းပေးမည်။ အများဆုံး 8 MB ဖြစ်သည်။
- ပုံမထည့်လည်း ထုတ်ဝေနိုင်သည်။ ထုတ်ဝေပြီးမှ ပုံထည့်၊ အစားထိုး၊ ဖယ်နိုင်သည်။ စာသား၊ အသံနှင့် ထုတ်ဝေမှု အတည်ပြုချက် မပျက်ပါ။
- Dashboard ရှိ **ပင်မစာမျက်နှာပုံ ပြောင်းရန်** မှတစ်ဆင့် Settings သို့သွားပြီး “ပုံပြင်တစ်ပုဒ် · ကမ္ဘာတစ်ခု” နေရာရှိ ပုံကို ပြောင်းနိုင်သည်။
- ပုံဖယ်လျှင် မူလဒီဇိုင်း ပြန်ပေါ်မည်။ Public စာမျက်နှာကို ပြန်ဖွင့်မှ နောက်ဆုံးပုံကို မြင်ရမည်။
- ပုံဖိုင်များသည် `data/runtime/images` ထဲတွင်ရှိသည်။ Backup ယူလျှင် database၊ audio နှင့် images folder တို့ကို အတူသိမ်းပါ။
