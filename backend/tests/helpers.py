import hashlib

async def make_document(conn, loan_file_id: str, text: str, filename: str = "doc.txt"):
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    doc_id = await conn.fetchval(
        """INSERT INTO documents (loan_file_id, file_path, raw_text, content_hash)
           VALUES ($1, $2, $3, $4) RETURNING document_id""",
        loan_file_id, filename, text, content_hash,
    )
    return str(doc_id)