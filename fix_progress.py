path = "database.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_func_marker = "def get_user_progress(user_id):"
start = content.find(old_func_marker)

new_func = """def get_user_progress(user_id):
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = (
            db.query(
                ConversationModel.subject,
                func.count(ConversationModel.id),
                func.max(ConversationModel.timestamp)
            )
            .filter(ConversationModel.user_id == str(user_id), ConversationModel.role == "user")
            .group_by(ConversationModel.subject)
            .all()
        )
        return rows
    except Exception as e:
        print(f"Error laporan: {e}")
        return []
    finally:
        db.close()
"""

if start != -1:
    content = content[:start] + new_func
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("database.py berhasil diselaraskan dengan SQLAlchemy!")
else:
    print("Fungsi tidak ditemukan.")
