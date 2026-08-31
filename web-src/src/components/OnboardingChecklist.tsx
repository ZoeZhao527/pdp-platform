import { CheckCircle2, Circle, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api";

type Step = {
  key: string;
  label: string;
  done: boolean;
  link: string;
  detail?: string;
};

export function OnboardingChecklist({ onNavigate }: { onNavigate: (path: string) => void }) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(0);
  const [total, setTotal] = useState(0);
  const [collapsed, setCollapsed] = useState(false);

  const load = () => {
    api.onboarding().then((d) => {
      setSteps(d.steps);
      setProgress(d.progress);
      setDone(d.done);
      setTotal(d.total);
      setCollapsed(d.progress >= 100);
    }).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  if (collapsed) return null;

  return (
    <section className="onboarding-card">
      <div className="onboarding-head">
        <div>
          <h2>品牌接入引导</h2>
          <span className="onboarding-progress-text">{done}/{total} 步完成</span>
        </div>
        <button className="onboarding-collapse" onClick={() => setCollapsed(true)}>收起</button>
      </div>
      <div className="onboarding-bar">
        <div className="onboarding-bar-fill" style={{ width: `${progress}%` }} />
      </div>
      <div className="onboarding-steps">
        {steps.map((s) => (
          <div
            key={s.key}
            className={`onboarding-step ${s.done ? "done" : ""}`}
            onClick={() => onNavigate(s.link)}
          >
            {s.done ? <CheckCircle2 size={18} className="onboarding-check" /> : <Circle size={18} className="onboarding-pending" />}
            <span className="onboarding-label">{s.label}</span>
            {s.detail && <span className="onboarding-detail">{s.detail}</span>}
            {!s.done && <ExternalLink size={13} className="onboarding-go" />}
          </div>
        ))}
      </div>
    </section>
  );
}
