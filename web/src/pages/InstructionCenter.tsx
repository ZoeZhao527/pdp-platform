import { CheckCircle2, Download, Package, Play, Upload, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api";
import { WriteGate } from "../components/WriteGate";
import type { AssetPackage, FlywheelAdvisories, FlywheelSuggestion, IndustryRow, InstructionRow } from "../types";

const EMPTY_PARAMS = {
  goal_type: "GMV",
  goal_value: "",
  priority: "高",
  layers: "",
  tags: "",
  age: "",
  city: "",
  source: "",
  product_categories: "",
  product_roles: "",
  price_range: "",
  margin: "",
  inventory: "",
  bundles: "",
  activity_type: "",
  gameplay: "",
  budget: "",
  materials: "",
  content_types: "",
  content_channels: "",
  frequency: "",
  tone: "",
  sales_tone: "",
  objections: "",
  follow_up: "",
  referral: "",
  touch_channels: "",
  touch_frequency: "",
  time_window: "",
  auto_mode: "半自动",
  kpi_metrics: "",
  kpi_targets: "",
  data_source: "",
  acceptance: "",
  forbidden_words: "",
  review: "是",
  budget_limit: "",
  time_limit: "",
  automation_mode: "半自动",
  schedule: "",
  related_signals: "",
  related_history: "",
 related_knowledge: "",
};

type ExampleTemplate = { category: string; text: string };

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  instruction_id?: string;
  title?: string;
  summary?: string;
  asset?: AssetPackage | null;
  can_revise?: boolean;
};

const EXAMPLE_TEMPLATES: Record<string, ExampleTemplate[]> = {
  beauty: [
   { category: "活动策划", text: "帮我策划8月敏感肌活动，主打补水修复，针对干皮和敏感肌客户，预算5万，目标GMV增长20%" },
    { category: "卡项推广", text: "高端卡项推广，针对老客复购，设计逼单话术和异议处理，目标转化率15%" },
   { category: "朋友圈托管", text: "本月朋友圈和社群内容托管，美业护肤方向，每周3条朋友圈，1次社群活动" },
    { category: "1v1话术", text: "新客到店后1v1护肤咨询话术，从肤质分析到产品推荐，含常见异议处理" },
    { category: "社群运营", text: "本周末社群秒杀活动，限时3小时，设计预热-开抢-追单全套流程" },
    { category: "分层打法", text: "按消费金额分3层运营，高频客推新品、中频客推套餐、低频客激活" },
  ],
  catering: [
    { category: "活动策划", text: "策划本月会员日满减活动，满200减30，目标到店客流提升25%" },
    { category: "货盘规划", text: "梳理本月主推菜品，区分引流套餐、利润单品、招牌菜，设计组合套餐" },
    { category: "朋友圈托管", text: "本月朋友圈内容托管，餐饮方向，每周4条朋友圈，2条菜品视频" },
    { category: "1v1话术", text: "老客回访1v1话术，从关怀到推荐新品，含常见异议处理" },
    { category: "社群运营", text: "本周社群拼团活动，3人成团享8折，设计预热-成团-追单流程" },
    { category: "分层打法", text: "按消费频次分3层运营，高频客推会员卡、中频客推套餐、低频客推体验券" },
  ],
  retail: [
    { category: "活动策划", text: "策划夏季饮用水促销活动，针对社区团购渠道，主打家庭装，目标销量提升30%" },
    { category: "货盘规划", text: "梳理本月主推SKU，区分引流款、利润款、形象款，设计组合套装策略" },
    { category: "朋友圈托管", text: "本月朋友圈内容托管，品牌方向，每周4条朋友圈，2条视频" },
    { category: "1v1话术", text: "社区团长开发1v1话术，从破冰到试饮到首单，含常见异议处理" },
    { category: "社群运营", text: "本周社群拼团活动，5人成团享8折，设计预热-成团-追单流程" },
    { category: "分层打法", text: "按购买频次分3层运营，高频客推年卡、中频客推月套餐、低频客推体验装" },
  ],
  education: [
    { category: "活动策划", text: "策划暑期体验课活动，针对3-12岁儿童家长，目标报名转化率12%" },
    { category: "货盘规划", text: "梳理本月主推课程，区分体验课、正价课、年卡课，设计组合套餐" },
    { category: "朋友圈托管", text: "本月朋友圈内容托管，教育方向，每周3条朋友圈，1次社群讲座" },
    { category: "1v1话术", text: "新客咨询1v1话术，从需求分析到课程推荐，含常见异议处理" },
    { category: "社群运营", text: "本周社群拼团活动，3人成团享8折，设计预热-成团-追单流程" },
    { category: "分层打法", text: "按学习阶段分3层运营，新生推体验课、在读推进阶课、毕业推续报" },
  ],
  pet: [
    { category: "活动策划", text: "策划宠物洗护套餐活动，针对新客到店体验，目标转化率20%" },
    { category: "货盘规划", text: "梳理本月主推服务，区分引流洗护、利润SPA、高端寄养，设计组合套餐" },
    { category: "朋友圈托管", text: "本月朋友圈内容托管，宠物方向，每周4条朋友圈，2条萌宠视频" },
    { category: "1v1话术", text: "新客到店1v1话术，从宠物评估到服务推荐，含常见异议处理" },
    { category: "社群运营", text: "本周社群拼团活动，3人成团享8折，设计预热-成团-追单流程" },
    { category: "分层打法", text: "按消费金额分3层运营，高频客推年卡、中频客推套餐、低频客推体验装" },
  ],
  health: [
    { category: "活动策划", text: "策划本月健康检测活动，针对25-45岁白领，目标到店转化率15%" },
    { category: "货盘规划", text: "梳理本月主推服务，区分引流检测、利润套餐、高端定制，设计组合策略" },
    { category: "朋友圈托管", text: "本月朋友圈内容托管，大健康方向，每周3条朋友圈，1次社群科普" },
    { category: "1v1话术", text: "新客咨询1v1话术，从健康评估到方案推荐，含常见异议处理" },
    { category: "社群运营", text: "本周社群拼团活动，3人成团享8折，设计预热-成团-追单流程" },
    { category: "分层打法", text: "按消费金额分3层运营，高频客推年卡、中频客推套餐、低频客推体验装" },
  ],
};

function AssetView({ asset }: { asset: AssetPackage }) {
  const ap = asset.activity_plan || { theme: "", types: [], channels: [], budget: "", kpi: [] };
  const sp = asset.sales_playbook || { layer_plays: [], objections: [], sections: [] };
  const cs = asset.content_schedule || { schedules: [], materials: [], channels: [] };
  const kp = asset.kpi_targets || [];
  const ad = asset.audience;
  const st = asset.script_templates || ({} as NonNullable<AssetPackage["script_templates"]>);
  const card = asset.card_structure || ({} as NonNullable<AssetPackage["card_structure"]>);
  const det = asset.activity_details || ({} as NonNullable<AssetPackage["activity_details"]>);
  const mat = asset.content_materials || ({} as NonNullable<AssetPackage["content_materials"]>);
 const con = asset.constraints || ({} as NonNullable<AssetPackage["constraints"]>);
  const [assetTab, setAssetTab] = useState("activity");
 return (
   <div className="asset-package">
      <div className="asset-tabs">
        <button type="button" className={`asset-tab ${assetTab === "activity" ? "active" : ""}`} onClick={() => setAssetTab("activity")}>活动策划</button>
        <button type="button" className={`asset-tab ${assetTab === "product" ? "active" : ""}`} onClick={() => setAssetTab("product")}>货盘卡项</button>
        <button type="button" className={`asset-tab ${assetTab === "sales" ? "active" : ""}`} onClick={() => setAssetTab("sales")}>销售话术</button>
        <button type="button" className={`asset-tab ${assetTab === "content" ? "active" : ""}`} onClick={() => setAssetTab("content")}>内容排期</button>
        <button type="button" className={`asset-tab ${assetTab === "kpi" ? "active" : ""}`} onClick={() => setAssetTab("kpi")}>KPI约束</button>
      </div>
      {assetTab === "activity" && (
      <>
     <div className="asset-section">
       <h3>活动策划</h3>
        <div className="tag-row">
          <span className="tag">{ap.theme}</span>
        {ap.goal && <span className="tag">目标：{ap.goal}</span>}
         {ap.timeline && <span className="tag">时间线：{ap.timeline}</span>}
         {ap.types.map((item: any, i: number) => {
            const name = typeof item === "string" ? item : item?.name || "";
            if (typeof item === "string") {
              return <span key={i} className="tag">{name}</span>;
            }
            return (
              <div key={i} className="asset-sub-card">
                <div className="tag-row" style={{ marginBottom: 6 }}>
                  <span className="tag accent">{name}</span>
                  {item?.mechanism && <span className="tag">玩法：{item.mechanism}</span>}
                  {item?.target_audience && <span className="tag">目标：{item.target_audience}</span>}
                </div>
                {item?.products?.length > 0 && (
                  <p className="cell-muted" style={{ marginBottom: 4 }}>
                    参与产品：{item.products.join("、")}
                  </p>
                )}
                {item?.rhythm?.length > 0 && (
                  <div className="rhythm-grid">
                    {item.rhythm.map((r: any, ri: number) => (
                      <div key={ri} className="rhythm-item">
                        <span className="rhythm-phase">{r.phase}</span>
                        {r.days && <span className="rhythm-days">{r.days}</span>}
                        <p className="cell-text">{r.actions}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
       </div>
       {det.summary && <p className="cell-text">{det.summary}</p>}
        {det.calendar && (
         <div className="cell-block">
           <span className="cell-label">18 天执行日历</span>
            {Array.isArray(det.calendar) ? (
              <table style={{ width: "100%", marginTop: 4, borderCollapse: "collapse" }}>
                <tbody>
                  {det.calendar.map((c: any, ci: number) => (
                    <tr key={ci} style={{ borderBottom: "1px solid var(--line)" }}>
                      <td className="cell-main" style={{ whiteSpace: "nowrap", width: 100, padding: "6px 8px" }}>{c.date}</td>
                      <td className="cell-text" style={{ padding: "6px 8px" }}>{c.task}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="cell-text">{String(det.calendar)}</p>
            )}
         </div>
       )}
        {det.reference && (
          <div className="cell-block">
            <span className="cell-label">真实活动素材参考</span>
            <p className="cell-text muted">{det.reference}</p>
          </div>
        )}
      </div>
      {ad && (
        <div className="asset-section">
          <h3>目标人群</h3>
          <div className="tag-row">
            {(ad.layers || []).map((item) => (
              <span key={item} className="tag">
                {item}
              </span>
            ))}
          </div>
       </div>
     )}
      </>
      )}
     {assetTab === "product" && (
     <>

     {(card.cards?.length || card.summary || card.rules || card.reference) ? (
       <div className="asset-section">
         <h3>卡项结构</h3>
         {card.cards?.length ? (
           <div style={{ marginBottom: 12 }}>
             <span className="cell-label">组卡方案</span>
             {card.cards.map((c: any, ci: number) => (
               <div key={ci} className="cell-block" style={{ marginBottom: 8, padding: 8, border: "1px solid #e0e0e6", borderRadius: 6 }}>
                 <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                   <span style={{ fontWeight: 600, fontSize: 14 }}>{c.card_type} · {c.card_name}</span>
                   <span style={{ fontSize: 12, color: (c.compliance || "").includes("合规") ? "#16a34a" : "#dc2626" }}>{c.compliance}</span>
                 </div>
                 {(c.zones || []).map((z: any, zi: number) => (
                   <div key={zi} style={{ display: "flex", gap: 4, marginBottom: 4, fontSize: 13 }}>
                     <span style={{ minWidth: 60, color: "#6b7280" }}>{z.zone}({z.tier}档)</span>
                     <span style={{ flex: 1 }}>{(z.items || []).map((it: any) => it.name).join(" / ")}</span>
                     <span style={{ color: "#6b7280" }}>{z.pick_rule}</span>
                   </div>
                 ))}
                 <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 13, fontWeight: 500 }}>
                   <span>门市价: {c.total_retail}元</span>
                   <span>定价: {c.selling_price}元</span>
                   <span style={{ color: "#2563eb" }}>折扣: {c.discount}</span>
                 </div>
                 {c.selling_point && <p className="cell-text" style={{ marginTop: 4, fontSize: 12 }}>{c.selling_point}</p>}
               </div>
             ))}
           </div>
         ) : null}

         {card.summary && <p className="cell-text">{card.summary}</p>}
          {card.rules && (
            <div className="cell-block">
              <span className="cell-label">组合规则</span>
              <p className="cell-text">{card.rules}</p>
            </div>
          )}
          {card.reference && (
            <div className="cell-block">
              <span className="cell-label">真实卡项素材参考</span>
              <p className="cell-text muted">{card.reference}</p>
            </div>
          )}
       </div>
     ) : null}
      </>
      )}
      {assetTab === "sales" && (
      <>
     <div className="asset-section">
       <h3>销售执行包</h3>
        <div className="tag-row">
          {(sp.layer_plays || []).map((item) => (
            <span key={item.layer} className="tag">
              {item.layer}：{item.goal}
            </span>
          ))}
        </div>
        {sp.tone && <p className="cell-muted">话术：{sp.tone}</p>}
        {(st.opening || st.close || st.objection || st.follow_up) && (
          <div className="script-grid">
            {st.opening && (
              <div className="cell-block">
                <span className="cell-label">破冰开场</span>
                <p className="cell-text">{st.opening}</p>
              </div>
            )}
            {st.close && (
              <div className="cell-block">
                <span className="cell-label">逼单促成</span>
                <p className="cell-text">{st.close}</p>
              </div>
            )}
            {st.objection && (
              <div className="cell-block">
                <span className="cell-label">异议处理</span>
                <p className="cell-text">{st.objection}</p>
              </div>
            )}
          {st.objection_handling?.length ? (
            <div className="cell-block" style={{ gridColumn: "1 / -1" }}>
              <span className="cell-label">异议处理（分场景）</span>
               {Array.isArray(st.objection_handling) ? (
                 st.objection_handling.map((item, i) => (
                   <div key={i} className="cell-block" style={{ marginBottom: 8 }}>
                     <div className="tag-row" style={{ marginBottom: 4 }}>
                       {item.category && <span className="tag accent">{item.category}</span>}
                       <span className="cell-label">{item.scenario}</span>
                     </div>
                     <p className="cell-text">{item.response}</p>
                   </div>
                 ))
               ) : (
                 <p className="cell-text">{String(st.objection_handling)}</p>
               )}
            </div>
          ) : null}
            {st.follow_up && (
              <div className="cell-block">
                <span className="cell-label">回访跟进</span>
                <p className="cell-text">{st.follow_up}</p>
              </div>
            )}
            {st.layered_scripts?.length ? (
              <div className="cell-block" style={{ gridColumn: "1 / -1" }}>
                <span className="cell-label">分层话术</span>
                <div className="layered-scripts-grid">
                  {st.layered_scripts.map((item, i) => (
                    <div key={i} className="layered-script-card">
                      <span className="tag accent">{item.layer}</span>
                      {item.opening && (
                        <div className="cell-block" style={{ marginTop: 4 }}>
                          <span className="cell-label">开场白</span>
                          <p className="cell-text">{item.opening}</p>
                        </div>
                      )}
                      {item.close && (
                        <div className="cell-block" style={{ marginTop: 4 }}>
                          <span className="cell-label">逼单</span>
                          <p className="cell-text">{item.close}</p>
                        </div>
                      )}
                      {item.follow_up && (
                        <div className="cell-block" style={{ marginTop: 4 }}>
                          <span className="cell-label">回访</span>
                          <p className="cell-text">{item.follow_up}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
       )}
     </div>
      </>
      )}
      {assetTab === "content" && (
      <>
     <div className="asset-section">
       <h3>内容排期</h3>
        <div className="tag-row">
          {(cs.schedules || []).map((item) => (
            <span key={`${item.channel}-${item.cadence}`} className="tag">
              {item.channel} · {item.cadence}
            </span>
          ))}
        </div>
        {cs.frequency && <p className="cell-muted">频率：{cs.frequency}</p>}
        {cs.daily_content?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>渠道</th>
                  <th>内容</th>
                </tr>
              </thead>
              <tbody>
                {cs.daily_content.map((item, i) => (
                  <tr key={i}>
                    <td className="cell-main">{item.day}</td>
                    <td>{item.channel}</td>
                    <td>{item.content}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {mat.summary && <p className="cell-text">{mat.summary}</p>}
        {mat.reference && (
          <div className="cell-block">
            <span className="cell-label">真实内容素材参考</span>
            <p className="cell-text muted">{mat.reference}</p>
          </div>
       )}
     </div>
      </>
      )}
      {assetTab === "kpi" && (
      <>
     <div className="asset-section">
       <h3>KPI 目标</h3>
        <div className="tag-row">
          {kp.map((item) => (
            <span key={item} className="tag">
              {item}
            </span>
          ))}
        </div>
      </div>
      {(con.automation_mode || con.review || con.budget_limit || con.time_limit) ? (
        <div className="asset-section">
          <h3>合规与约束</h3>
          <p className="cell-muted">
            自动化：{con.automation_mode || "-"} · 审核：{con.review || "-"} · 预算上限：
            {con.budget_limit || "-"} · 时间限制：{con.time_limit || "-"}
          </p>
        </div>
     ) : null}
      </>
     )}
    </div>
  );
}

export default function InstructionCenter() {
  const [industries, setIndustries] = useState<IndustryRow[]>([]);
  const [industryId, setIndustryId] = useState(localStorage.getItem("pdp_industry_id") || "");
  const [rows, setRows] = useState<InstructionRow[]>([]);
  const [asset, setAsset] = useState<AssetPackage | null>(null);
  const [assetInstructionId, setAssetInstructionId] = useState("");
  const [exporting, setExporting] = useState(false);
  const [acceptTarget, setAcceptTarget] = useState<InstructionRow | null>(null);
  const [kpiDraft, setKpiDraft] = useState<Record<string, string>>({});
  const [advisories, setAdvisories] = useState<FlywheelAdvisories | null>(null);
  const [tab, setTab] = useState<"advice" | "new" | "list">("advice");
  const [advisoryDetail, setAdvisoryDetail] = useState<{
    kind: string;
    title: string;
    fields: { label: string; value: string }[];
  } | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
 const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => {
   try {
     const _tid = localStorage.getItem("pdp_tenant_id") || "default";
     return JSON.parse(localStorage.getItem(`pdp_chat_messages_${_tid}`) || "[]");
   }
   catch { return []; }
 });
const [chatInput, setChatInput] = useState("");
const [chatLoading, setChatLoading] = useState(false);
  const [briefTarget, setBriefTarget] = useState<{ id: string; title: string } | null>(null);
  const [briefCards, setBriefCards] = useState<any[]>([]);
  const [briefDraft, setBriefDraft] = useState({ card_name: "", market_price: "", selling_price: "", items: "", selling_point: "" });
  const [briefSaving, setBriefSaving] = useState(false);
 const [attachedBrief, setAttachedBrief] = useState<any[]>([]);
const [pendingClarification, setPendingClarification] = useState<{
  originalMessage: string;
  questions: { dimension: string; question: string; examples: string[] }[];
  attachedBrief?: any[];
} | null>(null);

  const currentIndustry = industries.find((item) => item.id === industryId);

const load = useCallback(() => {
  api
    .platformInstructions()
    .then(setRows)
    .catch((err: Error) => setError(err.message));
}, []);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    try {
      const _tid = localStorage.getItem("pdp_tenant_id") || "default";
      localStorage.setItem(`pdp_chat_messages_${_tid}`, JSON.stringify(chatMessages.slice(-50)));
    } catch { /* ignore quota */ }
  }, [chatMessages]);

 useEffect(() => {
    api
      .platformIndustries()
      .then((rows) => {
        setIndustries(rows);
        if (!industryId && rows.length > 0) {
          localStorage.setItem("pdp_industry_id", rows[0].id);
          setIndustryId(rows[0].id);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [industryId]);

  useEffect(load, [load]);

  useEffect(() => {
    api
      .flywheelAdvisories()
      .then(setAdvisories)
      .catch(() => undefined);
  }, [industryId]);


 const sendChat = async () => {
   const msg = chatInput.trim();
   if (!msg || chatLoading) return;
   setChatInput("");
   setAttachedBrief([]);
   setChatLoading(true);
   setChatMessages((prev) => [...prev, { role: "user", content: msg }]);
   try {
    const res = await api.chatInstruction(msg, undefined, attachedBrief.length ? { cards: attachedBrief } : undefined);
   if (res.needs_clarification) {
     const qs = (res.questions || [])
       .map((q: any) => `▸ ${q.question}\n  示例：${(q.examples || []).join("、")}`)
       .join("\n\n");
     setPendingClarification({
       originalMessage: msg,
       questions: res.questions || [],
       attachedBrief: attachedBrief.length ? [...attachedBrief] : [],
     });
     setChatMessages((prev) => [...prev, {
       role: "assistant",
       content: `${res.summary || `已识别你的意图「${res.title}」`}\n\n还需要补充以下信息：\n\n${qs}\n\n请直接回复补充内容`,
     }]);
     setChatLoading(false);
     return;
   }
    setChatMessages((prev) => [...prev, {
      role: "assistant",
      content: `已创建指令「${res.title}」\n${res.summary}\n正在自动生成资产包，预计1-3分钟...`,
      instruction_id: res.instruction_id,
      title: res.title,
      summary: res.summary,
    }]);
    load();
    // Auto-generate asset package immediately after instruction creation
    chatGenerate(res.instruction_id);
   } catch (err) {
     setChatMessages((prev) => [...prev, { role: "assistant", content: `解析失败：${(err as Error).message}` }]);
     setChatLoading(false);
   }
 };
 // 3.0: If the last assistant message has can_revise + instruction_id,
 // the user's new message is a modification request → route to revise endpoint
const sendChatOrRevise = async () => {
  const msg = chatInput.trim();
  if (!msg || chatLoading) return;
  // --- Clarification flow: merge user's answer into the original instruction ---
  if (pendingClarification) {
    const combined = pendingClarification.originalMessage + "（补充说明：" + msg + "）";
    const brief = pendingClarification.attachedBrief || [];
    setPendingClarification(null);
    setChatInput("");
    setChatLoading(true);
    setChatMessages((prev) => [...prev, { role: "user", content: msg }]);
    try {
      const res = await api.chatInstruction(combined, undefined, brief.length ? { cards: brief } : undefined);
      if (res.needs_clarification) {
        setPendingClarification({
          originalMessage: combined,
          questions: res.questions || [],
          attachedBrief: brief,
        });
        const qs = (res.questions || [])
          .map((q: any) => `▸ ${q.question}\n  示例：${(q.examples || []).join("、")}`)
          .join("\n\n");
        setChatMessages((prev) => [...prev, {
          role: "assistant",
          content: `${res.summary || ""}\n\n还需要补充以下信息：\n\n${qs}\n\n请继续回复补充内容。`,
        }]);
        setChatLoading(false);
        return;
      }
      setChatMessages((prev) => [...prev, {
        role: "assistant",
        content: `已创建指令「${res.title}」\n${res.summary}\n正在自动生成资产包，预计1-3分钟...`,
        instruction_id: res.instruction_id,
        title: res.title,
        summary: res.summary,
      }]);
      load();
      chatGenerate(res.instruction_id);
    } catch (err) {
      setChatMessages((prev) => [...prev, { role: "assistant", content: `解析失败：${(err as Error).message}` }]);
      setChatLoading(false);
    }
    return;
  }
  // Find the last assistant message with an instruction_id
   const lastWithInstr = [...chatMessages].reverse().find(
     (m) => m.role === "assistant" && m.instruction_id && m.can_revise
   );
   if (lastWithInstr?.instruction_id) {
     // Route to revision
     setChatInput("");
     setChatLoading(true);
     setChatMessages((prev) => [...prev, { role: "user", content: msg }]);
     setChatMessages((prev) => [...prev, { role: "assistant", content: "正在根据你的修改意见修订资产包，请稍候..." }]);
     try {
       const res = await api.reviseInstruction(lastWithInstr.instruction_id, msg);
       setChatMessages((prev) => [...prev, {
         role: "assistant",
         content: `资产包已修订完成。你可以继续提出修改意见，或批准下发执行。`,
         instruction_id: res.instruction_id,
         asset: res.asset,
         can_revise: true,
       }]);
       load();
     } catch (err) {
       setChatMessages((prev) => [...prev, {
         role: "assistant",
         content: `修订失败：${(err as Error).message}。你可以重新描述修改意见，或直接批准当前版本。`,
         instruction_id: lastWithInstr.instruction_id,
         can_revise: true,
       }]);
     } finally {
       setChatLoading(false);
     }
     return;
   }
   // Normal flow: create new instruction
   sendChat();
 };
const chatGenerate = async (instructionId: string) => {
  setChatLoading(true);
  setChatMessages((prev) => [...prev, { role: "assistant", content: "正在生成资产包，请稍候..." }]);
  try {
    const res = await api.generateInstruction(instructionId);
     if (res.status === "generating") {
       setChatMessages((prev) => [...prev, { role: "assistant", content: "后台正在生成资产包，预计1-2分钟，完成后自动刷新指令列表..." }]);
       load();
       if (pollRef.current) clearInterval(pollRef.current);
       pollRef.current = setInterval(() => {
         api.platformInstructions()
           .then((newRows) => {
             setRows(newRows);
            const target = newRows.find((r) => r.id === instructionId);
            if (target && target.status !== "生成中") {
              if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
              const done = target.status === "已产出";
              setChatMessages((prev) => [...prev, {
                role: "assistant",
                content: done
                  ? `资产包已生成！下方展示完整内容，你可以直接提出修改意见（如"把预算改成3万"），满意后点批准。`
                  : `生成${target.status}，请重试或检查日志。`,
                instruction_id: done ? instructionId : undefined,
                asset: done ? target.asset : null,
                can_revise: done,
              }]);
              setChatLoading(false);
            }
          })
          .catch(() => undefined);
      }, 3000);
      return;
     }
     setChatMessages((prev) => [...prev, {
       role: "assistant",
       content: `资产包已生成！下方展示完整内容，你可以直接提出修改意见，满意后点批准。`,
       instruction_id: instructionId,
       can_revise: true,
     }]);
     // Load the asset for inline display
     api.platformInstructions().then((newRows) => {
       const target = newRows.find((r) => r.id === instructionId);
       if (target?.asset) {
         setChatMessages((prev) => prev.map((m, i) =>
           i === prev.length - 1 ? { ...m, asset: target.asset } : m
         ));
       }
     }).catch(() => undefined);
   } catch (err) {
     setChatMessages((prev) => [...prev, { role: "assistant", content: `生成失败：${(err as Error).message}` }]);
    } finally {
      setChatLoading(false);
      load();
    }
  };

  const adoptSuggestion = async (suggestion: FlywheelSuggestion) => {
    const title = suggestion.title
      .replace(/^(信号|需求|货盘匹配|策略建议)[：:]\s*/, "")
      .slice(0, 40);
    await api.createInstruction({
      title: title || suggestion.kind,
      content: suggestion.summary,
      industry_id: industryId || undefined,
      params: { ...EMPTY_PARAMS, ...suggestion.params },
    });
    setNotice(`已从“${suggestion.title}”创建指令，可继续生成资产包`);
    setTab("list");
    load();
  };

  const openAdvisoryDetail = (suggestion: FlywheelSuggestion) => {
    if (!advisories) return;
    const fields: { label: string; value: string }[] = [];
    if (suggestion.kind === "signal") {
      const row = advisories.signals.find((item) => item.id === suggestion.id);
      fields.push({ label: "信号原文", value: row?.raw_content || suggestion.summary });
      fields.push({ label: "来源", value: row?.source_type || "-" });
      fields.push({ label: "状态", value: row?.status || "-" });
      fields.push({
        label: "时间",
        value: row?.created_at ? new Date(row.created_at).toLocaleString() : "-",
      });
    } else if (suggestion.kind === "demand") {
      const row = advisories.demands.find((item) => `demand-${item.scenario}` === suggestion.id);
      fields.push({ label: "需求场景", value: row?.scenario || "-" });
      fields.push({ label: "标签", value: row?.tags.join("、") || "-" });
      fields.push({ label: "数量", value: String(row?.count ?? 0) });
      fields.push({ label: "强度", value: String(row?.intensity ?? 0) });
      fields.push({ label: "证据", value: row?.evidence || "-" });
    } else if (suggestion.kind === "match") {
      const row = advisories.matches.find((item) => `match-${item.product_name}` === suggestion.id);
      fields.push({ label: "需求场景", value: row?.demand_scenario || "-" });
      fields.push({ label: "需求标签", value: row?.demand_tags.join("、") || "-" });
      fields.push({ label: "匹配品项", value: row?.product_name || "-" });
      fields.push({ label: "分类", value: row?.product_category || "-" });
      fields.push({ label: "得分", value: String(row?.score ?? 0) });
      fields.push({ label: "匹配理由", value: (row?.reasons || []).join("、") || "-" });
    } else {
      const row = advisories.strategies.find((item) => item.id === suggestion.id);
      fields.push({ label: "策略类型", value: row?.strategy_type || "-" });
      fields.push({ label: "状态", value: row?.status || "-" });
      fields.push({ label: "托管", value: row?.managed ? "是" : "否" });
      fields.push({ label: "下次运行", value: row?.next_run_at || "-" });
      fields.push({ label: "效果分", value: row ? row.score.toFixed(2) : "-" });
      fields.push({ label: "执行/胜/反馈", value: row ? `${row.runs}/${row.wins}/${row.feedback_count}` : "-" });
      const paramText = Object.entries(suggestion.params)
        .filter(([, value]) => value)
        .map(([key, value]) => `${key}: ${value}`)
        .join("\n");
      fields.push({ label: "可转指令参数", value: paramText || "-" });
    }
    setAdvisoryDetail({ kind: suggestion.kind, title: suggestion.title, fields });
  };

 const action = async (id: string, kind: "generate" | "approve" | "reject") => {
    if (kind === "generate") {
      await api.generateInstruction(id);
      load();
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(() => {
        api
          .platformInstructions()
          .then((newRows) => {
            setRows(newRows);
            if (!newRows.some((r) => r.status === "生成中")) {
              if (pollRef.current) {
                clearInterval(pollRef.current);
                pollRef.current = null;
              }
            }
          })
          .catch(() => undefined);
      }, 3000);
      return;
    }
    if (kind === "approve") await api.approveInstruction(id);
    if (kind === "reject") await api.rejectInstruction(id);
    load();
  };

  const openAccept = (instruction: InstructionRow) => {
    setKpiDraft({});
    setAcceptTarget(instruction);
  };

  const confirmAccept = async () => {
    if (!acceptTarget) return;
    const results: Record<string, string | number> = {};
    for (const [key, value] of Object.entries(kpiDraft)) {
      const trimmed = value.trim();
      if (!trimmed) continue;
      results[key] = Number.isNaN(Number(trimmed)) ? trimmed : Number(trimmed);
    }
    await api.acceptInstruction(acceptTarget.id, { kpi_results: results });
    setAcceptTarget(null);
    load();
  };

 const exportExcel = async (id: string) => {
   if (!id) return;
   setExporting(true);
   try {
     await api.exportInstruction(id);
   } catch (e) {
     setError(e instanceof Error ? e.message : "导出失败");
   } finally {
     setExporting(false);
   }
 };

  const openBrief = async (instruction: { id: string; title: string }) => {
    setBriefTarget(instruction);
    setBriefCards([]);
    setBriefDraft({ card_name: "", market_price: "", selling_price: "", items: "", selling_point: "" });
    try {
      const res = await api.getCampaignBrief(instruction.id);
      setBriefCards(res.campaign_brief?.cards || []);
    } catch { /* no brief yet */ }
  };

  const addBriefCard = () => {
    if (!briefDraft.card_name.trim()) return;
    setBriefCards([...briefCards, { ...briefDraft }]);
    setBriefDraft({ card_name: "", market_price: "", selling_price: "", items: "", selling_point: "" });
  };

  const deleteBriefCard = (index: number) => {
    setBriefCards(briefCards.filter((_, i) => i !== index));
  };

  const saveBrief = async () => {
    if (!briefTarget) return;
    setBriefSaving(true);
    try {
      await api.saveCampaignBrief(briefTarget.id, { cards: briefCards });
      setBriefTarget(null);
      setNotice("品牌素材已保存，生成资产包时将优先使用");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBriefSaving(false);
    }
  };

  const uploadBriefFile = async (file: File) => {
    if (!briefTarget) return;
    try {
      const res = await api.uploadCampaignBrief(briefTarget.id, file);
      if (res.cards) setBriefCards(res.cards);
      setNotice(`已从 ${res.count || 0} 行导入品牌素材`);
    } catch (e) {
    setError(e instanceof Error ? e.message : "上传失败");
   }
 };

  const handleBriefUpload = async (file: File) => {
    try {
      const res = await api.parseCampaignBrief(file);
      if (res.cards) setAttachedBrief(res.cards);
      setNotice(`已附 ${res.count || 0} 个品牌卡项，发送指令时将作为优先数据`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "解析失败");
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>指令中心</h1>
          <p>当前行业：{currentIndustry?.name || "未选择"} · 按 12 个维度下发运营指令</p>
        </div>
        {error && <span className="error-text">{error}</span>}
      </header>

      <div className="sub-tabs">
        {[
          { key: "advice" as const, label: `飞轮洞察建议${advisories?.suggestions?.length ? ` (${advisories.suggestions.length})` : ""}` },
         { key: "new" as const, label: "对话发指令" },
          { key: "list" as const, label: `指令列表${rows.length ? ` (${rows.length})` : ""}` },
        ].map((item) => (
          <button
            type="button"
            key={item.key}
            className={`sub-tab ${tab === item.key ? "active" : ""}`}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {notice && <span className="success-text">{notice}</span>}

      {tab === "advice" && (
      <section className="panel">
        <div className="panel-head">
          <h2>飞轮洞察建议</h2>
          <span className="cell-muted">先洞察、后发指令，建议会自动带入人群/货盘/活动上下文</span>
        </div>
        <div className="advisory-grid">
          {(advisories?.suggestions || []).map((suggestion) => (
            <div key={suggestion.id} className="advisory-card">
              <div className="tag-row">
                <span className={`pill ${suggestion.kind}`}>
                  {{ signal: "信号", demand: "需求", match: "货盘", strategy: "策略" }[suggestion.kind]}
                </span>
              </div>
              <button type="button" className="advisory-open" onClick={() => openAdvisoryDetail(suggestion)}>
                <span className="cell-main">{suggestion.title}</span>
                <span className="cell-muted advisory-summary">{suggestion.summary}</span>
              </button>
              <div className="tag-row">
                <button type="button" className="btn small" onClick={() => openAdvisoryDetail(suggestion)}>
                  查看详情
                </button>
                <WriteGate>
                  <button type="button" className="btn small" onClick={() => adoptSuggestion(suggestion)}>
                    转为指令
                  </button>
                </WriteGate>
              </div>
            </div>
          ))}
          {(!advisories || advisories.suggestions.length === 0) && (
            <div className="empty">还没有飞轮建议，先让系统采集信号和热点</div>
          )}
        </div>
      </section>
      )}

      {tab === "new" && (
      <section className="panel chat-panel">
        <div className="panel-head">
          <h2>对话发指令</h2>
          <span className="cell-muted">用自然语言描述运营需求，系统自动解析为结构化指令</span>
        </div>
        <div className="chat-body">
          {chatMessages.length === 0 && (
           <div className="chat-empty">
              <p>选择场景快速开始，或直接在下方输入你的运营需求：</p>
             <div className="chat-suggestions">
                {(EXAMPLE_TEMPLATES[currentIndustry?.code || "beauty"] || EXAMPLE_TEMPLATES.beauty).map((tpl) => (
                  <button key={tpl.category} type="button" className="chip chip-categorized" onClick={() => setChatInput(tpl.text)}>
                    <span className="chip-cat">{tpl.category}</span>
                  </button>
                ))}
             </div>
           </div>
          )}
        {chatMessages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            <div className="chat-bubble">
              {msg.content.split("\n").map((line, j) => (
                <p key={j}>{line}</p>
              ))}
              {msg.asset && (
                <div className="chat-asset-inline" style={{ marginTop: 12, maxWidth: "100%", overflow: "auto", borderTop: "1px solid rgba(0,0,0,0.06)", paddingTop: 12 }}>
                  <AssetView asset={msg.asset} />
                </div>
              )}
              {msg.can_revise && msg.role === "assistant" && (
                <div className="revise-hint" style={{ marginTop: 8, padding: "6px 10px", background: "rgba(99,102,241,0.08)", borderRadius: 6, fontSize: 12, color: "#6366f1" }}>
                  在下方输入框输入修改意见（如"把预算改成3万"、"增加社群活动"），系统会重新修订资产包
                </div>
              )}
              {msg.instruction_id && msg.role === "assistant" && (
                <div className="chat-actions">
                 <WriteGate>
                   {!msg.can_revise && (
                     <button type="button" className="btn small primary" onClick={() => chatGenerate(msg.instruction_id!)}>
                       <Play size={14} />
                       生成资产包
                     </button>
                   )}
                   {msg.can_revise && (
                     <button type="button" className="btn small primary" onClick={() => action(msg.instruction_id!, "approve")}>
                       <CheckCircle2 size={14} />
                       批准下发
                     </button>
                   )}
                 </WriteGate>
                 {msg.can_revise && (
                   <button type="button" className="btn small" onClick={() => {
                     setAssetInstructionId(msg.instruction_id!);
                     setAsset(msg.asset || null);
                     setTab("list");
                   }}>
                     查看指令列表
                   </button>
                 )}
                 {!msg.can_revise && (
                   <button type="button" className="btn small" onClick={() => setTab("list")}>
                     查看指令列表
                   </button>
                 )}
                </div>
              )}
            </div>
          </div>
        ))}

          {chatLoading && (
            <div className="chat-msg assistant">
              <div className="chat-bubble typing">思考中...</div>
            </div>
          )}
        </div>
       <div className="chat-input-bar">
          {attachedBrief.length > 0 && (
            <div className="brief-chip-row">
              <span className="brief-chip">
                <Package size={13} />
                已附 {attachedBrief.length} 个品牌卡项
                <button type="button" onClick={() => setAttachedBrief([])} className="brief-chip-clear">
                  <X size={13} />
                </button>
              </span>
            </div>
          )}
          <WriteGate>
            <label className="btn small" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
              <Upload size={16} />
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleBriefUpload(f);
                  e.target.value = "";
                }}
              />
            </label>
            <textarea
              className="chat-input"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
             onKeyDown={(e) => {
               if (e.key === "Enter" && !e.shiftKey) {
                 e.preventDefault();
                 sendChatOrRevise();
               }
             }}
            placeholder={
              pendingClarification
                ? "补充缺失信息后发送，系统会自动合并到原始指令... (Enter 发送)"
              : chatMessages.some((m) => m.can_revise)
                ? "输入修改意见（如：把预算改成3万、增加社群活动），或直接批准 →  (Enter 发送)"
                : "描述你的运营需求... (Enter 发送, Shift+Enter 换行)"
            }
             rows={2}
           />
           <button type="button" className="btn primary" onClick={sendChatOrRevise} disabled={chatLoading || !chatInput.trim()}>
             发送
           </button>
          </WriteGate>
        </div>
      </section>
      )}

      {tab === "list" && (
      <section className="panel">
        <div className="panel-head">
          <h2>指令列表</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>指令</th>
                <th>状态</th>
                <th>时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((instruction) => (
                <tr key={instruction.id}>
                  <td className="cell-main">{instruction.title}</td>
                  <td>
                    <span className={`pill ${instruction.status}`}>{instruction.status}</span>
                  </td>
                  <td className="cell-muted">
                    {instruction.created_at ? new Date(instruction.created_at).toLocaleString() : "-"}
                  </td>
                  <td>
                    <div className="tag-row">
                     {instruction.status === "待处理" && (
                       <WriteGate>
                         <button type="button" className="btn small" onClick={() => action(instruction.id, "generate")}>
                           <Play size={14} />
                           生成策略
                         </button>
                       </WriteGate>
                     )}
                      {instruction.status === "生成中" && (
                        <span className="pill" style={{ color: "#f59e0b" }}>⏳ 生成中...</span>
                      )}
                      {instruction.status === "生成失败" && (
                        <>
                          <span className="pill" style={{ color: "#ef4444" }}>生成失败</span>
                          <WriteGate>
                            <button type="button" className="btn small" onClick={() => action(instruction.id, "generate")}>
                              <Play size={14} />
                              重试
                            </button>
                          </WriteGate>
                        </>
                      )}
                     {instruction.status === "已产出" && (
                        <>
                          <WriteGate>
                            <button type="button" className="btn small" onClick={() => action(instruction.id, "approve")}>
                              批准
                            </button>
                            <button type="button" className="btn small" onClick={() => action(instruction.id, "reject")}>
                              驳回
                            </button>
                          </WriteGate>
                        </>
                      )}
                      {instruction.status === "已批准" && (
                        <WriteGate>
                          <button type="button" className="btn small" onClick={() => openAccept(instruction)}>
                            <CheckCircle2 size={14} />
                            验收
                          </button>
                        </WriteGate>
                      )}
                    <WriteGate>
                      <button type="button" className="btn small" onClick={() => openBrief(instruction)}>
                        <Package size={14} />
                        品牌素材
                      </button>
                    </WriteGate>
                    {instruction.asset && (
                       <>
                        <button
                          type="button"
                          className="btn small"
                          onClick={() => {
                            setAssetInstructionId(instruction.id);
                            setAsset(instruction.asset);
                          }}
                        >
                         查看资产包
                       </button>
                        <button
                          type="button"
                          className="btn small"
                          disabled={exporting}
                          onClick={() => exportExcel(instruction.id)}
                        >
                          <Download size={14} />
                          导出 Excel
                        </button>
                       </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="empty">
                    暂无指令
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      )}

      {asset && (
        <div className="asset-overlay">
          <div className="asset-overlay-head">
            <h2>策略资产包</h2>
            <div className="asset-overlay-actions">
              <button
                type="button"
                className="btn small"
                disabled={exporting || !assetInstructionId}
                onClick={() => exportExcel(assetInstructionId)}
              >
                <Download size={14} />
                {exporting ? "导出中…" : "导出 Excel"}
              </button>
              <button type="button" className="btn" onClick={() => setAsset(null)}>
                <X size={15} />
                关闭
              </button>
            </div>
          </div>
          <div className="asset-overlay-body">
            <AssetView asset={asset} />
          </div>
        </div>
      )}

      {acceptTarget && (
        <div className="asset-overlay">
          <div className="asset-overlay-head">
            <h2>验收回填 · {acceptTarget.title}</h2>
            <button type="button" className="btn" onClick={() => setAcceptTarget(null)}>
              <X size={15} />
              关闭
            </button>
          </div>
          <div className="asset-overlay-body">
            <section className="panel">
              <div className="panel-head">
                <h2>KPI 实际结果</h2>
                <span className="cell-muted">填写后生成验收报告，自动计算达成率</span>
              </div>
              <div className="form-grid">
                {(acceptTarget.asset?.kpi_targets || []).map((metric) => (
                  <label className="field" key={metric}>
                    <span>{metric}</span>
                    <input
                      value={kpiDraft[metric] || ""}
                      onChange={(event) => setKpiDraft({ ...kpiDraft, [metric]: event.target.value })}
                      placeholder="如 300000 或 12%"
                    />
                  </label>
                ))}
                {(acceptTarget.asset?.kpi_targets || []).length === 0 && (
                  <p className="cell-muted">该指令未设置 KPI 指标</p>
                )}
              </div>
              <div className="overlay-actions">
                <button type="button" className="btn primary" onClick={confirmAccept}>
                  <CheckCircle2 size={15} />
                  确认验收
                </button>
              </div>
            </section>
          </div>
        </div>
      )}

      {advisoryDetail && (
        <div className="asset-overlay">
          <div className="asset-overlay-head">
            <h2>{advisoryDetail.title}</h2>
            <button type="button" className="btn" onClick={() => setAdvisoryDetail(null)}>
              <X size={15} />
              关闭
            </button>
          </div>
          <div className="asset-overlay-body">
            <div className="asset-package">
              <div className="detail-fields">
                {advisoryDetail.fields.map((field) => (
                  <div key={field.label} className="detail-field">
                    <span className="detail-label">{field.label}</span>
                    <pre className="cell-text">{field.value}</pre>
                  </div>
                ))}
              </div>
            </div>
          </div>
       </div>
     )}
      {briefTarget && (
        <div className="asset-overlay">
          <div className="asset-overlay-head">
            <h2>品牌素材 · {briefTarget.title}</h2>
            <button type="button" className="btn" onClick={() => setBriefTarget(null)}>
              <X size={15} />
              关闭
            </button>
          </div>
          <div className="asset-overlay-body">
            <section className="panel">
              <div className="panel-head">
                <h2>上传卡项表</h2>
                <span className="cell-muted">支持 xlsx / csv，列名建议：卡名、门市价、售价、包含项目、卖点</span>
              </div>
              <WriteGate>
                <label className="btn small" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <Upload size={14} />
                  选择文件上传
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) uploadBriefFile(f);
                      e.target.value = "";
                    }}
                  />
                </label>
              </WriteGate>
            </section>

            <section className="panel" style={{ marginTop: 16 }}>
              <div className="panel-head">
                <h2>手动添加卡项</h2>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>卡名</span>
                  <input value={briefDraft.card_name} onChange={(e) => setBriefDraft({ ...briefDraft, card_name: e.target.value })} placeholder="如：秋季补水3次卡" />
                </label>
                <label className="field">
                  <span>门市价</span>
                  <input value={briefDraft.market_price} onChange={(e) => setBriefDraft({ ...briefDraft, market_price: e.target.value })} placeholder="如：2320" />
                </label>
                <label className="field">
                  <span>售价</span>
                  <input value={briefDraft.selling_price} onChange={(e) => setBriefDraft({ ...briefDraft, selling_price: e.target.value })} placeholder="如：599" />
                </label>
                <label className="field" style={{ gridColumn: "1 / -1" }}>
                  <span>包含项目</span>
                  <input value={briefDraft.items} onChange={(e) => setBriefDraft({ ...briefDraft, items: e.target.value })} placeholder="如：980水动力1次+680肩颈1次+660面部1次" />
                </label>
                <label className="field" style={{ gridColumn: "1 / -1" }}>
                  <span>卖点</span>
                  <input value={briefDraft.selling_point} onChange={(e) => setBriefDraft({ ...briefDraft, selling_point: e.target.value })} placeholder="如：限时秋季补水，门市价7.3折" />
                </label>
              </div>
              <div style={{ marginTop: 8 }}>
                <WriteGate>
                  <button type="button" className="btn small primary" onClick={addBriefCard} disabled={!briefDraft.card_name.trim()}>
                    添加卡项
                  </button>
                </WriteGate>
              </div>
            </section>

            {briefCards.length > 0 && (
              <section className="panel" style={{ marginTop: 16 }}>
                <div className="panel-head">
                  <h2>已添加卡项 ({briefCards.length})</h2>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>卡名</th>
                        <th>门市价</th>
                        <th>售价</th>
                        <th>包含项目</th>
                        <th>卖点</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {briefCards.map((card: any, i: number) => (
                        <tr key={i}>
                          <td className="cell-main">{card.card_name || card.卡名 || card.名称 || "-"}</td>
                          <td>{card.market_price || card.门市价 || card.原价 || "-"}</td>
                          <td>{card.selling_price || card.售价 || card.定价 || "-"}</td>
                          <td>{card.items || card.包含项目 || card.项目 || "-"}</td>
                          <td>{card.selling_point || card.卖点 || "-"}</td>
                          <td>
                            <WriteGate>
                              <button type="button" className="btn small" onClick={() => deleteBriefCard(i)}>
                                <X size={14} />
                              </button>
                            </WriteGate>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <div className="overlay-actions" style={{ marginTop: 16 }}>
              <WriteGate>
                <button type="button" className="btn primary" onClick={saveBrief} disabled={briefSaving}>
                  {briefSaving ? "保存中…" : "保存品牌素材"}
                </button>
              </WriteGate>
              <button type="button" className="btn" onClick={() => setBriefTarget(null)}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
