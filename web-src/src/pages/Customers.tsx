import { useEffect, useState } from "react";

import { api } from "../api";
import type { CustomerProfile } from "../types";

export default function Customers() {
  const [customers, setCustomers] = useState<CustomerProfile[]>([]);
  const [selected, setSelected] = useState<CustomerProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .customers()
      .then(setCustomers)
      .catch((err: Error) => setError(err.message));
  }, []);

  const open = async (customer: CustomerProfile) => {
    setSelected(await api.customerProfile(customer.id));
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>客户画像</h1>
          <p>会话与需求信号自动沉淀标签，画像反哺 Agent 上下文</p>
        </div>
        {error && <span className="error-text">{error}</span>}
      </header>

      <div className="split-grid">
        <section className="panel">
          <div className="panel-head">
            <h2>客户列表</h2>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>OneID</th>
                  <th>标签</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.id} onClick={() => open(customer)} className="clickable-row">
                    <td className="cell-main">{customer.name || customer.one_id}</td>
                    <td>
                      <div className="tag-row">
                        {((customer.profile as { tags?: string[] })?.tags ?? []).slice(0, 5).map((tag) => (
                          <span key={tag} className="tag">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="cell-muted">
                      {customer.created_at ? new Date(customer.created_at).toLocaleString() : "-"}
                    </td>
                  </tr>
                ))}
                {customers.length === 0 && (
                  <tr>
                    <td colSpan={3} className="empty">
                      暂无客户，先在会话页模拟一条客户消息
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>画像详情</h2>
          </div>
          {selected ? (
            <pre className="json-pre">{JSON.stringify(selected.profile, null, 2)}</pre>
          ) : (
            <div className="empty">选择左侧客户查看画像</div>
          )}
        </section>
      </div>
    </div>
  );
}

