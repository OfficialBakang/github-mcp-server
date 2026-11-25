# GitHub MCP Server 🐙

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects AI clients like **Claude Desktop** directly to the GitHub REST API — letting the AI search repositories, read and create issues, inspect pull requests, browse commits, and read file contents without leaving the chat.

---

## What is MCP?

The Model Context Protocol is an open standard that lets AI applications talk to external tools and data sources through a common interface. This server implements the protocol over **stdio transport**, meaning it runs as a local process that Claude Desktop (or any other MCP client) spawns and communicates with via stdin/stdout.

---

## Tools Exposed

| Tool | Description |
|---|---|
| `get_authenticated_user` | Returns the profile of the logged-in GitHub user |
| `search_repositories` | Search GitHub repos by keyword, sortable by stars/forks/updated |
| `get_repository` | Fetch metadata (stars, forks, topics, license) for any repo |
| `list_issues` | List open/closed issues with optional label filtering |
| `get_issue` | Fetch full details and body for a single issue |
| `create_issue` | Create a new issue with title, body, and labels |
| `update_issue` | Edit title/body, open/close, or relabel an issue |
| `list_pull_requests` | List PRs by state (open/closed/all) |
| `get_pull_request` | Full PR details including diff stats and mergeable status |
| `list_pr_files` | Every file changed in a PR with additions/deletions |
| `get_file_contents` | Read any file from a repo at any branch/commit |
| `list_repository_commits` | Recent commits on any branch with messages and authors |

---

## Prerequisites

- Python 3.11 or higher
- A GitHub [Personal Access Token](https://github.com/settings/tokens)
  - For public repos: no scopes needed
  - For private repos / creating issues: enable the `repo` scope

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/OfficialBakang/github-mcp-server.git
cd github-mcp-server

# 2. Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Export your GitHub token before running the server:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or add it to your shell profile (`~/.zshrc`, `~/.bashrc`) so it persists.

---

## Running the Server

```bash
python server.py
```

The server will start and wait for MCP messages on stdin. You won't see output here — connect it through Claude Desktop instead.

---

## Connecting to Claude Desktop

1. Open Claude Desktop → **Settings → Developer → Edit Config**
2. Add this block to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "python3",
      "args": ["/absolute/path/to/github-mcp-server/server.py"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

3. Save and **restart Claude Desktop**.
4. You should now see the GitHub tools available in the tools panel (🔧 icon).

---

## Example Prompts (once connected)

```
"Search for the top 5 Python MCP server projects on GitHub"

"List all open bugs in the facebook/react repository"

"Show me the last 10 commits on the main branch of vercel/next.js"

"Read the contents of the README.md file from torvalds/linux"

"Create an issue in my repo called 'Fix login button on mobile' with the label 'bug'"

"Get the details of PR #42 in microsoft/vscode and summarise the changes"
```

---

## Project Structure

```
github-mcp-server/
├── src/
│   └── github_mcp/
│       ├── __init__.py
│       └── server.py        ← All tools live here
├── tests/
│   └── test_server.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Running Tests

```bash
pip install pytest pytest-mock
python -m pytest test_server.py -v
```

---

## How It Works

```
Claude Desktop  ──stdio──►  github-mcp-server  ──HTTPS──►  api.github.com
     (MCP client)               (this project)               (GitHub REST API)
```

1. Claude Desktop spawns this script as a subprocess.
2. They communicate via JSON-RPC messages over stdin/stdout (the MCP protocol).
3. When Claude wants to call a tool (e.g. `search_repositories`), it sends a tool-call message.
4. This server receives it, calls the GitHub REST API with your token, and returns the result.
5. Claude uses the result to compose its response.

---

## Security Notes

- Your GitHub token is **never sent to Anthropic** — it only leaves your machine to reach `api.github.com` directly.
- Use a token with the minimum scopes your use case requires.
- Treat your token like a password; don't commit it to source control.

---

## Contributing

Pull requests are welcome! Ideas for new tools:

- [ ] Create and merge pull requests
- [ ] Add PR review comments
- [ ] Manage repository labels and milestones
- [ ] List GitHub Actions workflow runs
- [ ] Star / unstar repositories

---

## License

MIT — see [LICENSE](LICENSE) for details.
