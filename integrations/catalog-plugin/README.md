# LLM Fallbacks catalog plugin candidate

A local, read-only MCP server searches a bundled snapshot of `configs/free_models.json` from [llm_fallbacks](https://github.com/ai-llm-experiments/llm_fallbacks). It makes no network requests, accesses no credentials, changes no routes and runs no inference. Each result includes source commit, date and catalog SHA-256. Snapshot information can be stale or wrong: a free label or heuristic score is not proof of current price, eligibility, model quality, privacy or availability. Verify against the actual provider and account before using a model. The original ordering is preserved, including any pinned entries.

Requires Node.js 18 or newer. Update the catalog, provenance constants and version together when preparing a release. This is a review candidate; it has not been installed in either client or validated by their marketplace/extension validators.

## Codex

The portable `plugin.json` and `mcp.json` describe a desktop-only plugin with a local stdio MCP server. Add this directory to a local plugin marketplace and install it using the [OpenAI packaging guide](https://developers.openai.com/plugins/build/plugins). The plugin has no hooks and requests no secret. A marketplace entry needs a source path valid relative to its marketplace root; do not copy a private absolute path into a public marketplace.

## Claude Desktop

Create a bundle using the [MCPB tool](https://github.com/modelcontextprotocol/mcpb) from this directory (`mcpb pack`) and install the resulting `.mcpb` through the [custom desktop extension flow](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). The bundle includes `manifest.json`, `server/index.js` and `data/free_models.json`; it has no npm dependencies. Claude Desktop extension support and policies depend on platform and organization configuration. Validate the manifest and bundle with the official tool before distributing it.

## Tool

`search_catalog` accepts optional `query` (model/provider substring), `mode` (exact value), `requires_tools` (boolean), and `limit` (1–100, default 20). Results preserve snapshot order; `total_matches` is the count before the limit. No tool changes the catalog. This adapter is informational only; it does not provide automatic failover or OmniRoute synchronization.
