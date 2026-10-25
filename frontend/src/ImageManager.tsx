import { useEffect, useState } from "react";
import { api } from "./api";
import { ImagePlus, CheckCircle2 } from "lucide-react";

export function ImageManager({ csrf, storyId, imageUrl = "", onChanged }: { csrf: string; storyId?: string; imageUrl?: string; onChanged?: (url: string) => void }) {
  const [url, setUrl] = useState(imageUrl);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const path = storyId ? `/api/admin/story/${encodeURIComponent(storyId)}/cover-image` : "/api/admin/site/hero-image";
  useEffect(() => { setUrl(imageUrl); }, [imageUrl, storyId]);
  useEffect(() => {
    if (!storyId) void api.site().then((site) => setUrl(site.hero_image_url)).catch(() => setError("ပင်မစာမျက်နှာပုံကို ဖတ်မရပါ။"));
  }, [storyId]);
  const change = async (file?: File) => {
    if (file && file.size > 8 * 1024 * 1024) { setError("ပုံဖိုင်ကို 8 MB အောက် ရွေးပါ။"); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = file ? await api.uploadImage(path, file, csrf) : await api.removeImage(path, csrf);
      setUrl(result.image_url); onChanged?.(result.image_url);
      setMessage(result.image_url ? "ပုံ သိမ်းပြီးပါပြီ။ ထုတ်ဝေထားလျှင် public စာမျက်နှာကို ပြန်ဖွင့်၍ ကြည့်နိုင်ပါပြီ။" : "ပုံဖယ်ပြီးပါပြီ။ မူလဒီဇိုင်းကို ပြန်သုံးပါမည်။");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "ပုံ သိမ်းမရပါ။"); }
    finally { setBusy(false); }
  };
  return <section className="admin-panel image-manager" aria-label={storyId ? "ပုံပြင်မျက်နှာဖုံးပုံ" : "ပင်မစာမျက်နှာပုံ"}>
    <h2>{storyId ? "ပုံပြင် မျက်နှာဖုံးပုံ" : "ပုံပြင်တစ်ပုဒ် · ကမ္ဘာတစ်ခု — ပင်မစာမျက်နှာပုံ"}</h2>
    <p>{storyId ? "ပုံက ရွေးချယ်စရာပါ။ ပုံမထည့်လည်း ထုတ်ဝေနိုင်သည်။ ထုတ်ဝေပြီးမှလည်း ပုံထည့်၊ ပြောင်း၊ ဖယ်နိုင်သည်။" : "Public website ပင်မစာမျက်နှာရှိ ပုံကို ဤနေရာမှ ပြောင်းနိုင်သည်။ ပုံဖယ်လျှင် မူလဒီဇိုင်းကို ပြန်သုံးမည်။"}</p>
    <div className="image-upload-layout"><div>{url ? <><img className="image-manager-preview" src={url} alt={storyId ? "လက်ရှိပုံပြင် မျက်နှာဖုံးပုံ" : "လက်ရှိပင်မစာမျက်နှာပုံ"} /><span className="image-added-state"><CheckCircle2 size={15} /> Image Added</span></> : <div className="image-placeholder">ပုံမထည့်ရသေးပါ · မူလဒီဇိုင်းကို သုံးနေသည်</div>}</div>
    <div className={`image-dropzone ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); const file = event.dataTransfer.files[0]; if (!busy && file) void change(file); }}><ImagePlus size={34} aria-hidden="true" /><strong>Image Preview</strong><p>ပုံဖိုင်ကို ဤနေရာသို့ ဆွဲထည့်နိုင်သည်</p><label className="editor-field">{url ? "ပုံအသစ် အစားထိုးရွေးရန်" : "ပုံဖိုင် ရွေးရန်"}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void change(file); }} /></label></div></div>
    <p>JPG / PNG / WebP · အများဆုံး 8 MB · ရွေးလိုက်သည်နှင့် သိမ်းပေးမည်။</p>
    {url && <button type="button" className="button button-quiet" disabled={busy} onClick={() => { if (window.confirm("ဤပုံကို ဖယ်ပြီး မူလဒီဇိုင်းပြန်သုံးမည်လား။")) void change(); }}>ပုံဖယ်ရန်</button>}
    {busy && <p role="status">ပုံ သိမ်းနေသည်…</p>}{message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>;
}
