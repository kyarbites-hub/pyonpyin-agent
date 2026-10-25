import { useEffect, useRef, useState } from "react";
import { Download, Pause, Play, RotateCcw, Volume2 } from "lucide-react";

interface DemoAudioPlayerProps {
  title: string;
  duration?: number;
  frequency?: number;
  compact?: boolean;
  onNotice?: (message: string) => void;
}

function createPreviewWav(frequency: number, duration: number): Blob {
  // Player စမ်းရန် sine wave အသံကို WAV အဖြစ်ထုတ်သည်။ ပုံပြင်ဖတ်ပြသည့် TTS အသံမဟုတ်ပါ။
  const sampleRate = 22050;
  const frameCount = sampleRate * duration;
  const buffer = new ArrayBuffer(44 + frameCount * 2);
  const view = new DataView(buffer);
  const writeText = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index));
    }
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + frameCount * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, frameCount * 2, true);
  for (let frame = 0; frame < frameCount; frame += 1) {
    const fade = Math.min(1, frame / 1000, (frameCount - frame) / 1000);
    const sample = Math.sin((2 * Math.PI * frequency * frame) / sampleRate) * 0.12 * fade;
    view.setInt16(44 + frame * 2, sample * 32767, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function formatTime(value: number): string {
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export default function DemoAudioPlayer({
  title,
  duration = 75,
  frequency = 196,
  compact = false,
  onNotice,
}: DemoAudioPlayerProps) {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(65);
  const [speed, setSpeed] = useState(1);
  const [audioError, setAudioError] = useState("");
  const contextRef = useRef<AudioContext | null>(null);
  const oscillatorRef = useRef<OscillatorNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);

  const stopTone = () => {
    oscillatorRef.current?.stop();
    oscillatorRef.current?.disconnect();
    oscillatorRef.current = null;
    gainRef.current?.disconnect();
    gainRef.current = null;
  };

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setCurrentTime((value) => {
        if (value + speed >= duration) {
          setPlaying(false);
          return 0;
        }
        return value + speed;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [duration, playing, speed]);

  useEffect(() => {
    if (!playing) stopTone();
  }, [playing]);

  useEffect(() => () => {
    stopTone();
    void contextRef.current?.close();
  }, []);

  useEffect(() => {
    if (gainRef.current && contextRef.current) {
      gainRef.current.gain.setTargetAtTime(volume / 100 * 0.12, contextRef.current.currentTime, 0.04);
    }
  }, [volume]);

  useEffect(() => {
    if (oscillatorRef.current) oscillatorRef.current.frequency.value = frequency * speed;
  }, [frequency, speed]);

  const togglePlayback = async () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    setAudioError("");
    try {
      const AudioContextConstructor = window.AudioContext;
      if (!AudioContextConstructor) throw new Error("This browser does not support audio preview.");
      const context = contextRef.current ?? new AudioContextConstructor();
      contextRef.current = context;
      await context.resume();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.value = volume / 100 * 0.12;
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillatorRef.current = oscillator;
      gainRef.current = gain;
      setPlaying(true);
      onNotice?.("Synthesized tone preview started — this is not narration or generated story audio.");
    } catch (cause) {
      setAudioError(cause instanceof Error ? cause.message : "Audio preview could not start.");
    }
  };

  const downloadPreview = () => {
    const url = URL.createObjectURL(createPreviewWav(frequency, Math.min(duration, 10)));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-ui-tone-demo.wav`;
    anchor.click();
    URL.revokeObjectURL(url);
    onNotice?.("Downloaded a short synthesized tone for UI testing, not story narration.");
  };

  const regeneratePreview = () => {
    setCurrentTime(0);
    setPlaying(false);
    onNotice?.("Demo preview reset. No speech provider or AI service was called.");
  };

  return (
    <section className={`audio-player ${compact ? "audio-player-compact" : ""}`} aria-label={`Demo audio player: ${title}`}>
      <div className="audio-player-top">
        <div className="audio-art"><Volume2 size={compact ? 19 : 24} /></div>
        <div className="audio-track-meta">
          <span className="audio-demo-chip">SYNTHETIC UI DEMO · NOT NARRATION</span>
          <strong>{title}</strong>
          {!compact && <small>Browser-generated tone · no Burmese voice or story audio</small>}
        </div>
        <button className="audio-icon-button" type="button" aria-label="Reset demo audio" onClick={regeneratePreview}><RotateCcw size={16} /></button>
        <button className="audio-icon-button" type="button" aria-label="Download synthesized tone demo" onClick={downloadPreview}><Download size={16} /></button>
      </div>
      <div className="audio-seek-row">
        <span>{formatTime(currentTime)}</span>
        <input aria-label="Demo audio seek" type="range" min="0" max={duration} step="1" value={currentTime} onChange={(event) => setCurrentTime(Number(event.target.value))} />
        <span>{formatTime(duration)}</span>
      </div>
      <div className="audio-controls">
        <button className="audio-play-button" type="button" onClick={() => void togglePlayback()} aria-label={playing ? "Pause demo audio" : "Play demo audio"}>
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <label className="audio-volume"><Volume2 size={16} /><input aria-label="Demo audio volume" type="range" min="0" max="100" value={volume} onChange={(event) => setVolume(Number(event.target.value))} /></label>
        <label className="audio-speed-label">Speed
          <select aria-label="Demo playback speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
            <option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option>
          </select>
        </label>
      </div>
      {audioError && <p className="form-error" role="alert">{audioError}</p>}
    </section>
  );
}
