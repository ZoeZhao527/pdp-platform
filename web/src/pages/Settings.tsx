import { useEffect, useState } from "react";

import { api } from "../api";
import { currentRole, WriteGate } from "../components/WriteGate";
import type { Agent, AuthUser, Channel, FeishuConfigRow, TenantRow } from "../types";

export default function Settings() {
  const isAdmin = currentRole() === "admin";
  const [channels, setChannels] = useState<Channel[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [passwordForm, setPasswordForm] = useState({ old_password: "", new_password: "" });
  const [userForm, setUserForm] = useState({ username: "", password: "", display_name: "", role: "operator" });
  const [channelDrafts, setChannelDrafts] = useState<Record<string, { name: string; enabled: boolean; config: string }>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [feishuConfig, setFeishuConfig] = useState<FeishuConfigRow>({
    app_id: "",
    app_secret: "",
    chat_id: "",
    verification_token: "",
    encrypt_key: "",
    enabled: false,
    messaging_enabled: false,
    configured: false,
  });

  useEffect(() => {
    Promise.all([api.channels(), api.agents(), api.platformTenants()])
      .then(([channelRows, agentRows, tenantRows]) => {
        setChannels(channelRows);
        setAgents(agentRows);
        setTenants(tenantRows);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    api
      .authUsers()
      .then(setUsers)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    api.feishuConfig().then(setFeishuConfig).catch(() => undefined);
  }, []);

  const changePassword = async () => {
    setMessage("");
    await api.changePassword(passwordForm.old_password, passwordForm.new_password);
    setMessage("密码已修改");
    setPasswordForm({ old_password: "", new_password: "" });
  };

  const addUser = async () => {
    setMessage("");
    await api.createAuthUser(userForm);
    setUsers(await api.authUsers());
    setUserForm({ username: "", password: "", display_name: "", role: "operator" });
    setMessage("账号已创建");
  };

  const saveFeishuConfig = async () => {
    setMessage("");
    try {
      await api.updateFeishuConfig(feishuConfig);
      const updated = await api.feishuConfig();
      setFeishuConfig(updated);
      setMessage("飞书配置已保存");
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  const testFeishu = async () => {
    setMessage("");
    try {
      const result = await api.testFeishu();
      setMessage(result.ok ? `连接成功：${result.detail}` : `连接失败：${result.detail}`);
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  const channelDraft = (channel: Channel) =>
    channelDrafts[channel.id] || {
      name: channel.name,
      enabled: channel.enabled,
      config: JSON.stringify(channel.config || {}, null, 2),
    };

  const saveChannel = async (channel: Channel) => {
    const draft = channelDraft(channel);
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(draft.config || "{}");
    } catch {
      setError("渠道配置 JSON 格式不正确");
      return;
    }
    await api.updateChannel(channel.id, { name: draft.name, enabled: draft.enabled, config });
    setChannels(await api.channels());
    setMessage("渠道配置已保存");
  };

  const testChannel = async (channel: Channel) => {
    const result = await api.testChannel(channel.id);
    setMessage(result.ok ? `渠道测试成功：${result.message_id || result.detail}` : `渠道测试失败：${result.detail}`);
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>平台配置</h1>
          <p>渠道接入与业务 Agent 目录</p>
        </div>
        {error && <span className="error-text">{error}</span>}
      </header>

      <section className="panel">
        <div className="panel-head">
          <h2>渠道</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>类型</th>
                <th>状态</th>
                <th>配置（JSON）</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {channels.map((channel) => (
                <ChannelRow
                  key={channel.id}
                  channel={channel}
                  draft={channelDraft(channel)}
                  onChange={(draft) => setChannelDrafts({ ...channelDrafts, [channel.id]: draft })}
                  onSave={() => saveChannel(channel)}
                  onTest={() => testChannel(channel)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>飞书接入</h2>
          <span className="cell-muted">每个品牌独立配置</span>
        </div>
        {message && <span className="success-text">{message}</span>}
        <div className="form-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
          <label className="form-label">
            App ID
            <input
              value={feishuConfig.app_id}
              onChange={(e) => setFeishuConfig({ ...feishuConfig, app_id: e.target.value })}
              placeholder="cli_xxxxxxxxx"
            />
          </label>
          <label className="form-label">
            App Secret
            <input
              type="password"
              value={feishuConfig.app_secret}
              onChange={(e) => setFeishuConfig({ ...feishuConfig, app_secret: e.target.value })}
              placeholder={feishuConfig.configured ? "****（已配置，留空不修改）" : "飞书应用密钥"}
            />
          </label>
          <label className="form-label">
            群聊 Chat ID
            <input
              value={feishuConfig.chat_id}
              onChange={(e) => setFeishuConfig({ ...feishuConfig, chat_id: e.target.value })}
              placeholder="oc_xxxxxxxxx"
            />
          </label>
          <label className="form-label">
            Verification Token
            <input
              value={feishuConfig.verification_token}
              onChange={(e) => setFeishuConfig({ ...feishuConfig, verification_token: e.target.value })}
              placeholder="事件订阅验证令牌"
            />
          </label>
          <label className="form-label">
            Encrypt Key
            <input
              value={feishuConfig.encrypt_key}
              onChange={(e) => setFeishuConfig({ ...feishuConfig, encrypt_key: e.target.value })}
              placeholder="事件订阅加密密钥（可选）"
            />
          </label>
          <div className="form-label" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            开关
            <label className="check-chip">
              <input
                type="checkbox"
                checked={feishuConfig.enabled}
                onChange={(e) => setFeishuConfig({ ...feishuConfig, enabled: e.target.checked })}
              />
              启用接入
            </label>
            <label className="check-chip">
              <input
                type="checkbox"
                checked={feishuConfig.messaging_enabled}
                onChange={(e) => setFeishuConfig({ ...feishuConfig, messaging_enabled: e.target.checked })}
              />
              允许发消息（早九晚六定时简报）
            </label>
          </div>
        </div>
        <div className="tag-row" style={{ marginTop: 12 }}>
          <WriteGate>
            <button type="button" className="btn small" onClick={testFeishu}>
              测试连接
            </button>
            <button type="button" className="btn primary small" onClick={saveFeishuConfig}>
              保存配置
            </button>
          </WriteGate>
        </div>
        {!feishuConfig.messaging_enabled && (
          <p className="cell-muted" style={{ marginTop: 8, fontSize: 13 }}>
            消息发送默认关闭，等你说可以发的时候再开启。
          </p>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>账号与安全</h2>
        </div>
        {message && <span className="success-text">{message}</span>}
        <div className="simulate-bar">
          <input
            type="password"
            value={passwordForm.old_password}
            onChange={(event) => setPasswordForm({ ...passwordForm, old_password: event.target.value })}
            placeholder="原密码"
          />
          <input
            type="password"
            value={passwordForm.new_password}
            onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })}
            placeholder="新密码"
          />
          <button type="button" className="btn primary" onClick={changePassword}>
            修改密码
          </button>
        </div>
        <div className="simulate-bar" style={{ marginTop: 12 }}>
          <input value={userForm.username} onChange={(event) => setUserForm({ ...userForm, username: event.target.value })} placeholder="新账号用户名" />
          <input value={userForm.password} onChange={(event) => setUserForm({ ...userForm, password: event.target.value })} placeholder="密码" />
          <input value={userForm.display_name} onChange={(event) => setUserForm({ ...userForm, display_name: event.target.value })} placeholder="姓名" />
          <select className="task-status-select" value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value })}>
            <option value="operator">运营</option>
            <option value="viewer">查看</option>
            <option value="admin">管理员</option>
          </select>
          {isAdmin && (
            <button type="button" className="btn primary" onClick={addUser}>
              创建账号
            </button>
          )}
        </div>
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                <th>用户名</th>
                <th>姓名</th>
                <th>角色</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td className="cell-main">{user.username}</td>
                  <td>{user.display_name || "-"}</td>
                  <td>{user.role}</td>
                  <td>{user.enabled ? "启用" : "停用"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>中台架构</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>层级</th>
                <th>名称</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>L5</td>
                <td>业务应用层：需求飞轮工作台/信号/需求/供给/匹配/策略/驾驶舱/汇报</td>
                <td>
                  <span className="pill done">已建</span>
                </td>
              </tr>
              <tr>
                <td>L4</td>
                <td>Agent 中台核心层：编排/LLM 网关/记忆/知识库/工具/护栏</td>
                <td>
                  <span className="pill done">已建</span>
                </td>
              </tr>
              <tr>
                <td>L3</td>
                <td>数据层：需求库/画像/品项/热点/KPI</td>
                <td>
                  <span className="pill done">已建</span>
                </td>
              </tr>
              <tr>
                <td>L2</td>
                <td>渠道接入网关：企微/微信客服/开放接口</td>
                <td>
                  <span className="pill pending">待增强</span>
                </td>
              </tr>
              <tr>
                <td>L1</td>
                <td>平台支撑：多租户/告警/审计/护栏</td>
                <td>
                  <span className="pill pending">部分已建</span>
                </td>
              </tr>
              <tr>
                <td>L0</td>
                <td>基础设施：云/容器/消息/向量库/域名</td>
                <td>
                  <span className="pill pending">待建</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>客户租户</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>编码</th>
                <th>ID</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((tenant) => (
                <tr key={tenant.id}>
                  <td className="cell-main">{tenant.name}</td>
                  <td>{tenant.code}</td>
                  <td className="cell-muted">{tenant.id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Agent 目录</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>名称</th>
                <th>说明</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.key}>
                  <td className="cell-main">{agent.key}</td>
                  <td>{agent.name}</td>
                  <td className="cell-muted">{agent.description}</td>
                  <td>{agent.enabled ? "启用" : "停用"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ChannelRow({
  channel,
  draft,
  onChange,
  onSave,
  onTest,
}: {
  channel: Channel;
  draft: { name: string; enabled: boolean; config: string };
  onChange: (draft: { name: string; enabled: boolean; config: string }) => void;
  onSave: () => void;
  onTest: () => void;
}) {
  return (
    <tr>
      <td>
        <input
          className="channel-name-input"
          value={draft.name}
          onChange={(event) => onChange({ ...draft, name: event.target.value })}
        />
      </td>
      <td>{channel.channel_type}</td>
      <td>
        <label className="check-chip">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => onChange({ ...draft, enabled: event.target.checked })}
          />
          {draft.enabled ? "启用" : "停用"}
        </label>
      </td>
      <td>
        <textarea
          className="channel-config-input"
          rows={3}
          value={draft.config}
          onChange={(event) => onChange({ ...draft, config: event.target.value })}
        />
      </td>
      <td>
        <div className="tag-row">
          <WriteGate>
            <button type="button" className="btn small" onClick={onTest}>
              测试
            </button>
            <button type="button" className="btn small" onClick={onSave}>
              保存
            </button>
          </WriteGate>
        </div>
      </td>
    </tr>
  );
}
