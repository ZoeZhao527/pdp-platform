import StrategyCenter from "../components/StrategyCenter";

export default function Strategies() {
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>策略沉淀中心</h1>
          <p>把验证过、可复用的打法沉淀成策略卡，供飞轮建议与整月排期复用</p>
        </div>
      </header>
      <StrategyCenter />
    </div>
  );
}
