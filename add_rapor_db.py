path = "database.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_db_func = """
def get_all_recent_messages(user_id, limit=20):
    db = SessionLocal()
    try:
        rows = (
            db.query(ConversationModel.subject, ConversationModel.role, ConversationModel.message)
            .filter(ConversationModel.user_id == str(user_id))
            .order_by(ConversationModel.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [{"subject": subject, "role": role, "content": message} for subject, role, message in rows]
    finally:
        db.close()
"""

if "def get_all_recent_messages" not in content:
    content += "\n" + new_db_func
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fungsi get_all_recent_messages berhasil ditambahkan ke database.py!")
else:
    print("Fungsi get_all_recent_messages sudah ada.")
