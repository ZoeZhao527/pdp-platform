from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth import require_roles
from app.api.deps import Runtime, get_runtime
from app.knowledge.service import KnowledgeService, parse_text_file
from app.models import KnowledgeDoc

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.post("/documents")
def upload_document(
    file: UploadFile = File(...),
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    data = file.file.read()
    name = file.filename or "未命名.txt"
    file_type = name.rsplit(".", 1)[-1].lower() if "." in name else "txt"
    try:
        content = parse_text_file(name, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    service = KnowledgeService(runtime.db)
    doc = service.ingest(
        runtime.tenant_id,
        name,
        content,
        file_type,
        len(data),
        industry_id=runtime.industry_id,
    )
    return {"id": doc.id, "name": doc.name, "status": doc.status, "chunk_count": doc.chunk_count}


@router.get("/documents")
def list_documents(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = runtime.db.query(KnowledgeDoc).filter(
        KnowledgeDoc.tenant_id == runtime.tenant_id,
        KnowledgeDoc.industry_id == runtime.industry_id,
    ).order_by(KnowledgeDoc.created_at.desc()).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "file_type": row.file_type,
            "status": row.status,
            "chunk_count": row.chunk_count,
            "size_bytes": row.size_bytes,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    ok = KnowledgeService(runtime.db).delete(runtime.tenant_id, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"ok": True}


@router.get("/search")
def search_knowledge(
    q: str,
    top_k: int = 5,
    runtime: Runtime = Depends(get_runtime),
) -> list[dict]:
    results = KnowledgeService(runtime.db).search(
        runtime.tenant_id, q, top_k=top_k, industry_id=runtime.industry_id
    )
    return results
