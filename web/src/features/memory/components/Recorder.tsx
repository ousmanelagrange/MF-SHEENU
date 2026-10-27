// Enregistrer la voix d'un ancien directement depuis le navigateur (ordinateur ou téléphone),
// ou choisir un fichier audio ou vidéo déjà enregistré (WhatsApp, dictaphone…).

import { AudioOutlined, PaperClipOutlined } from "@ant-design/icons";
import { Button, Upload } from "antd";
import { useEffect, useRef, useState } from "react";

export type PickedMedia = { blob: Blob; name: string; preview: string; video: boolean };

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function Recorder({ value, onChange }: { value: PickedMedia | null; onChange: (m: PickedMedia | null) => void }) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);

  // Arrête le micro si l'on quitte l'écran pendant l'enregistrement
  useEffect(() => () => recorder.current?.stream.getTracks().forEach((t) => t.stop()), []);
  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [recording]);

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        const ext = blob.type.includes("mp4") ? "m4a" : "webm";
        onChange({ blob, name: `recit.${ext}`, preview: URL.createObjectURL(blob), video: false });
      };
      rec.start();
      recorder.current = rec;
      setSeconds(0);
      setRecording(true);
    } catch {
      setError("Le micro n'est pas accessible. Autorisez-le dans le navigateur, ou envoyez un fichier.");
    }
  };

  const stop = () => {
    recorder.current?.stop();
    setRecording(false);
  };

  if (value) {
    return (
      <div className="recorder recorder--done">
        {value.video ? <video src={value.preview} controls /> : <audio src={value.preview} controls />}
        <Button type="link" onClick={() => onChange(null)}>
          Remplacer
        </Button>
      </div>
    );
  }

  return (
    <div className="recorder">
      {recording ? (
        <>
          <span className="recorder__live" aria-live="polite">
            <span className="recorder__dot" /> Enregistrement {clock(seconds)}
          </span>
          <Button onClick={stop}>Arrêter</Button>
        </>
      ) : (
        <>
          <Button icon={<AudioOutlined />} onClick={start}>
            Enregistrer
          </Button>
          <Upload
            accept="audio/*,video/*"
            showUploadList={false}
            beforeUpload={(file) => {
              onChange({ blob: file, name: file.name, preview: URL.createObjectURL(file), video: file.type.startsWith("video/") });
              return false;
            }}
          >
            <Button type="text" icon={<PaperClipOutlined />}>
              Choisir un fichier
            </Button>
          </Upload>
        </>
      )}
      {error && <p className="recorder__error">{error}</p>}
    </div>
  );
}
