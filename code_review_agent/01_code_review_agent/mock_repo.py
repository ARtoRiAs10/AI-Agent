"""
Mock 'repository' backing the get_file_content / get_file_blame_summary /
search_repo tools, so the agent is runnable without real GitHub credentials.
Swap these functions for real GitHub API calls (PyGithub / REST) in production:
  - get_file_content -> GET /repos/{owner}/{repo}/contents/{path}
  - get_blame_summary -> GET /repos/{owner}/{repo}/commits?path=...
  - search_repo -> GET /search/code?q=...
"""

_FILES = {
    "app/auth/login.py": '''
import hashlib

def check_password(user, password):
    stored = get_stored_hash(user)
    return hashlib.md5(password.encode()).hexdigest() == stored

def get_stored_hash(user):
    # looked up from db
    return db.users.find_one({"name": user})["password_hash"]
''',
    "app/api/orders.py": '''
def get_order(order_id):
    query = "SELECT * FROM orders WHERE id = " + order_id
    return db.execute(query)
''',
    "app/utils/strings.py": '''
def slugify(text):
    return text.lower().replace(" ", "-")
''',
}

_BLAME = {
    "app/auth/login.py": "Last touched 3 times in 90 days by 2 authors. Considered security-critical.",
    "app/api/orders.py": "Frequently modified file, 5 authors in 30 days. High churn.",
    "app/utils/strings.py": "Stable utility file, unchanged for 8 months.",
}


def get_file_content(path: str) -> str:
    return _FILES.get(path, f"[mock repo] No content found for {path}")


def get_blame_summary(path: str) -> str:
    return _BLAME.get(path, f"[mock repo] No history found for {path}")


def search_repo(query: str) -> str:
    hits = [p for p, content in _FILES.items() if query.lower() in content.lower() or query.lower() in p.lower()]
    if not hits:
        return f"[mock repo] No matches for '{query}'"
    return f"[mock repo] Matches for '{query}': " + ", ".join(hits)
