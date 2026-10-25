# PyonPyin MVP စစ်ဆေးချက်

> ဤစာတမ်းသည် အကောင်အထည်မဖော်မီ စစ်ဆေးချက်မှတ်တမ်းဖြစ်သည်။ နောက်ဆက်တွဲတွင် queue crash/error state၊ original review၊ publish API၊ SQLite worker နှင့် Azure/upload audio workflow တို့ကို ရေးပြီးဖြစ်သည်။ လက်ရှိအသုံးပြုရန် [MVP setup လမ်းညွှန်](MVP_SETUP_MM.md) နှင့် [API contract](MVP_API.md) ကို ကြည့်ပါ။ Live account/key စမ်းခြင်းနှင့် hosting တို့မှာ ကျန်နေဆဲဖြစ်သည်။

စစ်ဆေးသည့်နေ့ — ၂၀၂၆ အောက်တိုဘာ ၂၅။ Repository ထဲက code၊ workflow၊ docs နှင့် offline tests အပေါ် အခြေခံထားသည်။ Live Google Sheets၊ feed၊ Gemini၊ TTS၊ GitHub Actions နှင့် deployment ကို မစမ်းထားပါ။

လက်ရှိအဆင့်သည် **backend workflow အတော်များများရှိပြီး admin interface တစ်စိတ်တစ်ပိုင်းချိတ်ထားသော prototype/private preview** ဖြစ်သည်။ Public MVP အတွက် အဓိကလိုအပ်ချက်မှာ feature ထပ်များခြင်းထက် ပုံပြင်တစ်ပုဒ်ကို အစမှအဆုံး အမှန်တကယ် ထုတ်ဝေနိုင်အောင် ချိတ်ဆက်ပြီး failure များကို ကိုင်တွယ်နိုင်ရန် ဖြစ်သည်။

## Project ဘယ်လိုအလုပ်လုပ်သလဲ

```text
approved_sources.json
        ↓
story_finder.py → Story Library → Story Production (QUEUED)
                                      ↓
                  process_stories.py → GeminiClient
                                      ↓
                         မူကြမ်း + episodes + quiz + reflection
                                      ↓
                         Admin ပြင်ဆင်ခြင်း / လူစစ်ခြင်း
                                      ↓
                  rights + content + publication approval + လိုအပ်လျှင် audio
                                      ↓
                          Publishing History (PUBLISHED)
                                      ↓
                          /api/stories → Public React site
```

- `src/story_finder.py` — approved source မှ Atom/RSS metadata ရှာသည်။ Stable ID၊ duplicate စစ်ခြင်း၊ category တစ်မျိုးလျှင် ငါးပုဒ်အကန့်အသတ်နှင့် queue ထည့်ခြင်း ရှိသည်။
- `src/process_stories.py` — queue ထဲက မူကြမ်းကို ပုံမှန်တစ်ကြိမ်လျှင် တစ်ပုဒ် ထုတ်သည်။ Automation opt-in လိုသည်။
- `src/pyonpyin/gemini.py` — Gemini ခေါ်ပြီး JSON၊ episode စဉ်နှင့် ပုံပြင်စာသားကိုက်ညီမှု၊ quiz စစ်သည်။
- `src/pyonpyin/core.py` — category၊ rights၊ publication gate၊ URL နှင့် ID စည်းမျဉ်းများ စုထားသည်။
- `src/pyonpyin/sheets.py` — Google Sheets tab ခြောက်ခုတွင် သိမ်းသည်။ ရှိပြီးသားဒေတာမဖျက်ဘဲ schema ဖြည့်ပြီး ရှည်သောစာသားကို အပိုင်းခွဲသည်။
- `src/pyonpyin/web_app.py` — Flask API၊ session login၊ CSRF၊ legacy HTML admin၊ public catalogue နှင့် React build ဖိုင်များ ပေးသည်။
- `frontend/src/App.tsx` — public reader နှင့် admin workspace တို့ပါသော React SPA ဖြစ်သည်။
- `frontend/src/demo.ts` / `DemoAudioPlayer.tsx` — fixture data နှင့် synthetic အသံ preview ဖြစ်သည်။ TTS narration မဟုတ်ပါ။
- `.github/workflows/` — offline backend tests၊ manual discovery နှင့် manual/dispatch generation ရှိသည်။ လက်ရှိ YAML များတွင် `schedule` မရှိပါ။

## ရှိပြီးသားနှင့် အသုံးဝင်သောအပိုင်းများ

- Source အသုံးပြုခွင့်၊ content review နှင့် publication approval ကို သီးခြားစစ်ထားသည်။
- Theme-only generation တွင် မူရင်းစာသား၊ စာအုပ်ခေါင်းစဉ်၊ စာရေးဆရာအချက်အလက်ကို AI သို့ မပို့ပါ။
- React rights review၊ draft editor၊ content approval နှင့် configuration ရှိမှလုပ်နိုင်သော GitHub dispatch API ရှိသည်။
- Public API က PUBLISHED history နှင့် လက်ရှိ gate များကို ပြန်စစ်ပြီးမှ ထုတ်ပေးသည်။
- Offline regression tests၊ Dockerfile နှင့် setup/deployment docs ရှိသည်။

## MVP မတိုင်မီ ဦးစားပေးလုပ်ရန်

### P0 — အသုံးပြုမှုတားနေသောအချက်များ

1. **Production queue ဖွင့်လျှင် crash ဖြစ်နိုင်သည်။** `frontend/src/App.tsx` ရှိ `ProductionQueue` တွင် `stories.some(...)` အတွင်း `storyId` ကို သုံးပြီးမှ `useState` ဖြင့် ကြေညာထားသည်။ Stories မလွတ်လျှင် `Cannot access 'storyId' before initialization` ဖြစ်နိုင်သည်။ State declaration ကို ရှေ့ရွှေ့ပြီး non-empty queue render test ထည့်ရန်လိုသည်။ လက်ရှိ tests သည် ဤ route ကို မဖမ်းမိပါ။

2. **Public API မအောင်မြင်လျှင် loading မှာပဲ ကျန်နိုင်သည်။** `usePublishedStories` သည် error ကိုသိမ်းသော်လည်း initial `stories` က `null` အတိုင်း ကျန်သည်။ `HomePage`၊ `LibraryPage`၊ `StoryPage` တို့က `stories === null` ကို error ထက်အရင်စစ်ထားသောကြောင့် error/retry UI မပေါ်နိုင်ပါ။ Error ကိုဦးစားပေးစစ်ခြင်း သို့မဟုတ် loading state သီးခြားထားခြင်းနှင့် failed-fetch test လိုသည်။

3. **အသံပါသော MVP အတွက် narration pipeline မရှိသေးပါ။** `audio.py` ရှိ `synthesize()` သည် အမြဲ `AudioUnavailable` ပေးသည်။ Processor ကလည်း TTS adapter ကို မခေါ်ပါ။ အလိုအလျောက် queue ထည့်သော record များက `audio_required=YES` ဖြစ်ပြီး မူကြမ်းအပြီးတွင် `WAITING_PROVIDER_VERIFICATION` ဖြစ်သည်။ အသံမရှိလျှင် ထုတ်ဝေမှုတားမည်။ ရွေးစရာမှာ text-first MVP အတွက် audio requirement ကို admin က ရှင်းလင်းစွာရွေးနိုင်အောင်လုပ်ခြင်း၊ သို့မဟုတ် လူဖတ်အသံဖိုင် URL ကို စစ်ပြီးချိတ်ခြင်း၊ သို့မဟုတ် တကယ်အလုပ်လုပ်သော TTS + storage ထည့်ခြင်းဖြစ်သည်။ လက်ရှိ adapter ပိတ်ထားခြင်းကို provider များအားလုံး၏ လက်ရှိ voice support အပေါ် ကောက်ချက်အဖြစ် မယူရပါ။

4. **React admin မှ နောက်ဆုံးထုတ်ဝေခြင်း မပြီးသေးပါ။** `api.ts` တွင် publish action မရှိဘဲ React publishing page က history ကြည့်ရန်သာဖြစ်သည်။ Legacy `POST /admin/story/<story_id>/publish` တွင် နောက်ဆုံး publication gate ရှိပြီးသားဖြစ်သည်။ MVP အတွက် legacy admin ကို editorial လုပ်ငန်းစဉ်အဖြစ် သေချာသတ်မှတ်သုံးခြင်း၊ သို့မဟုတ် CSRF ပါသော publish API/UI ကိုချိတ်ခြင်း လိုသည်။ React content approval တစ်ခုတည်းဖြင့် public မဖြစ်ပါ။

5. **Theme-only original ၏ publication review လမ်းကြောင်းကို ရှင်းရန်လိုသည်။** Generation က unknown-rights source မသုံးဘဲ original ထုတ်နိုင်သော်လည်း `publication_blockers()` က mode မခွဲဘဲ မူရင်း Library record ၏ translation/AI rights clearance ကို `eligible_candidate()` ဖြင့် လိုအပ်နေသည်။ ထို့ကြောင့် original ထုတ်ပြီးလည်း ထို record ၏ rights မပြောင်းမချင်း ထုတ်ဝေမရပါ။ မသုံးထားသော source ကို ခွင့်ပြုပြီးဟု မမှတ်ဘဲ generated original ၏ provenance နှင့် publication review အတွက် သီးခြား state/စည်းမျဉ်း လိုသည်။

### P1 — လက်တွေ့စမ်းသုံးနိုင်ရန် ပြည့်စုံစေရမည့်အချက်များ

6. **Demo နှင့် live admin ကို ပြည့်ပြည့်စုံစုံခွဲရန်။** `FinderStudio` နှင့် `AudioStudio` တို့တွင် live mode ၌ပင် fixtures ရှိဆဲဖြစ်သည်။ Episode Manager ကမူ live mode တွင် authenticated API ကိုသုံးပြီး editor သို့ချိတ်ထားပြီးသားဖြစ်သည်။ Source list ကို live configuration မှဖတ်ရန် သို့မဟုတ် demo-only အဖြစ် ရှင်းလင်းစွာပိတ်ထားရန်လိုသည်။ Sidebar/publishing/settings က “disabled/not configured” ဟု တစ်သမတ်တည်းရေးထားသောနေရာများကို backend အမှန်တကယ်အခြေအနေမှ ပြရန်လိုသည်။ Dispatch code ရှိပြီးသားကို settings စာသားက မရှိသေးဟုဆိုနေသည်။

7. **Discovery မှ generation ဆက်သွားနိုင်မှုကို အမှန်တကယ်စစ်ရန်။** လက်ရှိ approved source တစ်ခုဖြစ်သော Standard Ebooks configuration တွင် category mapping/default နှင့် verified rights policy မပါပါ။ Category evidence မရသော record များသည် `UNCLASSIFIED` ဖြင့်ရပ်မည်။ လူက category review လုပ်ပြီး processor queue ထဲဝင်သည်အထိ အစမ်းပုံပြင်တစ်ပုဒ်နှင့် စမ်းရန်လိုသည်။ လိုအပ်သောဒေတာမရှိဘဲ source တစ်ခုလုံးကို ကလေးပုံပြင်ဟု မသတ်မှတ်သင့်ပါ။

8. **Quiz/reflection ကို real public API နှင့်ချိတ်ရန်။** Frontend `PublicStory` နှင့် reader UI က quiz/reflection ကိုပြနိုင်သော်လည်း `/api/stories` response ထဲတွင် ထို field နှစ်ခု မပါပါ။ Admin မှ approve ပြီးသော structured data ကို parse/validate လုပ်၍ public DTO တွင် ထည့်ရန်လိုသည်။ လက်ရှိ demo မှာမြင်ရခြင်းသည် live မှာပါ အလုပ်လုပ်ကြောင်း မဆိုလိုပါ။

9. **Job ပိတ်မိမှုနှင့် တစ်ပြိုင်နက်ရေးမှုကို ကိုင်တွယ်ရန်။** Sheets upsert သည် atomic lock မဟုတ်ပါ။ Dispatch လက်ခံပြီး workflow မပြီးလျှင် `DISPATCHED` / `GENERATING` အဖြစ် ကျန်ပြီး နောက် job ကိုတားနိုင်သည်။ `DISPATCH_UNKNOWN` အတွက် စုံစမ်းပြီးမှ retry လုပ်နိုင်သော admin recovery၊ job/run ID၊ stale timeout၊ transaction ပါသော claim သို့မဟုတ် single-writer စည်းမျဉ်း လိုသည်။ သီးခြား discovery/processing concurrency group များက admin နှင့် တစ်ပြိုင်နက် Sheets ရေးမှုအားလုံးကို မကာကွယ်ပါ။

10. **Public rollout အတွက် လက်တွေ့အတည်ပြုရန်။** Live credentials ကို secret store မှပေးခြင်း၊ HTTPS နှင့် stable session secret၊ login rate limiting/access restriction၊ Sheets backup/restore၊ logs/alerts၊ audio URL ရှိလျှင် အမှန်တကယ်ဖွင့်ရမှုတို့ကို staging တွင် စမ်းရန်လိုသည်။ `/health` သည် app အသက်ရှင်မှုသာပြပြီး Sheets ချိတ်ဆက်မှုကို မစစ်ပါ။ Backend shared password သည် တစ်ဦးချင်း reviewer identity အတည်ပြုမှု မပေးပါ။ အစပိုင်း single-editor MVP သုံးပါက admin access ကန့်သတ်ထားရန်လိုသည်။

### P2 — ပထမဆုံး MVP အပြီးမှ ဆက်လုပ်နိုင်သောအချက်များ

- Catalogue ကြီးလာမှ pagination၊ public detail API နှင့် read cache ထည့်ရန်။ လက်ရှိ React detail page အတွက် ပုံပြင်အားလုံးကို API မှဆွဲသည်။
- Team ကြီးလာမှ per-user roles၊ review audit trail နှင့် ပိုမိုခိုင်မာသော database သို့ပြောင်းရန် စဉ်းစားနိုင်သည်။ MVP အတွက် microservices ခွဲရန် မလိုအပ်သေးပါ။
- README ရှိ weekly schedule နှင့် အဟောင်း limitation စာသားများကို လက်ရှိ workflow/code နှင့် ညှိရန်။

## အကြံပြုထားသော ပထမ release နယ်ပယ်

ဤအပိုင်းသည် scope အတွက် အကြံပြုချက်ဖြစ်ပြီး လက်ရှိ configuration ကို ပြောင်းထားခြင်းမရှိပါ။ ပထမ MVP ကို **admin တစ်ဦး၊ manual job run၊ လူစစ်ပြီးသော မြန်မာစာပုံပြင် ဖတ်ရှုနိုင်မှု၊ search/category၊ optional reviewed audio URL** အထိ ကန့်သတ်နိုင်သည်။ Full TTS၊ multi-user account၊ auto-publish နှင့် microservices တို့ကို နောက်မှလုပ်နိုင်သည်။

လုပ်ငန်းစဉ် — P0 crash/error state ကိုပြင် → audio scope နှင့် original review model ရှင်း → publication လမ်းကြောင်းပြီးစီး → demo/live ခွဲ → staging တွင် ပုံပြင်တစ်ပုဒ် အစမှအဆုံးစမ်း → ပြီးမှ public release လုပ်ရန်ဖြစ်သည်။

MVP ပြည့်မီမှုကို အောက်ပါအတိုင်း စစ်နိုင်သည်။

- ရှာတွေ့သောပုံပြင်ကို category review → queue → draft generation → edit → content review → publication approval → public reader အထိ ဆက်လုပ်နိုင်ရမည်။
- Publish မလုပ်ရသေးသော သို့မဟုတ် approval ပြန်ဖြုတ်ထားသော ပုံပြင်ကို public မှ မမြင်ရရပါ။
- Source-based နှင့် theme-only လမ်းကြောင်းနှစ်ခု၏ review စည်းမျဉ်းများကို သီးခြားစမ်းရမည်။
- API ပျက်လျှင် error/retry ပြရမည်။ Job ပိတ်မိလျှင် အခြေအနေကြည့်ပြီး ပြန်ဆယ်နိုင်ရမည်။
- ဖုန်းပေါ်တွင် မြန်မာစာ၊ episode navigation နှင့် ရှိပါက audio ကို လက်တွေ့စမ်းရမည်။
- Private source text နှင့် credentials များ public response ထဲ မပါရပါ။

## ယခုစစ်ဆေးထားသောရလဒ်

- Python offline tests — **၅၀/၅၀ အောင်**။
- Frontend Vitest tests — **၁၂/၁၂ အောင်**။
- TypeScript + Vite production build — **အောင်**။
- Tests အောင်ခြင်းသည် အပေါ်က မစမ်းရသေးသော route/error condition နှင့် live integration များ အားလုံးအောင်ကြောင်း မဆိုလိုပါ။
- ယခုအပြောင်းအလဲတွင် အဓိက backend/frontend လုပ်ငန်းစဉ်များ၌ မြန်မာ comment နှင့် ဤ review စာတမ်းကို ထည့်ထားသည်။ Business logic၊ credentials၊ publication setting နှင့် deployment မပြောင်းထားပါ။ တွေ့ရှိထားသော bug များသည် ပြင်ဆင်ရန်ကျန်နေဆဲဖြစ်သည်။
