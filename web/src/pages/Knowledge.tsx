import { Search, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { WriteGate } from "../components/WriteGate";
import type { KnowledgeDoc, KnowledgeHit } from "../types";

export default function Knowledge() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<KnowledgeHit[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .knowledgeDocs()
      .then(setDocs)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setError("");
    setMessage("");
    try {
      const result = await api.uploadKnowledge(file);
      setMessage(`已导入 ${result.name}，生成 ${result.chunk_count} 个切片`);
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const search = async () => {
    if (!query.trim()) return;
    try {
      setHits(await api.knowledgeSearch(query.trim()));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const remove = async (id: string) => {
    await api.deleteKnowledge(id);
    load();
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>知识库</h1>
          <p>上传私域话术、商品与政策文档，自动切片入库供 Agent 检索</p>
        </div>
      </header>

      <WriteGate>
        <div className="upload-bar">
          <input
            type="file"
            accept=".txt,.md,.csv,.json"
            className="file-input"
            onChange={(event) => upload(event.target.files?.[0])}
          />
          <button type="button" className="btn primary">
            <Upload size={15} />
            上传文档
          </button>
        </div>
      </WriteGate>
      {message && <span className="success-text">{message}</span>}
      {error && <span className="error-text">{error}</span>}

      <div className="split-grid">
        <section className="panel">
          <div className="panel-head">
            <h2>文档</h2>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>名称</th>
                  <th>状态</th>
                  <th>切片</th>
                  <th>大小</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <tr key={doc.id}>
                    <td className="cell-main">{doc.name}</td>
                    <td>
                      <span className={`pill ${doc.status}`}>{doc.status}</span>
                    </td>
                    <td>{doc.chunk_count}</td>
                    <td className="cell-muted">{(doc.size_bytes / 1024).toFixed(1)} KB</td>
                    <td>
                      <WriteGate>
                        <button
                          type="button"
                          className="icon-btn ghost"
                          onClick={() => remove(doc.id)}
                          aria-label="删除文档"
                        >
                          <Trash2 size={15} />
                        </button>
                      </WriteGate>
                    </td>
                  </tr>
                ))}
                {docs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="empty">
                      暂无文档
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>检索测试</h2>
          </div>
          <div className="simulate-bar">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && search()}
              placeholder="输入问题测试 RAG 检索"
            />
            <button type="button" className="btn primary icon-btn" onClick={search} aria-label="检索">
              <Search size={15} />
            </button>
          </div>
          <div className="hit-list compact">
            {hits.map((hit) => (
              <div key={hit.id} className="hit-item">
                <div className="hit-head">
                  <span className="tag">score {hit.score}</span>
                </div>
                <p>{hit.content}</p>
              </div>
            ))}
            {hits.length === 0 && query && <div className="empty">没有匹配结果</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
