path = "database.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_func = """
def get_user_progress(user_id):
    import sqlite3
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    rows = []
    try:
        # Mencari otomatis nama tabel riwayat yang Anda gunakan
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        
        for table in tables:
            if table != "sqlite_sequence": 
                try:
                    cursor.execute(f"SELECT subject, COUNT(*), MAX(timestamp) FROM {table} WHERE user_id = ? GROUP BY subject", (user_id,))
                    rows = cursor.fetchall()
                    if rows: 
                        break
                except Exception:
                    pass
    except Exception as e:
        pass
    finally:
        conn.close()
    return rows
"""

if "def get_user_progress" in content:
    start = content.find("def get_user_progress")
    end = content.find("def ", start + 20)
    if end == -1: end = len(content)
    content = content[:start] + new_func.strip() + "\n\n" + content[end:]
else:
    content += "\n\n" + new_func.strip() + "\n"

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("database.py berhasil diperbarui dengan aman!")
